"""Andamento do processo: o que cada cargo vê (Spec 048, US4).

Cada teste parte de um processo na Fase 3 do template 1, com os cargos
designados e um recebimento aberto por laboratório, e olha o detalhe com os
olhos de um cargo. As regras estão em `pivma.core.process_progress`.
"""

from http import HTTPStatus
from typing import get_args

import pytest

from pivma.schemas import ParticipantRole
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.structure_approval_factory import structure_process
from tests.factories.user_factory import UserFactory

PHASE_3 = 'phase_3_validation_execution'
ALL_ROLES = list(get_args(ParticipantRole))
LAB_ROLES = {'lead_laboratory', 'participating_laboratory'}
COORDINATION = ['group_manager', 'proponent', 'sponsor']


async def _new_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _phase_3(session, bracvam):
    return await structure_process(
        session, bracvam, lab_count=2, previous_version=True
    )


async def _viewer(session, ctx, role_key):
    """Pessoa nova no cargo, fora dos laboratórios."""
    user = await _new_user(session)
    await grant_cargo(
        session, process_id=ctx.process_id, user=user, role_key=role_key
    )
    return user


def _progress(client, ctx, user):
    authenticate(client, user)
    response = client.get(f'/processes/{ctx.process_id}/progress')
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _people(body):
    return {
        r['role_key']: [p['user']['id'] for p in r['people']]
        for r in body['roles']
    }


def _run_labs(body):
    return {
        a['laboratory']['id']
        for a in body['open_activities']
        if a['laboratory']
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('role_key', ['group_manager', 'study_manager'])
async def test_coordenacao_ve_todos_os_cargos_e_laboratorios(
    client, session, bracvam_user, role_key
):
    ctx = await _phase_3(session, bracvam_user)
    viewer = await _viewer(session, ctx, role_key)

    body = _progress(client, ctx, viewer)

    assert [r['role_key'] for r in body['roles']] == ALL_ROLES
    assert _run_labs(body) == {str(lab.id) for lab in ctx.laboratories}
    people = _people(body)
    assert people['adhoc_evaluator'] == [str(ctx.adhoc.id)]
    assert len(people['participating_laboratory']) == len(ctx.laboratories)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'role_key',
    [
        'statistician',
        'collaborator',
        'sample_selection_group',
        'regulatory_observer',
    ],
)
async def test_cargo_de_apoio_ve_a_coordenacao_sem_laboratorios(
    client, session, bracvam_user, role_key
):
    ctx = await _phase_3(session, bracvam_user)
    viewer = await _viewer(session, ctx, role_key)

    body = _progress(client, ctx, viewer)

    roles = [r['role_key'] for r in body['roles']]
    assert set(roles) == {*COORDINATION, 'study_manager', role_key}
    assert _run_labs(body) == set()
    assert body['current_phase']['key'] == PHASE_3


@pytest.mark.asyncio
async def test_proponente_ve_a_coordenacao_sem_avaliador_nem_laboratorio(
    client, session, bracvam_user
):
    ctx = await _phase_3(session, bracvam_user)

    body = _progress(client, ctx, ctx.proponent)

    people = _people(body)
    assert set(people) == {*COORDINATION, 'study_manager'}
    assert people['group_manager'] == [str(ctx.manager.id)]
    assert people['sponsor'] == [str(ctx.sponsor.id)]
    assert people['proponent'] == [str(ctx.proponent.id)]
    assert ctx.adhoc.username not in str(body)
    assert ctx.lab_users[0].username not in str(body)
    assert _run_labs(body) == set()


@pytest.mark.asyncio
async def test_laboratorio_ve_so_a_propria_equipe_e_a_propria_execucao(
    client, session, bracvam_user
):
    ctx = await _phase_3(session, bracvam_user)
    other_lab, own_lab = ctx.laboratories

    body = _progress(client, ctx, ctx.lab_users[1])

    people = _people(body)
    assert people['participating_laboratory'] == [str(ctx.lab_users[1].id)]
    assert people['lead_laboratory'] == []
    assert _run_labs(body) == {str(own_lab.id)}
    assert other_lab.name not in str(body)
    assert body['my_roles'][0]['laboratory']['id'] == str(own_lab.id)


@pytest.mark.asyncio
async def test_laboratorio_e_patrocinador_veem_a_mesma_fase(
    client, session, bracvam_user
):
    ctx = await _phase_3(session, bracvam_user)

    lab = _progress(client, ctx, ctx.lab_users[1])
    sponsor = _progress(client, ctx, ctx.sponsor)

    assert lab['current_phase'] == sponsor['current_phase']
    assert lab['phases'] == sponsor['phases']
    assert len(lab['open_activities']) < len(sponsor['open_activities'])


@pytest.mark.asyncio
async def test_cartao_do_laboratorio_conta_so_o_que_ele_ve(
    client, session, bracvam_user
):
    ctx = await _phase_3(session, bracvam_user)
    detail = _progress(client, ctx, ctx.lab_users[1])

    response = client.get(
        '/processes', params={'role': 'participating_laboratory'}
    )

    (item,) = response.json()['data']
    assert item['open_activity_count'] == len(detail['open_activities'])
    assert item['current_phase'] == detail['current_phase']


@pytest.mark.asyncio
@pytest.mark.parametrize('role_key', ['adhoc_evaluator', 'peer_reviewer'])
async def test_avaliador_nao_ve_o_proponente_nem_outro_avaliador(
    client, session, bracvam_user, role_key
):
    ctx = await _phase_3(session, bracvam_user)
    viewer = await _viewer(session, ctx, role_key)

    body = _progress(client, ctx, viewer)

    people = _people(body)
    assert 'proponent' not in people
    assert people[role_key] == [str(viewer.id)]
    assert ctx.proponent.username not in str(body)
    assert ctx.adhoc.username not in str(body)
    assert set(people) == {
        'group_manager',
        'study_manager',
        'sponsor',
        role_key,
    }


@pytest.mark.asyncio
async def test_avaliador_com_outro_cargo_ve_a_uniao(
    client, session, bracvam_user
):
    ctx = await _phase_3(session, bracvam_user)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.adhoc,
        role_key='collaborator',
    )

    people = _people(_progress(client, ctx, ctx.adhoc))

    assert people['proponent'] == [str(ctx.proponent.id)]
    assert people['adhoc_evaluator'] == [str(ctx.adhoc.id)]
