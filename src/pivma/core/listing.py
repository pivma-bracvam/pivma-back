"""Padrão de listagem da API (Specs 032 e 033): paginação por página."""

from math import ceil
from typing import Annotated

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.schemas import Pagination


def build_pagination(page: int, per_page: int, total: int) -> Pagination:
    total_pages = ceil(total / per_page) if total else 0
    return Pagination(
        page=page,
        per_page=per_page,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1 and total_pages > 0,
    )


# Parâmetros de paginação comuns a todas as listagens (Spec 033, R3).
PageQuery = Annotated[int, Query(ge=1)]
PerPageQuery = Annotated[int, Query(ge=1, le=100)]


async def paginate_query(
    session: AsyncSession, stmt: Select, *, order_by, page: int, per_page: int
) -> tuple[list, int]:
    """Página e total de uma listagem montada numa consulta só (R2)."""
    # O total precisa das mesmas opções da consulta (ex.: ignorar o filtro
    # global de exclusão lógica em listagens de inativos).
    total = await session.scalar(
        select(func.count())
        .select_from(stmt.order_by(None).subquery())
        .execution_options(**stmt.get_execution_options())
    )
    items = await session.scalars(
        stmt.order_by(*order_by).offset((page - 1) * per_page).limit(per_page)
    )
    return list(items), total or 0


def paginate_items(items: list, page: int, per_page: int) -> tuple[list, int]:
    """Página de uma lista já filtrada em Python (R2).

    Para listagens cujo filtro de acesso roda depois da consulta: paginar
    antes dele daria totais e páginas errados.
    """
    start = (page - 1) * per_page
    return items[start : start + per_page], len(items)
