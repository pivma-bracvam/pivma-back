"""Massas persistidas para os cenários de ciclo de vida de processos."""

from pathlib import Path

from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.attachment_service import attachment_relpath
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    AuditEvent,
    FormInstance,
    FormValue,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process


class ProcessRetirementFactory:
    """Cria processos com os estados usados pela spec 022."""

    def __init__(self, session):
        self.session = session

    async def _new_process(self, owner: User, title: str) -> ProcessInstance:
        await bootstrap_all_templates(self.session)
        version = await self.session.scalar(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'pre_validated_method')
            .order_by(ProcessTemplateVersion.version_number.desc())
        )
        if version is None:
            raise AssertionError('template de teste não foi criado')
        return await instantiate_process(
            self.session, version, title, owner.id
        )

    async def draft(self, owner: User, title: str = 'Rascunho descartável'):
        return await self._new_process(owner, title)

    async def submitted(
        self,
        owner: User,
        *,
        status: str = 'AI_PRE_EVALUATION',
        title: str = 'Processo submetido',
    ):
        process = await self._new_process(owner, title)
        process.status = status
        self.session.add(
            AuditEvent(
                process_instance_id=process.id,
                user_id=owner.id,
                event_type='SUBMISSION_SUBMITTED',
                context_data={'run_number': 1},
            )
        )
        await self.session.commit()
        return process

    async def terminal(
        self,
        owner: User,
        *,
        status: str = 'CLOSED',
        title: str = 'Processo terminal',
    ):
        process = await self.submitted(owner, status=status, title=title)
        process.closed_at = process.started_at
        process.closure_reason = 'Encerramento de teste'
        await self.session.commit()
        return process

    async def returned_revision(
        self,
        owner: User,
        title: str = 'Processo devolvido para revisão',
    ):
        process = await self.submitted(owner, status='SUBMISSION', title=title)
        self.session.add(
            AuditEvent(
                process_instance_id=process.id,
                user_id=owner.id,
                event_type='REVISION_REQUESTED',
                context_data={'new_run_number': 2},
            )
        )
        await self.session.commit()
        return process

    async def add_attachment(
        self,
        process: ProcessInstance,
        owner: User,
        root: Path,
        filename: str = 'documento.txt',
    ) -> Artifact:
        run = await self.session.scalar(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == process.id)
            .order_by(ActivityRun.run_number)
        )
        if run is None:
            raise AssertionError('processo de teste sem activity run')
        artifact = Artifact(
            process_instance_id=process.id,
            activity_run_id=run.id,
            key='form_attachment',
            name=filename,
            file_path=None,
            file_size=5,
            mime_type='text/plain',
            status='DRAFT',
        )
        artifact.set_creation_audit(owner.id)
        self.session.add(artifact)
        await self.session.flush()
        artifact.file_path = attachment_relpath(
            process.id, artifact.id, Path(filename).suffix.lstrip('.') or 'bin'
        )
        form = await self.session.scalar(
            select(FormInstance).where(FormInstance.activity_run_id == run.id)
        )
        if form is not None:
            field = await self.session.scalar(
                select(FormValue).where(FormValue.form_instance_id == form.id)
            )
            if field is not None:
                field.file_attachment_id = artifact.id
            else:
                # O vínculo é opcional na massa; o artefato ainda pertence ao
                # agregado e valida a remoção do diretório físico.
                pass
        path = root / str(process.id) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('teste')
        await self.session.commit()
        return artifact
