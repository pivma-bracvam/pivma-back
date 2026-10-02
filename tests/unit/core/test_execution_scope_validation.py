"""Validação de `execution_scope` e `custody` no template (Spec 036, US6)."""

import copy

import pytest

from pivma.core.process_engine import (
    ValidationError,
    validate_execution_scopes,
)
from tests.factories.laboratory_run_factory import LAB_RUN_TEMPLATE


def _template(**changes):
    """Cópia do template de teste com mudanças na atividade `upload`."""
    data = copy.deepcopy(LAB_RUN_TEMPLATE)
    for activity in data['phases'][1]['activities']:
        if activity['key'] == 'upload':
            activity.update(changes)
    return data


def _without_scopes(data):
    for phase in data['phases']:
        for activity in phase['activities']:
            activity.pop('execution_scope', None)
            activity.pop('custody', None)
    return data


def test_template_without_new_keys_passes():
    validate_execution_scopes(_without_scopes(copy.deepcopy(LAB_RUN_TEMPLATE)))


def test_unknown_scope_is_rejected_naming_template_and_activity():
    with pytest.raises(ValidationError) as exc:
        validate_execution_scopes(_template(execution_scope='per_lab'))

    assert 'lab_run_probe' in str(exc.value)
    assert 'upload' in str(exc.value)


def test_lab_activity_without_path_to_sample_definition_is_rejected():
    data = _template(dependencies=[])

    with pytest.raises(ValidationError) as exc:
        validate_execution_scopes(data)

    assert 'upload' in str(exc.value)


def test_lab_activity_with_transitive_path_to_sample_definition_passes():
    # `lab_feedback` → `statistics` → `upload` → `receipt` → definição.
    validate_execution_scopes(copy.deepcopy(LAB_RUN_TEMPLATE))


def test_lab_activity_not_editable_by_participating_lab_is_rejected():
    data = _template(access={'edit': ['group_manager'], 'view': []})

    with pytest.raises(ValidationError) as exc:
        validate_execution_scopes(data)

    assert 'upload' in str(exc.value)


def test_custody_on_single_execution_activity_is_rejected():
    data = copy.deepcopy(LAB_RUN_TEMPLATE)
    for activity in data['phases'][1]['activities']:
        if activity['key'] == 'statistics':
            activity['custody'] = True

    with pytest.raises(ValidationError) as exc:
        validate_execution_scopes(data)

    assert 'statistics' in str(exc.value)
