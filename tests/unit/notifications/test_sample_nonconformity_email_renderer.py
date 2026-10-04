"""Spec 040 — aviso de problema no recebimento ao Grupo de Seleção."""

import pytest

from pivma.notifications.renderers import get_renderer

PAYLOAD = {
    'process_code': 'VAL-2026-0001',
    'process_title': 'Estudo cego',
    'laboratory_name': 'Lab A',
    'blind_code': 'XR3921KM',
    'deviations': ['temperature_out_of_range', 'package_damaged'],
}


def render(payload=PAYLOAD):
    return get_renderer('sample_receipt_nonconformity_email')(payload)


def test_subject_names_the_problem_and_process():
    subject, _text, _html = render()

    assert 'recebimento de amostras' in subject
    assert 'VAL-2026-0001' in subject


@pytest.mark.parametrize('body_index', [1, 2], ids=['text', 'html'])
def test_body_has_laboratory_code_and_reasons(body_index):
    body = render()[body_index]

    assert 'Lab A' in body
    assert 'XR3921KM' in body
    assert 'temperatura fora da faixa, embalagem avariada' in body


def test_html_escapes_values():
    payload = {**PAYLOAD, 'laboratory_name': '<script>Lab</script>'}

    _subject, _text, html = render(payload)

    assert '<script>' not in html
    assert '&lt;script&gt;' in html
