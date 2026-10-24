import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import process_engine
from pivma.core.database.models import (
    ActivityRun,
    Assignment,
    AuditEvent,
    FormInstance,
    ProcessCodeSequence,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process
from tests.factories.user_factory import UserFactory

# 12h UTC: o mesmo ano em UTC e em Brasília.
MID_2026 = datetime(2026, 6, 1, 12, tzinfo=UTC)


def _freeze_clock(monkeypatch, moment):
    monkeypatch.setattr('pivma.core.process_engine.utc_now', lambda: moment)


async def _version_and_user(session):
    user = UserFactory()
    template = ProcessTemplate(key=f'code-{uuid4().hex}', name='Código')
    session.add_all([user, template])
    await session.flush()
    version = ProcessTemplateVersion(
        template_id=template.id, version_number=1, definition_payload={}
    )
    session.add(version)
    await session.commit()
    return version, user


async def _create(session, version, user):
    process = await instantiate_process(session, version, 'Processo', user.id)
    return process.code


@pytest.mark.asyncio
async def test_concurrent_process_creation_yields_distinct_crcodes(
    engine, monkeypatch
):
    """Duas instanciações concorrentes, em sessões e conexões distintas,
    devem gravar `code` distintos e consecutivos (FR-008).

    Este teste grava fora da transação do teste: começa e termina apagando a
    linha do ano em `process_code_sequences`."""
    _freeze_clock(monkeypatch, MID_2026)
    remove_sequence = delete(ProcessCodeSequence).where(
        ProcessCodeSequence.year == MID_2026.year
    )
    suffix = uuid4().hex
    async with AsyncSession(engine, expire_on_commit=False) as setup_session:
        user = UserFactory(
            username=f'crcode-actor-{suffix}',
            email=f'crcode-actor-{suffix}@test.com',
            password_hash='unused',
        )
        template = ProcessTemplate(
            key=f'crcode-{suffix}', name='Concurrency crCode template'
        )
        await setup_session.execute(remove_sequence)
        setup_session.add_all([user, template])
        await setup_session.flush()
        version = ProcessTemplateVersion(
            template_id=template.id, version_number=1, definition_payload={}
        )
        setup_session.add(version)
        await setup_session.commit()
        user_id, version_id, template_id = user.id, version.id, template.id

    async def create_process():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            template_version = await session.get(
                ProcessTemplateVersion, version_id
            )
            process = await instantiate_process(
                session, template_version, 'Processo concorrente', user_id
            )
            return process.id, process.code

    try:
        results = await asyncio.gather(create_process(), create_process())
        codes = {code for _, code in results}

        assert codes == {'VAL-2026-0001', 'VAL-2026-0002'}
    finally:
        # Apaga pela versão do template, não pela lista de resultados:
        # se uma criação falhar, a outra pode ter gravado.
        process_ids = select(ProcessInstance.id).where(
            ProcessInstance.template_version_id == version_id
        )
        async with AsyncSession(engine, expire_on_commit=False) as cleanup:
            await cleanup.execute(
                delete(AuditEvent).where(
                    AuditEvent.process_instance_id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(Assignment).where(
                    Assignment.process_instance_id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(ProcessInstance).where(
                    ProcessInstance.id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(ProcessTemplateVersion).where(
                    ProcessTemplateVersion.id == version_id
                )
            )
            await cleanup.execute(
                delete(ProcessTemplate).where(
                    ProcessTemplate.id == template_id
                )
            )
            # A sequência referencia o usuário: sai antes dele.
            await cleanup.execute(remove_sequence)
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_failed_instantiation_rolls_back_all_process_records(
    session, monkeypatch
):
    _freeze_clock(monkeypatch, MID_2026)
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    version = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'pre_validated_method')
        )
    ).scalar_one()

    async def fail_after_process_flush(*args, **kwargs):
        raise RuntimeError('falha simulada na preparação da atividade')

    create_phases = process_engine._create_phases_and_activities
    monkeypatch.setattr(
        process_engine,
        '_create_phases_and_activities',
        fail_after_process_flush,
    )

    user_id = user.id
    with pytest.raises(RuntimeError, match='falha simulada'):
        await instantiate_process(session, version, 'Falha atômica', user_id)

    process_count = await session.scalar(select(ProcessInstance.id))
    assignment_count = await session.scalar(select(Assignment.id))
    run_count = await session.scalar(select(ActivityRun.id))
    form_count = await session.scalar(select(FormInstance.id))

    assert process_count is None
    assert assignment_count is None
    assert run_count is None
    assert form_count is None
    assert await session.scalar(select(ProcessCodeSequence.year)) is None

    # A criação seguinte, sem falha, recebe o número que a falha teria usado.
    monkeypatch.setattr(
        process_engine, '_create_phases_and_activities', create_phases
    )
    await session.refresh(version)
    process = await instantiate_process(session, version, 'Processo', user_id)
    assert process.code == 'VAL-2026-0001'


@pytest.mark.asyncio
async def test_falha_com_contador_existente_nao_consome_numero(
    session, monkeypatch
):
    _freeze_clock(monkeypatch, MID_2026)
    version, user = await _version_and_user(session)
    user_id = user.id
    assert await _create(session, version, user) == 'VAL-2026-0001'

    async def fail(*args, **kwargs):
        raise RuntimeError('falha simulada na preparação da atividade')

    create_phases = process_engine._create_phases_and_activities
    monkeypatch.setattr(process_engine, '_create_phases_and_activities', fail)
    with pytest.raises(RuntimeError, match='falha simulada'):
        await instantiate_process(session, version, 'Falha', user_id)
    monkeypatch.setattr(
        process_engine, '_create_phases_and_activities', create_phases
    )

    await session.refresh(version)
    process = await instantiate_process(session, version, 'Processo', user_id)
    assert process.code == 'VAL-2026-0002'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('last_value', 'expected'),
    [(None, 'VAL-2026-0001'), (5, 'VAL-2026-0006')],
    ids=['primeira-do-ano', 'contador-existente'],
)
async def test_criacao_que_espera_outra_desfeita_recebe_o_numero_livre(
    engine, monkeypatch, last_value, expected
):
    """A segunda criação espera a trava da primeira; quando a primeira faz
    rollback, a segunda recebe o número que a primeira teria usado (FR-008,
    FR-009).

    Grava fora da transação do teste: começa e termina apagando a linha do
    ano em `process_code_sequences` e apaga o usuário no fim."""
    _freeze_clock(monkeypatch, MID_2026)
    remove_sequence = delete(ProcessCodeSequence).where(
        ProcessCodeSequence.year == MID_2026.year
    )
    suffix = uuid4().hex
    async with AsyncSession(engine) as setup_session:
        await setup_session.execute(remove_sequence)
        user = UserFactory(
            username=f'code-wait-{suffix}',
            email=f'code-wait-{suffix}@test.com',
            password_hash='unused',
        )
        setup_session.add(user)
        await setup_session.flush()
        user_id = user.id
        if last_value is not None:
            setup_session.add(
                ProcessCodeSequence(
                    year=MID_2026.year,
                    last_value=last_value,
                    created_by=user_id,
                )
            )
        await setup_session.commit()

    try:
        async with (
            AsyncSession(engine) as first,
            AsyncSession(engine) as second,
            AsyncSession(engine) as observer,
        ):
            await process_engine.generate_process_code(first, user_id)
            waiting = asyncio.create_task(
                process_engine.generate_process_code(second, user_id)
            )
            # Confirma que a segunda conexão está parada na trava da
            # primeira antes de desfazer a primeira.
            for _ in range(100):
                blocked = await observer.scalar(
                    text(
                        'SELECT count(*) FROM pg_stat_activity '
                        "WHERE wait_event_type = 'Lock' "
                        "AND query LIKE '%process_code_sequences%'"
                    )
                )
                await observer.rollback()
                if blocked:
                    break
                await asyncio.sleep(0.05)
            assert blocked == 1
            assert not waiting.done()

            await first.rollback()

            assert await asyncio.wait_for(waiting, timeout=5) == expected
            await second.commit()
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(remove_sequence)
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_primeira_submissao_do_ano_recebe_0001_e_a_seguinte_0002(
    session, monkeypatch
):
    _freeze_clock(monkeypatch, MID_2026)
    version, user = await _version_and_user(session)

    assert await _create(session, version, user) == 'VAL-2026-0001'
    assert await _create(session, version, user) == 'VAL-2026-0002'


@pytest.mark.asyncio
async def test_sequencia_recomeca_em_0001_no_ano_seguinte(
    session, monkeypatch
):
    version, user = await _version_and_user(session)
    _freeze_clock(monkeypatch, MID_2026)
    assert await _create(session, version, user) == 'VAL-2026-0001'

    _freeze_clock(monkeypatch, datetime(2027, 6, 1, 12, tzinfo=UTC))

    assert await _create(session, version, user) == 'VAL-2027-0001'


@pytest.mark.asyncio
async def test_ano_do_codigo_segue_o_horario_de_brasilia(session, monkeypatch):
    # 1h de 1/1/2027 em UTC são 22h de 31/12/2026 em Brasília.
    _freeze_clock(monkeypatch, datetime(2027, 1, 1, 1, tzinfo=UTC))
    version, user = await _version_and_user(session)

    assert await _create(session, version, user) == 'VAL-2026-0001'


@pytest.mark.asyncio
async def test_numero_acima_de_9999_ganha_mais_digitos(session, monkeypatch):
    _freeze_clock(monkeypatch, MID_2026)
    version, user = await _version_and_user(session)
    session.add(ProcessCodeSequence(year=MID_2026.year, last_value=9999))
    await session.commit()

    assert await _create(session, version, user) == 'VAL-2026-10000'


@pytest.mark.asyncio
async def test_sequencia_registra_quem_criou_e_quem_incrementou(
    session, monkeypatch
):
    _freeze_clock(monkeypatch, MID_2026)
    version, first_user = await _version_and_user(session)
    second_user = UserFactory()
    session.add(second_user)
    await session.commit()

    await _create(session, version, first_user)
    await _create(session, version, second_user)

    sequence = await session.scalar(
        select(ProcessCodeSequence)
        .where(ProcessCodeSequence.year == MID_2026.year)
        .execution_options(populate_existing=True)
    )
    assert sequence.created_by == first_user.id
    assert sequence.updated_by == second_user.id
