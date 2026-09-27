"""Padrão de listagem (Spec 032): paginação por página e envelope."""

from pydantic import BaseModel

from pivma.core.listing import build_pagination
from pivma.schemas import ListEnvelope, SortApplied


def test_pagination_middle_page():
    pagination = build_pagination(page=2, per_page=20, total=45)

    assert pagination.total_items == 45  # noqa: PLR2004
    assert pagination.total_pages == 3  # noqa: PLR2004
    assert pagination.has_next is True
    assert pagination.has_prev is True


def test_pagination_empty():
    pagination = build_pagination(page=1, per_page=20, total=0)

    assert pagination.total_pages == 0
    assert pagination.has_next is False
    assert pagination.has_prev is False


def test_pagination_page_beyond_last():
    pagination = build_pagination(page=5, per_page=20, total=45)

    assert pagination.total_pages == 3  # noqa: PLR2004
    assert pagination.has_next is False
    assert pagination.has_prev is True


def test_pagination_exact_multiple():
    pagination = build_pagination(page=2, per_page=20, total=40)

    assert pagination.total_pages == 2  # noqa: PLR2004
    assert pagination.has_next is False


class _Item(BaseModel):
    name: str
    due_date: str | None = None


class _Filters(BaseModel):
    q: str | None = None


class _Facets(BaseModel):
    name: dict[str, int]


class _Summary(BaseModel):
    total: int


_Envelope = ListEnvelope[_Item, _Filters, _Facets, _Summary]


def _envelope(**extra):
    return _Envelope(
        data=[_Item(name='a')],
        pagination=build_pagination(page=1, per_page=20, total=1),
        filters_applied=_Filters(),
        sort=SortApplied(by='name', order='asc'),
        **extra,
    )


def test_envelope_omits_facets_and_summary_when_none():
    dumped = _envelope().model_dump(mode='json')

    assert set(dumped) == {'data', 'pagination', 'filters_applied', 'sort'}
    assert dumped['data'][0] == {'name': 'a', 'due_date': None}
    assert dumped['filters_applied'] == {'q': None}


def test_envelope_keeps_facets_and_summary_when_set():
    dumped = _envelope(
        facets=_Facets(name={'a': 1}), summary=_Summary(total=1)
    ).model_dump(mode='json')

    assert dumped['facets'] == {'name': {'a': 1}}
    assert dumped['summary'] == {'total': 1}
