from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from pivma.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

JWT_SECRET_KEY = 'test-jwt-secret-key-with-at-least-32-bytes'


def test_hash_password_uses_argon2id_and_random_salt():
    password = 'Unique-Passphrase-2026'

    first = hash_password(password)
    second = hash_password(password)

    assert first.startswith('$argon2id$')
    assert first != second
    assert password not in first
    assert verify_password(first, password)
    assert not verify_password(first, 'incorrect-password')


def test_hash_password_preserves_128_unicode_code_points():
    password = '🧪' * 128

    password_hash = hash_password(password)

    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, password[:-1])


def test_verify_password_rejects_malformed_hash():
    assert not verify_password('not-an-argon2-hash', 'password')


def test_access_token_contains_required_claims_and_round_trips_subject():
    user_id = uuid4()
    issued_at = datetime.now(UTC)

    token = create_access_token(user_id, JWT_SECRET_KEY, now=issued_at)
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=['HS256'],
        options={'verify_exp': False},
    )

    assert payload['sub'] == str(user_id)
    assert payload['iat'] == int(issued_at.timestamp())
    assert payload['exp'] == int((issued_at + timedelta(hours=8)).timestamp())
    assert set(payload) == {'sub', 'iat', 'exp'}
    assert decode_access_token(token, JWT_SECRET_KEY) == user_id


@pytest.mark.parametrize('missing_claim', ['sub', 'iat', 'exp'])
def test_access_token_rejects_missing_required_claim(missing_claim):
    now = datetime.now(UTC)
    payload = {
        'sub': str(uuid4()),
        'iat': now,
        'exp': now + timedelta(hours=8),
    }
    del payload[missing_claim]
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, JWT_SECRET_KEY)


def test_access_token_rejects_expired_token():
    token = create_access_token(
        uuid4(),
        JWT_SECRET_KEY,
        now=datetime.now(UTC) - timedelta(hours=8, seconds=1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, JWT_SECRET_KEY)


def test_access_token_rejects_tampering():
    token = create_access_token(uuid4(), JWT_SECRET_KEY)
    header, payload, signature = token.split('.')
    replacement = 'a' if signature[0] != 'a' else 'b'
    tampered_token = f'{header}.{payload}.{replacement}{signature[1:]}'

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(tampered_token, JWT_SECRET_KEY)


def test_access_token_rejects_invalid_subject():
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            'sub': 'not-a-uuid',
            'iat': now,
            'exp': now + timedelta(hours=8),
        },
        JWT_SECRET_KEY,
        algorithm='HS256',
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, JWT_SECRET_KEY)
