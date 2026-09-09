"""Script de carga para usuários e atribuições de perfis RBAC."""

import asyncio

from scripts.seeds.common import (
    ensure_admin_profile,
    ensure_profile_by_name,
    get_or_create_user,
    get_session,
)


async def run_seed_users() -> None:
    async with get_session() as session:
        # 1. Usuário Administrador
        admin, _ = await get_or_create_user(
            session,
            username='admin',
            email='admin@bracvam.fiocruz.br',
            full_name='Administrador do Sistema BraCVAM',
            password='Admin@123456',
        )
        await ensure_admin_profile(session, admin.id)

        # 2. Usuário Proponente
        proponent, _ = await get_or_create_user(
            session,
            username='proponent_user',
            email='proponente@laboratorio.com.br',
            full_name='Dra. Helena Proponente',
            password='Proponent@123456',
        )
        await ensure_profile_by_name(session, proponent.id, 'Proponente')

        # 3. Usuário Avaliador de Triagem
        evaluator, _ = await get_or_create_user(
            session,
            username='triage_evaluator',
            email='avaliador@bracvam.fiocruz.br',
            full_name='Dr. Roberto Avaliador',
            password='Triage@123456',
        )
        await ensure_profile_by_name(session, evaluator.id, 'Revisor')

        # 4. Usuários para consulta e teste de filtros
        sample_users = [
            (
                'carlos_pesquisador',
                'carlos@fiocruz.br',
                'Dr. Carlos Eduardo',
                'Carlos@123456',
                'Laboratório Participante',
            ),
            (
                'mariana_gestora',
                'mariana@fiocruz.br',
                'Mariana Rocha',
                'Mariana@123456',
                'Grupo Gestor',
            ),
            (
                'beatriz_estudo',
                'beatriz@fiocruz.br',
                'Beatriz Lima',
                'Beatriz@123456',
                'Gerente do Estudo',
            ),
        ]

        for uname, uemail, ufname, upass, uprofile in sample_users:
            u, _ = await get_or_create_user(
                session, uname, uemail, ufname, upass
            )
            if uprofile:
                await ensure_profile_by_name(session, u.id, uprofile)

        await session.commit()
        print('✓ Seed de Usuários e RBAC concluído com sucesso.')


def main() -> None:
    asyncio.run(run_seed_users())


if __name__ == '__main__':
    main()
