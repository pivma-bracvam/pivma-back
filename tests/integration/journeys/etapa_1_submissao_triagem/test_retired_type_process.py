"""Jornada: o processo continua visível depois que o tipo sai de uso.

Spec 044, US1. Persona: um proponente que criou uma submissão de um tipo que
o BraCVAM retirou depois, e outra de um tipo vigente. Um novo deploy aposenta
o tipo retirado.

O proponente abre a lista e vê as duas submissões, cada uma com o seu tipo.
Ao abrir a submissão do tipo retirado, encontra o mesmo tipo e a mesma versão.
"""

from http import HTTPStatus

import pytest

from tests.factories.retired_template_factory import (
    RETIRED_KEY,
    RETIRED_NAME,
    deploy_without_retiring_type,
    seed_retiring_type,
)
from tests.integration.journeys.conftest import (
    bootstrap_fresh_deploy,
    log_in,
    sign_up,
)


def _create(client, template_key, title):
    response = client.post(
        '/processes', json={'template_key': template_key, 'title': title}
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()['id']


@pytest.mark.asyncio
async def test_proponente_ve_processo_de_tipo_aposentado_na_lista_e_no_detalhe(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    version = await seed_retiring_type(session)

    # 1. O proponente cria uma submissão do tipo que vai sair e uma vigente.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    retired_id = _create(client, RETIRED_KEY, 'Prova antiga')
    current_id = _create(client, 'pre_validated_method', 'Método atual')

    # 2. Um novo deploy roda o bootstrap sem o tipo retirado.
    await deploy_without_retiring_type(session)

    # 3. O proponente abre a lista e vê as duas submissões com os seus tipos.
    response = client.get('/processes', params={'page': 1, 'per_page': 100})
    assert response.status_code == HTTPStatus.OK, response.text
    types = {
        item['id']: item['template']['key'] for item in response.json()['data']
    }
    assert types == {
        retired_id: RETIRED_KEY,
        current_id: 'pre_validated_method',
    }

    # 4. O proponente abre a submissão do tipo retirado e reconhece o tipo.
    response = client.get(f'/processes/{retired_id}')
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['template'] == {
        'key': RETIRED_KEY,
        'name': RETIRED_NAME,
        'version': version,
    }
