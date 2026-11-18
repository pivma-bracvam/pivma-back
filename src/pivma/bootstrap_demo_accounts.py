"""Contas de demonstração do deploy de desenvolvimento (TEMPORÁRIO).

Lê ``demo_accounts.yaml`` e cria, se faltarem, a instituição, os
laboratórios, as contas, os perfis globais e os vínculos com laboratório.
Contas que já existem ficam como estão, inclusive a senha. Sem o YAML, não
faz nada: a remoção do arquivo desliga o provisionamento.
"""

from pathlib import Path

import structlog
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import (
    AccessProfile,
    Institution,
    Laboratory,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)

logger = structlog.get_logger(__name__)

DEMO_ACCOUNTS_FILE = Path(__file__).parent / 'demo_accounts.yaml'


async def _get_or_create_institution(
    session: AsyncSession, name: str
) -> Institution:
    institution = await session.scalar(
        select(Institution).where(
            func.lower(Institution.name) == name.lower(),
            Institution.deleted_at.is_(None),
        )
    )
    if institution is None:
        institution = Institution(name=name)
        session.add(institution)
        await session.flush()
    return institution


async def _get_or_create_laboratory(
    session: AsyncSession, institution: Institution, name: str
) -> Laboratory:
    laboratory = await session.scalar(
        select(Laboratory).where(
            Laboratory.institution_id == institution.id,
            func.lower(Laboratory.name) == name.lower(),
            Laboratory.deleted_at.is_(None),
        )
    )
    if laboratory is None:
        laboratory = Laboratory(institution_id=institution.id, name=name)
        session.add(laboratory)
        await session.flush()
    return laboratory


async def _get_or_create_user(session: AsyncSession, account: dict) -> User:
    username = account['username']
    user = await session.scalar(
        select(User).where(
            func.lower(User.username) == username.lower(),
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        user = User(
            username=username,
            email=f'{username}@example.com',
            full_name=account['full_name'],
            password_hash=account['password_hash'],
        )
        session.add(user)
        await session.flush()
        logger.info('Created demo account', username=username)
    return user


async def _ensure_profile(
    session: AsyncSession, user: User, profile: AccessProfile
) -> None:
    assignment = await session.scalar(
        select(UserAccessProfile).where(
            UserAccessProfile.user_id == user.id,
            UserAccessProfile.profile_id == profile.id,
            UserAccessProfile.deleted_at.is_(None),
        )
    )
    if assignment is None:
        assignment = UserAccessProfile(user_id=user.id, profile_id=profile.id)
        assignment.set_creation_audit(user.id)
        session.add(assignment)
        await session.flush()


async def _ensure_affiliation(
    session: AsyncSession, user: User, laboratory: Laboratory
) -> None:
    affiliation = await session.scalar(
        select(UserInstitutionalAffiliation).where(
            UserInstitutionalAffiliation.user_id == user.id,
            UserInstitutionalAffiliation.laboratory_id == laboratory.id,
            UserInstitutionalAffiliation.deleted_at.is_(None),
        )
    )
    if affiliation is None:
        session.add(
            UserInstitutionalAffiliation(
                user_id=user.id,
                institution_id=laboratory.institution_id,
                laboratory_id=laboratory.id,
            )
        )
        await session.flush()


async def sync_demo_accounts(
    session: AsyncSession,
    profiles: dict[str, AccessProfile],
    file_path: Path = DEMO_ACCOUNTS_FILE,
) -> None:
    if not file_path.exists():
        return
    data = yaml.safe_load(file_path.read_text(encoding='utf-8'))

    institution = await _get_or_create_institution(
        session, data['institution']
    )
    laboratories = {
        name: await _get_or_create_laboratory(session, institution, name)
        for name in data['laboratories']
    }

    for account in data['accounts']:
        user = await _get_or_create_user(session, account)
        if profile_key := account.get('profile'):
            await _ensure_profile(session, user, profiles[profile_key])
        if laboratory_name := account.get('laboratory'):
            await _ensure_affiliation(
                session, user, laboratories[laboratory_name]
            )
