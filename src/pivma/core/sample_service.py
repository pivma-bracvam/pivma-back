"""Definição e Preparação das Amostras — estudo cego (Spec 031).

O Grupo de Seleção de Amostras cadastra as substâncias do processo; cada
substância recebe um código cego opaco por laboratório participante. Todo o
conteúdo (substâncias, códigos, SDS, etiquetas, visão do frasco) exige a
concessão de **edição** da atividade ``sample_definition``, também nas
leituras: admin e BraCVAM veem a atividade (Spec 030), mas não o conteúdo
(research R3). Eventos de auditoria guardam só identificadores e contagens,
nunca nome químico, CAS, lote ou código (research R9).
"""

import re
import secrets
from pathlib import Path
from typing import Any
from uuid import UUID

import segno
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.attachment_service import (
    attachment_abspath,
    attachment_relpath,
    remove_file_best_effort,
    store_upload,
    validate_extension,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    BlindSampleCode,
    Laboratory,
    ProcessInstance,
    StudySubstance,
)
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _advance_dependent_activities,  # noqa: PLC2701
    _complete_activity_run,  # noqa: PLC2701
    ensure_process_mutable,
    require_activity_access,
)
from pivma.core.settings import Settings

SAMPLE_ACTIVITY_KEY = 'sample_definition'
SDS_ARTIFACT_KEY = 'sample_sds'
SDS_EXTENSIONS = frozenset({'pdf'})
_BYTES_PER_MB = 1024 * 1024
PARTICIPATING_LABORATORY = 'participating_laboratory'
# Sem 0/O e 1/I/L, para leitura sem ambiguidade na etiqueta (research R5).
CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
CODE_LENGTH = 8
CODE_ATTEMPTS = 10
CAS_PATTERN = re.compile(r'^(\d{2,7})-(\d{2})-(\d)$')
REQUIRED_FIELDS = frozenset({
    'chemical_name',
    'cas_number',
    'lot',
    'safe_handling_instructions',
})


class SampleConflictError(ConflictError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SampleValidationError(ValidationError):
    def __init__(self, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


async def _sample_activity(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    *,
    lock: bool = False,
) -> ActivityInstance:
    """Atividade de amostras do processo, exigindo a concessão de edição."""
    stmt = (
        select(ActivityInstance)
        .join(
            ProcessInstance,
            ProcessInstance.id == ActivityInstance.process_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == SAMPLE_ACTIVITY_KEY,
            ActivityInstance.deleted_at.is_(None),
            ProcessInstance.deleted_at.is_(None),
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=ActivityInstance).execution_options(
            populate_existing=True
        )
    act = await session.scalar(stmt)
    if act is None:
        raise NotFoundError('Atividade de amostras não encontrada.')
    await require_activity_access(session, user_id, act, 'edit')
    return act


# ---------------------------------------------------------------------------
# Regras puras
# ---------------------------------------------------------------------------


def validate_cas(value: str) -> str:
    """Normaliza e valida o CAS: formato e dígito verificador (FR-006).

    Com os dígitos antes do último lidos da direita para a esquerda com pesos
    1, 2, 3, …, a soma ponderada módulo 10 é o último dígito.
    """
    cas = (value or '').strip()
    match = CAS_PATTERN.match(cas)
    if match is None:
        raise SampleValidationError('invalid_cas', f'CAS inválido: {cas!r}.')
    digits = match.group(1) + match.group(2)
    checksum = sum(
        weight * int(digit)
        for weight, digit in enumerate(reversed(digits), start=1)
    )
    if checksum % 10 != int(match.group(3)):
        raise SampleValidationError(
            'invalid_cas', f'Dígito verificador do CAS inválido: {cas!r}.'
        )
    return cas


def generate_code() -> str:
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def unique_code(taken: set[str], attempts: int = CODE_ATTEMPTS) -> str:
    """Código cego fora de `taken`; colisão gera outro (research R5)."""
    for _ in range(attempts):
        code = generate_code()
        if code not in taken:
            return code
    raise RuntimeError('Não foi possível gerar um código cego único.')


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


async def _open_run(
    session: AsyncSession, act: ActivityInstance
) -> ActivityRun | None:
    return await session.scalar(
        select(ActivityRun)
        .where(
            ActivityRun.activity_instance_id == act.id,
            ActivityRun.status == 'IN_PROGRESS',
            ActivityRun.deleted_at.is_(None),
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
    )


async def _mutable_activity(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> tuple[ActivityInstance, ActivityRun]:
    """Atividade travada e aberta, em processo mutável (FR-009, R6)."""
    act = await _sample_activity(session, process_id, user_id, lock=True)
    await ensure_process_mutable(session, process_id)
    run = (
        await _open_run(session, act) if act.status == 'IN_PROGRESS' else None
    )
    if run is None:
        raise SampleConflictError(
            'invalid_transition',
            f'Atividade de amostras em status {act.status!r} não permite '
            'alterações.',
        )
    return act, run


async def active_laboratories(
    session: AsyncSession, process_id: UUID
) -> list[Laboratory]:
    """Laboratórios com designação ativa de participante (research R4)."""
    return list(
        await session.scalars(
            select(Laboratory)
            .where(
                Laboratory.id.in_(
                    select(Assignment.laboratory_id).where(
                        Assignment.process_instance_id == process_id,
                        Assignment.role_key == PARTICIPATING_LABORATORY,
                        Assignment.revoked_at.is_(None),
                        Assignment.deleted_at.is_(None),
                    )
                ),
                Laboratory.deleted_at.is_(None),
            )
            .order_by(Laboratory.name, Laboratory.id)
        )
    )


async def _active_substances(
    session: AsyncSession, process_id: UUID
) -> list[StudySubstance]:
    return list(
        await session.scalars(
            select(StudySubstance)
            .where(
                StudySubstance.process_instance_id == process_id,
                StudySubstance.deleted_at.is_(None),
            )
            .order_by(StudySubstance.created_at, StudySubstance.id)
        )
    )


async def _substance(
    session: AsyncSession, process_id: UUID, substance_id: UUID
) -> StudySubstance:
    substance = await session.scalar(
        select(StudySubstance).where(
            StudySubstance.id == substance_id,
            StudySubstance.process_instance_id == process_id,
            StudySubstance.deleted_at.is_(None),
        )
    )
    if substance is None:
        raise NotFoundError('Substância não encontrada.')
    return substance


async def _active_codes(
    session: AsyncSession, process_id: UUID
) -> list[BlindSampleCode]:
    return list(
        await session.scalars(
            select(BlindSampleCode).where(
                BlindSampleCode.process_instance_id == process_id,
                BlindSampleCode.deleted_at.is_(None),
            )
        )
    )


async def _generate_missing_codes(
    session: AsyncSession,
    process_id: UUID,
    substances: list[StudySubstance],
    laboratories: list[Laboratory],
    actor_id: UUID,
) -> list[BlindSampleCode]:
    """Cria o código de cada combinação substância × laboratório que falta."""
    existing = await _active_codes(session, process_id)
    taken = {code.code for code in existing}
    pairs = {(code.substance_id, code.laboratory_id) for code in existing}
    created = []
    for substance in substances:
        for laboratory in laboratories:
            if (substance.id, laboratory.id) in pairs:
                continue
            code = BlindSampleCode(
                process_instance_id=process_id,
                substance_id=substance.id,
                laboratory_id=laboratory.id,
                code=unique_code(taken),
            )
            code.set_creation_audit(actor_id)
            session.add(code)
            taken.add(code.code)
            created.append(code)
    await session.flush()
    return created


def _audit(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    run: ActivityRun,
    user_id: UUID,
    event_type: str,
    context: dict[str, Any],
) -> None:
    """Evento só com ids e contagens — nunca identidade química (R9)."""
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type=event_type,
            context_data=context,
        )
    )


def _codes_generated_context(
    substance_id: UUID | None, codes: list[BlindSampleCode]
) -> dict[str, Any]:
    return {
        'substance_id': str(substance_id) if substance_id else None,
        'code_count': len(codes),
        'laboratory_ids': sorted({str(c.laboratory_id) for c in codes}),
    }


async def _serialize(
    session: AsyncSession,
    process_id: UUID,
    substances: list[StudySubstance],
) -> list[dict[str, Any]]:
    """Substâncias com códigos e SDS, uma consulta por tabela (sem N+1)."""
    substance_ids = {s.id for s in substances}
    codes = [
        c
        for c in await _active_codes(session, process_id)
        if c.substance_id in substance_ids
    ]
    lab_ids = {c.laboratory_id for c in codes}
    lab_names = (
        dict(
            (
                await session.execute(
                    select(Laboratory.id, Laboratory.name)
                    .where(Laboratory.id.in_(lab_ids))
                    .execution_options(skip_soft_delete_filter=True)
                )
            ).all()
        )
        if lab_ids
        else {}
    )
    artifact_ids = {s.sds_artifact_id for s in substances if s.sds_artifact_id}
    artifacts = (
        {
            a.id: a
            for a in await session.scalars(
                select(Artifact).where(Artifact.id.in_(artifact_ids))
            )
        }
        if artifact_ids
        else {}
    )
    codes_by_substance: dict[UUID, list[BlindSampleCode]] = {}
    for code in sorted(
        codes, key=lambda c: (lab_names.get(c.laboratory_id, ''), c.code)
    ):
        codes_by_substance.setdefault(code.substance_id, []).append(code)

    result = []
    for substance in substances:
        artifact = artifacts.get(substance.sds_artifact_id)
        result.append({
            'id': substance.id,
            'chemical_name': substance.chemical_name,
            'cas_number': substance.cas_number,
            'lot': substance.lot,
            'purity': substance.purity,
            'solubility': substance.solubility,
            'safe_handling_instructions': (
                substance.safe_handling_instructions
            ),
            'sds': (
                {
                    'filename': (artifact.metadata_payload or {}).get(
                        'original_filename'
                    )
                    or artifact.name,
                    'size': artifact.file_size,
                    'uploaded_at': artifact.created_at,
                }
                if artifact is not None
                else None
            ),
            'blind_codes': [
                {
                    'code': code.code,
                    'laboratory_id': code.laboratory_id,
                    'laboratory_name': lab_names.get(code.laboratory_id, ''),
                }
                for code in codes_by_substance.get(substance.id, [])
            ],
        })
    return result


async def _serialize_one(
    session: AsyncSession, process_id: UUID, substance: StudySubstance
) -> dict[str, Any]:
    return (await _serialize(session, process_id, [substance]))[0]


async def _ensure_unique_cas(
    session: AsyncSession,
    process_id: UUID,
    cas: str,
    exclude_id: UUID | None = None,
) -> None:
    stmt = select(StudySubstance.id).where(
        StudySubstance.process_instance_id == process_id,
        StudySubstance.cas_number == cas,
        StudySubstance.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(StudySubstance.id != exclude_id)
    if await session.scalar(stmt.limit(1)) is not None:
        raise _duplicate_cas(cas)


def _duplicate_cas(cas: str) -> SampleConflictError:
    return SampleConflictError(
        'duplicate_cas', f'CAS {cas} já cadastrado neste processo.'
    )


async def _commit_or_duplicate(session: AsyncSession, cas: str) -> None:
    """Commit; CAS duplicado por corrida vira 409 (research R6)."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if 'uq_study_substances_process_cas_active' in str(exc):
            raise _duplicate_cas(cas) from exc
        raise


# ---------------------------------------------------------------------------
# Cadastro (US1)
# ---------------------------------------------------------------------------


async def list_substances(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    act = await _sample_activity(session, process_id, user_id)
    substances = await _active_substances(session, process_id)
    return {
        'activity_status': act.status,
        'substances': await _serialize(session, process_id, substances),
    }


async def create_substance(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    _act, run = await _mutable_activity(session, process_id, user_id)
    cas = validate_cas(data['cas_number'])
    await _ensure_unique_cas(session, process_id, cas)

    substance = StudySubstance(
        process_instance_id=process_id,
        chemical_name=data['chemical_name'],
        cas_number=cas,
        lot=data['lot'],
        safe_handling_instructions=data['safe_handling_instructions'],
        purity=data.get('purity'),
        solubility=data.get('solubility'),
    )
    substance.set_creation_audit(user_id)
    session.add(substance)
    await session.flush()

    codes = await _generate_missing_codes(
        session,
        process_id,
        [substance],
        await active_laboratories(session, process_id),
        user_id,
    )
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_SUBSTANCE_REGISTERED',
        {'substance_id': str(substance.id)},
    )
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_CODES_GENERATED',
        _codes_generated_context(substance.id, codes),
    )
    await _commit_or_duplicate(session, cas)
    return await _serialize_one(session, process_id, substance)


async def update_substance(
    session: AsyncSession,
    process_id: UUID,
    substance_id: UUID,
    user_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    _act, run = await _mutable_activity(session, process_id, user_id)
    substance = await _substance(session, process_id, substance_id)
    blank = sorted(k for k in REQUIRED_FIELDS if k in data and data[k] is None)
    if blank:
        raise SampleValidationError(
            'required_field',
            f'Campos obrigatórios não podem ser nulos: {", ".join(blank)}.',
        )
    if 'cas_number' in data:
        data['cas_number'] = validate_cas(data['cas_number'])
        await _ensure_unique_cas(
            session, process_id, data['cas_number'], exclude_id=substance.id
        )
    for field, value in data.items():
        setattr(substance, field, value)
    substance.set_update_audit(user_id)
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_SUBSTANCE_UPDATED',
        {'substance_id': str(substance.id), 'fields': sorted(data)},
    )
    await _commit_or_duplicate(session, substance.cas_number)
    await session.refresh(substance)
    return await _serialize_one(session, process_id, substance)


async def delete_substance(
    session: AsyncSession,
    process_id: UUID,
    substance_id: UUID,
    user_id: UUID,
) -> str | None:
    """Exclui logicamente substância, códigos e SDS (FR-008).

    Devolve o caminho relativo do arquivo da SDS, para o chamador remover
    do disco depois do commit.
    """
    _act, run = await _mutable_activity(session, process_id, user_id)
    substance = await _substance(session, process_id, substance_id)
    substance.set_deletion_audit(user_id)
    for code in await session.scalars(
        select(BlindSampleCode).where(
            BlindSampleCode.substance_id == substance.id,
            BlindSampleCode.deleted_at.is_(None),
        )
    ):
        code.set_deletion_audit(user_id)
    removed_file = None
    if substance.sds_artifact_id is not None:
        artifact = await session.get(Artifact, substance.sds_artifact_id)
        if artifact is not None:
            artifact.set_deletion_audit(user_id)
            removed_file = artifact.file_path
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_SUBSTANCE_REMOVED',
        {'substance_id': str(substance.id)},
    )
    await session.commit()
    return removed_file


# ---------------------------------------------------------------------------
# SDS e conclusão (US2)
# ---------------------------------------------------------------------------


async def upload_sds(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    substance_id: UUID,
    user_id: UUID,
    upload: UploadFile,
) -> dict[str, Any]:
    """Anexa ou substitui a SDS em PDF da substância (FR-007, R7)."""
    _act, run = await _mutable_activity(session, process_id, user_id)
    substance = await _substance(session, process_id, substance_id)
    extension = validate_extension(upload.filename, set(SDS_EXTENSIONS))

    artifact = Artifact(
        process_instance_id=process_id,
        activity_run_id=run.id,
        key=SDS_ARTIFACT_KEY,
        name=(upload.filename or 'sds.pdf')[:255],
        metadata_payload={
            'original_filename': upload.filename,
            'extension': extension,
            'substance_id': str(substance.id),
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
    artifact.mime_type = 'application/pdf'
    artifact.checksum_sha256 = checksum

    previous_file = None
    if substance.sds_artifact_id is not None:
        previous = await session.get(Artifact, substance.sds_artifact_id)
        if previous is not None:
            previous.set_deletion_audit(user_id)
            previous_file = previous.file_path
    substance.sds_artifact_id = artifact.id
    substance.set_update_audit(user_id)
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_SDS_UPLOADED',
        {'substance_id': str(substance.id), 'artifact_id': str(artifact.id)},
    )
    await session.commit()
    if previous_file:
        remove_file_best_effort(attachment_abspath(settings, previous_file))
    await session.refresh(substance)
    return await _serialize_one(session, process_id, substance)


async def get_sds(
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    substance_id: UUID,
    user_id: UUID,
) -> tuple[Artifact, Path]:
    """SDS original para download; só o Grupo de Seleção (FR-022)."""
    act = await _sample_activity(session, process_id, user_id)
    substance = await _substance(session, process_id, substance_id)
    artifact = (
        await session.get(Artifact, substance.sds_artifact_id)
        if substance.sds_artifact_id
        else None
    )
    path = (
        attachment_abspath(settings, artifact.file_path)
        if artifact is not None and artifact.file_path
        else None
    )
    if path is None or not path.is_file():
        raise NotFoundError('Substância sem SDS.')
    run = await session.scalar(
        select(ActivityRun)
        .where(ActivityRun.activity_instance_id == act.id)
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
    )
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_SDS_DOWNLOADED',
        {'substance_id': str(substance.id), 'artifact_id': str(artifact.id)},
    )
    await session.commit()
    return artifact, path


async def complete_sample_definition(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Completa as combinações, descarta labs que saíram e congela (FR-013).

    O congelamento é o próprio `COMPLETED` da atividade (research R10).
    """
    act, run = await _mutable_activity(session, process_id, user_id)
    substances = await _active_substances(session, process_id)
    if not substances:
        raise SampleValidationError(
            'no_substances', 'Cadastre ao menos uma substância.'
        )
    missing = [str(s.id) for s in substances if s.sds_artifact_id is None]
    if missing:
        raise SampleValidationError(
            'missing_sds',
            'Há substâncias sem SDS anexada.',
            substance_ids=missing,
        )
    laboratories = await active_laboratories(session, process_id)
    if not laboratories:
        raise SampleValidationError(
            'no_laboratories',
            'O processo não tem laboratório participante vinculado.',
        )

    active_lab_ids = {lab.id for lab in laboratories}
    discarded = 0
    for code in await _active_codes(session, process_id):
        if code.laboratory_id not in active_lab_ids:
            code.set_deletion_audit(user_id)
            discarded += 1
    await session.flush()
    created = await _generate_missing_codes(
        session, process_id, substances, laboratories, user_id
    )
    if created:
        _audit(
            session,
            process_id,
            run,
            user_id,
            'SAMPLE_CODES_GENERATED',
            _codes_generated_context(None, created),
        )
    code_count = len(substances) * len(laboratories)
    _audit(
        session,
        process_id,
        run,
        user_id,
        'SAMPLE_DEFINITION_COMPLETED',
        {
            'substance_count': len(substances),
            'laboratory_count': len(laboratories),
            'code_count': code_count,
            'discarded_code_count': discarded,
        },
    )
    await _complete_activity_run(session, run, act, user_id)
    process = await session.get(ProcessInstance, process_id)
    await _advance_dependent_activities(session, process, act, user_id)
    await session.commit()
    return {
        'activity_status': act.status,
        'substance_count': len(substances),
        'laboratory_count': len(laboratories),
        'code_count': code_count,
    }


# ---------------------------------------------------------------------------
# Etiquetas (US3)
# ---------------------------------------------------------------------------


def vial_qr_url(settings: Settings, process_id: UUID, code: str) -> str:
    """URL do frontend gravada no QR: só processo e código (FR-016, R8)."""
    base = settings.SAMPLE_QR_BASE_URL or settings.AUTH_ALLOWED_ORIGINS[0]
    return f'{base.rstrip("/")}/amostras/{process_id}/frascos/{code}'


async def list_labels(
    session: AsyncSession,
    settings: Settings,
    process_id: UUID,
    user_id: UUID,
) -> list[dict[str, Any]]:
    """Dados de etiqueta de cada frasco, com QR em SVG (FR-015, FR-018)."""
    await _sample_activity(session, process_id, user_id)
    process = await session.get(ProcessInstance, process_id)
    rows = (
        await session.execute(
            select(BlindSampleCode, StudySubstance.lot, Laboratory.name)
            .join(
                StudySubstance,
                StudySubstance.id == BlindSampleCode.substance_id,
            )
            .join(Laboratory, Laboratory.id == BlindSampleCode.laboratory_id)
            .where(
                BlindSampleCode.process_instance_id == process_id,
                BlindSampleCode.deleted_at.is_(None),
                StudySubstance.deleted_at.is_(None),
            )
            .order_by(Laboratory.name, BlindSampleCode.code)
            .execution_options(skip_soft_delete_filter=True)
        )
    ).all()
    labels = []
    for code, lot, laboratory_name in rows:
        url = vial_qr_url(settings, process_id, code.code)
        labels.append({
            'code': code.code,
            'study_code': process.code,
            'laboratory_id': code.laboratory_id,
            'laboratory_name': laboratory_name,
            'lot': lot,
            'qr_url': url,
            'qr_svg': segno.make(url, error='m').svg_data_uri(),
        })
    return labels


# ---------------------------------------------------------------------------
# Visão cega do frasco (US4)
# ---------------------------------------------------------------------------


async def get_blind_vial(
    session: AsyncSession, process_id: UUID, code: str, user_id: UUID
) -> dict[str, Any]:
    """Destino do QR: só código, lote e manuseio seguro (FR-021)."""
    await _sample_activity(session, process_id, user_id)
    row = (
        await session.execute(
            select(
                BlindSampleCode.code,
                StudySubstance.lot,
                StudySubstance.safe_handling_instructions,
            )
            .join(
                StudySubstance,
                StudySubstance.id == BlindSampleCode.substance_id,
            )
            .where(
                BlindSampleCode.process_instance_id == process_id,
                BlindSampleCode.code == code,
                BlindSampleCode.deleted_at.is_(None),
                StudySubstance.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError('Frasco não encontrado.')
    return {
        'code': row.code,
        'lot': row.lot,
        'safe_handling_instructions': row.safe_handling_instructions,
    }
