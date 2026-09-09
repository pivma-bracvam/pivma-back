# ruff: noqa
import asyncio
from datetime import datetime, timezone
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Ajustar PYTHONPATH para importar pivma
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src'))
)

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.authorization import (
    ADMINISTRATIVE_PERMISSIONS,
    ADMINISTRATOR_SYSTEM_KEY,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    ActivityInstance,
    ActivityRun,
    FormField,
    FormInstance,
    FormTemplate,
    FormValue,
    Permission,
    Phase,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
    UserAccessProfile,
)
from pivma.core.process_engine import instantiate_process
from pivma.core.security import create_access_token, hash_password
from pivma.core.settings import Settings


async def seed():
    settings = Settings()
    engine = create_async_engine(settings.DATABASE_URL)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        print('[*] 1. Sincronizando templates declarativos...')
        await bootstrap_all_templates(session)

        print('[*] 2. Configurando perfil de Administrador e Permissões...')
        # Garantir permissões administrativas
        for code in sorted(ADMINISTRATIVE_PERMISSIONS):
            stmt = select(Permission).where(Permission.code == code)
            perm = (await session.execute(stmt)).scalar_one_or_none()
            if not perm:
                perm = Permission(code=code, description=f'Permissão {code}')
                session.add(perm)
        await session.flush()

        # Garantir perfil administrator
        prof_stmt = select(AccessProfile).where(
            AccessProfile.system_key == ADMINISTRATOR_SYSTEM_KEY
        )
        profile = (await session.execute(prof_stmt)).scalar_one_or_none()
        if not profile:
            profile = AccessProfile(
                system_key=ADMINISTRATOR_SYSTEM_KEY,
                name='Administrador',
                description='Perfil completo de administração',
            )
            session.add(profile)
            await session.flush()

        # Associar permissões ao perfil
        for code in sorted(ADMINISTRATIVE_PERMISSIONS):
            p_stmt = select(Permission).where(Permission.code == code)
            perm = (await session.execute(p_stmt)).scalar_one()

            app_stmt = select(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == profile.id,
                AccessProfilePermission.permission_id == perm.id,
            )
            if not (await session.execute(app_stmt)).scalar_one_or_none():
                session.add(
                    AccessProfilePermission(
                        profile_id=profile.id, permission_id=perm.id
                    )
                )

        print('[*] 3. Configurando usuário administrador de teste...')
        admin_email = 'admin@pivma.local'
        user_stmt = select(User).where(
            (User.username == 'admin') | (User.email == admin_email)
        )
        admin_user = (await session.execute(user_stmt)).scalars().first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email=admin_email,
                password_hash=hash_password('Admin123!'),
                full_name='Administrador do Sistema',
            )
            session.add(admin_user)
            await session.flush()
        else:
            admin_user.password_hash = hash_password('Admin123!')
            await session.flush()

        # Vincular perfil ao admin
        uap_stmt = select(UserAccessProfile).where(
            UserAccessProfile.user_id == admin_user.id,
            UserAccessProfile.profile_id == profile.id,
        )
        if not (await session.execute(uap_stmt)).scalar_one_or_none():
            session.add(
                UserAccessProfile(user_id=admin_user.id, profile_id=profile.id)
            )

        print(
            "[*] 4. Habilitando flag de IA no campo 'scientific_justification'..."
        )
        field_stmt = select(FormField).where(
            FormField.field_key == 'scientific_justification',
            FormField.deleted_at.is_(None),
        )
        field_res = (await session.execute(field_stmt)).scalars().all()
        for f in field_res:
            f.ai_evaluation_enabled = True
            f.ai_context_instructions = 'Verificar justificativa científica e ausência de modelo animal correspondente.'

        print(
            '[*] 5. Provisionando instância de formulário para demonstração...'
        )
        ptv_stmt = (
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(
                ProcessTemplate.key == 'full_validation',
                ProcessTemplateVersion.deleted_at.is_(None),
            )
            .order_by(ProcessTemplateVersion.version_number.desc())
        )
        ptv = (await session.execute(ptv_stmt)).scalars().first()

        proc_title = 'Proposta Piloto - Validação de Irritação Cutânea'
        proc_stmt = select(ProcessInstance).where(
            ProcessInstance.title == proc_title
        )
        proc = (await session.execute(proc_stmt)).scalars().first()
        if not proc and ptv:
            proc = await instantiate_process(
                session,
                template_version=ptv,
                title=proc_title,
                creator_user_id=admin_user.id,
            )
            await session.refresh(proc)

        proc_id = proc.id
        fi_stmt = (
            select(FormInstance)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == proc_id)
        )
        form_inst = (await session.execute(fi_stmt)).scalars().first()

        if form_inst and field_res:
            val_stmt = select(FormValue).where(
                FormValue.form_instance_id == form_inst.id,
                FormValue.form_field_id == field_res[0].id,
            )
            val = (await session.execute(val_stmt)).scalars().first()
            if not val:
                val = FormValue(
                    form_instance_id=form_inst.id,
                    form_field_id=field_res[0].id,
                    text_value=(
                        'O presente estudo propõe a validação de modelo baseado em epiderme humana reconstruída '
                        '(RhE) como alternativa ao ensaio de Draize em coelhos para avaliação de corrosão e irritação cutânea.'
                    ),
                )
                session.add(val)

        await session.commit()

        # Gerar JWT token para o admin
        token = create_access_token(admin_user.id, settings.JWT_SECRET_KEY)

        print(
            '\n====================================================================='
        )
        print('  SEED CONCLUÍDO COM SUCESSO PARA A DEMONSTRAÇÃO (AGENTS.md)!')
        print(
            '====================================================================='
        )
        print(f'  Usuário Admin:      {admin_email}')
        print(f'  Senha Admin:        Admin123!')
        print(f'  Form Instance ID:   {form_inst.id}')
        print(f'  Token JWT Admin:    {token}')
        print(
            '---------------------------------------------------------------------'
        )
        print('  Catálogo de Demos:  http://127.0.0.1:8000/demos/index.html')
        print(
            '  Módulo 1 (Geral):   http://127.0.0.1:8000/demos/operational-index/index.html'
        )
        print(
            '  Módulo 2 (IA):      http://127.0.0.1:8000/demos/ai-pipeline/index.html'
        )
        print(
            '=====================================================================\n'
        )

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(seed())
