"""Seed script for development and demo environment.

This script:
1. Bootstraps all declarative process and form templates.
2. Creates or updates demo accounts for each canonical role.
3. Bootstraps the Administrator profile.
4. Assigns appropriate RBAC profiles to demo users.
5. Bootstraps sample institutions and laboratory affiliations.
"""

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.bootstrap_rbac import bootstrap_administrator
from pivma.core.authorization import (
    ADMINISTRATOR_SYSTEM_KEY,
    active_profiles_for_user,
)
from pivma.core.database.models import (
    AccessProfile,
    Institution,
    Laboratory,
    RbacChange,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)
from pivma.core.security import hash_password
from pivma.core.settings import get_settings

DEMO_PASSWORD = "Password123!"

DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@bracvam.gov.br",
        "name": "Administrador do Sistema",
        "role_key": ADMINISTRATOR_SYSTEM_KEY,
        "is_admin": True,
    },
    {
        "username": "helena.souza",
        "email": "helena.proponente@fiocruz.br",
        "name": "Dra. Helena Souza (Proponente)",
        "role_key": "proponent",
        "is_admin": False,
    },
    {
        "username": "carlos.mendes",
        "email": "carlos.gestor@bracvam.gov.br",
        "name": "Dr. Carlos Mendes (Grupo Gestor / Triador)",
        "role_key": "management_group",
        "is_admin": False,
    },
    {
        "username": "roberto.silva",
        "email": "avaliador.adhoc@fiocruz.br",
        "name": "Dr. Roberto Silva (Avaliador Ad Hoc)",
        "role_key": "ad_hoc_evaluator",
        "is_admin": False,
    },
]


async def _get_or_create_user(
    session: AsyncSession, user_data: dict[str, Any]
) -> User:
    stmt = select(User).where(
        func.lower(User.email) == user_data["email"].lower(),
        User.deleted_at.is_(None),
    )
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            password_hash=hash_password(DEMO_PASSWORD),
        )
        session.add(user)
        await session.flush()
        print(f"  + Usuário criado: {user_data['email']}")
    else:
        print(f"  * Usuário existente: {user_data['email']}")

    return user


async def _assign_profile(
    session: AsyncSession, user: User, role_key: str, actor_id: UUID
) -> None:
    profile_stmt = select(AccessProfile).where(
        AccessProfile.system_key == role_key,
        AccessProfile.deleted_at.is_(None),
    )
    profile = (await session.execute(profile_stmt)).scalar_one_or_none()
    if not profile:
        print(f"  ! Aviso: Perfil '{role_key}' não encontrado no banco.")
        return

    existing_profiles = await active_profiles_for_user(session, user.id)
    if any(p.id == profile.id for p in existing_profiles):
        return

    assignment = UserAccessProfile(user_id=user.id, profile_id=profile.id)
    assignment.set_creation_audit(actor_id)
    session.add(assignment)
    session.add(
        RbacChange(
            action="seed.assignment_granted",
            target_type="assignment",
            target_id=assignment.id,
        )
    )
    await session.flush()
    print(f"  + Perfil '{profile.name}' atribuído a {user.email}")


async def _seed_institutions_and_labs(
    session: AsyncSession, users: dict[str, User]
) -> None:
    inst_name = "Fundação Oswaldo Cruz - Fiocruz"
    inst_stmt = select(Institution).where(
        func.lower(Institution.name) == inst_name.lower(),
        Institution.deleted_at.is_(None),
    )
    inst = (await session.execute(inst_stmt)).scalar_one_or_none()
    if inst is None:
        inst = Institution(name=inst_name)
        session.add(inst)
        await session.flush()
        print(f"  + Instituição criada: {inst_name}")

    lab_name = "Laboratório de Métodos Alternativos e Toxicologia Celular"
    lab_stmt = select(Laboratory).where(
        Laboratory.institution_id == inst.id,
        func.lower(Laboratory.name) == lab_name.lower(),
        Laboratory.deleted_at.is_(None),
    )
    lab = (await session.execute(lab_stmt)).scalar_one_or_none()
    if lab is None:
        lab = Laboratory(institution_id=inst.id, name=lab_name)
        session.add(lab)
        await session.flush()
        print(f"  + Laboratório criado: {lab_name}")

    for user in users.values():
        aff_stmt = select(UserInstitutionalAffiliation).where(
            UserInstitutionalAffiliation.user_id == user.id,
            UserInstitutionalAffiliation.institution_id == inst.id,
            UserInstitutionalAffiliation.laboratory_id == lab.id,
            UserInstitutionalAffiliation.deleted_at.is_(None),
        )
        aff = (await session.execute(aff_stmt)).scalar_one_or_none()
        if aff is None:
            aff = UserInstitutionalAffiliation(
                user_id=user.id,
                institution_id=inst.id,
                laboratory_id=lab.id,
            )
            session.add(aff)
            await session.flush()


async def seed_database() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)

    print("==========================================================")
    print("🌱 Iniciando Semeadura do Banco de Dados (pi*VMA / BraCVAM)")
    print("==========================================================")

    async with AsyncSession(engine) as session:
        print("\n1. Sincronizando templates declarativos...")
        await bootstrap_all_templates(session)
        print("   ✓ Templates sincronizados com sucesso.")

        print("\n2. Criando usuários e associando perfis de acesso...")
        user_objects: dict[str, User] = {}
        admin_user: User | None = None

        for u_data in DEMO_USERS:
            user = await _get_or_create_user(session, u_data)
            user_objects[u_data["username"]] = user
            if u_data["is_admin"]:
                admin_user = user

        if admin_user:
            try:
                await bootstrap_administrator(session, admin_user.id)
                print(f"   ✓ Administrador configurado: {admin_user.email}")
            except Exception as e:
                print(f"   * Status Admin: {e}")

            for u_data in DEMO_USERS:
                if not u_data["is_admin"] and u_data.get("role_key"):
                    await _assign_profile(
                        session,
                        user_objects[u_data["username"]],
                        u_data["role_key"],
                        actor_id=admin_user.id,
                    )

        print("\n3. Configurando vínculos institucionais...")
        await _seed_institutions_and_labs(session, user_objects)
        print("   ✓ Vínculos institucionais criados.")

        await session.commit()

    await engine.dispose()

    print("\n==========================================================")
    print("🎉 Semeadura concluída com sucesso!")
    print("==========================================================")
    print("\nContas Disponíveis (Senha para todas: Password123!):")
    for u in DEMO_USERS:
        print(f"  • {u['name']}: {u['email']}")
    print("\nProtótipos disponíveis em:")
    print("  • Hub Central: http://localhost:8000/prototypes/")
    print("  • Formulários: http://localhost:8000/prototypes/forms-and-triage/")
    print("==========================================================\n")


def main() -> None:
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
