# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_triage_field_review_flow(client, session):
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    triador = UserFactory()
    session.add_all([proponente, triador])
    await session.commit()

    # 1. Proponente creates and submits process
    authenticate(client, proponente)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Estudo de Triagem e Revisão',
        },
    )
    process_id = resp.json()['id']

    full_payload = {
        'values': {
            'method_title': 'Método para Triagem',
            'endpoint_target': 'phototoxicity',
            'scientific_justification': 'Justificativa para análise.',
            'study_protocol_file': 'protocolo.pdf',
        }
    }
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=full_payload,
    )

    # 2. Triador submits field reviews
    authenticate(client, triador)
    review_payload = {
        'reviews': [
            {
                'field_key': 'method_title',
                'status': 'CONFORME',
                'comments': 'Título claro e objetivo.',
            },
            {
                'field_key': 'scientific_justification',
                'status': 'OBSERVACAO',
                'comments': 'Necessário complementar referências.',
            },
        ]
    }
    rev_resp = client.post(
        f'/processes/{process_id}/triage/reviews',
        json=review_payload,
    )
    assert rev_resp.status_code == HTTPStatus.OK

    # 3. Verify reviews in form endpoint
    form_resp = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp.status_code == HTTPStatus.OK
    reviews = form_resp.json()['reviews']
    assert reviews['method_title']['status'] == 'CONFORME'
    assert reviews['scientific_justification']['status'] == 'OBSERVACAO'
