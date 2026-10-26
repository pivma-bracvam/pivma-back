"""Jornada: a edição do formulário pelo BraCVAM sobrevive a um novo deploy.

Persona: a administradora inicial de um deploy novo, que ajusta o
formulário de submissão do Método Novo pelo editor. Depois a API passa por
um novo deploy, que roda o bootstrap dos templates de novo, e um
proponente cria uma submissão.

O proponente precisa ver o formulário como o BraCVAM o deixou: o rótulo
alterado e o campo acrescentado.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)

FORM_URL = (
    '/processes/templates/pre_validated_method'
    '/forms/submission_pre_validated_v1'
)
EDITED_FIELDS = [
    {
        'field_key': 'method_title',
        'label': 'Nome do método',
        'field_type': 'text',
        'is_required': True,
        'order_index': 1,
    },
    {
        'field_key': 'funding_source',
        'label': 'Fonte de financiamento',
        'field_type': 'text',
        'order_index': 2,
    },
]


def _labels(fields):
    return {field['field_key']: field['label'] for field in fields}


@pytest.mark.asyncio
async def test_edicao_do_formulario_sobrevive_ao_deploy_e_chega_ao_proponente(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. A administradora entra e edita o formulário de submissão.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.put(FORM_URL, json={'fields': EDITED_FIELDS})
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['version'] == 2  # noqa: PLR2004

    # 2. Um novo deploy roda o bootstrap dos templates, como faz o
    # entrypoint da API a cada início.
    await bootstrap_all_templates(session)

    # 3. A administradora abre o formulário e vê a edição intacta.
    response = client.get(FORM_URL)
    assert response.status_code == HTTPStatus.OK, response.text
    form = response.json()
    assert form['version'] == 2  # noqa: PLR2004
    assert _labels(form['fields']) == _labels(EDITED_FIELDS)
    log_out(client)

    # 4. O proponente cria uma submissão do Método Novo.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Ensaio'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    process_id = response.json()['id']

    # 5. O formulário da submissão tem o rótulo e o campo do editor.
    response = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert _labels(response.json()['fields']) == _labels(EDITED_FIELDS)
