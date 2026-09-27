"""Handlers de erro do app (Spec 034).

Garantem o formato único ``{"detail": {"code", "message", "fields"?}}`` em
qualquer resposta de erro, inclusive as do próprio framework (rota
inexistente, método não permitido) e as exceções não tratadas.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pivma.core.errors import field_errors, generic_error

logger = logging.getLogger(__name__)

_FRAMEWORK_DETAILS = frozenset({'Not Found', 'Method Not Allowed'})


def _error_body(status: int, detail) -> dict:
    code, message = generic_error(status)
    if isinstance(detail, dict) and 'code' in detail:
        return {'detail': {'message': message, **detail}}
    if isinstance(detail, str) and detail:
        # Texto livre que escapou da migração: formato garantido, com o
        # código genérico do status (Spec 034, R1).
        return {'detail': {'code': code, 'message': detail}}
    return {'detail': {'code': code, 'message': message}}


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    status = exc.status_code
    detail = exc.detail
    # 404/405 do roteamento chegam com o texto padrão do framework.
    if isinstance(detail, str) and detail in _FRAMEWORK_DETAILS:
        detail = None
    return JSONResponse(
        status_code=status,
        content=_error_body(status, detail),
        headers=getattr(exc, 'headers', None),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    code, message = generic_error(422)
    return JSONResponse(
        status_code=422,
        content={
            'detail': {
                'code': code,
                'message': message,
                'fields': field_errors(exc.errors()),
            }
        },
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        'unhandled error method=%s path=%s', request.method, request.url.path
    )
    return JSONResponse(status_code=500, content=_error_body(500, None))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(
        RequestValidationError, _validation_exception_handler
    )
    app.add_exception_handler(Exception, _unhandled_exception_handler)


_VALIDATION_SCHEMAS = ('HTTPValidationError', 'ValidationError')
_ERROR_REF = '#/components/schemas/ErrorResponse'


def install_openapi(app: FastAPI) -> None:
    """Documenta o formato único de erro no OpenAPI (Spec 034, R5).

    O FastAPI injeta `HTTPValidationError` na resposta `422` de toda rota
    com parâmetros; aqui essas respostas passam a apontar para
    `ErrorResponse`. O resultado fica em `app.openapi_schema` (gerado uma vez).
    """
    from pivma.schemas import ErrorResponse  # noqa: PLC0415

    original = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = original()
        components = schema.setdefault('components', {}).setdefault(
            'schemas', {}
        )
        error_schema = ErrorResponse.model_json_schema(
            ref_template='#/components/schemas/{model}'
        )
        components.update(error_schema.pop('$defs', {}))
        components['ErrorResponse'] = error_schema
        for name in _VALIDATION_SCHEMAS:
            components.pop(name, None)
        for operations in schema.get('paths', {}).values():
            for operation in operations.values():
                response = operation.get('responses', {}).get('422')
                if response is not None:
                    response['content'] = {
                        'application/json': {'schema': {'$ref': _ERROR_REF}}
                    }
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
