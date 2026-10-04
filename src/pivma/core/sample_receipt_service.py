"""Recebimento de amostras e inconformidades (Spec 040).

O laboratório participante registra cada frasco do próprio laboratório na
atividade por laboratório ``sample_receipt``. O lote do laboratório conclui
quando todo frasco ativo dele está em ordem ou aceito com ressalva. Um
frasco fora de ordem abre uma inconformidade, que só o Grupo de Seleção de
Amostras decide, na atividade ``sample_receipt_resolution``: aceitar com
ressalva, reenviar (código novo, débito da reserva) ou desclassificar (dispensa
do laboratório na fase, Spec 036).

O laboratório nunca recebe nome químico, CAS, SDS, gabarito, justificativa
nem o vínculo entre código novo e anterior. Recebe só a situação do frasco e
a orientação que o Grupo escreve para ele na decisão (FR-047 a FR-049).
Eventos guardam só identificadores e contagens (research R12).
"""

from datetime import UTC
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.attachment_service import (
    attachment_abspath,
    attachment_relpath,
    store_upload,
    validate_extension,
)
from pivma.core.authorization import (
    PARTICIPATING_LABORATORY_ROLE_KEY,
    effective_assignment_clause,
    effective_laboratory_ids,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    BlindSampleCode,
    Phase,
    ProcessInstance,
    SampleReceipt,
    SampleReceiptNonconformity,
    StudySubstance,
    Task,
    User,
)
from pivma.core.process_engine import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    _complete_activity_run,  # noqa: PLC2701
    _compute_activity_due_date,  # noqa: PLC2701
    _current_laboratory_run,  # noqa: PLC2701
    _finish_laboratory_run,  # noqa: PLC2701
    _lock_process,  # noqa: PLC2701
    _template_activity_data,  # noqa: PLC2701
    ensure_process_mutable,
    require_activity_access,
    utc_now,
    waive_laboratory,
)
from pivma.core.references import laboratory_refs, user_refs
from pivma.core.sample_service import (
    SampleConflictError,
    unique_code,
    vial_spec,
)
from pivma.core.settings import Settings
from pivma.notifications import enqueue_notification
from pivma.notifications.channels import email_channel_available
from pivma.notifications.renderers import (
    DEVIATION_LABELS,
    SAMPLE_DECISION_EMAIL,
    SAMPLE_NONCONFORMITY_EMAIL,
)

RECEIPT_KEY = 'sample_receipt'
RESOLUTION_KEY = 'sample_receipt_resolution'
SAMPLE_SELECTION_GROUP = 'sample_selection_group'
PHOTO_KEY = 'sample_receipt_photo'
PHOTO_EXTENSIONS = frozenset({'png', 'jpg', 'jpeg'})
PHOTO_MIME = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}
_BYTES_PER_MB = 1024 * 1024
OPEN = 'OPEN'
RESOLVED = 'RESOLVED'
ACCEPT = 'accept_with_caveat'
RESEND = 'resend'
DISQUALIFY = 'disqualify'
STATUS_BY_DECISION = {
    ACCEPT: 'accepted_with_caveat',
    RESEND: 'replaced',
    DISQUALIFY: 'disqualified',
}
VIAL_NOT_FOUND = 'Frasco não encontrado.'

MESSAGE_COMPLETED = (
    'Recebimento registrado. O lote do laboratório está completo na cadeia '
    'de custódia e liberado para os ensaios.'
)
MESSAGE_IN_PROGRESS = (
    'Recebimento do frasco {code} registrado. Ainda há frascos do lote a '
    'registrar.'
)
MESSAGE_WAITING_OTHER = (
    'Recebimento do frasco {code} registrado. O lote aguarda a decisão sobre '
    'um frasco com problema.'
)
MESSAGE_CHECK_OK = (
    'Condições dentro do padrão no frasco {code}. Confirme para registrar o '
    'recebimento.'
)
MESSAGE_CHECK_DEVIATION = (
    'Condição fora do padrão no frasco {code}: {reasons}. Ao confirmar, uma '
    'inconformidade será registrada automaticamente e a equipe responsável '
    'pelas amostras será avisada.'
)
ALERT = (
    'Alerta de Recebimento: o laboratório {laboratory} registrou desvio '
    '{kind} no frasco {code}.'
)
MESSAGE_NONCONFORMITY = (
    'Registramos o reporte de avaria/desvio no frasco {code}. A equipe '
    'responsável pelas amostras foi notificada e está avaliando o caso. '
    'Mantenha o material segregado e aguarde as orientações, que serão '
    'emitidas aqui na plataforma.'
)


# ---------------------------------------------------------------------------
# Regras puras
# ---------------------------------------------------------------------------


def receipt_deviations(
    temperature: float,
    package_state: str,
    minimum: float | None,
    maximum: float | None,
) -> list[str]:
    """Motivos de inconformidade do frasco (FR-024); vazio = em ordem.

    Os limites da faixa contam como dentro. Sem faixa cadastrada, a
    temperatura não gera inconformidade.
    """
    deviations = []
    if (
        minimum is not None
        and maximum is not None
        and not minimum <= temperature <= maximum
    ):
        deviations.append('temperature_out_of_range')
    if package_state == 'damaged':
        deviations.append('package_damaged')
    if package_state == 'violated':
        deviations.append('package_violated')
    return deviations


def deviation_kind(deviations: list[str]) -> str:
    """Desvio térmico, físico ou os dois, para o alerta (Jornada 4)."""
    thermal = 'temperature_out_of_range' in deviations
    physical = len(deviations) > int(thermal)
    if thermal and physical:
        return 'térmico e físico'
    return 'térmico' if thermal else 'físico'


def vial_status(
    receipt: SampleReceipt | None, nonconformity: SampleReceiptNonconformity
) -> str:
    """Situação do frasco, derivada do registro e da decisão (FR-037)."""
    if receipt is None:
        return 'pending'
    if receipt.conforming:
        return 'received'
    if nonconformity is None or nonconformity.status == OPEN:
        return 'awaiting_decision'
    return STATUS_BY_DECISION[nonconformity.decision]


# ---------------------------------------------------------------------------
# Acesso
# ---------------------------------------------------------------------------


async def _activity(
    session: AsyncSession, process_id: UUID, key: str
) -> ActivityInstance:
    act = await session.scalar(
        select(ActivityInstance)
        .join(
            ProcessInstance,
            ProcessInstance.id == ActivityInstance.process_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
            ActivityInstance.deleted_at.is_(None),
            ProcessInstance.deleted_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    if act is None:
        raise NotFoundError(f'Atividade {key!r} não encontrada.')
    return act


async def _receipt_access(
    session: AsyncSession, process_id: UUID, user_id: UUID, level: str
) -> tuple[ActivityInstance, set[UUID]]:
    """Atividade do recebimento e os laboratórios efetivos do usuário."""
    act = await _activity(session, process_id, RECEIPT_KEY)
    await require_activity_access(session, user_id, act, level)
    return act, await effective_laboratory_ids(session, user_id, process_id)


async def _resolution_access(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> ActivityInstance:
    """Só quem edita a resolução (Grupo de Seleção) lê e decide (FR-031)."""
    act = await _activity(session, process_id, RESOLUTION_KEY)
    await require_activity_access(session, user_id, act, 'edit')
    return act


# ---------------------------------------------------------------------------
# Consultas e serialização
# ---------------------------------------------------------------------------


async def _vial_rows(
    session: AsyncSession,
    process_id: UUID,
    laboratory_ids: set[UUID],
    code: str | None = None,
) -> list[tuple[BlindSampleCode, SampleReceipt | None, Any]]:
    """Frascos dos laboratórios: códigos ativos e substituídos com registro."""
    if not laboratory_ids:
        return []
    stmt = (
        select(BlindSampleCode, SampleReceipt, SampleReceiptNonconformity)
        .outerjoin(
            SampleReceipt,
            (SampleReceipt.blind_sample_code_id == BlindSampleCode.id)
            & SampleReceipt.deleted_at.is_(None),
        )
        .outerjoin(
            SampleReceiptNonconformity,
            (SampleReceiptNonconformity.receipt_id == SampleReceipt.id)
            & SampleReceiptNonconformity.deleted_at.is_(None),
        )
        .where(
            BlindSampleCode.process_instance_id == process_id,
            BlindSampleCode.laboratory_id.in_(laboratory_ids),
            BlindSampleCode.deleted_at.is_(None)
            | SampleReceipt.id.is_not(None),
        )
        .execution_options(skip_soft_delete_filter=True)
    )
    if code is not None:
        # O código ativo vem antes de um substituído com o mesmo texto.
        stmt = stmt.where(BlindSampleCode.code == code).order_by(
            BlindSampleCode.deleted_at.desc().nulls_first()
        )
    return list((await session.execute(stmt)).all())


async def _photos_by_receipt(
    session: AsyncSession, process_id: UUID, receipt_ids: set[UUID]
) -> dict[str, list[dict[str, Any]]]:
    if not receipt_ids:
        return {}
    artifacts = await session.scalars(
        select(Artifact)
        .where(
            Artifact.process_instance_id == process_id,
            Artifact.key == PHOTO_KEY,
            Artifact.deleted_at.is_(None),
            Artifact.metadata_payload['receipt_id'].astext.in_([
                str(i) for i in receipt_ids
            ]),
        )
        .order_by(Artifact.created_at, Artifact.id)
    )
    photos: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        meta = artifact.metadata_payload or {}
        photos.setdefault(meta['receipt_id'], []).append({
            'id': artifact.id,
            'filename': meta.get('original_filename') or artifact.name,
            'size': artifact.file_size,
            'uploaded_at': artifact.created_at,
        })
    return photos


def _receipt_public(receipt: SampleReceipt) -> dict[str, Any]:
    return {
        'id': receipt.id,
        'opened_at': receipt.opened_at,
        'temperature_celsius': receipt.temperature_celsius,
        'package_state': receipt.package_state,
        'notes': receipt.notes,
        'conforming': receipt.conforming,
        'deviations': list(receipt.deviations),
        'registered_at': receipt.created_at,
    }


async def _serialize_vials(
    session: AsyncSession, process_id: UUID, rows: list
) -> list[dict[str, Any]]:
    laboratories = await laboratory_refs(
        session, [code.laboratory_id for code, _, _ in rows]
    )
    photos = await _photos_by_receipt(
        session,
        process_id,
        {receipt.id for _, receipt, _ in rows if receipt is not None},
    )
    substances = (
        {
            s.id: s
            for s in await session.scalars(
                select(StudySubstance)
                .where(
                    StudySubstance.id.in_({c.substance_id for c, _, _ in rows})
                )
                .execution_options(skip_soft_delete_filter=True)
            )
        }
        if rows
        else {}
    )
    vials = [
        {
            'code': code.code,
            'laboratory': laboratories[code.laboratory_id],
            'status': vial_status(receipt, nonconformity),
            # Manuseio e conservação: o que o analista precisa na bancada,
            # sem identidade química (Jornada 1).
            'lot': substances[code.substance_id].lot,
            'safe_handling_instructions': substances[
                code.substance_id
            ].safe_handling_instructions,
            **vial_spec(substances[code.substance_id]),
            'receipt': _receipt_public(receipt) if receipt else None,
            'photos': photos.get(str(receipt.id), []) if receipt else [],
            'lab_guidance': nonconformity.lab_guidance
            if nonconformity
            else None,
        }
        for code, receipt, nonconformity in rows
    ]
    return sorted(vials, key=lambda v: (v['laboratory'].name, v['code']))


async def list_vials(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Frascos dos laboratórios do usuário, por laboratório e código.

    `search` filtra por trecho do código, sem diferenciar maiúsculas; a busca
    só alcança os frascos do próprio laboratório.
    """
    _act, laboratories = await _receipt_access(
        session, process_id, user_id, 'view'
    )
    rows = await _vial_rows(session, process_id, laboratories)
    if search:
        rows = [row for row in rows if search.upper() in row[0].code]
    return await _serialize_vials(session, process_id, rows)


async def _lot_complete(
    session: AsyncSession, process_id: UUID, laboratory_id: UUID
) -> bool:
    """Todo frasco ativo em ordem ou aceito com ressalva (FR-025)."""
    pending = await session.scalar(
        select(func.count())
        .select_from(BlindSampleCode)
        .outerjoin(
            SampleReceipt,
            (SampleReceipt.blind_sample_code_id == BlindSampleCode.id)
            & SampleReceipt.deleted_at.is_(None),
        )
        .outerjoin(
            SampleReceiptNonconformity,
            SampleReceiptNonconformity.receipt_id == SampleReceipt.id,
        )
        .where(
            BlindSampleCode.process_instance_id == process_id,
            BlindSampleCode.laboratory_id == laboratory_id,
            BlindSampleCode.deleted_at.is_(None),
            # Sem registro ou sem decisão os campos vêm nulos: `coalesce`
            # mantém a condição verdadeira ou falsa, nunca nula.
            ~(
                SampleReceipt.conforming.is_(True)
                | (
                    func.coalesce(SampleReceiptNonconformity.decision, '')
                    == ACCEPT
                )
            ),
        )
    )
    return pending == 0


async def _has_open_nonconformity(
    session: AsyncSession, process_id: UUID, laboratory_id: UUID | None = None
) -> bool:
    stmt = select(SampleReceiptNonconformity.id).where(
        SampleReceiptNonconformity.process_instance_id == process_id,
        SampleReceiptNonconformity.status == OPEN,
    )
    if laboratory_id is not None:
        stmt = stmt.where(
            SampleReceiptNonconformity.laboratory_id == laboratory_id
        )
    return await session.scalar(stmt.limit(1)) is not None


async def _close_lot_if_complete(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process: ProcessInstance,
    act: ActivityInstance,
    laboratory_id: UUID,
    user_id: UUID,
) -> bool:
    """Conclui a execução do laboratório quando o lote fecha (R3)."""
    run = await _current_laboratory_run(session, act.id, laboratory_id)
    if run is None or run.status != 'IN_PROGRESS':
        return False
    if not await _lot_complete(session, process.id, laboratory_id):
        return False
    await _finish_laboratory_run(session, process, act, run, user_id)
    return True


# ---------------------------------------------------------------------------
# Registro do frasco (US3, US4, US6)
# ---------------------------------------------------------------------------


async def _pending_vial(
    session: AsyncSession,
    process_id: UUID,
    act: ActivityInstance,
    laboratories: set[UUID],
    code: str,
) -> tuple[BlindSampleCode, ActivityRun, StudySubstance]:
    """Frasco ativo do laboratório, sem registro, com o recebimento aberto."""
    rows = await _vial_rows(session, process_id, laboratories, code)
    if not rows or rows[0][0].deleted_at is not None:
        raise NotFoundError(VIAL_NOT_FOUND)
    vial, receipt, _ = rows[0]
    run = await _current_laboratory_run(session, act.id, vial.laboratory_id)
    if run is None or run.status != 'IN_PROGRESS':
        raise SampleConflictError(
            'invalid_transition',
            'O recebimento deste laboratório não está em andamento.',
        )
    if receipt is not None:
        raise _already_registered()
    substance = await session.get(StudySubstance, vial.substance_id)
    return vial, run, substance


def _reasons(deviations: list[str], substance: StudySubstance) -> str:
    labels = []
    for deviation in deviations:
        label = DEVIATION_LABELS[deviation]
        if deviation == 'temperature_out_of_range':
            label += (
                f' (esperado de {substance.storage_temperature_min:g} °C a '
                f'{substance.storage_temperature_max:g} °C)'
            )
        labels.append(label)
    return ', '.join(labels)


async def check_receipt(
    session: AsyncSession,
    process_id: UUID,
    code: str,
    user_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Pré-verificação do registro, sem gravar nada (Jornada 2, passo 3).

    Mesmo acesso e mesmas recusas do registro: a tela avisa antes de o
    analista confirmar que a condição gera uma inconformidade.
    """
    act, laboratories = await _receipt_access(
        session, process_id, user_id, 'edit'
    )
    await ensure_process_mutable(session, process_id)
    vial, _run, substance = await _pending_vial(
        session, process_id, act, laboratories, code
    )
    deviations = receipt_deviations(
        data['temperature_celsius'],
        data['package_state'],
        substance.storage_temperature_min,
        substance.storage_temperature_max,
    )
    message = (
        MESSAGE_CHECK_DEVIATION.format(
            code=vial.code, reasons=_reasons(deviations, substance)
        )
        if deviations
        else MESSAGE_CHECK_OK.format(code=vial.code)
    )
    return {
        'conforming': not deviations,
        'deviations': deviations,
        'message': message,
    }


async def register_receipt(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    code: str,
    user_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    act, laboratories = await _receipt_access(
        session, process_id, user_id, 'edit'
    )
    process = await _lock_process(session, process_id)
    await ensure_process_mutable(session, process_id)
    vial, run, substance = await _pending_vial(
        session, process_id, act, laboratories, code
    )
    deviations = receipt_deviations(
        data['temperature_celsius'],
        data['package_state'],
        substance.storage_temperature_min,
        substance.storage_temperature_max,
    )
    receipt = SampleReceipt(
        process_instance_id=process_id,
        activity_run_id=run.id,
        blind_sample_code_id=vial.id,
        laboratory_id=vial.laboratory_id,
        opened_at=data['opened_at'].astimezone(UTC).replace(tzinfo=None),
        temperature_celsius=data['temperature_celsius'],
        package_state=data['package_state'],
        conforming=not deviations,
        deviations=deviations,
        notes=data.get('notes'),
    )
    receipt.set_creation_audit(user_id)
    session.add(receipt)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _already_registered() from exc
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SAMPLE_RECEIPT_REGISTERED',
            context_data={
                'laboratory_id': str(vial.laboratory_id),
                'blind_sample_code_id': str(vial.id),
                'receipt_id': str(receipt.id),
                'conforming': not deviations,
                'deviations': deviations,
            },
        )
    )

    if deviations:
        await _open_nonconformity(
            session, settings, process, receipt, vial, user_id
        )
        status, message = 'awaiting_decision', MESSAGE_NONCONFORMITY
    elif await _close_lot_if_complete(
        session, process, act, vial.laboratory_id, user_id
    ):
        status, message = 'completed', MESSAGE_COMPLETED
    elif await _has_open_nonconformity(
        session, process_id, vial.laboratory_id
    ):
        status, message = 'awaiting_decision', MESSAGE_WAITING_OTHER
    else:
        status, message = 'in_progress', MESSAGE_IN_PROGRESS
    await session.commit()

    rows = await _vial_rows(
        session, process_id, {vial.laboratory_id}, vial.code
    )
    return {
        'vial': (await _serialize_vials(session, process_id, rows))[0],
        'conforming': not deviations,
        'deviations': deviations,
        'laboratory_receipt_status': status,
        'message': message.format(code=vial.code),
    }


def _already_registered() -> SampleConflictError:
    return SampleConflictError(
        'vial_already_registered', 'Este frasco já tem recebimento registrado.'
    )


# ---------------------------------------------------------------------------
# Inconformidade: abertura e aviso (US6)
# ---------------------------------------------------------------------------


async def _open_resolution_run(
    session: AsyncSession, process: ProcessInstance, user_id: UUID
) -> ActivityRun:
    """Execução aberta da resolução, ou uma nova com a tarefa do Grupo."""
    act = await _activity(session, process.id, RESOLUTION_KEY)
    run = await session.scalar(
        select(ActivityRun).where(
            ActivityRun.activity_instance_id == act.id,
            ActivityRun.status == 'IN_PROGRESS',
            ActivityRun.deleted_at.is_(None),
        )
    )
    if run is not None:
        return run
    last = await session.scalar(
        select(func.max(ActivityRun.run_number)).where(
            ActivityRun.activity_instance_id == act.id
        )
    )
    run = ActivityRun(
        activity_instance_id=act.id,
        run_number=(last or 0) + 1,
        status='IN_PROGRESS',
        execution_reason='Problema registrado no recebimento de amostras.',
    )
    run.set_creation_audit(user_id)
    session.add(run)
    await session.flush()
    a_data = await _template_activity_data(session, process.id, act.key)
    task = Task(
        activity_run_id=run.id,
        title=act.name,
        assigned_role=SAMPLE_SELECTION_GROUP,
        status='READY',
        due_date=_compute_activity_due_date(
            run_started_at=run.started_at, sla_hours=a_data.get('sla_hours')
        ),
    )
    task.set_creation_audit(user_id)
    session.add(task)
    act.status = 'IN_PROGRESS'
    act.blocked_reason = None
    act.set_update_audit(user_id)
    phase = await session.get(Phase, act.phase_id)
    if phase is not None and phase.status == 'NOT_STARTED':
        phase.status = 'IN_PROGRESS'
        phase.set_update_audit(user_id)
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SAMPLE_RECEIPT_RESOLUTION_OPENED',
            context_data={'run_number': run.run_number},
        )
    )
    return run


async def _selection_group_emails(
    session: AsyncSession, process_id: UUID
) -> list[str]:
    return list(
        await session.scalars(
            select(User.email)
            .join(Assignment, Assignment.user_id == User.id)
            .where(
                Assignment.process_instance_id == process_id,
                Assignment.role_key == SAMPLE_SELECTION_GROUP,
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
            .distinct()
            .order_by(User.email)
        )
    )


async def _open_nonconformity(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    settings: Settings,
    process: ProcessInstance,
    receipt: SampleReceipt,
    vial: BlindSampleCode,
    user_id: UUID,
) -> SampleReceiptNonconformity:
    """Inconformidade, tarefa do Grupo e e-mails, na mesma transação."""
    nonconformity = SampleReceiptNonconformity(
        process_instance_id=process.id,
        receipt_id=receipt.id,
        laboratory_id=receipt.laboratory_id,
        status=OPEN,
    )
    nonconformity.set_creation_audit(user_id)
    session.add(nonconformity)
    await session.flush()
    run = await _open_resolution_run(session, process, user_id)
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SAMPLE_NONCONFORMITY_OPENED',
            context_data={
                'nonconformity_id': str(nonconformity.id),
                'laboratory_id': str(receipt.laboratory_id),
                'deviations': list(receipt.deviations),
            },
        )
    )
    # O e-mail não pode travar o registro do laboratório (research R7).
    if not email_channel_available(settings):
        return nonconformity
    laboratory = (await laboratory_refs(session, [receipt.laboratory_id]))[
        receipt.laboratory_id
    ]
    payload = {
        'process_code': process.code,
        'process_title': process.title,
        'laboratory_name': laboratory.name,
        'blind_code': vial.code,
        'deviations': list(receipt.deviations),
    }
    for email in await _selection_group_emails(session, process.id):
        await enqueue_notification(
            session,
            settings,
            kind=SAMPLE_NONCONFORMITY_EMAIL,
            channel='email',
            recipient=email,
            payload=payload,
            actor_id=user_id,
            subject=('sample_receipt_nonconformity', nonconformity.id),
            process_instance_id=process.id,
        )
    return nonconformity


# ---------------------------------------------------------------------------
# Inconformidades: lista e decisão (US6, US7)
# ---------------------------------------------------------------------------


async def _serialize_nonconformities(
    session: AsyncSession,
    process_id: UUID,
    items: list[SampleReceiptNonconformity],
) -> list[dict[str, Any]]:
    receipts = {
        r.id: r
        for r in await session.scalars(
            select(SampleReceipt).where(
                SampleReceipt.id.in_([n.receipt_id for n in items])
            )
        )
    }
    code_ids = {r.blind_sample_code_id for r in receipts.values()} | {
        n.replacement_code_id for n in items if n.replacement_code_id
    }
    codes = {
        c.id: c
        for c in await session.scalars(
            select(BlindSampleCode)
            .where(BlindSampleCode.id.in_(code_ids))
            .execution_options(skip_soft_delete_filter=True)
        )
    }
    substances = {
        s.id: s
        for s in await session.scalars(
            select(StudySubstance)
            .where(
                StudySubstance.id.in_({c.substance_id for c in codes.values()})
            )
            .execution_options(skip_soft_delete_filter=True)
        )
    }
    laboratories = await laboratory_refs(
        session, [n.laboratory_id for n in items]
    )
    deciders = await user_refs(session, [n.decided_by for n in items])
    photos = await _photos_by_receipt(session, process_id, set(receipts))
    result = []
    for item in items:
        receipt = receipts[item.receipt_id]
        code = codes[receipt.blind_sample_code_id]
        substance = substances[code.substance_id]
        replacement = codes.get(item.replacement_code_id)
        result.append({
            'id': item.id,
            'status': item.status,
            'alert': ALERT.format(
                laboratory=laboratories[item.laboratory_id].name,
                kind=deviation_kind(list(receipt.deviations)),
                code=code.code,
            ),
            'laboratory': laboratories[item.laboratory_id],
            'code': code.code,
            'substance': {
                'id': substance.id,
                'chemical_name': substance.chemical_name,
                'cas_number': substance.cas_number,
                'reserve_vials_count': substance.reserve_vials_count,
            },
            'expected_temperature': {
                'regime': substance.storage_temperature_regime,
                'min': substance.storage_temperature_min,
                'max': substance.storage_temperature_max,
            },
            'receipt': _receipt_public(receipt),
            'photos': photos.get(str(receipt.id), []),
            'deviations': list(receipt.deviations),
            'opened_at': item.created_at,
            'decision': item.decision,
            'justification': item.justification,
            'lab_guidance': item.lab_guidance,
            'decided_by': deciders.get(item.decided_by),
            'decided_at': item.decided_at,
            'replacement_code': replacement.code if replacement else None,
        })
    return result


async def list_nonconformities(  # noqa: PLR0913
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    *,
    status: str | None,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    await _resolution_access(session, process_id, user_id)
    stmt = select(SampleReceiptNonconformity).where(
        SampleReceiptNonconformity.process_instance_id == process_id
    )
    if status is not None:
        stmt = stmt.where(
            SampleReceiptNonconformity.status
            == (OPEN if status == 'open' else RESOLVED)
        )
    total = await session.scalar(
        select(func.count()).select_from(stmt.subquery())
    )
    items = list(
        await session.scalars(
            stmt
            .order_by(
                SampleReceiptNonconformity.created_at,
                SampleReceiptNonconformity.id,
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    )
    return (
        await _serialize_nonconformities(session, process_id, items),
        total or 0,
    )


def _resolve(  # noqa: PLR0913, PLR0917
    item: SampleReceiptNonconformity,
    decision: str,
    justification: str,
    lab_guidance: str | None,
    user_id: UUID,
) -> None:
    item.status = RESOLVED
    item.decision = decision
    item.justification = justification
    item.lab_guidance = lab_guidance
    item.decided_by = user_id
    item.decided_at = utc_now()
    item.set_update_audit(user_id)


async def _resend(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    run: ActivityRun,
    item: SampleReceiptNonconformity,
    receipt: SampleReceipt,
    user_id: UUID,
) -> None:
    """Debita a reserva e troca o código do frasco (FR-034, research R5)."""
    old = await session.get(BlindSampleCode, receipt.blind_sample_code_id)
    substance = await session.scalar(
        select(StudySubstance)
        .where(StudySubstance.id == old.substance_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if substance.reserve_vials_count <= 0:
        raise SampleConflictError(
            'no_reserve_vials',
            'A substância não tem frasco de reserva para reenviar.',
        )
    substance.reserve_vials_count -= 1
    substance.set_update_audit(user_id)
    old.set_deletion_audit(user_id)
    await session.flush()
    taken = set(
        await session.scalars(
            select(BlindSampleCode.code).where(
                BlindSampleCode.process_instance_id == process_id,
                BlindSampleCode.deleted_at.is_(None),
            )
        )
    )
    new = BlindSampleCode(
        process_instance_id=process_id,
        substance_id=old.substance_id,
        laboratory_id=old.laboratory_id,
        code=unique_code(taken),
        replaces_code_id=old.id,
    )
    new.set_creation_audit(user_id)
    session.add(new)
    await session.flush()
    item.replacement_code_id = new.id
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SAMPLE_VIAL_RESENT',
            context_data={
                'nonconformity_id': str(item.id),
                'laboratory_id': str(old.laboratory_id),
                'replacement_code_id': str(new.id),
                'reserve_vials_count': substance.reserve_vials_count,
            },
        )
    )


async def _disqualify(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    item: SampleReceiptNonconformity,
    justification: str,
    user_id: UUID,
) -> list[SampleReceiptNonconformity]:
    """Dispensa o laboratório na fase e devolve as outras abertas dele."""
    receipt_act = await _activity(session, process_id, RECEIPT_KEY)
    phase = await session.get(Phase, receipt_act.phase_id)
    try:
        await waive_laboratory(
            session,
            process_id,
            phase.key,
            item.laboratory_id,
            justification,
            user_id,
        )
    except ConflictError as exc:
        if exc.code != 'already_waived':
            raise
    return list(
        await session.scalars(
            select(SampleReceiptNonconformity)
            .where(
                SampleReceiptNonconformity.process_instance_id == process_id,
                SampleReceiptNonconformity.laboratory_id == item.laboratory_id,
                SampleReceiptNonconformity.status == OPEN,
                SampleReceiptNonconformity.id != item.id,
            )
            .with_for_update()
        )
    )


async def _laboratory_emails(
    session: AsyncSession, process_id: UUID, laboratory_id: UUID
) -> list[str]:
    """Quem tem designação efetiva pelo laboratório no processo."""
    return list(
        await session.scalars(
            select(User.email)
            .join(Assignment, Assignment.user_id == User.id)
            .where(
                Assignment.process_instance_id == process_id,
                Assignment.role_key == PARTICIPATING_LABORATORY_ROLE_KEY,
                Assignment.laboratory_id == laboratory_id,
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
                User.deleted_at.is_(None),
                effective_assignment_clause(),
            )
            .distinct()
            .order_by(User.email)
        )
    )


async def _notify_laboratory(
    session: AsyncSession,
    settings: Settings,
    process: ProcessInstance,
    items: list[SampleReceiptNonconformity],
    user_id: UUID,
) -> None:
    """E-mail da decisão ao laboratório: situação e orientação (FR-049).

    Nunca leva justificativa nem código novo. Sem e-mail configurado, a
    decisão segue (research R7).
    """
    if not email_channel_available(settings):
        return
    laboratory_id = items[0].laboratory_id
    laboratory = (await laboratory_refs(session, [laboratory_id]))[
        laboratory_id
    ]
    recipients = await _laboratory_emails(session, process.id, laboratory_id)
    for item in items:
        receipt = await session.get(SampleReceipt, item.receipt_id)
        code = await session.scalar(
            select(BlindSampleCode.code)
            .where(BlindSampleCode.id == receipt.blind_sample_code_id)
            .execution_options(skip_soft_delete_filter=True)
        )
        payload = {
            'process_code': process.code,
            'process_title': process.title,
            'laboratory_name': laboratory.name,
            'blind_code': code,
            'vial_status': STATUS_BY_DECISION[item.decision],
            'lab_guidance': item.lab_guidance,
        }
        for email in recipients:
            await enqueue_notification(
                session,
                settings,
                kind=SAMPLE_DECISION_EMAIL,
                channel='email',
                recipient=email,
                payload=payload,
                actor_id=user_id,
                subject=('sample_receipt_nonconformity', item.id),
                process_instance_id=process.id,
            )


async def decide_nonconformity(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    nonconformity_id: UUID,
    user_id: UUID,
    decision: str,
    justification: str,
    lab_guidance: str | None = None,
) -> dict[str, Any]:
    """Decisão do Grupo de Seleção sobre um frasco (FR-032 a FR-036)."""
    act = await _resolution_access(session, process_id, user_id)
    process = await _lock_process(session, process_id)
    await ensure_process_mutable(session, process_id)
    item = await session.scalar(
        select(SampleReceiptNonconformity)
        .where(
            SampleReceiptNonconformity.id == nonconformity_id,
            SampleReceiptNonconformity.process_instance_id == process_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise NotFoundError('Inconformidade não encontrada.')
    if item.status != OPEN:
        raise SampleConflictError(
            'already_decided', 'Esta inconformidade já foi decidida.'
        )
    run = await _open_resolution_run(session, process, user_id)
    receipt = await session.get(SampleReceipt, item.receipt_id)

    decided = [item]
    if decision == RESEND:
        await _resend(session, process_id, run, item, receipt, user_id)
    elif decision == DISQUALIFY:
        decided += await _disqualify(
            session, process_id, item, justification, user_id
        )
    for each in decided:
        _resolve(each, decision, justification, lab_guidance, user_id)
        session.add(
            AuditEvent(
                process_instance_id=process_id,
                activity_run_id=run.id,
                user_id=user_id,
                event_type='SAMPLE_NONCONFORMITY_RESOLVED',
                context_data={
                    'nonconformity_id': str(each.id),
                    'laboratory_id': str(each.laboratory_id),
                    'decision': decision,
                },
            )
        )
    await session.flush()
    if decision == ACCEPT:
        receipt_act = await _activity(session, process_id, RECEIPT_KEY)
        await _close_lot_if_complete(
            session, process, receipt_act, item.laboratory_id, user_id
        )
    if not await _has_open_nonconformity(session, process_id):
        await _complete_activity_run(session, run, act, user_id)
    await _notify_laboratory(session, settings, process, decided, user_id)
    await session.commit()
    return (await _serialize_nonconformities(session, process_id, [item]))[0]


# ---------------------------------------------------------------------------
# Fotos (US8)
# ---------------------------------------------------------------------------


async def add_photo(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    code: str,
    user_id: UUID,
    upload: UploadFile,
) -> dict[str, Any]:
    """Imagem no registro de um frasco do laboratório (FR-038, research R9)."""
    act, laboratories = await _receipt_access(
        session, process_id, user_id, 'edit'
    )
    await _lock_process(session, process_id)
    await ensure_process_mutable(session, process_id)
    rows = await _vial_rows(session, process_id, laboratories, code)
    if not rows or rows[0][1] is None:
        raise NotFoundError(VIAL_NOT_FOUND)
    vial, receipt, _ = rows[0]
    run = await _current_laboratory_run(session, act.id, vial.laboratory_id)
    if run is None or run.status != 'IN_PROGRESS':
        raise SampleConflictError(
            'invalid_transition',
            'O recebimento deste laboratório não está em andamento.',
        )
    extension = validate_extension(upload.filename, set(PHOTO_EXTENSIONS))
    artifact = Artifact(
        process_instance_id=process_id,
        activity_run_id=run.id,
        key=PHOTO_KEY,
        name=(upload.filename or f'foto.{extension}')[:255],
        metadata_payload={
            'original_filename': upload.filename,
            'extension': extension,
            'receipt_id': str(receipt.id),
        },
    )
    artifact.set_creation_audit(user_id)
    session.add(artifact)
    await session.flush()
    relpath = attachment_relpath(process_id, artifact.id, extension)
    try:
        size, checksum = await store_upload(
            upload,
            attachment_abspath(settings, relpath),
            settings.ATTACHMENT_MAX_SIZE_MB * _BYTES_PER_MB,
        )
    except Exception:
        await session.rollback()
        raise
    artifact.file_path = relpath
    artifact.file_size = size
    artifact.mime_type = PHOTO_MIME[extension]
    artifact.checksum_sha256 = checksum
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SAMPLE_RECEIPT_PHOTO_ATTACHED',
            context_data={
                'laboratory_id': str(vial.laboratory_id),
                'receipt_id': str(receipt.id),
                'artifact_id': str(artifact.id),
            },
        )
    )
    await session.commit()
    return {
        'id': artifact.id,
        'filename': upload.filename or artifact.name,
        'size': size,
        'uploaded_at': artifact.created_at,
    }


async def get_photo(
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    photo_id: UUID,
    user_id: UUID,
) -> tuple[Artifact, Any]:
    """Foto para o laboratório do registro ou o Grupo de Seleção (FR-039)."""
    artifact = await session.scalar(
        select(Artifact).where(
            Artifact.id == photo_id,
            Artifact.process_instance_id == process_id,
            Artifact.key == PHOTO_KEY,
        )
    )
    receipt = (
        await session.get(
            SampleReceipt, UUID(artifact.metadata_payload['receipt_id'])
        )
        if artifact is not None
        else None
    )
    if receipt is None:
        raise NotFoundError('Foto não encontrada.')
    try:
        await _resolution_access(session, process_id, user_id)
    except NotFoundError, AuthorizationError:
        _act, laboratories = await _receipt_access(
            session, process_id, user_id, 'view'
        )
        if receipt.laboratory_id not in laboratories:
            raise NotFoundError('Foto não encontrada.') from None
    path = attachment_abspath(settings, artifact.file_path)
    if not path.is_file():
        raise NotFoundError('Foto não encontrada.')
    return artifact, path
