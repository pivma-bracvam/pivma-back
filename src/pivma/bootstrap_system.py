"""Bootstrap canônico e idempotente do baseline de produção da PIVMA.

Executado automaticamente no container pelo ``entrypoint.sh`` após as
migrações DDL. Provisiona:
1. Perfis de acesso globais ativos (Administrator e BraCVAM).
2. Catálogo canônico de permissões da plataforma.
3. Associação canônica de permissões aos perfis.
4. Sincronização dos templates canônicos de processos e formulários (Fase 1).
5. (Opcional) Conta inicial de Administrador configurada por variáveis de
   ambiente.

Nenhum dado fictício, processo de teste ou avaliação simulada é criado aqui.
"""

import asyncio
import os
import sys
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    User,
    UserAccessProfile,
)
from pivma.core.security import hash_password
from pivma.core.settings import get_settings

logger = structlog.get_logger(__name__)

# IDs canônicos determinísticos para o baseline de governança
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
BRACVAM_PROFILE_ID = UUID('00000000-0000-0000-0000-00000000000a')

CANONICAL_PROFILES = [
    {
        'id': ADMIN_PROFILE_ID,
        'system_key': ADMINISTRATOR_SYSTEM_KEY,
        'name': 'Administrador',
        'description': (
            'Administrador do sistema com acesso irrestrito a governança, '
            'catálogo e usuários.'
        ),
    },
    {
        'id': BRACVAM_PROFILE_ID,
        'system_key': 'bracvam',
        'name': 'BraCVAM',
        'description': (
            'Equipe do BraCVAM: coordena submissões, conduz triagem e '
            'gerencia métodos candidatos.'
        ),
    },
]

CANONICAL_PERMISSIONS = [
    {
        'id': UUID('00000000-0000-0000-0000-000000000101'),
        'code': 'rbac.read',
        'description': 'Consultar o estado do RBAC.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000102'),
        'code': 'rbac.profiles.manage',
        'description': 'Gerir perfis e suas permissões.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000103'),
        'code': 'rbac.assignments.manage',
        'description': 'Gerir atribuições de perfis.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000104'),
        'code': 'institutional.read',
        'description': 'Consultar catálogo institucional e afiliações.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000105'),
        'code': 'institutional.catalogs.manage',
        'description': 'Gerir catálogo de instituições e laboratórios.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000106'),
        'code': 'institutional.affiliations.manage',
        'description': 'Gerir afiliações institucionais de usuários.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000107'),
        'code': 'process.participants.manage',
        'description': 'Gerir designações de participantes do processo.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000108'),
        'code': 'users.read',
        'description': 'Consultar contas de usuários.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-000000000109'),
        'code': 'users.manage',
        'description': 'Atualizar dados administrativos de usuários.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-00000000010a'),
        'code': 'ai_evaluations.read',
        'description': 'Consultar avaliações por IA e seus resultados.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-00000000010b'),
        'code': 'ai_evaluations.manage',
        'description': 'Configurar e publicar avaliações por IA.',
    },
    {
        'id': UUID('00000000-0000-0000-0000-00000000010c'),
        'code': 'triage.review',
        'description': (
            'Conduzir a triagem: parecer de campo, decisão, e ver/comentar '
            'a pré-avaliação por IA.'
        ),
    },
]

# Regras de associação perfil -> códigos de permissão
PROFILE_PERMISSION_MAPPINGS: dict[str, list[str]] = {
    # Administrador tem acesso a todas as permissões
    ADMINISTRATOR_SYSTEM_KEY: [p['code'] for p in CANONICAL_PERMISSIONS],
    # BraCVAM tem acesso às permissões operacionais de triagem e IA
    'bracvam': [
        'triage.review',
        'ai_evaluations.read',
        'ai_evaluations.manage',
    ],
}


async def sync_canonical_profiles(
    session: AsyncSession,
) -> dict[str, AccessProfile]:
    """Garante a existência dos perfis canônicos de acesso."""
    profiles_by_key: dict[str, AccessProfile] = {}
    for data in CANONICAL_PROFILES:
        stmt = select(AccessProfile).where(
            AccessProfile.system_key == data['system_key']
        )
        profile = (await session.execute(stmt)).scalar_one_or_none()
        if profile is None:
            profile = AccessProfile(
                system_key=data['system_key'],
                name=data['name'],
                description=data['description'],
            )
            profile.id = data['id']
            session.add(profile)
            await session.flush()
            logger.info(
                'Created canonical access profile',
                system_key=data['system_key'],
            )
        else:
            if profile.deleted_at is not None:
                profile.deleted_at = None
            profile.name = data['name']
            profile.description = data['description']
        profiles_by_key[data['system_key']] = profile
    return profiles_by_key


async def sync_canonical_permissions(
    session: AsyncSession,
) -> dict[str, Permission]:
    """Garante a existência de todas as permissões canônicas do catálogo."""
    permissions_by_code: dict[str, Permission] = {}
    for data in CANONICAL_PERMISSIONS:
        stmt = select(Permission).where(Permission.code == data['code'])
        permission = (await session.execute(stmt)).scalar_one_or_none()
        if permission is None:
            permission = Permission(
                code=data['code'],
                description=data['description'],
            )
            permission.id = data['id']
            session.add(permission)
            await session.flush()
            logger.info('Created canonical permission', code=data['code'])
        else:
            permission.description = data['description']
        permissions_by_code[data['code']] = permission
    return permissions_by_code


async def sync_profile_permissions(
    session: AsyncSession,
    profiles: dict[str, AccessProfile],
    permissions: dict[str, Permission],
) -> None:
    """Garante a composição correta entre perfis e permissões."""
    for system_key, codes in PROFILE_PERMISSION_MAPPINGS.items():
        profile = profiles.get(system_key)
        if profile is None:
            continue

        for code in codes:
            permission = permissions.get(code)
            if permission is None:
                continue

            stmt = select(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == profile.id,
                AccessProfilePermission.permission_id == permission.id,
                AccessProfilePermission.deleted_at.is_(None),
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                comp = AccessProfilePermission(
                    profile_id=profile.id,
                    permission_id=permission.id,
                )
                session.add(comp)
                await session.flush()


async def sync_initial_administrator(
    session: AsyncSession, admin_profile: AccessProfile
) -> None:
    """Cria a conta do primeiro administrador se configurada por

    variáveis de ambiente.
    """
    admin_email = os.getenv('INITIAL_ADMIN_EMAIL')
    admin_password = os.getenv('INITIAL_ADMIN_PASSWORD')
    admin_username = os.getenv('INITIAL_ADMIN_USERNAME', 'admin')

    if not admin_email or not admin_password:
        return

    stmt = select(User).where(
        func.lower(User.email) == admin_email.lower(),
        User.deleted_at.is_(None),
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(
            username=admin_username,
            email=admin_email,
            full_name='Administrador Inicial da Plataforma',
            password_hash=hash_password(admin_password),
        )
        session.add(user)
        await session.flush()
        logger.info(
            'Created initial administrator user',
            username=admin_username,
            email=admin_email,
        )

    assign_stmt = select(UserAccessProfile).where(
        UserAccessProfile.user_id == user.id,
        UserAccessProfile.profile_id == admin_profile.id,
        UserAccessProfile.deleted_at.is_(None),
    )
    assignment = (await session.execute(assign_stmt)).scalar_one_or_none()
    if assignment is None:
        new_assign = UserAccessProfile(
            user_id=user.id, profile_id=admin_profile.id
        )
        new_assign.set_creation_audit(user.id)
        session.add(new_assign)
        await session.flush()
        logger.info(
            'Assigned administrator profile to initial user',
            user_id=str(user.id),
        )


async def run_system_bootstrap() -> None:
    """Executa o ciclo completo de provisionamento de produção."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    logger.info('Starting system production bootstrap...')
    async with session_factory() as session:
        # 1. Perfis oficiais
        profiles = await sync_canonical_profiles(session)

        # 2. Catálogo de permissões
        permissions = await sync_canonical_permissions(session)

        # 3. Composição perfil-permissão
        await sync_profile_permissions(session, profiles, permissions)
        await session.commit()

        # 4. Sincronização dos templates canônicos da Fase 1 (YAMLs)
        logger.info('Syncing standard process templates (Fase 1)...')
        await bootstrap_all_templates(session)

        # 5. Administrador inicial (se configurado)
        if ADMINISTRATOR_SYSTEM_KEY in profiles:
            await sync_initial_administrator(
                session, profiles[ADMINISTRATOR_SYSTEM_KEY]
            )
            await session.commit()

    await engine.dispose()
    logger.info('System production bootstrap completed successfully!')


def main() -> None:
    try:
        asyncio.run(run_system_bootstrap())
    except Exception as exc:
        logger.error('System bootstrap failed', error=str(exc))
        sys.exit(1)


if __name__ == '__main__':
    main()
