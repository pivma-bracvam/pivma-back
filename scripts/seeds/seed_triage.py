"""Script de carga para processo de triagem e decisão."""

import asyncio

from sqlalchemy import func, select, update

from pivma.core.database.models import (
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import (
    instantiate_process,
    submit_proposal_form,
)
from scripts.seeds.common import get_session
from scripts.seeds.seed_forms import OFFICIAL_DEMO_PROCESSES

TRIAGE_DEMO_TITLE = '[DEMO 1] Método Pré-Validado'


async def run_seed_triage() -> None:
    async with get_session() as session:
        # Obter proponente
        proponent = (
            await session.execute(
                select(User).where(
                    func.lower(User.username) == 'proponent_user',
                    User.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if not proponent:
            print('! Proponente ausente. Execute seed_users.py primeiro.')
            return

        tv = (
            (
                await session.execute(
                    select(ProcessTemplateVersion)
                    .join(ProcessTemplate)
                    .where(
                        ProcessTemplate.key == 'pre_validated_method',
                        ProcessTemplate.deleted_at.is_(None),
                        ProcessTemplateVersion.is_published.is_(True),
                    )
                    .order_by(ProcessTemplateVersion.version_number.desc())
                )
            )
            .scalars()
            .first()
        )

        if not tv:
            print('! Template não encontrado. Execute seed_forms.py primeiro.')
            return

        valid_titles = [item['title'] for item in OFFICIAL_DEMO_PROCESSES]

        # 1. Inativar processos que não pertencem aos demos oficiais
        await session.execute(
            update(ProcessInstance)
            .where(
                ProcessInstance.title.not_in(valid_titles),
                ProcessInstance.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )

        # 2. Localizar ou criar o processo de demonstração de triagem
        proc = (
            await session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.title == TRIAGE_DEMO_TITLE,
                    ProcessInstance.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if proc is None:
            proc = await instantiate_process(
                session=session,
                template_version=tv,
                title=TRIAGE_DEMO_TITLE,
                creator_user_id=proponent.id,
            )
            await session.commit()
            print(f'✓ Processo instanciado: {TRIAGE_DEMO_TITLE}')

        # 3. Se estiver em SUBMISSION, avançar para TRIAGE
        if proc.status == 'SUBMISSION':
            values = {
                'method_title': (
                    'Ensaio BCOP de opacidade e permeabilidade corneana'
                ),
            }
            await submit_proposal_form(
                session=session,
                process_id=proc.id,
                activity_key='proposal_submission',
                values_dict=values,
                user_id=proponent.id,
            )
            print(
                f'✓ Proposta submetida para {TRIAGE_DEMO_TITLE} (Status:'
                ' TRIAGE).'
            )
        else:
            print(f'✓ Processo já preparado (Status atual: {proc.status}).')

        await session.commit()
        print('✓ Seed de Triagem concluído com sucesso.')


def main() -> None:
    asyncio.run(run_seed_triage())


if __name__ == '__main__':
    main()
