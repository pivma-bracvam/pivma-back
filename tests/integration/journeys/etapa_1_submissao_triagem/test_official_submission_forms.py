"""Jornada: o proponente preenche o formulário oficial do BraCVAM.

Ator: proponente. Objetivo: enviar a proposta em qualquer tipo de submissão.
Estado inicial: ambiente recém-provisionado.
Passos: (1) abre uma submissão e vê o formulário por seções; (2) tenta enviar
só com o nome do método e recebe a recusa; (3) preenche os obrigatórios e
envia; (4) vê a proposta enviada, com os campos opcionais em branco.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.submission_factory import submission_values
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


@pytest.mark.parametrize(
    ('template_key', 'field_count'),
    [
        ('pre_validated_method', 56),
        ('validated_method_dossier', 64),
        ('scope_extension', 56),
        ('me_too_validation', 56),
    ],
)
@pytest.mark.asyncio
async def test_proponent_fills_required_fields_and_sends_the_proposal(
    client, session, template_key, field_count
):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    # 1. Abre a submissão e vê o formulário organizado por seções.
    created = client.post(
        '/processes',
        json={'template_key': template_key, 'title': 'Ensaio 3T3 NRU'},
        headers=ORIGIN,
    )
    assert created.status_code == HTTPStatus.CREATED
    form_url = (
        f'/processes/{created.json()["id"]}'
        '/activities/proposal_submission/form'
    )
    form = client.get(form_url).json()
    assert len(form['fields']) == field_count
    assert form['fields'][0]['section'] == '1. Identificação do Proponente'

    # 2. Só com o nome do método, o envio é recusado.
    refused = client.post(
        form_url,
        json={'values': {'method_title': 'Ensaio 3T3 NRU'}},
        headers=ORIGIN,
    )
    assert refused.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert 'institution_name' in refused.text
    assert client.get(form_url).json()['is_submitted'] is False

    # 3. Com os obrigatórios preenchidos, o envio passa.
    sent = client.post(
        form_url,
        json={'values': submission_values('Ensaio 3T3 NRU')},
        headers=ORIGIN,
    )
    assert sent.status_code == HTTPStatus.OK, sent.text

    # 4. A proposta fica enviada, sem exigir os campos opcionais.
    final = client.get(form_url).json()
    assert final['is_submitted'] is True
    assert final['values']['method_title'] == 'Ensaio 3T3 NRU'
