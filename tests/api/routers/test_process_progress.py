"""Andamento do processo: lista por cargo e detalhe (Spec 048, US1 e US2).

A jornada fica em
`tests/integration/journeys/etapa_2_planejamento_preparacao/test_process_progress_journey.py`.
Aqui ficam as regras de cada campo, as exclusões, a paginação e os estados,
vistos pelo Patrocinador. O recorte de cada cargo fica em
`test_process_progress_visibility.py`.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from math import ceil
from typing import get_args

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Phase,
    ProcessInstance,
)
from pivma.core.process_engine import delete_process
from pivma.schemas import ParticipantRole
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.invite_factory import InviteFactory
from tests.factories.laboratory_run_factory import (
    complete_lab,
    end_affiliation,
    frozen_lab_process,
    reopen,
    runs_by_lab,
    waive,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.structure_approval_factory import (
    designate,
    planning_process,
    structure_process,
)
from tests.factories.user_factory import UserFactory

LIST = '/processes'
SPONSOR = {'role': 'sponsor'}
PHASE_2 = 'phase_2_role_assignment'
PHASE_3 = 'phase_3_validation_execution'
PER_PAGE = 2


def _detail(client, process_id):
    return client.get(f'{LIST}/{process_id}/progress')


def _items(client, **params):
    response = client.get(LIST, params=SPONSOR | params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _new_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _sponsored_draft(session, factory, sponsor):
    """Processo em rascunho com `sponsor` designado como Patrocinador."""
    process = await factory.draft(await _new_user(session))
    await grant_cargo(
        session, process_id=process.id, user=sponsor, role_key='sponsor'
    )
    return process


async def _open_runs(session, process_id):
    """Execuções em andamento, lidas no banco para conferir a resposta."""
    return (
        await session.execute(
            select(ActivityInstance.key, ActivityRun)
            .join(ActivityRun.activity_instance)
            .where(
                ActivityInstance.process_instance_id == process_id,
                ActivityRun.status == 'IN_PROGRESS',
            )
            .execution_options(populate_existing=True)
        )
    ).all()


async def _phase(session, process_id, key):
    phase = await session.scalar(
        select(Phase).where(
            Phase.process_instance_id == process_id, Phase.key == key
        )
    )
    return {'key': phase.key, 'name': phase.name, 'order': phase.order_index}


async def _sponsored_planning(session, bracvam):
    """Processo na Fase 2 com o Patrocinador designado."""
    ctx = await planning_process(session, bracvam)
    ctx.sponsor_assignment = await designate(
        session, ctx, ctx.sponsor, 'sponsor'
    )
    return ctx


async def _without_open_runs(session, ctx):
    """Estado do template 1 depois do último recebimento confirmado: o
    processo segue `OPEN` sem execução em andamento (montado na sessão).
    """
    for _, run in await _open_runs(session, ctx.process_id):
        run.status = 'COMPLETED'
    await session.commit()


async def _close(session, process_id, status):
    """Encerramento depois da Fase 2, que a API ainda não oferece (Notes)."""
    process = await session.get(ProcessInstance, process_id)
    process.status = status
    process.closed_at = datetime(2026, 11, 20)
    process.closure_reason = 'Estudo encerrado.'
    await session.commit()


# ---------------------------------------------------------------- lista


@pytest.mark.asyncio
async def test_lista_traz_campos_do_contrato(client, session, bracvam_user):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    body = _items(client)

    (item,) = body['data']
    assert {
        'current_phase',
        'open_activity_count',
        'my_roles',
    } <= set(item)
    assert set(item['current_phase']) == {'key', 'name', 'order'}
    assert item['my_roles'] == [
        {
            'role_key': 'sponsor',
            'laboratory': None,
            'assigned_at': ctx.sponsor_assignment.assigned_at.isoformat(),
        }
    ]
    assert body['pagination']['total_items'] == 1
    assert body['filters_applied'] == {
        'status': None,
        'mine': False,
        'role': 'sponsor',
        'submission_state': None,
    }
    assert body['sort'] == {'by': 'created_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_lista_traz_fase_e_contagem_na_fase_2(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    (item,) = _items(client)['data']

    assert item['current_phase'] == await _phase(
        session, ctx.process_id, PHASE_2
    )
    assert item['open_activity_count'] == len(
        await _open_runs(session, ctx.process_id)
    )
    assert item['open_activity_count'] >= 1


@pytest.mark.asyncio
async def test_lista_conta_uma_execucao_por_laboratorio_na_fase_3(
    client, session, bracvam_user
):
    ctx = await structure_process(
        session, bracvam_user, lab_count=3, previous_version=True
    )
    authenticate(client, ctx.sponsor)

    (item,) = _items(client)['data']

    runs = await _open_runs(session, ctx.process_id)
    receipts = [run for key, run in runs if key == 'sample_receipt']
    assert {run.laboratory_id for run in receipts} == {
        lab.id for lab in ctx.laboratories
    }
    assert item['current_phase']['key'] == PHASE_3
    assert item['open_activity_count'] == len(runs)


@pytest.mark.asyncio
async def test_lista_sem_fase_para_processo_aberto_sem_atividade(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user, previous_version=True)
    await _without_open_runs(session, ctx)
    authenticate(client, ctx.sponsor)

    (item,) = _items(client)['data']

    assert item['status'] == 'OPEN'
    assert item['current_phase'] is None
    assert item['open_activity_count'] == 0


@pytest.mark.asyncio
async def test_lista_exclui_processo_so_com_outro_cargo(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    other = await process_retirement_factory.draft(await _new_user(session))
    await grant_cargo(
        session, process_id=other.id, user=user, role_key='group_manager'
    )
    sponsored = await _sponsored_draft(
        session, process_retirement_factory, user
    )
    authenticate(client, user)

    assert [i['id'] for i in _items(client)['data']] == [str(sponsored.id)]


@pytest.mark.asyncio
async def test_lista_exclui_designacao_revogada(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    process = await process_retirement_factory.draft(await _new_user(session))
    assignment = await grant_cargo(
        session, process_id=process.id, user=user, role_key='sponsor'
    )
    assignment.revoked_at = datetime(2026, 11, 1)
    await session.commit()
    authenticate(client, user)

    assert _items(client)['data'] == []


@pytest.mark.asyncio
async def test_lista_exclui_convite_pendente(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    process = await process_retirement_factory.draft(await _new_user(session))
    session.add(
        InviteFactory(process=process, role_key='sponsor', email=user.email)
    )
    await session.commit()
    authenticate(client, user)

    assert _items(client)['data'] == []


@pytest.mark.asyncio
async def test_lista_exclui_processo_excluido(
    client, session, process_retirement_factory
):
    user, owner = await _new_user(session), await _new_user(session)
    process = await process_retirement_factory.draft(owner)
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='sponsor'
    )
    await delete_process(session, process.id, owner.id)
    await session.commit()
    authenticate(client, user)

    assert _items(client)['data'] == []


@pytest.mark.asyncio
async def test_lista_sem_filtro_traz_os_dois_processos_com_os_cargos(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    other = await process_retirement_factory.draft(await _new_user(session))
    await grant_cargo(
        session, process_id=other.id, user=user, role_key='collaborator'
    )
    sponsored = await _sponsored_draft(
        session, process_retirement_factory, user
    )
    authenticate(client, user)

    response = client.get(LIST)

    assert response.status_code == HTTPStatus.OK
    roles = {
        i['id']: [r['role_key'] for r in i['my_roles']]
        for i in response.json()['data']
    }
    assert roles == {
        str(other.id): ['collaborator'],
        str(sponsored.id): ['sponsor'],
    }


@pytest.mark.asyncio
async def test_lista_mostra_processo_uma_vez_com_dois_cargos(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    process = await _sponsored_draft(session, process_retirement_factory, user)
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='proponent'
    )
    authenticate(client, user)

    body = _items(client)

    assert [i['id'] for i in body['data']] == [str(process.id)]
    assert body['pagination']['total_items'] == 1
    assert [r['role_key'] for r in body['data'][0]['my_roles']] == [
        'sponsor',
        'proponent',
    ]


@pytest.mark.asyncio
async def test_lista_mostra_processo_encerrado_sem_fase(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    await _close(session, ctx.process_id, 'CLOSED')
    authenticate(client, ctx.sponsor)

    (item,) = _items(client)['data']

    assert item['status'] == 'CLOSED'
    assert item['closed_at'] is not None
    assert item['current_phase'] is None
    assert item['open_activity_count'] == 0


@pytest.mark.asyncio
async def test_lista_por_cargo_omite_arquivado_como_a_lista_geral(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    await _close(session, ctx.process_id, 'ARCHIVED')
    authenticate(client, ctx.sponsor)

    assert _items(client)['data'] == []


@pytest.mark.asyncio
async def test_lista_recusa_cargo_fora_do_catalogo(client, session):
    authenticate(client, await _new_user(session))

    response = client.get(LIST, params={'role': 'auditor'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


@pytest.mark.asyncio
async def test_lista_vazia_para_admin_sem_designacao(
    client, session, bracvam_user, process_retirement_factory
):
    await process_retirement_factory.draft(await _new_user(session))
    authenticate(client, bracvam_user)

    body = _items(client)

    assert body['data'] == []
    assert body['pagination']['total_items'] == 0


async def _three_sponsored(session, factory, user):
    """Três processos com `created_at` distintos, do mais antigo ao novo.

    Na transação do teste `now()` é o mesmo para todos, por isso a data é
    gravada na sessão.
    """
    processes = [await _sponsored_draft(session, factory, user) for _ in '123']
    for offset, process in enumerate(processes):
        process.created_at = datetime(2026, 11, 1) + timedelta(days=offset)
    await session.commit()
    return processes


@pytest.mark.asyncio
async def test_lista_ordena_por_criacao_decrescente(
    client, session, process_retirement_factory
):
    user = await _new_user(session)
    processes = await _three_sponsored(
        session, process_retirement_factory, user
    )
    authenticate(client, user)

    ids = [i['id'] for i in _items(client)['data']]

    assert ids == [str(p.id) for p in reversed(processes)]


@pytest.mark.asyncio
async def test_lista_pagina(client, session, process_retirement_factory):
    user = await _new_user(session)
    processes = await _three_sponsored(
        session, process_retirement_factory, user
    )
    authenticate(client, user)

    first = _items(client, per_page=PER_PAGE)
    second = _items(client, per_page=PER_PAGE, page=2)

    newest_first = [str(p.id) for p in reversed(processes)]
    assert [i['id'] for i in first['data']] == newest_first[:PER_PAGE]
    assert first['pagination']['has_next'] is True
    assert first['pagination']['total_pages'] == ceil(
        len(processes) / PER_PAGE
    )
    assert [i['id'] for i in second['data']] == newest_first[PER_PAGE:]
    assert second['pagination']['has_next'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('per_page', [0, 101])
async def test_lista_recusa_per_page_fora_do_intervalo(
    client, session, per_page
):
    authenticate(client, await _new_user(session))

    response = client.get(LIST, params={'per_page': per_page})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


def test_lista_exige_sessao(client):
    response = client.get(LIST)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


# -------------------------------------------------------------- detalhe


@pytest.mark.asyncio
async def test_detalhe_traz_um_cargo_por_participant_role(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    roles = _detail(client, ctx.process_id).json()['roles']

    assert [r['role_key'] for r in roles] == list(get_args(ParticipantRole))
    by_role = {r['role_key']: r['people'] for r in roles}
    assert by_role['statistician'] == []


@pytest.mark.asyncio
async def test_detalhe_traz_todas_as_fases_com_a_situacao(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    phases = _detail(client, ctx.process_id).json()['phases']

    stored = (
        await session.scalars(
            select(Phase)
            .where(Phase.process_instance_id == ctx.process_id)
            .order_by(Phase.order_index)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert phases == [
        {
            'key': p.key,
            'name': p.name,
            'order': p.order_index,
            'status': p.status,
        }
        for p in stored
    ]
    assert {p['status'] for p in phases} >= {'COMPLETED', 'IN_PROGRESS'}


@pytest.mark.asyncio
async def test_detalhe_traz_proponente_sem_email(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    response = _detail(client, ctx.process_id)

    by_role = {r['role_key']: r['people'] for r in response.json()['roles']}
    assert by_role['proponent'] == [
        {
            'user': {
                'id': str(ctx.proponent.id),
                'username': ctx.proponent.username,
                'full_name': ctx.proponent.full_name,
            },
            'laboratory': None,
        }
    ]
    assert '"email"' not in response.text
    assert ctx.proponent.email not in response.text
    assert ctx.sponsor.email not in response.text


@pytest.mark.asyncio
async def test_detalhe_traz_laboratorio_so_em_cargo_de_laboratorio(
    client, session, bracvam_user
):
    ctx = await structure_process(
        session, bracvam_user, complete_samples=False
    )
    authenticate(client, ctx.sponsor)

    roles = _detail(client, ctx.process_id).json()['roles']

    labs = {
        r['role_key']: [p['laboratory']['name'] for p in r['people']]
        for r in roles
        if r['role_key'] in {'lead_laboratory', 'participating_laboratory'}
    }
    assert labs == {
        'lead_laboratory': [ctx.laboratories[0].name],
        'participating_laboratory': [lab.name for lab in ctx.laboratories],
    }
    others = [
        p['laboratory']
        for r in roles
        if r['role_key'] not in labs
        for p in r['people']
    ]
    assert others
    assert set(others) == {None}


@pytest.mark.asyncio
async def test_detalhe_traz_dois_patrocinadores_e_cada_um_ve_a_propria_data(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    second = await _new_user(session)
    second_assignment = await designate(session, ctx, second, 'sponsor')

    authenticate(client, ctx.sponsor)
    first_body = _detail(client, ctx.process_id).json()
    authenticate(client, second)
    second_body = _detail(client, ctx.process_id).json()

    sponsors = {r['role_key']: r['people'] for r in first_body['roles']}[
        'sponsor'
    ]
    assert [p['user']['id'] for p in sponsors] == [
        str(ctx.sponsor.id),
        str(second.id),
    ]
    assert [r['assigned_at'] for r in first_body['my_roles']] == [
        ctx.sponsor_assignment.assigned_at.isoformat()
    ]
    assert [r['assigned_at'] for r in second_body['my_roles']] == [
        second_assignment.assigned_at.isoformat()
    ]


@pytest.mark.asyncio
async def test_detalhe_omite_usuario_desativado(client, session, bracvam_user):
    ctx = await _sponsored_planning(session, bracvam_user)
    manager = await _new_user(session)
    await designate(session, ctx, manager, 'group_manager')
    manager.deleted_at = datetime(2026, 11, 1)
    await session.commit()
    authenticate(client, ctx.sponsor)

    roles = _detail(client, ctx.process_id).json()['roles']

    assert {r['role_key']: r['people'] for r in roles}['group_manager'] == []


@pytest.mark.asyncio
async def test_detalhe_omite_laboratorio_sem_vinculo_ativo(
    client, session, bracvam_user
):
    ctx = await structure_process(
        session, bracvam_user, complete_samples=False
    )
    await end_affiliation(session, ctx.lab_users[1])
    authenticate(client, ctx.sponsor)

    roles = _detail(client, ctx.process_id).json()['roles']

    people = {r['role_key']: r['people'] for r in roles}
    assert [p['user']['id'] for p in people['participating_laboratory']] == [
        str(ctx.lab_users[0].id)
    ]


@pytest.mark.asyncio
async def test_detalhe_na_fase_2_lista_execucoes_abertas(
    client, session, bracvam_user
):
    ctx = await _sponsored_planning(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    body = _detail(client, ctx.process_id).json()

    expected = sorted(
        (key, run.started_at.isoformat())
        for key, run in await _open_runs(session, ctx.process_id)
    )
    assert body['current_phase'] == await _phase(
        session, ctx.process_id, PHASE_2
    )
    assert (
        sorted((a['key'], a['started_at']) for a in body['open_activities'])
        == expected
    )
    assert {a['phase_key'] for a in body['open_activities']} == {PHASE_2}
    assert {a['laboratory'] for a in body['open_activities']} == {None}


@pytest.mark.asyncio
async def test_detalhe_na_fase_3_traz_uma_execucao_por_laboratorio(
    client, session, bracvam_user
):
    ctx = await structure_process(
        session, bracvam_user, lab_count=3, previous_version=True
    )
    authenticate(client, ctx.sponsor)

    body = _detail(client, ctx.process_id).json()

    assert body['current_phase']['key'] == PHASE_3
    receipts = [
        a['laboratory']['name']
        for a in body['open_activities']
        if a['key'] == 'sample_receipt'
    ]
    assert receipts == sorted(lab.name for lab in ctx.laboratories)


async def _lab_process_with_sponsor(session):
    ctx = await frozen_lab_process(session)
    ctx.sponsor = await _new_user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.sponsor,
        role_key='sponsor',
    )
    return ctx


def _receipt_labs(body):
    return [
        a['laboratory']['id']
        for a in body['open_activities']
        if a['key'] == 'receipt'
    ]


@pytest.mark.asyncio
async def test_detalhe_omite_laboratorio_dispensado(client, session):
    ctx = await _lab_process_with_sponsor(session)
    await waive(session, ctx, 0)
    authenticate(client, ctx.sponsor)

    labs = _receipt_labs(_detail(client, ctx.process_id).json())

    assert str(ctx.labs[0].id) not in labs
    assert set(labs) == {str(ctx.labs[1].id), str(ctx.labs[2].id)}


@pytest.mark.asyncio
async def test_detalhe_mostra_execucao_reaberta_com_data_da_reabertura(
    client, session
):
    ctx = await _lab_process_with_sponsor(session)
    await complete_lab(session, ctx, 'receipt', 0)
    await reopen(session, ctx, 'receipt', 0)
    reopened = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[0].id
    ]
    authenticate(client, ctx.sponsor)

    body = _detail(client, ctx.process_id).json()

    lab_0 = [
        a
        for a in body['open_activities']
        if a['key'] == 'receipt'
        and a['laboratory']['id'] == str(ctx.labs[0].id)
    ]
    assert [a['started_at'] for a in lab_0] == [
        reopened.started_at.isoformat()
    ]


@pytest.mark.asyncio
async def test_detalhe_de_processo_aberto_sem_atividade(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user, previous_version=True)
    await _without_open_runs(session, ctx)
    authenticate(client, ctx.sponsor)

    response = _detail(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['current_phase'] is None
    assert body['open_activities'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['CLOSED', 'ARCHIVED'])
async def test_detalhe_de_processo_encerrado_ou_arquivado_sem_fase(
    client, session, bracvam_user, status
):
    ctx = await _sponsored_planning(session, bracvam_user)
    await _close(session, ctx.process_id, status)
    authenticate(client, ctx.sponsor)

    response = _detail(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['current_phase'] is None
    assert body['open_activities'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('profile', ['administrator', 'bracvam'])
async def test_detalhe_para_admin_e_bracvam_sem_designacao(
    client, session, bracvam_user, ai_eval_admin, profile
):
    ctx = await _sponsored_planning(session, bracvam_user)
    viewer = {'administrator': ai_eval_admin, 'bracvam': bracvam_user}[profile]
    authenticate(client, viewer)

    response = _detail(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['my_roles'] == []
    assert [r['role_key'] for r in body['roles']] == list(
        get_args(ParticipantRole)
    )
