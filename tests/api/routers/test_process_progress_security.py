"""Andamento do processo: acesso e sigilo (Spec 048, US3 e US4).

Quem não vê o processo recebe o mesmo `404` de um processo inexistente; a
resposta só tem os campos do contrato e nenhum cargo vê dado interno do
estudo; as rotas de dados internos continuam recusando o Patrocinador.
"""

from datetime import datetime
from http import HTTPStatus
from typing import get_args
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import AuditEvent
from pivma.core.process_engine import delete_process
from pivma.schemas import ParticipantRole
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    complete_lab,
    frozen_lab_process,
    runs_by_lab,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.structure_approval_factory import (
    designate,
    planning_process,
    structure_process,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
LIST = '/processes'


def _detail(client, process_id):
    return client.get(f'{LIST}/{process_id}/progress')


async def _new_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _assert_not_found(response):
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


# ---------------------------------------------------------------- acesso


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'role_key',
    # Cargo de laboratório só vale com vínculo: fica nos testes de recorte.
    [r for r in get_args(ParticipantRole) if not r.endswith('_laboratory')],
)
async def test_detalhe_abre_para_todo_cargo_do_processo(
    client, session, bracvam_user, role_key
):
    ctx = await planning_process(session, bracvam_user)
    user = await _new_user(session)
    await grant_cargo(
        session, process_id=ctx.process_id, user=user, role_key=role_key
    )
    authenticate(client, user)

    response = _detail(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    assert [r['role_key'] for r in response.json()['my_roles']] == [role_key]


@pytest.mark.asyncio
async def test_detalhe_responde_404_a_quem_nao_participa(
    client, session, bracvam_user
):
    ctx = await planning_process(session, bracvam_user)
    authenticate(client, await _new_user(session))

    _assert_not_found(_detail(client, ctx.process_id))


@pytest.mark.asyncio
async def test_detalhe_responde_404_a_patrocinador_revogado(
    client, session, bracvam_user
):
    ctx = await planning_process(session, bracvam_user)
    assignment = await designate(session, ctx, ctx.sponsor, 'sponsor')
    assignment.revoked_at = datetime(2026, 11, 1)
    await session.commit()
    authenticate(client, ctx.sponsor)

    _assert_not_found(_detail(client, ctx.process_id))


@pytest.mark.asyncio
async def test_detalhe_responde_404_igual_a_processo_inexistente(
    client, session, bracvam_user
):
    ctx = await planning_process(session, bracvam_user)
    authenticate(client, await _new_user(session))

    existing = _detail(client, ctx.process_id)
    missing = _detail(client, uuid4())

    _assert_not_found(existing)
    assert existing.json() == missing.json()


@pytest.mark.asyncio
async def test_detalhe_responde_404_a_processo_excluido(
    client, session, process_retirement_factory
):
    owner, sponsor = await _new_user(session), await _new_user(session)
    process = await process_retirement_factory.draft(owner)
    await grant_cargo(
        session, process_id=process.id, user=sponsor, role_key='sponsor'
    )
    result = await delete_process(session, process.id, owner.id)
    await session.commit()
    assert result['status'] == 'CANCELLED'
    authenticate(client, sponsor)

    _assert_not_found(_detail(client, process.id))


@pytest.mark.asyncio
async def test_detalhe_recusa_id_que_nao_e_uuid(client, session):
    authenticate(client, await _new_user(session))

    response = _detail(client, 'nao-e-uuid')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


def test_detalhe_exige_sessao(client):
    assert _detail(client, uuid4()).status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_consultas_nao_gravam_evento(client, session, bracvam_user):
    ctx = await structure_process(session, bracvam_user)

    async def events():
        return await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.process_instance_id == ctx.process_id)
        )

    before = await events()
    authenticate(client, ctx.sponsor)
    assert client.get(LIST, params={'role': 'sponsor'}).status_code == (
        HTTPStatus.OK
    )
    assert _detail(client, ctx.process_id).status_code == HTTPStatus.OK

    assert await events() == before


# ---------------------------------------------------------------- sigilo


@pytest.mark.asyncio
async def test_detalhe_tem_so_as_chaves_do_contrato(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user, previous_version=True)
    authenticate(client, ctx.sponsor)

    body = _detail(client, ctx.process_id).json()

    assert set(body) == {
        'process_id',
        'my_roles',
        'current_phase',
        'phases',
        'roles',
        'open_activities',
    }
    assert set(body['current_phase']) == {'key', 'name', 'order'}
    assert {frozenset(p) for p in body['phases']} == {
        frozenset({'key', 'name', 'order', 'status'})
    }
    assert {frozenset(r) for r in body['my_roles']} == {
        frozenset({'role_key', 'laboratory', 'assigned_at'})
    }
    assert {frozenset(r) for r in body['roles']} == {
        frozenset({'role_key', 'people'})
    }
    people = [p for r in body['roles'] for p in r['people']]
    assert {frozenset(p) for p in people} == {
        frozenset({'user', 'laboratory'})
    }
    assert {frozenset(p['user']) for p in people} == {
        frozenset({'id', 'username', 'full_name'})
    }
    assert {frozenset(a) for a in body['open_activities']} == {
        frozenset({'key', 'name', 'phase_key', 'started_at', 'laboratory'})
    }


def _secrets(substance):
    return [
        substance['chemical_name'],
        substance['cas_number'],
        *(code['code'] for code in substance['blind_codes']),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'viewer',
    ['sponsor', 'proponent', 'manager', 'statistician', 'adhoc', 'lab'],
)
async def test_nenhum_cargo_ve_identidade_da_substancia(
    client, session, bracvam_user, viewer
):
    ctx = await structure_process(session, bracvam_user, previous_version=True)
    user = ctx.lab_users[1] if viewer == 'lab' else getattr(ctx, viewer)
    authenticate(client, user)

    texts = [client.get(LIST).text, _detail(client, ctx.process_id).text]

    assert ctx.substance['blind_codes']
    for secret in _secrets(ctx.substance):
        assert all(secret not in text for text in texts), secret


INTERNAL_READS = [
    'samples',
    'samples/labels',
    'sample-receipt/vials',
    'sample-receipt/nonconformities',
    'structure-approval',
    'activities/sample_definition/form',
    'activities/statistical_plan/form',
]


@pytest.mark.asyncio
@pytest.mark.parametrize('path', INTERNAL_READS)
async def test_rotas_de_leitura_internas_continuam_fechadas_ao_patrocinador(
    client, session, bracvam_user, path
):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, ctx.sponsor)

    response = client.get(f'/processes/{ctx.process_id}/{path}')

    assert response.status_code in {
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
    }, response.text
    assert ctx.substance['chemical_name'] not in response.text


def _waiver(client, ctx):
    return client.post(
        f'/processes/{ctx.process_id}/phases/phase_execution/'
        'laboratory-waivers',
        json={'laboratory_id': str(ctx.labs[0].id), 'reason': 'Sem leitora.'},
        headers=ORIGIN,
    )


def _reopen(client, ctx):
    return client.post(
        f'/processes/{ctx.process_id}/activities/receipt/laboratories/'
        f'{ctx.labs[0].id}/reopen',
        json={'reason': 'Controle positivo fora.'},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('action', [_waiver, _reopen])
async def test_acoes_de_execucao_continuam_fechadas_ao_patrocinador(
    client, session, action
):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 0)
    sponsor = await _new_user(session)
    await grant_cargo(
        session, process_id=ctx.process_id, user=sponsor, role_key='sponsor'
    )
    before = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[0].id
    ]
    before_id, before_status = before.id, before.status
    authenticate(client, sponsor)

    response = action(client, ctx)

    assert response.status_code in {
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
    }, response.text
    after = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[0].id
    ]
    assert (after.id, after.status) == (before_id, before_status)
