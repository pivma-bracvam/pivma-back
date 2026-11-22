"""Jornada: o proponente acompanha as decisões sobre a submissão pela caixa
de alerts (Spec 047, US3).

Ator: o proponente e a estatística do estudo. Objetivo: saber, sem abrir o
processo, que a triagem aprovou e, depois, que o BraCVAM homologou a
estrutura. Usa os passos de API das jornadas da Etapa 2
(`sample_steps.py`). A ida para a triagem pela IA fica no teste focado
`test_ai_approval_tells_proponent_submission_went_to_triage`.
"""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import VALID_CAS, substance_payload
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    approve_structure,
    complete_study_team,
    ok,
    open_sample_definition,
    register_substance,
    study_team,
)


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _alerts_of(client, user, kind):
    authenticate(client, user)
    response = client.get('/alerts')
    assert response.status_code == HTTPStatus.OK, response.text
    return [a for a in response.json()['data'] if a['kind'] == kind]


@pytest.mark.asyncio
async def test_proponente_ve_a_aprovacao_da_triagem_e_a_homologacao(
    client, session, bracvam_user
):
    team = await study_team(session, lab_count=1)

    # 1. O proponente envia a proposta e o BraCVAM aprova a triagem. O
    #    proponente vê a situação nova, sem a justificativa da triagem.
    process_id = open_sample_definition(client, team, bracvam_user)
    [decided] = _alerts_of(client, team.proponent, 'submission_status_changed')
    assert decided['params']['status'] == 'approved'
    assert decided['target'] == {
        'type': 'process',
        'process_id': process_id,
        'id': None,
    }
    assert 'Aderente' not in str(decided)

    # 2. A equipe se forma, as amostras ficam prontas e o BraCVAM homologa
    #    a estrutura.
    complete_study_team(client, team, process_id, bracvam_user)
    authenticate(client, team.selector)
    register_substance(
        client,
        process_id,
        substance_payload(chemical_name='Secreta', cas_number=VALID_CAS[0]),
    )
    ok(
        client.post(
            f'/processes/{process_id}/samples/complete', headers=ORIGIN
        )
    )
    approve_structure(client, process_id, bracvam_user)

    # 3. O proponente e a estatística veem a homologação; quem homologou,
    #    não.
    for person in (team.proponent, team.statistician):
        [approved] = _alerts_of(client, person, 'structure_approved')
        assert approved['target']['process_id'] == process_id
    assert _alerts_of(client, bracvam_user, 'structure_approved') == []
