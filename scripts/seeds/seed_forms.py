"""Script de carga para templates de processos e formulários dinâmicos."""

import asyncio

from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process
from scripts.seeds.common import get_session

OFFICIAL_DEMO_PROCESSES = [
    {
        'key': 'pre_validated_method',
        'title': '[DEMO 1] Método Pré-Validado',
    },
    {
        'key': 'scope_extension',
        'title': '[DEMO 2] Extensão de Escopo',
    },
    {
        'key': 'me_too_validation',
        'title': '[DEMO 3] Validação Me-Too',
    },
    {
        'key': 'validated_method_dossier',
        'title': '[DEMO 4] Dossiê Validado — Exemplo de IA',
    },
    {
        'key': 'proof_of_concept',
        'title': '[DEMO 5] Prova de Conceito — Formulário Preliminar (FP)',
    },
]


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

        # 3. Instanciar cada um dos 5 processos oficiais caso não existam
        for item in OFFICIAL_DEMO_PROCESSES:
            key = item['key']
            title = item['title']

            tv_stmt = (
                select(ProcessTemplateVersion)
                .join(ProcessTemplate)
                .where(
                    ProcessTemplate.key == key,
                    ProcessTemplate.deleted_at.is_(None),
                    ProcessTemplate.is_active.is_(True),
                    ProcessTemplateVersion.deleted_at.is_(None),
                    ProcessTemplateVersion.is_published.is_(True),
                )
                .order_by(ProcessTemplateVersion.version_number.desc())
            )
            tv = (await session.execute(tv_stmt)).scalars().first()
            if tv is None:
                print(f"! Template '{key}' não encontrado.")
                continue

            existing_p = (
                await session.execute(
                    select(ProcessInstance).where(
                        ProcessInstance.title == title,
                        ProcessInstance.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if existing_p is None:
                await instantiate_process(
                    session=session,
                    template_version=tv,
                    title=title,
                    creator_user_id=proponent.id,
                )
                await session.commit()
                print(f'✓ Processo oficial instanciado: {title} ({key})')
            else:
                print(f'✓ Processo oficial já existente: {title} ({key})')

        await session.commit()
        print('✓ Seed dos 5 Processos e Formulários concluído com sucesso.')


def main() -> None:
    asyncio.run(run_seed_forms())


if __name__ == '__main__':
    main()
