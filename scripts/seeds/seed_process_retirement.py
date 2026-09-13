"""Seed idempotente para a demonstração de ciclo de vida (Spec 022)."""

import asyncio

from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.attachment_service import (
    attachment_abspath,
    attachment_relpath,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    AuditEvent,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process, utc_now
from pivma.core.settings import Settings
from scripts.seeds.common import get_session

DEMO_DRAFT = '[DEMO 11] Rascunho excluível pelo proponente'
DEMO_ACTIVE = '[DEMO 11] Processo excluível por Admin/BraCVAM'
DEMO_CLOSED = '[DEMO 11] Processo encerrado arquivável'
DEMO_BLOCKED = '[DEMO 11] Processo já arquivado (tentativa bloqueada)'


async def _template_version(session, key: str):
    return await session.scalar(
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(
            ProcessTemplate.key == key,
            ProcessTemplate.deleted_at.is_(None),
            ProcessTemplateVersion.deleted_at.is_(None),
            ProcessTemplateVersion.is_published.is_(True),
        )
        .order_by(ProcessTemplateVersion.version_number.desc())
    )


async def _get_or_create(session, title: str, owner: User) -> ProcessInstance:
    process = await session.scalar(
        select(ProcessInstance).where(
            ProcessInstance.title == title,
            ProcessInstance.deleted_at.is_(None),
        )
    )
    if process is not None:
        return process
    version = await _template_version(session, 'pre_validated_method')
    if version is None:
        raise RuntimeError('Template pre_validated_method não encontrado.')
    return await instantiate_process(session, version, title, owner.id)


async def _ensure_attachment(session, process: ProcessInstance, owner: User):
    artifact = await session.scalar(
        select(Artifact).where(
            Artifact.process_instance_id == process.id,
            Artifact.key == 'form_attachment',
            Artifact.deleted_at.is_(None),
        )
    )
    if artifact is not None:
        return
    run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(ActivityInstance.process_instance_id == process.id)
        .order_by(ActivityRun.run_number)
    )
    if run is None:
        raise RuntimeError('Processo da demo não possui execução inicial.')
    extension = 'txt'
    artifact = Artifact(
        process_instance_id=process.id,
        activity_run_id=run.id,
        key='form_attachment',
        name='documento-da-demo.txt',
        file_path=None,
        file_size=24,
        mime_type='text/plain',
        checksum_sha256='demo-process-retirement',
        status='DRAFT',
        metadata_payload={
            'field_key': 'supporting_document',
            'original_filename': 'documento-da-demo.txt',
            'extension': extension,
        },
    )
    artifact.set_creation_audit(owner.id)
    session.add(artifact)
    await session.flush()
    artifact.file_path = attachment_relpath(process.id, artifact.id, extension)
    path = attachment_abspath(Settings(), artifact.file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('Anexo da demonstração 022\n')


async def _ensure_submission_event(
    session, process: ProcessInstance, owner: User
):
    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process.id,
            AuditEvent.event_type == 'SUBMISSION_SUBMITTED',
            AuditEvent.deleted_at.is_(None),
        )
    )
    if event is None:
        session.add(
            AuditEvent(
                process_instance_id=process.id,
                user_id=owner.id,
                event_type='SUBMISSION_SUBMITTED',
                context_data={'source': 'seed_process_retirement'},
            )
        )


async def run_seed_process_retirement() -> None:
    async with get_session() as session:
        await bootstrap_all_templates(session)
        owner = await session.scalar(
            select(User).where(
                func.lower(User.username) == 'proponent_user',
                User.deleted_at.is_(None),
            )
        )
        if owner is None:
            print('! Execute seed_users.py antes deste seed.')
            return

        draft = await _get_or_create(session, DEMO_DRAFT, owner)
        draft.status = 'SUBMISSION'
        await _ensure_attachment(session, draft, owner)

        active = await _get_or_create(session, DEMO_ACTIVE, owner)
        if active.status not in {'CANCELLED', 'ARCHIVED'}:
            active.status = 'TRIAGE'
            await _ensure_submission_event(session, active, owner)

        closed = await _get_or_create(session, DEMO_CLOSED, owner)
        if closed.status not in {'CLOSED', 'CANCELLED', 'ARCHIVED'}:
            closed.status = 'CLOSED'
            closed.closed_at = closed.closed_at or utc_now()
            closed.closure_reason = (
                closed.closure_reason or 'Seed de demonstração'
            )
            await _ensure_submission_event(session, closed, owner)

        blocked = await _get_or_create(session, DEMO_BLOCKED, owner)
        if blocked.status != 'ARCHIVED':
            blocked.status = 'ARCHIVED'
            blocked.closed_at = blocked.closed_at or utc_now()
            blocked.closure_reason = (
                blocked.closure_reason or 'Seed de demonstração'
            )
            await _ensure_submission_event(session, blocked, owner)
        await session.commit()
        print('✓ Seed da demonstração de ciclo de vida concluído.')
        print(f'  Rascunho excluível (proponente): {draft.code}')
        print(f'  Processo excluível (Admin/BraCVAM): {active.code}')
        print(f'  Processo fechado arquivável: {closed.code}')
        print(f'  Processo já arquivado (tentativa bloqueada): {blocked.code}')


def main() -> None:
    asyncio.run(run_seed_process_retirement())


if __name__ == '__main__':
    main()
