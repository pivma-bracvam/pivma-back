import pytest
from sqlalchemy import func, select

from pivma.bootstrap_system import (
    ADMIN_PROFILE_ID,
    BRACVAM_PROFILE_ID,
    CANONICAL_PERMISSIONS,
    CANONICAL_PROFILES,
    sync_canonical_permissions,
    sync_canonical_profiles,
    sync_profile_permissions,
)
from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    ProcessInstance,
)


@pytest.mark.asyncio
async def test_bootstrap_system_provisions_catalog_and_is_idempotent(session):
    # 1. Primeira execução do bootstrap
    profiles = await sync_canonical_profiles(session)
    permissions = await sync_canonical_permissions(session)
    await sync_profile_permissions(session, profiles, permissions)
    await session.commit()

    # Validação dos perfis
    assert set(profiles.keys()) == {ADMINISTRATOR_SYSTEM_KEY, 'bracvam'}
    assert profiles[ADMINISTRATOR_SYSTEM_KEY].id == ADMIN_PROFILE_ID
    assert profiles['bracvam'].id == BRACVAM_PROFILE_ID

    # Validação das permissões
    canonical_codes = {p['code'] for p in CANONICAL_PERMISSIONS}
    assert set(permissions.keys()) == canonical_codes

    # Validação da composição do Administrador (todas as 12 permissões)
    admin_perms_count = await session.scalar(
        select(func.count())
        .select_from(AccessProfilePermission)
        .where(
            AccessProfilePermission.profile_id == ADMIN_PROFILE_ID,
            AccessProfilePermission.deleted_at.is_(None),
        )
    )
    assert admin_perms_count == len(CANONICAL_PERMISSIONS)

    # Validação da composição do BraCVAM (3 permissões operacionais)
    bracvam_perms = set(
        await session.scalars(
            select(Permission.code)
            .join(
                AccessProfilePermission,
                AccessProfilePermission.permission_id == Permission.id,
            )
            .where(
                AccessProfilePermission.profile_id == BRACVAM_PROFILE_ID,
                AccessProfilePermission.deleted_at.is_(None),
            )
        )
    )
    assert bracvam_perms == {
        'triage.review',
        'ai_evaluations.read',
        'ai_evaluations.manage',
    }

    # Validação de que nenhum processo é criado no bootstrap
    process_count = await session.scalar(
        select(func.count()).select_from(ProcessInstance)
    )
    assert process_count == 0

    # 2. Segunda execução (teste de idempotência)
    profiles_2 = await sync_canonical_profiles(session)
    permissions_2 = await sync_canonical_permissions(session)
    await sync_profile_permissions(session, profiles_2, permissions_2)
    await session.commit()

    # O número total de perfis e permissões deve permanecer exatamente o mesmo
    total_profiles = await session.scalar(
        select(func.count())
        .select_from(AccessProfile)
        .where(AccessProfile.deleted_at.is_(None))
    )
    total_permissions = await session.scalar(
        select(func.count()).select_from(Permission)
    )
    total_compositions = await session.scalar(
        select(func.count())
        .select_from(AccessProfilePermission)
        .where(AccessProfilePermission.deleted_at.is_(None))
    )

    assert total_profiles == len(CANONICAL_PROFILES)
    assert total_permissions == len(CANONICAL_PERMISSIONS)
    assert total_compositions == len(CANONICAL_PERMISSIONS) + 3
