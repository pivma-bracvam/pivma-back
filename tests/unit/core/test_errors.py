"""Formato único de erro (Spec 034): api_error, genéricos e campos."""

import json

import pytest

from pivma.core.errors import api_error, field_errors, generic_error


def test_api_error_builds_detail_object():
    error = api_error(404, 'not_found', 'Processo não encontrado.')

    assert error.status_code == 404  # noqa: PLR2004
    assert error.detail == {
        'code': 'not_found',
        'message': 'Processo não encontrado.',
    }


def test_api_error_keeps_context():
    error = api_error(
        422, 'missing_sds', 'Há substâncias sem SDS.', substance_ids=['a']
    )

    assert error.detail['substance_ids'] == ['a']


@pytest.mark.parametrize(
    ('status', 'code'),
    [
        (400, 'bad_request'),
        (401, 'not_authenticated'),
        (403, 'forbidden'),
        (404, 'not_found'),
        (405, 'method_not_allowed'),
        (409, 'conflict'),
        (413, 'payload_too_large'),
        (422, 'validation_error'),
        (500, 'internal_error'),
        (503, 'service_unavailable'),
    ],
)
def test_generic_error_covers_every_status(status, code):
    generic_code, message = generic_error(status)

    assert generic_code == code
    assert message


def test_generic_error_unknown_status():
    code, message = generic_error(418)

    assert code == 'http_418'
    assert message


def _error(loc, type_, msg='x', **extra):
    return {'loc': loc, 'type': type_, 'msg': msg, 'input': 'VALOR', **extra}


def test_field_errors_map_location_and_path():
    [item] = field_errors([
        _error(('body', 'values', 'method_title'), 'missing', 'Field required')
    ])

    assert item == {
        'location': 'body',
        'field': 'values.method_title',
        'code': 'missing',
        'message': 'Campo obrigatório.',
    }


def test_field_errors_never_include_input():
    items = field_errors([
        _error(('body', 'name'), 'string_too_long', ctx={'max_length': 5}),
        _error(('query', 'per_page'), 'less_than_equal', ctx={'le': 100}),
    ])

    for item in items:
        assert set(item) == {'location', 'field', 'code', 'message'}
    assert 'VALOR' not in json.dumps(items)


@pytest.mark.parametrize(
    ('type_', 'ctx', 'expected'),
    [
        ('missing', None, 'Campo obrigatório.'),
        (
            'string_too_short',
            {'min_length': 3},
            'Deve ter pelo menos 3 caracteres.',
        ),
        (
            'string_too_long',
            {'max_length': 5},
            'Deve ter no máximo 5 caracteres.',
        ),
        ('greater_than_equal', {'ge': 1}, 'Deve ser maior ou igual a 1.'),
        ('less_than_equal', {'le': 100}, 'Deve ser menor ou igual a 100.'),
        ('int_parsing', None, 'Deve ser um número inteiro.'),
        ('uuid_parsing', None, 'Deve ser um identificador válido.'),
        ('enum', None, 'Valor fora das opções permitidas.'),
        ('literal_error', None, 'Valor fora das opções permitidas.'),
        ('bool_parsing', None, 'Deve ser verdadeiro ou falso.'),
    ],
)
def test_field_errors_translate_common_types(type_, ctx, expected):
    extra = {'ctx': ctx} if ctx else {}
    [item] = field_errors([_error(('body', 'x'), type_, **extra)])

    assert item['message'] == expected


def test_field_errors_translate_email_value_error():
    [item] = field_errors([
        _error(
            ('body', 'email'),
            'value_error',
            'value is not a valid email address: An email address must '
            'have an @-sign.',
            ctx={'reason': 'An email address must have an @-sign.'},
        )
    ])

    assert item['message'] == 'E-mail inválido.'


def test_field_errors_unknown_type_uses_generic_message():
    [item] = field_errors([_error(('body', 'x'), 'algo_novo')])

    assert item['code'] == 'algo_novo'
    assert item['message'] == 'Valor inválido.'


def test_field_errors_value_error_uses_validator_message():
    [item] = field_errors([
        _error(
            ('body',), 'value_error', 'Value error, Informe ao menos um campo.'
        )
    ])

    assert not item['field']
    assert item['message'] == 'Informe ao menos um campo.'


def test_field_errors_hide_password_rule():
    [item] = field_errors([
        _error(('body', 'password'), 'string_too_short', ctx={'min_length': 8})
    ])

    assert item == {
        'location': 'body',
        'field': 'password',
        'code': 'invalid',
        'message': 'Senha inválida.',
    }


def test_field_errors_hide_current_password_rule():
    [item] = field_errors([
        _error(
            ('body', 'current_password'),
            'string_too_long',
            ctx={'max_length': 128},
        )
    ])

    assert item == {
        'location': 'body',
        'field': 'current_password',
        'code': 'invalid',
        'message': 'Senha inválida.',
    }


def test_field_errors_hide_new_password_rule():
    [item] = field_errors([
        _error(
            ('body', 'new_password'), 'string_too_short', ctx={'min_length': 8}
        )
    ])

    assert item == {
        'location': 'body',
        'field': 'new_password',
        'code': 'invalid',
        'message': 'Senha inválida.',
    }
