"""Spec 036 — mensagem do convite por e-mail (FR-012, research R12)."""

from pivma.notifications.renderers import get_renderer

PAYLOAD = {
    'invite_url': 'https://front.test/convites/abc123',
    'process_code': 'PRC-0042',
    'process_title': 'Método alternativo X',
    'role_key': 'participating_laboratory',
    'laboratory_name': 'Laboratório Beta',
    'expires_at': '2026-10-01T15:00:00',
}


def test_invite_email_has_process_role_laboratory_deadline_and_link():
    subject, text, html = get_renderer('invite_email')(PAYLOAD)

    assert 'PRC-0042' in subject
    for body in (text, html):
        assert 'PRC-0042' in body
        assert 'Método alternativo X' in body
        assert 'Laboratório Participante' in body
        assert 'Laboratório Beta' in body
        assert '01/10/2026 15:00 (UTC)' in body
        assert 'https://front.test/convites/abc123' in body


def test_invite_email_without_laboratory_omits_laboratory_line():
    payload = {**PAYLOAD, 'role_key': 'statistician', 'laboratory_name': None}

    _subject, text, html = get_renderer('invite_email')(payload)

    assert 'Estatístico' in text
    assert 'Laboratório:' not in text
    assert 'Laboratório:' not in html


def test_invite_email_escapes_values_in_html():
    payload = {**PAYLOAD, 'process_title': '<script>alert(1)</script>'}

    _subject, _text, html = get_renderer('invite_email')(payload)

    assert '<script>' not in html
    assert '&lt;script&gt;' in html
