"""Templates de coleta, permissão e processos vinculados (Spec 041).

O banco de teste nasce com ``create_all``, sem o catálogo de permissões:
``catalog_manager`` e ``grant_catalog_permission`` criam a linha de
``collection_templates.manage`` quando ela falta.
"""

from http import HTTPStatus
from itertools import count
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from pivma.core import sample_service
from pivma.core.authorization import COLLECTION_TEMPLATES_MANAGE
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    CollectionTemplate,
    CollectionTemplateColumn,
    Permission,
    ProcessInstance,
    User,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.conftest import _make_rbac_user
from tests.factories.sample_receipt_factory import receipt_process

ORIGIN = {'Origin': 'https://testserver'}
_sequence = count(1)


def template_payload(**overrides) -> dict:
    payload = {
        'name': 'Ensaio de citotoxicidade',
        'description': 'Leitura de viabilidade celular.',
        'min_experiments': 3,
        'min_replicates': 2,
    }
    payload.update(overrides)
    return payload


def column_payload(**overrides) -> dict:
    """Coluna `text` com chave única por chamada."""
    number = next(_sequence)
    payload = {
        'key': f'coluna_{number}',
        'label': f'Coluna {number}',
        'type': 'text',
    }
    payload.update(overrides)
    return payload


async def catalog_manager(session) -> User:
    """Usuário do perfil BraCVAM com `collection_templates.manage`."""
    return await _make_rbac_user(
        session,
        system_key='bracvam',
        name='BraCVAM',
        codes=(COLLECTION_TEMPLATES_MANAGE,),
    )


async def grant_catalog_permission(session, user: User) -> None:
    """Dá a `user` um perfil personalizado só com a permissão do catálogo."""
    permission = await session.scalar(
        select(Permission).where(
            Permission.code == COLLECTION_TEMPLATES_MANAGE
        )
    )
    if permission is None:
        permission = Permission(
            code=COLLECTION_TEMPLATES_MANAGE,
            description=f'Permission {COLLECTION_TEMPLATES_MANAGE}',
        )
        session.add(permission)
    profile = AccessProfile(
        system_key='collection_editor',
        name='Editor de templates de coleta',
        description='Editor de templates de coleta',
    )
    session.add(profile)
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()


async def collection_template(
    session, actor: User, *, columns=()
) -> CollectionTemplate:
    """Template gravado pelos modelos; `columns` são dicts de
    ``column_payload``, com posições 1, 2, ... na ordem dada."""
    data = template_payload()
    template = CollectionTemplate(
        name=data['name'],
        description=data['description'],
        min_experiments=data['min_experiments'],
        min_replicates=data['min_replicates'],
    )
    template.set_creation_audit(actor.id)
    session.add(template)
    await session.flush()
    for position, column in enumerate(columns, start=1):
        row = CollectionTemplateColumn(
            collection_template_id=template.id,
            label=column['label'],
            key=column['key'],
            column_type=column['type'],
            position=column.get('position', position),
            required=column.get('required', False),
            options=column.get('options'),
        )
        row.set_creation_audit(actor.id)
        session.add(row)
    await session.commit()
    await session.refresh(template)
    return template


async def linked_process(
    session, template_id: UUID, *, complete_definition: bool
) -> SimpleNamespace:
    """Processo de `receipt_process` vinculado ao template.

    Com `complete_definition`, conclui a definição das amostras, o que
    trava o template.
    """
    ctx = await receipt_process(session, freeze=False)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.collection_template_id = template_id
    await session.commit()
    if complete_definition:
        await sample_service.complete_sample_definition(
            session, ctx.process_id, ctx.selector.id
        )
    return ctx


# ---------------------------------------------------------------------------
# Chamadas à API
# ---------------------------------------------------------------------------


def authenticate(client, user: User) -> None:
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


def create_template(client, **overrides):
    return client.post(
        '/collection-templates',
        headers=ORIGIN,
        json=template_payload(**overrides),
    )


def add_column(client, template_id, **overrides):
    return client.post(
        f'/collection-templates/{template_id}/columns',
        headers=ORIGIN,
        json=column_payload(**overrides),
    )


def read_template(client, template_id) -> dict:
    response = client.get(f'/collection-templates/{template_id}')
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()
