"""Concessões de ver/editar declaradas por atividade de template (Spec 030)."""

import pytest

from pivma.core.process_engine import ValidationError, resolve_activity_access


def test_access_defaults_to_assigned_role_for_edit_and_view():
    view, edit = resolve_activity_access({
        'key': 'x',
        'assigned_role': 'proponent',
    })

    assert edit == ['proponent']
    assert view == ['admin', 'bracvam', 'proponent']


def test_access_view_always_includes_admin_and_bracvam():
    view, edit = resolve_activity_access({
        'key': 'triage_evaluation',
        'assigned_role': 'bracvam',
        'access': {'edit': ['bracvam'], 'view': []},
    })

    assert edit == ['bracvam']
    assert view == ['admin', 'bracvam']


def test_access_edit_implies_view():
    view, _ = resolve_activity_access({
        'key': 'x',
        'assigned_role': 'group_manager',
        'access': {'edit': ['group_manager'], 'view': ['sponsor']},
    })

    assert set(view) >= {'group_manager', 'sponsor', 'admin', 'bracvam'}


def test_access_rejects_empty_edit():
    with pytest.raises(ValidationError, match='triage_evaluation'):
        resolve_activity_access({
            'key': 'triage_evaluation',
            'assigned_role': 'bracvam',
            'access': {'edit': []},
        })


def test_access_rejects_unknown_cargo():
    with pytest.raises(ValidationError, match='reviewer_x') as exc:
        resolve_activity_access({
            'key': 'proposal_submission',
            'assigned_role': 'proponent',
            'access': {'edit': ['reviewer_x']},
        })

    assert 'proposal_submission' in str(exc.value)


def test_access_result_is_deterministic_sorted():
    view, edit = resolve_activity_access({
        'key': 'x',
        'assigned_role': 'sponsor',
        'access': {
            'edit': ['sponsor', 'proponent', 'sponsor'],
            'view': ['bracvam', 'collaborator'],
        },
    })

    assert edit == ['proponent', 'sponsor']
    assert view == [
        'admin',
        'bracvam',
        'collaborator',
        'proponent',
        'sponsor',
    ]
