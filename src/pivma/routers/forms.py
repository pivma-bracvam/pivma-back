from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from pivma.core.attachment_service import (
    AttachmentError,
    attachment_abspath,
    attachment_relpath,
    remove_file_best_effort,
    resolve_allowed_extensions,
    resolve_max_bytes,
    store_upload,
    validate_extension,
)
from pivma.core.database.models import (
    Artifact,
    AuditEvent,
    FormField,
    FormValue,
)
from pivma.core.pre_evaluation_service import run_pre_evaluation
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
    get_current_form_instance,
    is_artifact_referenced_by_submitted_form,
    save_form_values_draft,
    submit_proposal_form,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.schemas import (
    ActivityCompletionResponse,
    AttachmentMetadata,
    AttachmentRemovedResponse,
    AttachmentUploadResponse,
    FieldReviewSummary,
    FormFieldDefinition,
    FormInstanceResponse,
    SaveFormValuesRequest,
    SubmitFormRequest,
)

router = APIRouter(prefix='/processes', tags=['Forms'])

_ATTACHMENT_ERROR_STATUS = {
    'empty_file': HTTPStatus.BAD_REQUEST,
    'file_too_large': HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    'extension_not_allowed': HTTPStatus.UNPROCESSABLE_ENTITY,
}


def _extract_form_field_value(fv: Any, field_type: str) -> Any:  # noqa: PLR0911
    if field_type in {'text', 'textarea'}:
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
    if field_type == 'file_upload':
        return None
    return fv.json_value


def _attachment_metadata(artifact: Artifact) -> AttachmentMetadata:
    meta = artifact.metadata_payload or {}
    return AttachmentMetadata(
        artifact_id=artifact.id,
        filename=meta.get('original_filename') or artifact.name,
        size=artifact.file_size or 0,
        mime_type=artifact.mime_type,
        extension=meta.get('extension') or '',
        checksum_sha256=artifact.checksum_sha256 or '',
        uploaded_at=artifact.created_at,
    )


async def _attachments_by_field_key(
    session: Any, form_inst: Any, fields: list[FormField]
) -> dict[str, AttachmentMetadata]:
    file_field_keys = {
        f.id: f.field_key for f in fields if f.field_type == 'file_upload'
    }
    if not file_field_keys:
        return {}
    by_artifact = {
        fv.file_attachment_id: file_field_keys[fv.form_field_id]
        for fv in form_inst.values
        if fv.deleted_at is None
        and fv.form_field_id in file_field_keys
        and fv.file_attachment_id is not None
    }
    if not by_artifact:
        return {}
    rows = (
        (
            await session.execute(
                select(Artifact).where(
                    Artifact.id.in_(by_artifact.keys()),
                    Artifact.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return {by_artifact[a.id]: _attachment_metadata(a) for a in rows}


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
            if fld.field_type == 'file_upload':
                continue
            values_dict[fld.field_key] = _extract_form_field_value(
                fv, fld.field_type
            )

    attachments = await _attachments_by_field_key(session, form_inst, fields)

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
                section=(
                    f.validation_rules.get('section')
                    if f.validation_rules
                    else 'Geral'
                ),
                options=f.options,
                validation_rules=f.validation_rules,
                ai_evaluation_enabled=f.ai_evaluation_enabled,
                ai_context_instructions=f.ai_context_instructions,
                ai_validation_rules=f.ai_validation_rules,
                attachment=attachments.get(f.field_key),
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
async def submit_form(  # noqa: PLR0913, PLR0917
    id: UUID,
    activity_key: str,
    body: SubmitFormRequest,
    session: Session,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    try:
        act, run, artifact, pre_eval_run = await submit_proposal_form(
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
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={'code': 'invalid_form_values', 'errors': e.errors}
            if e.errors
            else str(e),
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e

    pre_evaluation = None
    if pre_eval_run is not None:
        background_tasks.add_task(run_pre_evaluation, pre_eval_run.id)
        pre_evaluation = {
            'run_id': str(pre_eval_run.id),
            'status': pre_eval_run.status,
        }

    return ActivityCompletionResponse(
        activity_key=act.key,
        run_number=run.run_number,
        status=run.status,
        artifact_id=artifact.id if artifact else None,
        pre_evaluation=pre_evaluation,
    )


# ---------------------------------------------------------------------------
# Anexos de campo (Spec 016)
# ---------------------------------------------------------------------------


async def _load_file_field(
    session: Any,
    process_id: UUID,
    activity_key: str,
    field_key: str,
    user_id: UUID,
) -> tuple[Any, Any, FormField]:
    try:
        _, run, form_inst, _, fields = await get_current_form_instance(
            session, process_id, activity_key, user_id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e

    field = next((f for f in fields if f.field_key == field_key), None)
    if field is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Campo não encontrado.'
        )
    if field.field_type != 'file_upload':
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                'code': 'not_a_file_field',
                'message': 'O campo indicado não aceita anexos.',
            },
        )
    return run, form_inst, field


async def _active_form_value(
    session: Any, form_instance_id: UUID, form_field_id: UUID
) -> FormValue | None:
    return await session.scalar(
        select(FormValue).where(
            FormValue.form_instance_id == form_instance_id,
            FormValue.form_field_id == form_field_id,
            FormValue.deleted_at.is_(None),
        )
    )


@router.post(
    '/{id}/activities/{activity_key}/form/fields/{field_key}/attachment',
    response_model=AttachmentUploadResponse,
    status_code=HTTPStatus.OK,
)
async def upload_field_attachment(  # noqa: PLR0913, PLR0914, PLR0917
    id: UUID,
    activity_key: str,
    field_key: str,
    file: UploadFile,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _: TrustedOrigin,
):
    run, form_inst, field = await _load_file_field(
        session, id, activity_key, field_key, current_user.id
    )
    if form_inst.is_submitted:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                'code': 'form_submitted',
                'message': 'O formulário submetido é imutável.',
            },
        )

    allowed = resolve_allowed_extensions(field, settings)
    max_bytes = resolve_max_bytes(field, settings)
    try:
        extension = validate_extension(file.filename, allowed)
    except AttachmentError as e:
        raise _attachment_http_error(e) from e

    artifact = Artifact(
        process_instance_id=id,
        activity_run_id=run.id,
        key='form_attachment',
        name=(file.filename or 'anexo')[:255],
        status='DRAFT',
        metadata_payload={
            'field_key': field_key,
            'original_filename': file.filename,
            'extension': extension,
        },
    )
    artifact.set_creation_audit(current_user.id)
    session.add(artifact)
    await session.flush()

    relpath = attachment_relpath(id, artifact.id, extension)
    dest = attachment_abspath(settings, relpath)
    try:
        size, checksum = await store_upload(file, dest, max_bytes)
    except AttachmentError as e:
        await session.rollback()
        raise _attachment_http_error(e) from e

    artifact.file_path = relpath
    artifact.file_size = size
    artifact.mime_type = file.content_type
    artifact.checksum_sha256 = checksum

    form_value = await _active_form_value(session, form_inst.id, field.id)
    replaced_previous = False
    previous_abspath = None
    if form_value is None:
        form_value = FormValue(
            form_instance_id=form_inst.id, form_field_id=field.id
        )
        form_value.set_creation_audit(current_user.id)
        session.add(form_value)
    else:
        form_value.set_update_audit(current_user.id)
        if form_value.file_attachment_id is not None:
            previous = await session.get(
                Artifact, form_value.file_attachment_id
            )
            preserve_previous = await is_artifact_referenced_by_submitted_form(
                session, form_value.file_attachment_id
            )
            if (
                previous is not None
                and previous.deleted_at is None
                and not preserve_previous
            ):
                previous.set_deletion_audit(current_user.id)
                replaced_previous = True
                if previous.file_path:
                    previous_abspath = attachment_abspath(
                        settings, previous.file_path
                    )
            elif previous is not None and previous.deleted_at is None:
                replaced_previous = True
    form_value.file_attachment_id = artifact.id

    session.add(
        AuditEvent(
            process_instance_id=id,
            activity_run_id=run.id,
            user_id=current_user.id,
            event_type='FORM_ATTACHMENT_UPLOADED',
            context_data={
                'activity_key': activity_key,
                'field_key': field_key,
                'artifact_id': str(artifact.id),
                'replaced_previous': replaced_previous,
            },
        )
    )
    await session.commit()
    await session.refresh(artifact)

    if previous_abspath is not None:
        remove_file_best_effort(previous_abspath)

    return AttachmentUploadResponse(
        field_key=field_key,
        attachment=_attachment_metadata(artifact),
        replaced_previous=replaced_previous,
    )


@router.delete(
    '/{id}/activities/{activity_key}/form/fields/{field_key}/attachment',
    response_model=AttachmentRemovedResponse,
    status_code=HTTPStatus.OK,
)
async def delete_field_attachment(  # noqa: PLR0913, PLR0917
    id: UUID,
    activity_key: str,
    field_key: str,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _: TrustedOrigin,
):
    _run, form_inst, field = await _load_file_field(
        session, id, activity_key, field_key, current_user.id
    )
    if form_inst.is_submitted:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                'code': 'form_submitted',
                'message': 'O formulário submetido é imutável.',
            },
        )

    form_value = await _active_form_value(session, form_inst.id, field.id)
    if form_value is None or form_value.file_attachment_id is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Campo sem anexo.',
        )

    artifact = await session.get(Artifact, form_value.file_attachment_id)
    removed_abspath = None
    preserve_artifact = await is_artifact_referenced_by_submitted_form(
        session, form_value.file_attachment_id
    )
    if (
        artifact is not None
        and artifact.deleted_at is None
        and not preserve_artifact
    ):
        artifact.set_deletion_audit(current_user.id)
        if artifact.file_path:
            removed_abspath = attachment_abspath(settings, artifact.file_path)
    form_value.file_attachment_id = None
    form_value.set_update_audit(current_user.id)

    session.add(
        AuditEvent(
            process_instance_id=id,
            activity_run_id=_run.id,
            user_id=current_user.id,
            event_type='FORM_ATTACHMENT_REMOVED',
            context_data={
                'activity_key': activity_key,
                'field_key': field_key,
            },
        )
    )
    await session.commit()

    if removed_abspath is not None:
        remove_file_best_effort(removed_abspath)

    return AttachmentRemovedResponse(field_key=field_key, removed=True)


@router.get(
    '/{id}/activities/{activity_key}/form/fields/{field_key}/attachment',
    status_code=HTTPStatus.OK,
)
async def download_field_attachment(  # noqa: PLR0913, PLR0917
    id: UUID,
    activity_key: str,
    field_key: str,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    _run, form_inst, field = await _load_file_field(
        session, id, activity_key, field_key, current_user.id
    )
    form_value = await _active_form_value(session, form_inst.id, field.id)
    if form_value is None or form_value.file_attachment_id is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Campo sem anexo.'
        )
    artifact = await session.get(Artifact, form_value.file_attachment_id)
    if artifact is None or artifact.deleted_at is not None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Anexo não encontrado.'
        )

    abspath = attachment_abspath(settings, artifact.file_path or '')
    if not abspath.is_file():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Anexo não encontrado.'
        )

    meta = artifact.metadata_payload or {}
    return FileResponse(
        path=abspath,
        media_type=artifact.mime_type or 'application/octet-stream',
        filename=meta.get('original_filename') or artifact.name,
        headers={'ETag': f'"{artifact.checksum_sha256 or ""}"'},
    )


def _attachment_http_error(error: AttachmentError) -> HTTPException:
    status = _ATTACHMENT_ERROR_STATUS.get(
        error.code, HTTPStatus.UNPROCESSABLE_ENTITY
    )
    return HTTPException(
        status_code=status,
        detail={'code': error.code, 'message': error.message},
    )
