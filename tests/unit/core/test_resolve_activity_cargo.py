"""Spec 029 - guarda da validação de cargo de atividade (US2, cenário 3).

A Spec 029 edita o docstring de `_resolve_activity_cargo`; estes testes
garantem que a validação de `assigned_role` do template não muda.
"""

import pytest

from pivma.core.process_engine import (
    ValidationError,
    _resolve_activity_cargo,  # noqa: PLC2701
)


def test_unknown_assigned_role_raises_validation_error():
    with pytest.raises(ValidationError, match='Cargo de atividade inválido'):
        _resolve_activity_cargo({'assigned_role': 'cargo_inexistente'})


def test_missing_assigned_role_defaults_to_proponent():
    assert _resolve_activity_cargo({}) == 'proponent'


def test_global_cargo_is_accepted():
    assert _resolve_activity_cargo({'assigned_role': 'bracvam'}) == 'bracvam'
