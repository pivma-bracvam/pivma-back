"""Spec 040 (FR-049) — aviso da decisão ao laboratório."""

import pytest

from pivma.notifications.renderers import get_renderer

PAYLOAD = {
    'process_code': 'VAL-2026-0001',
    'process_title': 'Estudo cego',
    'laboratory_name': 'Lab A',
    'blind_code': 'XR3921KM',
    'vial_status': 'accepted_with_caveat',
    'lab_guidance': 'Transfira para um frasco limpo.',
}


def render(payload=PAYLOAD):
    return get_renderer('sample_receipt_decision_email')(payload)


def test_subject_names_the_decision_and_process():
    subject, _text, _html = render()

    assert 'Decisão' in subject
    assert 'VAL-2026-0001' in subject


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
@pytest.mark.parametrize(
    ('status', 'label'),
    [
        ('accepted_with_caveat', 'aceito com ressalva'),
        ('replaced', 'substituído'),
        ('disqualified', 'desclassificado'),
    ],
)
def test_body_has_code_status_and_guidance(body_index, status, label):
    body = render({**PAYLOAD, 'vial_status': status})[body_index]

    assert 'Lab A' in body
    assert 'XR3921KM' in body
    assert label in body
    assert 'Transfira para um frasco limpo.' in body


def test_without_guidance_says_there_is_none():
    _subject, text, _html = render({**PAYLOAD, 'lab_guidance': None})

    assert 'Nenhuma orientação adicional.' in text


def test_html_escapes_guidance():
    payload = {**PAYLOAD, 'lab_guidance': '<script>x</script>'}

    _subject, _text, html = render(payload)

    assert '<script>' not in html
    assert '&lt;script&gt;' in html
