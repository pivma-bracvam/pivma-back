"""Referências resumidas carregadas em lote (Spec 033, research R6).

Uma consulta por tipo para a página inteira, em vez de uma por item.
Pessoas, laboratórios e instituições desativados continuam aparecendo: a
referência mostra a situação, não esconde o registro.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import Institution, Laboratory, User
from pivma.schemas import InstitutionRef, LaboratoryRef, UserRef


async def user_refs(
    session: AsyncSession, ids: Iterable[UUID | None]
) -> dict[UUID, UserRef]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = await session.execute(
        select(User.id, User.username, User.full_name)
        .where(User.id.in_(wanted))
        .execution_options(skip_soft_delete_filter=True)
    )
    return {
        row.id: UserRef(
            id=row.id, username=row.username, full_name=row.full_name
        )
        for row in rows
    }


async def laboratory_refs(
    session: AsyncSession, ids: Iterable[UUID | None]
) -> dict[UUID, LaboratoryRef]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = await session.execute(
        select(Laboratory, Institution)
        .join(Institution, Institution.id == Laboratory.institution_id)
        .where(Laboratory.id.in_(wanted))
        .execution_options(skip_soft_delete_filter=True)
    )
    return {
        laboratory.id: laboratory_ref(laboratory, institution)
        for laboratory, institution in rows
    }


def institution_ref(institution: Institution) -> InstitutionRef:
    return InstitutionRef(
        id=institution.id,
        name=institution.name,
        active=institution.deleted_at is None,
    )


def laboratory_ref(
    laboratory: Laboratory, institution: Institution
) -> LaboratoryRef:
    return LaboratoryRef(
        id=laboratory.id,
        name=laboratory.name,
        active=laboratory.deleted_at is None,
        institution=institution_ref(institution),
    )
