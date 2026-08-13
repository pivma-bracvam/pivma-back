from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.profiles import RFC_9106_LOW_MEMORY

password_hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
ACCESS_TOKEN_TTL = timedelta(hours=8)
DUMMY_PASSWORD_HASH = password_hasher.hash(
    'invalid-login-password-used-only-for-timing'
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_access_token(
    user_id: UUID,
    secret_key: str,
    *,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    return jwt.encode(
        {
            'sub': str(user_id),
            'iat': issued_at,
            'exp': issued_at + ACCESS_TOKEN_TTL,
        },
        secret_key,
        algorithm='HS256',
    )


def decode_access_token(token: str, secret_key: str) -> UUID:
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=['HS256'],
        options={'require': ['sub', 'iat', 'exp']},
    )
    try:
        return UUID(payload['sub'])
    except (TypeError, ValueError):
        raise jwt.InvalidTokenError('Invalid subject') from None
