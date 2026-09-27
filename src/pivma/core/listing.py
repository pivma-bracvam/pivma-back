"""Padrão de listagem da API (Spec 032): cálculo da paginação por página."""

from math import ceil

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
