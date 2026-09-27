"""Formato único das respostas de erro (Spec 034).

Todo erro sai como ``{"detail": {"code", "message", "fields"?}}``: código
estável em inglês para o frontend decidir o comportamento e mensagem em
português para exibir. Nenhuma resposta repete valores enviados pelo usuário.
"""

from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException

# Código e mensagem padrão de cada status sem código específico.
GENERIC_ERRORS: dict[int, tuple[str, str]] = {
    400: ('bad_request', 'Requisição inválida.'),
    401: ('not_authenticated', 'Sessão ausente ou expirada.'),
    403: ('forbidden', 'Sem permissão para esta ação.'),
    404: ('not_found', 'Recurso não encontrado.'),
    405: ('method_not_allowed', 'Método não permitido.'),
    409: ('conflict', 'A operação conflita com o estado atual.'),
    413: ('payload_too_large', 'Conteúdo grande demais.'),
    422: ('validation_error', 'Dados inválidos.'),
    500: ('internal_error', 'Erro interno do servidor.'),
    503: ('service_unavailable', 'Serviço indisponível no momento.'),
}

# Mensagem por tipo de erro de validação do Pydantic. Os limites vêm do
# `ctx`, que é regra da API, nunca do valor enviado.
VALIDATION_MESSAGES: dict[str, str] = {
    'missing': 'Campo obrigatório.',
    'string_too_short': 'Deve ter pelo menos {min_length} caracteres.',
    'string_too_long': 'Deve ter no máximo {max_length} caracteres.',
    'too_short': 'Deve ter pelo menos {min_length} itens.',
    'too_long': 'Deve ter no máximo {max_length} itens.',
    'greater_than': 'Deve ser maior que {gt}.',
    'greater_than_equal': 'Deve ser maior ou igual a {ge}.',
    'less_than': 'Deve ser menor que {lt}.',
    'less_than_equal': 'Deve ser menor ou igual a {le}.',
    'int_parsing': 'Deve ser um número inteiro.',
    'int_type': 'Deve ser um número inteiro.',
    'float_parsing': 'Deve ser um número.',
    'float_type': 'Deve ser um número.',
    'bool_parsing': 'Deve ser verdadeiro ou falso.',
    'bool_type': 'Deve ser verdadeiro ou falso.',
    'string_type': 'Deve ser um texto.',
    'uuid_parsing': 'Deve ser um identificador válido.',
    'uuid_type': 'Deve ser um identificador válido.',
    'datetime_parsing': 'Deve ser uma data e hora válidas.',
    'datetime_from_date_parsing': 'Deve ser uma data e hora válidas.',
    'date_parsing': 'Deve ser uma data válida.',
    'date_from_datetime_parsing': 'Deve ser uma data válida.',
    'enum': 'Valor fora das opções permitidas.',
    'literal_error': 'Valor fora das opções permitidas.',
    'string_pattern_mismatch': 'Formato inválido.',
    'list_type': 'Deve ser uma lista.',
    'dict_type': 'Deve ser um objeto.',
    'model_type': 'Deve ser um objeto.',
    'model_attributes_type': 'Deve ser um objeto.',
    'extra_forbidden': 'Campo não permitido.',
    'json_invalid': 'JSON inválido.',
}
GENERIC_FIELD_MESSAGE = 'Valor inválido.'
_VALIDATOR_PREFIX = 'Value error, '
_LOCATIONS = frozenset({'body', 'query', 'path', 'header', 'cookie'})


def generic_error(status: int) -> tuple[str, str]:
    return GENERIC_ERRORS.get(
        status, (f'http_{status}', 'Não foi possível concluir a requisição.')
    )


def api_error(
    status: int, code: str, message: str, **context: Any
) -> HTTPException:
    """Erro HTTP no formato único, com contexto opcional do código."""
    return HTTPException(
        status_code=status,
        detail={'code': code, 'message': message, **context},
    )


def field_errors(errors: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Erros do Pydantic como `FieldError`, sem `input`, `ctx` nem `url`."""
    return [_field_error(error) for error in errors]


def _field_error(error: dict[str, Any]) -> dict[str, str]:
    loc = tuple(error.get('loc', ()))
    if loc and loc[0] in _LOCATIONS:
        location, path = loc[0], loc[1:]
    else:
        location, path = 'body', loc
    field = '.'.join(str(part) for part in path)
    if 'password' in path:
        # Não expõe a regra da senha nem o valor enviado (Spec 034, FR-010).
        return {
            'location': location,
            'field': field,
            'code': 'invalid',
            'message': 'Senha inválida.',
        }
    code = error.get('type', 'value_error')
    return {
        'location': location,
        'field': field,
        'code': code,
        'message': _message(code, error),
    }


def _message(code: str, error: dict[str, Any]) -> str:
    if code == 'value_error':
        msg = str(error.get('msg', ''))
        # Mensagem dos validadores do próprio projeto, escrita para o usuário.
        if msg.startswith(_VALIDATOR_PREFIX):
            return msg.removeprefix(_VALIDATOR_PREFIX)
        if 'email' in msg:
            return 'E-mail inválido.'
        return GENERIC_FIELD_MESSAGE
    template = VALIDATION_MESSAGES.get(code)
    if template is None:
        return GENERIC_FIELD_MESSAGE
    try:
        return template.format(**(error.get('ctx') or {}))
    except KeyError, IndexError:
        return GENERIC_FIELD_MESSAGE


def http_error(status: int, message: str) -> HTTPException:
    """Erro com o código genérico do status e mensagem própria."""
    return api_error(status, generic_error(status)[0], message)


def domain_error(status: int, exc: Exception) -> HTTPException:
    """Erro a partir de uma exceção de domínio: usa o `code` dela, se houver.

    A mensagem da exceção de domínio é escrita para o usuário, em português.
    """
    code = getattr(exc, 'code', None) or generic_error(status)[0]
    return api_error(status, code, str(exc))


def form_field_errors(errors) -> list[dict[str, str]]:
    """Erros de formulário dinâmico (`{field_key, code, message}`) como
    `FieldError`, no mesmo formato da validação de entrada."""
    return [
        {
            'location': 'body',
            'field': f'values.{error["field_key"]}',
            'code': error['code'],
            'message': error['message'],
        }
        for error in errors
    ]
