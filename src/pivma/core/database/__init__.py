from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.orm.session import ORMExecuteState

from pivma.core.database.models import AuditMixin
from pivma.core.settings import Settings

engine = create_async_engine(Settings().DATABASE_URL)


@event.listens_for(Session, 'do_orm_execute')
def _filter_soft_deleted(execute_state: ORMExecuteState) -> None:
    """Oculta por padrão qualquer linha `AuditMixin` soft-deletada (Spec 022).

    Rede de segurança global além dos filtros manuais já existentes em
    módulos como `authorization.py`; não os substitui. Cobre apenas `SELECT`
    via ORM — `UPDATE`/`DELETE` em massa e SQL fora do ORM continuam
    dependendo de filtro manual explícito. Uma consulta administrativa que
    precise enxergar registros excluídos passa
    `execution_options(skip_soft_delete_filter=True)`.
    """
    skip_filter = execute_state.execution_options.get(
        'skip_soft_delete_filter', False
    )
    if execute_state.is_select and not skip_filter:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                AuditMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


async def get_session():  # pragma: no cover
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
