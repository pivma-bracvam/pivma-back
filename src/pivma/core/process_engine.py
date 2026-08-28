from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pivma.core.authorization import has_current_conflict
from pivma.core.database.models import (
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    Decision,
    FieldReview,
    FormField,
    FormInstance,
    FormTemplate,
    FormValue,
    Phase,
    ProcessInstance,
    ProcessTemplateVersion,
    Task,
)


class ProcessEngineError(Exception):
    pass


class ValidationError(ProcessEngineError):
    pass


class ConflictError(ProcessEngineError):
    pass


class NotFoundError(ProcessEngineError):
    pass


class AuthorizationError(ProcessEngineError):
    pass


async def _guard_against_current_conflict(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> None:
    if await has_current_conflict(session, user_id, process_id):
        raise AuthorizationError(
            'Usuário com conflito de interesse vigente neste processo.'
        )


@dataclass
class TriageContext:
    process: ProcessInstance
    triage_act: ActivityInstance
    triage_run: ActivityRun
    justification: str
    user_id: UUID


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def generate_process_code(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    stmt = select(func.count(ProcessInstance.id))
    res = await session.execute(stmt)
    count = (res.scalar() or 0) + 1
    return f'VAL-{year}-{count:04d}'


async def _create_phases_and_activities(
    session: AsyncSession,
    process_id: UUID,
    payload: dict[str, Any],
    creator_id: UUID,
) -> tuple[dict[str, ActivityInstance], dict[str, dict[str, Any]]]:
    activity_map: dict[str, ActivityInstance] = {}
    activity_meta: dict[str, dict[str, Any]] = {}

    for p_data in payload.get('phases', []):
        is_first = p_data.get('order_index') == 1
        phase = Phase(
            process_instance_id=process_id,
            key=p_data['key'],
            name=p_data['name'],
            order_index=p_data.get('order_index', 1),
            status='IN_PROGRESS' if is_first else 'NOT_STARTED',
        )
        phase.set_creation_audit(creator_id)
        session.add(phase)
        await session.flush()

        for a_data in p_data.get('activities', []):
            act_key = a_data['key']
            act = ActivityInstance(
                process_instance_id=process_id,
                phase_id=phase.id,
                key=act_key,
                name=a_data['name'],
                order_index=a_data.get('order_index', 1),
                status='BLOCKED',
                blocked_reason=None,
            )
            act.set_creation_audit(creator_id)
            session.add(act)
            await session.flush()
            activity_map[act_key] = act
            activity_meta[act_key] = a_data

    return activity_map, activity_meta


async def _init_first_activity(
    session: AsyncSession,
    act: ActivityInstance,
    a_data: dict[str, Any],
    creator_id: UUID,
) -> None:
    act.status = 'IN_PROGRESS'
    act.blocked_reason = None

    run = ActivityRun(
        activity_instance_id=act.id,
        run_number=1,
        status='IN_PROGRESS',
        execution_reason='Submissão inicial',
    )
    run.set_creation_audit(creator_id)
    session.add(run)
    await session.flush()

    task = Task(
        activity_run_id=run.id,
        title=f'Preencher {act.name}',
        assigned_role=a_data.get('assigned_role', 'PROPONENT'),
        assigned_user_id=creator_id,
        status='READY',
    )
    task.set_creation_audit(creator_id)
    session.add(task)

    f_key = a_data.get('form_template_key')
    if f_key:
        f_stmt = select(FormTemplate).where(
            FormTemplate.key == f_key, FormTemplate.deleted_at.is_(None)
        )
        f_template = (await session.execute(f_stmt)).scalar_one_or_none()
        if f_template:
            form_inst = FormInstance(
                form_template_id=f_template.id,
                activity_run_id=run.id,
                is_submitted=False,
            )
            form_inst.set_creation_audit(creator_id)
            session.add(form_inst)


async def instantiate_process(
    session: AsyncSession,
    template_version: ProcessTemplateVersion,
    title: str,
    creator_user_id: UUID,
) -> ProcessInstance:
    code = await generate_process_code(session)
    payload = template_version.definition_payload

    process = ProcessInstance(
        template_version_id=template_version.id,
        code=code,
        title=title,
        status='SUBMISSION',
        started_at=utc_now(),
    )
    process.set_creation_audit(creator_user_id)
    session.add(process)
    await session.flush()

    assignment = Assignment(
        process_instance_id=process.id,
        user_id=creator_user_id,
        role_key='proponent',
        assigned_by=creator_user_id,
    )
    assignment.set_creation_audit(creator_user_id)
    session.add(assignment)

    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=creator_user_id,
            event_type='PROCESS_CREATED',
            context_data={'code': code, 'title': title},
        )
    )
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=creator_user_id,
            event_type='PARTICIPANT_ASSIGNED',
            context_data={
                'assignment_id': str(assignment.id),
                'participant_user_id': str(creator_user_id),
                'role_key': 'proponent',
                'laboratory_id': None,
                'result': 'success',
                'source': 'process_creation',
            },
        )
    )

    act_map, act_meta = await _create_phases_and_activities(
        session, process.id, payload, creator_user_id
    )

    for act_key, a_data in act_meta.items():
        act = act_map[act_key]
        deps = a_data.get('dependencies', [])
        if not deps:
            await _init_first_activity(session, act, a_data, creator_user_id)
        else:
            act.status = 'BLOCKED'
            act.blocked_reason = 'Aguardando atividades predecessoras.'
            for dep in deps:
                req_key = dep.get('required_activity_key')
                req_act = act_map.get(req_key) if req_key else None
                dep_row = ActivityDependency(
                    dependent_activity_id=act.id,
                    required_activity_id=req_act.id if req_act else None,
                    required_status=dep.get('required_status', 'COMPLETED'),
                    condition_type=dep.get(
                        'condition_type', 'ACTIVITY_COMPLETED'
                    ),
                )
                dep_row.set_creation_audit(creator_user_id)
                session.add(dep_row)

    await session.commit()
    return process


async def get_current_form_instance(
    session: AsyncSession, process_id: UUID, activity_key: str
) -> tuple[
    ActivityInstance,
    ActivityRun,
    FormInstance,
    FormTemplate,
    list[FormField],
]:
    stmt = (
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == activity_key,
            ActivityInstance.deleted_at.is_(None),
        )
        .options(
            selectinload(ActivityInstance.runs)
            .selectinload(ActivityRun.form_instances)
            .selectinload(FormInstance.values),
            selectinload(ActivityInstance.runs)
            .selectinload(ActivityRun.form_instances)
            .selectinload(FormInstance.reviews),
        )
    )
    act = (await session.execute(stmt)).scalar_one_or_none()
    if not act:
        raise NotFoundError(f'Atividade {activity_key!r} não encontrada.')

    runs = sorted(
        [r for r in act.runs if r.deleted_at is None],
        key=lambda x: x.run_number,
        reverse=True,
    )
    if not runs:
        raise NotFoundError(f'Sem execuções na atividade {activity_key!r}.')

    current_run = runs[0]
    form_instances = [
        fi for fi in current_run.form_instances if fi.deleted_at is None
    ]
    if not form_instances:
        raise NotFoundError(f'Sem formulário na atividade {activity_key!r}.')

    form_instance = form_instances[0]

    f_stmt = (
        select(FormTemplate)
        .where(
            FormTemplate.id == form_instance.form_template_id,
            FormTemplate.deleted_at.is_(None),
        )
        .options(selectinload(FormTemplate.fields))
    )
    template = (await session.execute(f_stmt)).scalar_one_or_none()
    if not template:
        raise NotFoundError('Template do formulário não encontrado.')

    fields = sorted(
        [f for f in template.fields if f.deleted_at is None],
        key=lambda x: x.order_index,
    )
    return act, current_run, form_instance, template, fields


def _set_value_on_field(
    form_value: FormValue, field_type: str, val: Any
) -> None:
    if field_type in {'text', 'textarea'}:
        form_value.text_value = str(val) if val is not None else None
    elif field_type == 'integer':
        form_value.numeric_value = int(val) if val is not None else None
    elif field_type == 'float':
        form_value.numeric_value = float(val) if val is not None else None
    elif field_type == 'boolean':
        form_value.boolean_value = bool(val) if val is not None else None
    elif field_type == 'date':
        if isinstance(val, str):
            form_value.date_value = date.fromisoformat(val)
        elif isinstance(val, date):
            form_value.date_value = val
        else:
            form_value.date_value = None
    elif field_type == 'file_upload':
        form_value.text_value = str(val) if val is not None else None
    else:
        form_value.json_value = val


async def save_form_values_draft(
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    values_dict: dict[str, Any],
    user_id: UUID,
) -> FormInstance:
    _, current_run, form_instance, _, fields = await get_current_form_instance(
        session, process_id, activity_key
    )

    if form_instance.is_submitted:
        raise ConflictError('Formulário já submetido.')

    field_map = {f.field_key: f for f in fields}
    val_stmt = select(FormValue).where(
        FormValue.form_instance_id == form_instance.id,
        FormValue.deleted_at.is_(None),
    )
    existing_vals = {
        v.form_field_id: v for v in (await session.execute(val_stmt)).scalars()
    }

    for f_key, val in values_dict.items():
        if f_key not in field_map:
            continue
        field = field_map[f_key]
        fv = existing_vals.get(field.id)
        if fv is None:
            fv = FormValue(
                form_instance_id=form_instance.id,
                form_field_id=field.id,
            )
            fv.set_creation_audit(user_id)
            session.add(fv)
        else:
            fv.set_update_audit(user_id)

        _set_value_on_field(fv, field.field_type, val)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=current_run.id,
            user_id=user_id,
            event_type='FORM_DRAFT_SAVED',
            context_data={'activity_key': activity_key},
        )
    )
    await session.commit()
    return form_instance


def _validate_form_values(
    fields: list[FormField], values_dict: dict[str, Any]
) -> None:
    errors = []
    for field in fields:
        val = values_dict.get(field.field_key)
        if field.is_required and not val:
            errors.append(
                f"O campo '{field.label}' ({field.field_key}) é obrigatório."
            )
    if errors:
        raise ValidationError('; '.join(errors))


async def _save_submitted_values(
    session: AsyncSession,
    form_instance_id: UUID,
    fields: list[FormField],
    values_dict: dict[str, Any],
    user_id: UUID,
) -> None:
    field_map = {f.field_key: f for f in fields}
    val_stmt = select(FormValue).where(
        FormValue.form_instance_id == form_instance_id,
        FormValue.deleted_at.is_(None),
    )
    existing_vals = {
        v.form_field_id: v for v in (await session.execute(val_stmt)).scalars()
    }

    for f_key, val in values_dict.items():
        if f_key not in field_map:
            continue
        field = field_map[f_key]
        fv = existing_vals.get(field.id)
        if fv is None:
            fv = FormValue(
                form_instance_id=form_instance_id,
                form_field_id=field.id,
            )
            fv.set_creation_audit(user_id)
            session.add(fv)
        else:
            fv.set_update_audit(user_id)

        _set_value_on_field(fv, field.field_type, val)


async def _unblock_triage_activity(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> None:
    triage_stmt = select(ActivityInstance).where(
        ActivityInstance.process_instance_id == process_id,
        ActivityInstance.key == 'triage_evaluation',
        ActivityInstance.deleted_at.is_(None),
    )
    triage_act = (await session.execute(triage_stmt)).scalar_one_or_none()
    if not triage_act:
        return

    triage_act.status = 'READY'
    triage_act.blocked_reason = None
    triage_act.set_update_audit(user_id)

    tr_stmt = select(ActivityRun).where(
        ActivityRun.activity_instance_id == triage_act.id,
        ActivityRun.deleted_at.is_(None),
    )
    triage_run = (await session.execute(tr_stmt)).scalar_one_or_none()

    if not triage_run:
        triage_run = ActivityRun(
            activity_instance_id=triage_act.id,
            run_number=1,
            status='IN_PROGRESS',
            execution_reason='Triagem inicial da proposta submetida',
        )
        triage_run.set_creation_audit(user_id)
        session.add(triage_run)
        await session.flush()

        triage_task = Task(
            activity_run_id=triage_run.id,
            title='Realizar Triagem da Proposta',
            assigned_role='TRIAGE_LEAD',
            status='READY',
        )
        triage_task.set_creation_audit(user_id)
        session.add(triage_task)

        t_f_stmt = select(FormTemplate).where(
            FormTemplate.key == 'triage_review_v1',
            FormTemplate.deleted_at.is_(None),
        )
        t_f_template = (await session.execute(t_f_stmt)).scalar_one_or_none()
        if t_f_template:
            t_form_inst = FormInstance(
                form_template_id=t_f_template.id,
                activity_run_id=triage_run.id,
                is_submitted=False,
            )
            t_form_inst.set_creation_audit(user_id)
            session.add(t_form_inst)


async def submit_proposal_form(
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    values_dict: dict[str, Any],
    user_id: UUID,
) -> tuple[ActivityInstance, ActivityRun, Artifact]:
    (
        act,
        current_run,
        form_inst,
        template,
        fields,
    ) = await get_current_form_instance(session, process_id, activity_key)

    if form_inst.is_submitted:
        raise ConflictError('O formulário desta execução já foi submetido.')

    _validate_form_values(fields, values_dict)
    await _save_submitted_values(
        session, form_inst.id, fields, values_dict, user_id
    )

    form_inst.is_submitted = True
    form_inst.submitted_at = utc_now()
    form_inst.set_update_audit(user_id)

    current_run.status = 'COMPLETED'
    current_run.completed_at = utc_now()
    current_run.set_update_audit(user_id)

    act.status = 'COMPLETED'
    act.set_update_audit(user_id)

    t_stmt = select(Task).where(
        Task.activity_run_id == current_run.id, Task.deleted_at.is_(None)
    )
    for t in (await session.execute(t_stmt)).scalars().all():
        t.status = 'COMPLETED'
        t.completed_at = utc_now()
        t.set_update_audit(user_id)

    doc_name = (
        f'Dossiê de Submissão - {act.name} (Run #{current_run.run_number})'
    )
    artifact = Artifact(
        process_instance_id=process_id,
        activity_run_id=current_run.id,
        key='proposal_dossier',
        name=doc_name,
        status='SUBMITTED',
        metadata_payload={'form_key': template.key, 'values': values_dict},
    )
    artifact.set_creation_audit(user_id)
    session.add(artifact)

    await _unblock_triage_activity(session, process_id, user_id)

    p_stmt = select(ProcessInstance).where(ProcessInstance.id == process_id)
    process = (await session.execute(p_stmt)).scalar_one()
    process.status = 'TRIAGE'
    process.set_update_audit(user_id)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=current_run.id,
            user_id=user_id,
            event_type='SUBMISSION_SUBMITTED',
            context_data={'run_number': current_run.run_number},
        )
    )
    await session.commit()
    return act, current_run, artifact


async def save_field_reviews(
    session: AsyncSession,
    process_id: UUID,
    reviews_list: list[dict[str, Any]],
    user_id: UUID,
) -> None:
    await _guard_against_current_conflict(session, process_id, user_id)

    _, _, sub_form, _, sub_fields = await get_current_form_instance(
        session, process_id, 'proposal_submission'
    )
    _, triage_run, _, _, _ = await get_current_form_instance(
        session, process_id, 'triage_evaluation'
    )

    field_map = {f.field_key: f for f in sub_fields}

    rev_stmt = select(FieldReview).where(
        FieldReview.form_instance_id == sub_form.id,
        FieldReview.activity_run_id == triage_run.id,
        FieldReview.deleted_at.is_(None),
    )
    existing_revs = {
        r.form_field_id: r for r in (await session.execute(rev_stmt)).scalars()
    }

    for item in reviews_list:
        f_key = item['field_key']
        if f_key not in field_map:
            continue
        field = field_map[f_key]
        fr = existing_revs.get(field.id)
        if fr is None:
            fr = FieldReview(
                form_instance_id=sub_form.id,
                form_field_id=field.id,
                activity_run_id=triage_run.id,
                status=item['status'],
                comments=item.get('comments'),
                reviewed_by=user_id,
            )
            fr.set_creation_audit(user_id)
            session.add(fr)
        else:
            fr.status = item['status']
            fr.comments = item.get('comments')
            fr.reviewed_by = user_id
            fr.reviewed_at = utc_now()
            fr.set_update_audit(user_id)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=triage_run.id,
            user_id=user_id,
            event_type='FIELD_REVIEWED',
            context_data={'count': len(reviews_list)},
        )
    )
    await session.commit()


async def _handle_needs_revision(
    session: AsyncSession, ctx: TriageContext
) -> int:
    (
        sub_act,
        prev_sub_run,
        prev_sub_form,
        form_tmpl,
        _,
    ) = await get_current_form_instance(
        session, ctx.process.id, 'proposal_submission'
    )

    next_run_number = prev_sub_run.run_number + 1

    new_sub_run = ActivityRun(
        activity_instance_id=sub_act.id,
        run_number=next_run_number,
        status='IN_PROGRESS',
        execution_reason=f'Diligência de triagem: {ctx.justification}',
    )
    new_sub_run.set_creation_audit(ctx.user_id)
    session.add(new_sub_run)
    await session.flush()

    new_form_inst = FormInstance(
        form_template_id=form_tmpl.id,
        activity_run_id=new_sub_run.id,
        is_submitted=False,
    )
    new_form_inst.set_creation_audit(ctx.user_id)
    session.add(new_form_inst)
    await session.flush()

    prev_vals_stmt = select(FormValue).where(
        FormValue.form_instance_id == prev_sub_form.id,
        FormValue.deleted_at.is_(None),
    )
    for pv in (await session.execute(prev_vals_stmt)).scalars().all():
        nv = FormValue(
            form_instance_id=new_form_inst.id,
            form_field_id=pv.form_field_id,
            text_value=pv.text_value,
            numeric_value=pv.numeric_value,
            boolean_value=pv.boolean_value,
            date_value=pv.date_value,
            json_value=pv.json_value,
            file_attachment_id=pv.file_attachment_id,
        )
        nv.set_creation_audit(ctx.user_id)
        session.add(nv)

    prop_task = Task(
        activity_run_id=new_sub_run.id,
        title='Revisar e Ajustar Submissão da Proposta (Diligência)',
        assigned_role='PROPONENT',
        status='READY',
    )
    prop_task.set_creation_audit(ctx.user_id)
    session.add(prop_task)

    sub_act.status = 'IN_PROGRESS'
    sub_act.set_update_audit(ctx.user_id)

    ctx.triage_act.status = 'BLOCKED'
    ctx.triage_act.blocked_reason = 'Aguardando reenvio pelo proponente.'
    ctx.triage_act.set_update_audit(ctx.user_id)

    ctx.process.status = 'SUBMISSION'
    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='REVISION_REQUESTED',
            context_data={
                'new_run_number': next_run_number,
                'justification': ctx.justification,
            },
        )
    )
    return next_run_number


async def _handle_approved_decision(
    session: AsyncSession, ctx: TriageContext
) -> None:
    ctx.triage_act.status = 'COMPLETED'
    ctx.triage_act.set_update_audit(ctx.user_id)

    phase_stmt = select(Phase).where(Phase.id == ctx.triage_act.phase_id)
    phase = (await session.execute(phase_stmt)).scalar_one_or_none()
    if phase:
        phase.status = 'COMPLETED'
        phase.set_update_audit(ctx.user_id)

    ctx.process.status = 'PLANNING'
    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='TRIAGE_APPROVED',
            context_data={'justification': ctx.justification},
        )
    )


async def _handle_rejected_decision(
    session: AsyncSession, ctx: TriageContext
) -> None:
    ctx.triage_act.status = 'COMPLETED'
    ctx.triage_act.set_update_audit(ctx.user_id)

    ctx.process.status = 'CLOSED'
    ctx.process.closed_at = utc_now()
    ctx.process.closure_reason = f'Rejeitado na triagem: {ctx.justification}'
    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='TRIAGE_REJECTED',
            context_data={'justification': ctx.justification},
        )
    )


async def execute_triage_decision(
    session: AsyncSession,
    process_id: UUID,
    outcome: str,
    justification: str,
    user_id: UUID,
) -> tuple[Decision, str, int | None]:
    await _guard_against_current_conflict(session, process_id, user_id)

    p_stmt = select(ProcessInstance).where(
        ProcessInstance.id == process_id, ProcessInstance.deleted_at.is_(None)
    )
    process = (await session.execute(p_stmt)).scalar_one_or_none()
    if not process:
        raise NotFoundError('Processo não encontrado.')

    if process.status != 'TRIAGE':
        raise ConflictError(f'Processo em status {process.status!r}.')

    triage_act, triage_run, _, _, _ = await get_current_form_instance(
        session, process_id, 'triage_evaluation'
    )

    decision = Decision(
        process_instance_id=process_id,
        activity_run_id=triage_run.id,
        decision_type='TRIAGE_INITIAL_DECISION',
        outcome=outcome,
        justification=justification,
        decided_by=user_id,
    )
    decision.set_creation_audit(user_id)
    session.add(decision)

    triage_run.status = 'COMPLETED'
    triage_run.completed_at = utc_now()
    triage_run.set_update_audit(user_id)

    t_stmt = select(Task).where(
        Task.activity_run_id == triage_run.id, Task.deleted_at.is_(None)
    )
    for t in (await session.execute(t_stmt)).scalars().all():
        t.status = 'COMPLETED'
        t.completed_at = utc_now()
        t.set_update_audit(user_id)

    ctx = TriageContext(
        process=process,
        triage_act=triage_act,
        triage_run=triage_run,
        justification=justification,
        user_id=user_id,
    )

    next_run_number = None

    if outcome == 'APPROVED':
        await _handle_approved_decision(session, ctx)
    elif outcome == 'REJECTED':
        await _handle_rejected_decision(session, ctx)
    elif outcome == 'NEEDS_REVISION':
        next_run_number = await _handle_needs_revision(session, ctx)
    else:
        raise ValidationError(f'Resultado de triagem inválido: {outcome!r}.')

    await session.commit()
    return decision, process.status, next_run_number
