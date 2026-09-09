from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pivma.ai.contracts import PipelineContext
from pivma.ai.pipeline import FormAIPipelineEngine
from pivma.core.database.models import FormInstance, FormTemplate
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
    get_current_form_instance,
    save_form_values_draft,
    submit_proposal_form,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    ActivityCompletionResponse,
    FieldReviewSummary,
    FormFieldDefinition,
    FormInstanceResponse,
    SaveFormValuesRequest,
    SubmitFormRequest,
)

router = APIRouter(prefix='/processes', tags=['Forms'])


def _extract_form_field_value(fv: Any, field_type: str) -> Any:
    if field_type in {'text', 'textarea', 'file_upload'}:
        return fv.text_value
    if field_type == 'integer':
        return int(fv.numeric_value) if fv.numeric_value is not None else None
    if field_type == 'float':
        return (
            float(fv.numeric_value) if fv.numeric_value is not None else None
        )
    if field_type == 'boolean':
        return fv.boolean_value
    if field_type == 'date':
        return fv.date_value.isoformat() if fv.date_value else None
    return fv.json_value


@router.get(
    '/{id}/activities/{activity_key}/form',
    response_model=FormInstanceResponse,
    status_code=HTTPStatus.OK,
)
async def get_activity_form(
    id: UUID,
    activity_key: str,
    session: Session,
    current_user: CurrentUser,
):
    try:
        _, _, form_inst, template, fields = await get_current_form_instance(
            session, id, activity_key, current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e

    field_map = {f.id: f for f in fields}
    values_dict: dict[str, Any] = {}
    for fv in form_inst.values:
        if fv.deleted_at is None and fv.form_field_id in field_map:
            fld = field_map[fv.form_field_id]
            values_dict[fld.field_key] = _extract_form_field_value(
                fv, fld.field_type
            )

    reviews_dict: dict[str, FieldReviewSummary] = {}
    for fr in form_inst.reviews:
        if fr.deleted_at is None and fr.form_field_id in field_map:
            fld = field_map[fr.form_field_id]
            reviews_dict[fld.field_key] = FieldReviewSummary(
                status=fr.status,
                comments=fr.comments,
                reviewed_at=fr.reviewed_at,
            )

    return FormInstanceResponse(
        form_instance_id=form_inst.id,
        template_key=template.key,
        is_submitted=form_inst.is_submitted,
        fields=[
            FormFieldDefinition(
                field_key=f.field_key,
                label=f.label,
                help_text=f.help_text,
                field_type=f.field_type,
                is_required=f.is_required,
                order_index=f.order_index,
                options=f.options,
                validation_rules=f.validation_rules,
                ai_evaluation_enabled=f.ai_evaluation_enabled,
                ai_context_instructions=f.ai_context_instructions,
                ai_validation_rules=f.ai_validation_rules,
            )
            for f in fields
        ],
        values=values_dict,
        reviews=reviews_dict,
    )


@router.put(
    '/{id}/activities/{activity_key}/form',
    status_code=HTTPStatus.OK,
)
async def save_form_draft(
    id: UUID,
    activity_key: str,
    body: SaveFormValuesRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        form_inst = await save_form_values_draft(
            session=session,
            process_id=id,
            activity_key=activity_key,
            values_dict=body.values,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={'code': 'invalid_form_values', 'errors': e.errors},
        ) from e

    return {
        'message': 'Rascunho salvo com sucesso.',
        'form_instance_id': form_inst.id,
    }


@router.post(
    '/{id}/activities/{activity_key}/form',
    response_model=ActivityCompletionResponse,
    status_code=HTTPStatus.OK,
)
async def submit_form(
    id: UUID,
    activity_key: str,
    body: SubmitFormRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        act, run, artifact = await submit_proposal_form(
            session=session,
            process_id=id,
            activity_key=activity_key,
            values_dict=body.values,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e

    return ActivityCompletionResponse(
        activity_key=act.key,
        run_number=run.run_number,
        status=run.status,
        artifact_id=artifact.id if artifact else None,
    )


direct_forms_router = APIRouter(prefix='/forms', tags=['Forms AI'])


@direct_forms_router.post(
    '/instances/{instance_id}/evaluate-ai',
    status_code=HTTPStatus.OK,
)
async def evaluate_form_instance_ai(
    instance_id: UUID,
    session: Session,
    current_user: CurrentUser,
):
    stmt = (
        select(FormInstance)
        .where(
            FormInstance.id == instance_id, FormInstance.deleted_at.is_(None)
        )
        .options(
            selectinload(FormInstance.form_template).selectinload(
                FormTemplate.fields
            ),
            selectinload(FormInstance.values),
        )
    )
    result = await session.execute(stmt)
    form_inst = result.scalar_one_or_none()
    if not form_inst:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Instância de formulário não encontrada.',
        )

    engine = FormAIPipelineEngine()
    correlation_id = uuid4()
    evaluations = []

    # Mapeamento de valores submetidos indexados por form_field_id
    field_map = {
        f.id: f for f in form_inst.form_template.fields if f.deleted_at is None
    }
    values_map = {}
    for fv in form_inst.values:
        if fv.deleted_at is None and fv.form_field_id in field_map:
            fld = field_map[fv.form_field_id]
            values_map[fld.id] = _extract_form_field_value(fv, fld.field_type)

    # Filtrar apenas campos elegíveis para IA
    ai_fields = [
        f
        for f in form_inst.form_template.fields
        if f.deleted_at is None and f.ai_evaluation_enabled
    ]

    for fld in ai_fields:
        raw_val = values_map.get(fld.id)
        ctx = PipelineContext(
            form_instance_id=form_inst.id,
            field_key=fld.field_key,
            field_label=fld.label,
            submitted_value=raw_val,
            instructions=fld.ai_context_instructions,
            validation_rules=fld.ai_validation_rules,
            correlation_id=correlation_id,
        )
        group = engine.run_field_pipeline(ctx)
        if group.verdict:
            evaluations.append(group.verdict.model_dump(mode='json'))

    return {
        'form_instance_id': str(form_inst.id),
        'correlation_id': str(correlation_id),
        'status': 'COMPLETED',
        'evaluations': evaluations,
    }
