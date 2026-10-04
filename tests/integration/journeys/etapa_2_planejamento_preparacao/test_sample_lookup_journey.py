"""Jornada: sugestões do PubChem com confirmação (Spec 040, US2).

Ricardo, do Grupo de Seleção, digita o CAS do formaldeído e pede a
consulta. Recebe o nome e três pictogramas GHS sugeridos. A consulta não
cria nada. Ele aceita o nome, retira um pictograma que julga não se aplicar
à alíquota diluída e cadastra: a substância gravada tem os valores que ele
enviou, não os sugeridos.
"""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import substance_payload
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    ok,
    open_sample_definition,
    study_team,
)


@pytest.mark.asyncio
async def test_grupo_consulta_cas_revisa_sugestoes_e_cadastra(
    session, client, bracvam_user, fake_pubchem
):
    team = await study_team(session, lab_count=1)
    process_id = open_sample_definition(client, team, bracvam_user)
    samples = f'/processes/{process_id}/samples'
    fake_pubchem()

    # 1. Ricardo digita o CAS e pede as sugestões.
    authenticate(client, team.selector)
    suggestion = ok(client.get(f'{samples}/lookup', params={'cas': '50-00-0'}))
    assert suggestion['chemical_name'] == 'Formaldehyde'
    assert suggestion['ghs_hazard_pictograms'] == ['GHS05', 'GHS06', 'GHS08']

    # 2. A consulta sozinha não criou substância.
    assert ok(client.get(samples))['substances'] == []

    # 3. Ele confirma o nome, ajusta os pictogramas e cadastra.
    created = ok(
        client.post(
            samples,
            json=substance_payload(
                chemical_name=suggestion['chemical_name'],
                cas_number=suggestion['cas_number'],
                ghs_hazard_pictograms=['GHS05', 'GHS08'],
            ),
            headers=ORIGIN,
        ),
        HTTPStatus.CREATED,
    )

    # 4. O que ficou gravado é o que ele enviou.
    listed = ok(client.get(samples))['substances']
    assert [s['id'] for s in listed] == [created['id']]
    assert listed[0]['chemical_name'] == 'Formaldehyde'
    assert listed[0]['ghs_hazard_pictograms'] == ['GHS05', 'GHS08']
