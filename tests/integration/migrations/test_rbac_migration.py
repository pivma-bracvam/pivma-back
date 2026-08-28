# ruff: noqa: F401, F811, I001

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_rbac_migration_seeds_catalog_and_downgrades(
    migration_database,
):
    await run_migration('head')

    async with migration_database.connect() as connection:
        profile_names = set(
            await connection.scalars(
                sa.text('SELECT name FROM access_profiles')
            )
        )
        permission_count = await connection.scalar(
            sa.text('SELECT count(*) FROM permissions')
        )
        composition_count = await connection.scalar(
            sa.text('SELECT count(*) FROM access_profile_permissions')
        )

        non_admin_compositions = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions app '
                'JOIN access_profiles ap ON ap.id = app.profile_id '
                "WHERE ap.system_key <> 'administrator'"
            )
        )

    assert profile_names == {
        'Proponente',
        'Grupo Gestor',
        'Gerente do Estudo',
        'Laboratório Participante',
        'Avaliador Ad Hoc',
        'Revisor',
        'Especialista',
        'Analista Estatístico',
        'Administrador',
    }
    assert (permission_count, composition_count, non_admin_compositions) == (
        7,
        7,
        0,
    )

    await run_downgrade('2d7f9a4c6b81')
    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
    assert 'users' in tables
    assert 'access_profiles' not in tables
