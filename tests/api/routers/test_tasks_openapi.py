"""Spec 032 - documentação do envelope e das referências no OpenAPI."""

from pivma import app


def _schemas():
    return app.openapi()['components']['schemas']


def _resolve(ref):
    return _schemas()[ref['$ref'].rsplit('/', 1)[-1]]


def test_openapi_task_list_is_envelope():
    operation = app.openapi()['paths']['/tasks']['get']
    content = operation['responses']['200']['content']['application/json']
    envelope = _resolve(content['schema'])

    assert envelope['type'] == 'object'
    assert set(envelope['required']) == {
        'data',
        'pagination',
        'filters_applied',
        'sort',
    }
    assert {'facets', 'summary'} <= set(envelope['properties'])
    items = envelope['properties']['data']['items']
    assert items['$ref'].endswith('/TaskSummary')


def test_openapi_reference_fields_have_descriptions():
    for name in ('ProcessRef', 'PhaseRef'):
        for field, spec in _schemas()[name]['properties'].items():
            assert spec.get('description'), f'{name}.{field} sem descrição'
