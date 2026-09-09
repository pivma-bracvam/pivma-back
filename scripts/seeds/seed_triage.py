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

DEMO_PROCESS_TITLE = '[DEMO] Processo de Teste'


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
                        ProcessTemplate.key == 'full_validation',
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

        # 1. Inativar processos antigos para manter processo único
        await session.execute(
            update(ProcessInstance)
            .where(
                ProcessInstance.title != DEMO_PROCESS_TITLE,
                ProcessInstance.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )

        # 2. Localizar ou criar o processo único
        proc = (
            await session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.title == DEMO_PROCESS_TITLE,
                    ProcessInstance.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if proc is None:
            proc = await instantiate_process(
                session=session,
                template_version=tv,
                title=DEMO_PROCESS_TITLE,
                creator_user_id=proponent.id,
            )
            await session.commit()
            print(f'✓ Processo único instanciado: {DEMO_PROCESS_TITLE}')

        # 3. Se estiver em SUBMISSION, avançar para TRIAGE
        if proc.status == 'SUBMISSION':
            values = {
                'method_title': (
                    'Ensaio BCOP de Opacidade e Permeabilidade Corneana'
                ),
                'endpoint_target': 'ocular_irritation',
                'scientific_justification': (
                    'Método alternativo validado segundo OECD TG 437 para'
                    ' substituição do teste de Draize in vivo.'
                ),
                'expected_laboratories_count': 3,
                'study_protocol_file': 'protocolo_validacao_bcop.pdf',
            }
            await submit_proposal_form(
                session=session,
                process_id=proc.id,
                activity_key='proposal_submission',
                values_dict=values,
                user_id=proponent.id,
            )
            print(
                f'✓ Proposta submetida para {DEMO_PROCESS_TITLE} (Status:'
                ' TRIAGE).'
            )
        else:
            print(
                f'✓ Processo único já preparado (Status atual: {proc.status}).'
            )

        await session.commit()
        print('✓ Seed de Triagem concluído com sucesso.')


def main() -> None:
    asyncio.run(run_seed_triage())


if __name__ == '__main__':
    main()
