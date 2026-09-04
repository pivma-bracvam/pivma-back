from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from pivma.core.database.models import User
from pivma.core.security import hash_password


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('first', 'second', 'field'),
    [
        ('CaseUser', 'caseuser', 'username'),
        ('Case@Example.COM', 'case@example.com', 'email'),
    ],
)
async def test_active_user_identifiers_are_case_insensitive_unique(
    session, first, second, field
):
    base = {
        'username': 'first-user',
        'email': 'first@example.com',
        'password_hash': hash_password('First-Passphrase-2026'),
        'full_name': 'First User',
    }
    base[field] = first
    session.add(User(**base))
    await session.commit()

    duplicate = User(
        username='second-user',
        email='second@example.com',
        password_hash=hash_password('Second-Passphrase-2026'),
        full_name='Second User',
    )
    setattr(duplicate, field, second)
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('first', 'second', 'field'),
    [
        ('CaseUser', 'caseuser', 'username'),
        ('Case@Example.COM', 'case@example.com', 'email'),
    ],
)
async def test_deleted_user_identifiers_do_not_block_reuse(
    session, first, second, field
):
    base = {
        'username': 'deleted-first-user',
        'email': 'deleted-first@example.com',
        'password_hash': hash_password('First-Passphrase-2026'),
        'full_name': 'Deleted User',
    }
    base[field] = first
    existing = User(**base)
    existing.deleted_at = datetime.now()
    session.add(existing)
    await session.commit()

    reused = User(
        username='second-user',
        email='second@example.com',
        password_hash=hash_password('Second-Passphrase-2026'),
        full_name='Reused User',
    )
    setattr(reused, field, second)
    session.add(reused)

    await session.commit()

    assert reused.id is not None


@pytest.mark.asyncio
async def test_user_full_name_cannot_be_null(session):
    user = User(
        username='no-name-user',
        email='no-name@example.com',
        password_hash=hash_password('Passphrase-2026'),
        full_name=None,  # type: ignore[arg-type]
    )
    session.add(user)
    with pytest.raises(IntegrityError):
        await session.commit()


def test_user_model_requires_full_name():
    with pytest.raises(TypeError):
        User(
            username='user',
            email='user@example.com',
            password_hash='hash',
        )  # type: ignore[call-arg]
