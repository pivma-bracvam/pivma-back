"""Alerts prontos para os testes da caixa (Spec 047)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from pivma.core.database.models import (
    Alert,
    ProcessInstance,
    User,
    UserAccessProfile,
)
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.user_factory import UserFactory


async def make_process(session) -> ProcessInstance:
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    return process


async def make_user(session, **overrides) -> User:
    user = UserFactory(**overrides)
    session.add(user)
    await session.commit()
    return user


async def make_alert(  # noqa: PLR0913
    session,
    user: User,
    process: ProcessInstance,
    *,
    kind: str = 'task_opened',
    target_type: str = 'task',
    target_id: UUID | None = None,
    params: dict | None = None,
    read_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Alert:
    """Grava um alert. `created_at` explícito fixa a ordem da listagem."""
    if target_type != 'process' and target_id is None:
        target_id = uuid4()
    alert = Alert(
        user_id=user.id,
        kind=kind,
        target_type=target_type,
        process_instance_id=process.id,
        target_id=target_id,
        params=params
        if params is not None
        else {'process_code': process.code},
        read_at=read_at,
    )
    session.add(alert)
    await session.flush()
    if created_at is not None:
        alert.created_at = created_at
    await session.commit()
    await session.refresh(alert)
    return alert


async def alerts_for(session, user: User, kind: str | None = None) -> list:
    """Alerts gravados para o usuário, do mais antigo ao mais recente."""
    stmt = select(Alert).where(Alert.user_id == user.id)
    if kind is not None:
        stmt = stmt.where(Alert.kind == kind)
    return list(
        await session.scalars(
            stmt.order_by(Alert.created_at, Alert.id).execution_options(
                populate_existing=True
            )
        )
    )


async def same_profile_user(session, holder: User) -> User:
    """Outro usuário com o mesmo perfil global de `holder` (ex.: BraCVAM)."""
    profile_id = await session.scalar(
        select(UserAccessProfile.profile_id).where(
            UserAccessProfile.user_id == holder.id
        )
    )
    user = await make_user(session)
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile_id))
    await session.commit()
    return user
