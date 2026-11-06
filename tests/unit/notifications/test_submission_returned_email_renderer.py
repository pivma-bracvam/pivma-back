"""Spec 046 (FR-010) — aviso de devolução ao proponente."""

import pytest

from pivma.notifications.renderers import get_renderer

PAYLOAD = {
    'process_code': 'VAL-2026-0001',
    'process_title': 'Ensaio RhCE',
    'source': 'TRIAGE',
    'due_date': '2026-11-13T14:30:00',
}


def render(payload=PAYLOAD):
    return get_renderer('submission_returned_email')(payload)


def test_subject_names_return_and_process():
    subject, _text, _html = render()

    assert subject == 'Submissão devolvida — VAL-2026-0001'


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
@pytest.mark.parametrize(
    ('source', 'label'),
    [('TRIAGE', 'Triagem'), ('AI_PRE_EVALUATION', 'Pré-avaliação por IA')],
)
def test_body_has_process_origin_deadline_and_guidance(
    body_index, source, label
):
    body = render({**PAYLOAD, 'source': source})[body_index]

    assert 'VAL-2026-0001 — Ensaio RhCE' in body
    assert label in body
    assert '13/11/2026 14:30 (UTC)' in body
    assert 'Acesse a pi*VMA' in body


def test_body_omits_deadline_line_without_due_date():
    _subject, text, html = render({**PAYLOAD, 'due_date': None})

    assert 'Prazo' not in text
    assert 'Prazo' not in html


def test_html_escapes_process_title():
    payload = {**PAYLOAD, 'process_title': '<script>alert(1)</script>'}

    _subject, _text, html = render(payload)

    assert '<script>' not in html
    assert '&lt;script&gt;' in html
