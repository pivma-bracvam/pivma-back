# ruff: noqa: PLR2004
"""Ativação, conclusão e regra de conclusão por laboratório (Spec 036, US1)."""

import pytest

from tests.factories.laboratory_run_factory import (
    activity,
    frozen_lab_process,
)


@pytest.mark.asyncio
async def test_instantiation_copies_execution_scope_and_custody(session):
    ctx = await frozen_lab_process(session, freeze=False)

    receipt = await activity(session, ctx.process_id, 'receipt')
    material_return = await activity(
        session, ctx.process_id, 'material_return'
    )
    statistics = await activity(session, ctx.process_id, 'statistics')

    assert (receipt.execution_scope, receipt.is_custody) == (
        'per_laboratory',
        False,
    )
    assert (material_return.execution_scope, material_return.is_custody) == (
        'per_laboratory',
        True,
    )
    assert (statistics.execution_scope, statistics.is_custody) == (
        'process',
        False,
    )
