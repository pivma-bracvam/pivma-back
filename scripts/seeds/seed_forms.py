"""Script de carga para templates de processos e formulários dinâmicos."""

import asyncio

from sqlalchemy import func, select, update

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process
from scripts.seeds.common import get_session

DEMO_PROCESS_TITLE = '[DEMO] Processo de Teste'


async def run_seed_forms() -> None:
    async with get_session() as session:
        # 1. Sincronizar templates e formulários da pasta templates_data
        await bootstrap_all_templates(session)

        # 2. Obter proponente
        prop_stmt = select(User).where(
            func.lower(User.username) == 'proponent_user',
            User.deleted_at.is_(None),
        )
        proponent = (await session.execute(prop_stmt)).scalar_one_or_none()
        if proponent is None:
            print(
                '! Proponente não encontrado. Execute seed_users.py primeiro.'
            )
            return

        # 3. Obter template_version mais recente para full_validation
        tv_stmt = (
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(
                ProcessTemplate.key == 'full_validation',
                ProcessTemplate.deleted_at.is_(None),
                ProcessTemplate.is_active.is_(True),
                ProcessTemplateVersion.deleted_at.is_(None),
                ProcessTemplateVersion.is_published.is_(True),
            )
            .order_by(ProcessTemplateVersion.version_number.desc())
        )
        tv = (await session.execute(tv_stmt)).scalars().first()
        if tv is None:
            print('! Template de validação não encontrado.')
            return

        # 4. Inativar processos antigos para manter apenas um processo
        await session.execute(
            update(ProcessInstance)
            .where(
                ProcessInstance.title != DEMO_PROCESS_TITLE,
                ProcessInstance.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )

        # 5. Garantir a existência do processo único de demonstração
        existing_p = (
            await session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.title == DEMO_PROCESS_TITLE,
                    ProcessInstance.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if existing_p is None:
            await instantiate_process(
                session=session,
                template_version=tv,
                title=DEMO_PROCESS_TITLE,
                creator_user_id=proponent.id,
            )
            await session.commit()
            print(f'✓ Processo único instanciado: {DEMO_PROCESS_TITLE}')
        else:
            print(f'✓ Processo único já existente: {DEMO_PROCESS_TITLE}')

        await session.commit()
        print('✓ Seed de Templates e Formulários concluído com sucesso.')


def main() -> None:
    asyncio.run(run_seed_forms())


if __name__ == '__main__':
    main()
