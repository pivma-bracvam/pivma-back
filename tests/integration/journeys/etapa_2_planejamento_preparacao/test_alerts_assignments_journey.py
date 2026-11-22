"""Jornada: a pessoa designada sabe que entrou e que saiu do estudo
(Spec 047, US4).

Ator: o BraCVAM, que designa e revoga, e a estatística e o colaborador,
que recebem os alerts. Usa os passos de API das jornadas da Etapa 2
(`sample_steps.py`).
"""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    designate,
    open_sample_definition,
    study_team,
)


def _alerts_of(client, user, kind):
    authenticate(client, user)
    response = client.get('/alerts')
    assert response.status_code == HTTPStatus.OK, response.text
    return [a for a in response.json()['data'] if a['kind'] == kind]


@pytest.mark.asyncio
async def test_designada_ve_que_entrou_e_colaborador_ve_que_saiu(
    client, session, bracvam_user
):
    team = await study_team(session, lab_count=1)
    process_id = open_sample_definition(client, team, bracvam_user)

    # 1. O BraCVAM designa a estatística, que vê o cargo no alert.
    authenticate(client, bracvam_user)
    designate(client, process_id, team.statistician, 'statistician')
    [created] = _alerts_of(client, team.statistician, 'assignment_created')
    assert created['params']['role_key'] == 'statistician'
    assert created['params']['laboratory_name'] is None
    assert created['target']['process_id'] == process_id

    # 2. O BraCVAM designa e depois revoga o colaborador, que vê a saída.
    authenticate(client, bracvam_user)
    assignment = designate(
        client, process_id, team.collaborator, 'collaborator'
    )
    revoked = client.delete(
        f'/processes/{process_id}/participants/{assignment["id"]}',
        headers=ORIGIN,
    )
    assert revoked.status_code == HTTPStatus.NO_CONTENT, revoked.text
    [gone] = _alerts_of(client, team.collaborator, 'assignment_revoked')
    assert gone['params']['role_key'] == 'collaborator'

    # 3. O BraCVAM não recebe alert das próprias designações.
    authenticate(client, bracvam_user)
    kinds = {a['kind'] for a in client.get('/alerts').json()['data']}
    assert not kinds & {'assignment_created', 'assignment_revoked'}
