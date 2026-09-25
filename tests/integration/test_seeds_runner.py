import argparse

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    AuditEvent,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import instantiate_process
from scripts.seeds.runner import clean_demo_data

_SEEDED_PROCESS_COUNT = 2


@pytest.fixture
def parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true', default=False)
    parser.add_argument('--reset', action='store_true', default=False)
    return parser


def test_seeds_cli_parser_defaults(parser):
    args = parser.parse_args([])
    assert args.clean is False
    assert args.reset is False


def test_seeds_cli_parser_custom_options(parser):
    args = parser.parse_args(['--reset'])
    assert args.clean is False
    assert args.reset is True


def test_seeds_cli_parser_clean_flag(parser):
    args = parser.parse_args(['--clean'])
    assert args.clean is True


@pytest.mark.asyncio
async def test_clean_demo_data_purges_only_demo_processes(session, user):
    # 1. Cria um template e versão para os testes
    template = ProcessTemplate(key='tpl_test_runner', name='Template Teste')
    session.add(template)
    await session.flush()

    version = ProcessTemplateVersion(
        template_id=template.id,
        version_number=1,
        definition_payload={'phases': []},
        is_published=True,
    )
    session.add(version)
    await session.flush()

    # 2. Cria um processo oficial de demonstração [DEMO...]
    demo_proc = await instantiate_process(
        session=session,
        template_version=version,
        title='[DEMO 1] Processo Teste',
        creator_user_id=user.id,
    )

    # 3. Cria um processo de produção (SEM o prefixo [DEMO)
    prod_proc = await instantiate_process(
        session=session,
        template_version=version,
        title='Processo Real de Produção',
        creator_user_id=user.id,
    )
    await session.commit()

    # Confirma que ambos existem no banco
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ProcessInstance)
            .where(ProcessInstance.id.in_([demo_proc.id, prod_proc.id]))
        )
        == _SEEDED_PROCESS_COUNT
    )

    # 4. Executa a limpeza de dados de demonstração
    cleaned = await clean_demo_data(session=session)
    assert cleaned >= 1

    # 5. Validações pós-limpeza
    # Processo [DEMO deve ter sido expurgado fisicamente
    demo_exists = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == demo_proc.id)
    )
    assert demo_exists is None

    # Eventos de auditoria do processo DEMO também foram expurgados
    demo_audits = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.process_instance_id == demo_proc.id)
    )
    assert demo_audits == 0

    # Processo de PRODUÇÃO deve permanecer intacto
    prod_exists = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == prod_proc.id)
    )
    assert prod_exists is not None
    assert prod_exists.title == 'Processo Real de Produção'
