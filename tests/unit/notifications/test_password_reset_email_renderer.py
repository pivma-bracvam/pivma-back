"""Spec 039 — mensagem de redefinição de senha por e-mail."""

import pytest

from pivma.notifications.renderers import get_renderer

PAYLOAD = {
    'reset_url': 'https://front.test/redefinir-senha/abc123',
    'expires_at': '2026-10-01T15:30:00',
}


def render(payload=PAYLOAD):
    return get_renderer('password_reset_email')(payload)


def test_password_reset_email_subject_names_the_action_and_system():
    subject, _text, _html = render()

    assert 'Redefinição de senha' in subject
    assert 'pi*VMA' in subject


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
def test_password_reset_email_contains_reset_url(body_index):
    assert PAYLOAD['reset_url'] in render()[body_index]


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
def test_password_reset_email_contains_formatted_deadline(body_index):
    assert '01/10/2026 15:30 (UTC)' in render()[body_index]


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
def test_password_reset_email_says_to_ignore_if_not_requested(body_index):
    assert 'não pediu' in render()[body_index]


def test_password_reset_email_escapes_url_in_html():
    payload = {**PAYLOAD, 'reset_url': 'https://front.test/"<x'}

    _subject, _text, html = render(payload)

    assert '"<x' not in html
    assert '&quot;&lt;x' in html
