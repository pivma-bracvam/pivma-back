"""Spec 034, US3 - schema de erro documentado no OpenAPI."""

from pivma import app


def _spec():
    return app.openapi()


def test_error_schemas_documented():
    schemas = _spec()['components']['schemas']

    for name in ('ErrorResponse', 'ErrorDetail', 'FieldError'):
        for field, spec in schemas[name]['properties'].items():
            assert spec.get('description'), f'{name}.{field} sem descrição'


def test_validation_responses_point_to_error_response():
    spec = _spec()

    for path, operations in spec['paths'].items():
        for method, operation in operations.items():
            response = operation.get('responses', {}).get('422')
            if response is None:
                continue
            schema = response['content']['application/json']['schema']
            assert schema['$ref'] == '#/components/schemas/ErrorResponse', (
                method,
                path,
            )
    assert 'HTTPValidationError' not in spec['components']['schemas']
    assert 'ValidationError' not in spec['components']['schemas']


def test_openapi_is_cached():
    assert app.openapi() is app.openapi()
