"""Spec 018 - classificação de coluna do Kanban (`classify_kanban_column`).

Função pura, sem banco (data-model.md, tabela de classificação).
"""

from datetime import UTC, datetime, timedelta

import pytest

from pivma.core.process_engine import (
    KANBAN_CONCLUIDO,
    KANBAN_EM_ANDAMENTO,
    KANBAN_EM_ATRASO,
    KANBAN_NAO_INICIADO,
    classify_kanban_column,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def test_blocked_without_run_is_nao_iniciado():
    assert (
        classify_kanban_column(
            activity_status='BLOCKED',
            run_started_at=None,
            sla_hours=None,
            now=NOW,
        )
        == KANBAN_NAO_INICIADO
    )


def test_completed_is_concluido_regardless_of_sla():
    assert (
        classify_kanban_column(
            activity_status='COMPLETED',
            run_started_at=NOW - timedelta(hours=1000),
            sla_hours=1,
            now=NOW,
        )
        == KANBAN_CONCLUIDO
    )


def test_in_progress_without_sla_is_em_andamento_no_matter_the_age():
    assert (
        classify_kanban_column(
            activity_status='IN_PROGRESS',
            run_started_at=NOW - timedelta(days=365),
            sla_hours=None,
            now=NOW,
        )
        == KANBAN_EM_ANDAMENTO
    )


def test_in_progress_within_sla_is_em_andamento():
    assert (
        classify_kanban_column(
            activity_status='IN_PROGRESS',
            run_started_at=NOW - timedelta(hours=10),
            sla_hours=24,
            now=NOW,
        )
        == KANBAN_EM_ANDAMENTO
    )


def test_in_progress_past_sla_is_em_atraso():
    assert (
        classify_kanban_column(
            activity_status='IN_PROGRESS',
            run_started_at=NOW - timedelta(hours=25),
            sla_hours=24,
            now=NOW,
        )
        == KANBAN_EM_ATRASO
    )


def test_ready_past_sla_is_em_atraso():
    assert (
        classify_kanban_column(
            activity_status='READY',
            run_started_at=NOW - timedelta(hours=48),
            sla_hours=24,
            now=NOW,
        )
        == KANBAN_EM_ATRASO
    )


@pytest.mark.parametrize('status', ['READY', 'IN_PROGRESS'])
def test_exactly_at_sla_boundary_is_not_yet_em_atraso(status):
    assert (
        classify_kanban_column(
            activity_status=status,
            run_started_at=NOW - timedelta(hours=24),
            sla_hours=24,
            now=NOW,
        )
        == KANBAN_EM_ANDAMENTO
    )
