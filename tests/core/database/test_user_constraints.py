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
    }
    base[field] = first
    session.add(User(**base))
    await session.commit()

    duplicate = User(
        username='second-user',
        email='second@example.com',
        password_hash=hash_password('Second-Passphrase-2026'),
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
    )
    setattr(reused, field, second)
    session.add(reused)

    await session.commit()

    assert reused.id is not None
