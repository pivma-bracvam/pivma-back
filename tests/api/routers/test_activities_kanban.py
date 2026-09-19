# ruff: noqa: PLR2004
"""Spec 018 - `GET /activities/kanban` (User Story 1).

Cobre a classificação em 4 colunas, incluindo atividades `BLOCKED` sem
nenhuma `Task`/`ActivityRun` (ex.: a Fase 2 de exemplo da Spec 017), a
paginação, `counts_by_column` sobre o total visível e o estado vazio.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_kanban_includes_not_started_activity_without_any_task(
    client, session
):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    resp = client.post(
        '/processes',
        json={
            'template_key': 'validated_method_dossier',
            'title': 'Método para o Kanban',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']

    kanban_resp = client.get('/activities/kanban')
    assert kanban_resp.status_code == HTTPStatus.OK
    body = kanban_resp.json()

    by_key = {
        item['activity_key']: item
        for item in body['items']
        if item['process']['id'] == process_id
    }
    assert set(by_key) == {
        'proposal_submission',
        'triage_evaluation',
        'planning_preview',
    }

    # A submissão acabou de ser liberada: em andamento.
    assert by_key['proposal_submission']['column'] == 'EM_ANDAMENTO'
    assert by_key['proposal_submission']['cargo'] == 'proponent'

    # As duas atividades seguintes nunca tiveram Task/ActivityRun ainda,
    # mas aparecem mesmo assim, bloqueadas.
    assert by_key['triage_evaluation']['column'] == 'NAO_INICIADO'
    assert by_key['triage_evaluation']['run_started_at'] is None
    assert by_key['planning_preview']['column'] == 'NAO_INICIADO'
    assert by_key['planning_preview']['run_started_at'] is None
    # `planning_preview` não declara `sla_hours` no template (Spec 018).
    assert by_key['planning_preview']['sla_hours'] is None

    assert body['counts_by_column']['NAO_INICIADO'] >= 2
    assert body['counts_by_column']['EM_ANDAMENTO'] >= 1


@pytest.mark.asyncio
async def test_kanban_empty_state_for_user_without_any_activity(
    client, session
):
    await bootstrap_all_templates(session)
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = client.get('/activities/kanban')
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['items'] == []
    assert body['total'] == 0
    assert body['counts_by_column'] == {
        'NAO_INICIADO': 0,
        'EM_ANDAMENTO': 0,
        'EM_ATRASO': 0,
        'CONCLUIDO': 0,
    }


@pytest.mark.asyncio
async def test_kanban_pagination_respects_size(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    for i in range(3):
        resp = client.post(
            '/processes',
            json={
                'template_key': 'pre_validated_method',
                'title': f'Método {i}',
            },
        )
        assert resp.status_code == HTTPStatus.CREATED

    resp = client.get('/activities/kanban', params={'size': 2, 'page': 1})
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert len(body['items']) == 2
    assert body['total'] >= 6  # 3 processos x 2 atividades cada
    assert body['size'] == 2
    assert body['page'] == 1


@pytest.mark.asyncio
async def test_kanban_column_filter(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    resp = client.post(
        '/processes',
        json={
            'template_key': 'validated_method_dossier',
            'title': 'Filtro por coluna',
        },
    )
    process_id = resp.json()['id']

    resp = client.get(
        '/activities/kanban',
        params={'column': 'NAO_INICIADO', 'process_id': process_id},
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['items']
    assert all(item['column'] == 'NAO_INICIADO' for item in body['items'])


@pytest.mark.asyncio
async def test_kanban_triage_run_started_at_resets_after_diligencia(
    client, session, bracvam_user
):
    """Issue #22: antes, a rodada 2 da triagem reaproveitava `run_started_at`

    da rodada 1 (já concluída), travando o cálculo de SLA/atraso no início do
    processo em vez do início da rodada corrente.
    """
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    triador = bracvam_user
    session.add(proponent)
    await session.commit()

    authenticate(client, proponent)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Kanban - reinício de SLA da triagem',
        },
    )
    process_id = resp.json()['id']
    submission_values = {
        'method_title': 'Título V1',
        'endpoint_target': 'corrosivity',
        'scientific_justification': 'Justificativa inicial.',
        'pre_validation_evidence': 'Evidências prévias de repetibilidade.',
        'study_protocol_file': 'protocolo_v1.pdf',
    }
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': submission_values},
    )

    kanban_round_1 = client.get(
        '/activities/kanban', params={'process_id': process_id}
    )
    triage_card_1 = next(
        item
        for item in kanban_round_1.json()['items']
        if item['activity_key'] == 'triage_evaluation'
    )
    run_started_at_round_1 = triage_card_1['run_started_at']
    assert run_started_at_round_1 is not None

    authenticate(client, triador)
    client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Ajustar evidências.',
        },
        headers={'Origin': 'https://testserver'},
    )

    authenticate(client, proponent)
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {**submission_values, 'method_title': 'Título V2'}},
    )

    kanban_round_2 = client.get(
        '/activities/kanban', params={'process_id': process_id}
    )
    triage_card_2 = next(
        item
        for item in kanban_round_2.json()['items']
        if item['activity_key'] == 'triage_evaluation'
    )
    assert triage_card_2['run_started_at'] != run_started_at_round_1
    assert triage_card_2['column'] == 'EM_ANDAMENTO'
