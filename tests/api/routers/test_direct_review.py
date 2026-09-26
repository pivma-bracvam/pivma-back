"""API — a intervenção direta virou escolha da revisão do retorno (Spec 030).

Os comportamentos da antiga `POST /processes/{id}/submission/direct-review`
(Spec 013, US3) agora são cobertos pela escolha `CONTEST_AI` em
`tests/api/routers/test_return_review.py`.
"""

from http import HTTPStatus
from uuid import uuid4

import pytest

from tests.api.routers.test_rbac_router import authenticate

ROUTE = '/processes/{id}/submission/direct-review'


@pytest.mark.asyncio
async def test_direct_review_route_is_removed(client, user):
    authenticate(client, user)

    response = client.post(
        ROUTE.format(id=uuid4()),
        json={'justification': 'Discordo da IA.'},
        headers={'Origin': 'https://testserver'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert ROUTE not in client.get('/openapi.json').json()['paths']
