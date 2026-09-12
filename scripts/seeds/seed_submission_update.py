"""Seed mínimo e idempotente para a demonstração da Spec 021."""

import asyncio

from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import (
    NotFoundError,
    get_current_form_instance,
    instantiate_process,
)
from scripts.seeds.common import get_session

DEMO_TITLE = '[DEMO 10] Atualização de submissão'
DEMO_TEMPLATE_KEY = 'demo_submission_update'


async def run_seed_submission_update() -> None:
    async with get_session() as session:
        await bootstrap_all_templates(session)
        proponent = await session.scalar(
            select(User).where(
                func.lower(User.username) == 'proponent_user',
                User.deleted_at.is_(None),
            )
        )
        if proponent is None:
            print('! Execute seed_users.py antes deste seed.')
            return

        candidates = list(
            await session.scalars(
                select(ProcessInstance)
                .where(
                    ProcessInstance.title == DEMO_TITLE,
                    ProcessInstance.deleted_at.is_(None),
                )
                .order_by(ProcessInstance.created_at.desc())
            )
        )
        process = None
        for candidate in candidates:
            if candidate.status != 'SUBMISSION':
                continue
            try:
                _, _, form_instance, _, _ = await get_current_form_instance(
                    session, candidate.id, 'proposal_submission'
                )
            except NotFoundError:
                continue
            if not form_instance.is_submitted:
                process = candidate
                break

        if process is None:
            template_version = await session.scalar(
                select(ProcessTemplateVersion)
                .join(ProcessTemplate)
                .where(
                    ProcessTemplate.key == DEMO_TEMPLATE_KEY,
                    ProcessTemplate.deleted_at.is_(None),
                    ProcessTemplateVersion.deleted_at.is_(None),
                    ProcessTemplateVersion.is_published.is_(True),
                )
                .order_by(ProcessTemplateVersion.version_number.desc())
            )
            if template_version is None:
                print('! Template da demo não encontrado.')
                return
            process = await instantiate_process(
                session=session,
                template_version=template_version,
                title=DEMO_TITLE,
                creator_user_id=proponent.id,
            )
            print(f'✓ Processo da demonstração criado: {DEMO_TITLE}')
        else:
            print(f'✓ Processo da demonstração já existe: {DEMO_TITLE}')

        await session.commit()


def main() -> None:
    asyncio.run(run_seed_submission_update())


if __name__ == '__main__':
    main()
