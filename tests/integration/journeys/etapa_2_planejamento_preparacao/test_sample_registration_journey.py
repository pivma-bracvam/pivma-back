"""Jornada: cadastro ampliado da substância (Spec 040, US1).

Ricardo, do Grupo de Seleção de Amostras, cadastra uma substância com a
classificação de referência (gabarito), o regime refrigerado sem faixa
explícita, os dados do frasco, a reserva técnica e os pictogramas GHS. Vê
tudo na lista de substâncias, com a faixa de 2 °C a 8 °C preenchida pelo
regime. Conclui a definição e confere etiquetas e visão cega: pictogramas e
faixa aparecem; nome, CAS, SDS e gabarito não. Thiago, do laboratório, abre a
visão cega do próprio frasco e vê o mesmo.
"""

import json
from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import substance_payload
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    ok,
    open_sample_definition,
    register_substance,
    study_team,
)

GABARITO = 'Severamente irritante / Categoria 1'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _assert_blind(blob):
    text = json.dumps(blob, ensure_ascii=False)
    for secret in ('Formaldeído', '50-00-0', GABARITO):
        assert secret not in text
    for key in ('chemical_name', 'cas_number', 'reference_classification'):
        assert f'"{key}"' not in text


@pytest.mark.asyncio
async def test_grupo_cadastra_substancia_ampliada_e_laboratorio_ve_so_o_frasco(
    session, client, bracvam_user
):
    team = await study_team(session, lab_count=1)
    process_id = open_sample_definition(client, team, bracvam_user)
    samples = f'/processes/{process_id}/samples'

    # 1. Ricardo cadastra a substância com os dados novos.
    authenticate(client, team.selector)
    substance = register_substance(
        client,
        process_id,
        substance_payload(
            reference_classification=GABARITO,
            storage_temperature_regime='refrigerated',
            vial_nominal_quantity=50,
            vial_unit='mL',
            packaging_type='Frasco de vidro âmbar com lacre inviolável',
            expiration_date='2027-03-31',
            reserve_vials_count=2,
            ghs_hazard_pictograms=['GHS05', 'GHS06'],
        ),
    )

    # 2. Na lista, vê o gabarito, a reserva e a faixa do regime refrigerado.
    listed = ok(client.get(samples))['substances'][0]
    assert listed['reference_classification'] == GABARITO
    assert listed['reserve_vials_count'] == 2  # noqa: PLR2004
    assert listed['storage_temperature_min'] == 2.0  # noqa: PLR2004
    assert listed['storage_temperature_max'] == 8.0  # noqa: PLR2004
    assert listed['ghs_hazard_pictograms'] == ['GHS05', 'GHS06']

    # 3. Conclui a definição; etiqueta e visão cega trazem GHS e faixa, sem
    #    identidade química nem gabarito.
    ok(client.post(f'{samples}/complete', headers=ORIGIN))
    label = ok(client.get(f'{samples}/labels'))['data'][0]
    assert label['ghs_hazard_pictograms'] == ['GHS05', 'GHS06']
    assert label['storage_temperature_regime'] == 'refrigerated'
    assert label['vial_unit'] == 'mL'
    _assert_blind(label)
    code = substance['blind_codes'][0]['code']
    vial = ok(client.get(f'{samples}/vials/{code}'))
    assert vial['expiration_date'] == '2027-03-31'
    _assert_blind(vial)

    # 4. Thiago abre a visão cega do próprio frasco: mesmo conteúdo cego.
    authenticate(client, team.lab_users[0])
    assert ok(client.get(f'{samples}/vials/{code}')) == vial
    assert client.get(samples).status_code == HTTPStatus.NOT_FOUND
