from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest


def test_hashing_failure_rolls_back_without_exposing_secret(
    client, session, monkeypatch
):
    def fail_hashing(password):
        raise RuntimeError('sensitive internal failure')

    monkeypatch.setattr('pivma.routers.users.hash_password', fail_hashing)
    response = client.post(
        '/users/',
        json={
            'username': 'hash.failure',
            'email': 'hash.failure@example.com',
            'password': 'Failure-Passphrase-2026',
        },
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json() == {'detail': 'Internal server error'}
    assert 'sensitive' not in response.text
    assert not session.identity_map


@pytest.mark.parametrize('method_name', ['flush', 'commit'])
def test_persistence_failure_rolls_back(
    client, session, monkeypatch, method_name
):
    async def fail_operation(*args, **kwargs):
        raise RuntimeError('sensitive persistence failure')

    rollback = AsyncMock(wraps=session.rollback)
    monkeypatch.setattr(session, method_name, fail_operation)
    monkeypatch.setattr(session, 'rollback', rollback)

    response = client.post(
        '/users/',
        json={
            'username': f'{method_name}.failure',
            'email': f'{method_name}.failure@example.com',
            'password': 'Failure-Passphrase-2026',
        },
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json() == {'detail': 'Internal server error'}
    assert 'sensitive' not in response.text
    rollback.assert_awaited()
