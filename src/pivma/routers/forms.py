from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

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
            detail={"code": "invalid_form_values", "errors": e.errors},
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
