# Contrato HTTP: Formato único das respostas de erro

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **incompatível** em todas as respostas de erro. Status HTTP não mudam.

## Formato

```json
{ "detail": { "code": "not_found", "message": "Processo não encontrado." } }
```

Validação:

```json
{
  "detail": {
    "code": "validation_error",
    "message": "Dados inválidos.",
    "fields": [
      { "location": "body", "field": "email", "code": "value_error", "message": "E-mail inválido." },
      { "location": "body", "field": "full_name", "code": "missing", "message": "Campo obrigatório." },
      { "location": "query", "field": "per_page", "code": "less_than_equal", "message": "Deve ser menor ou igual a 100." }
    ]
  }
}
```

Formulário dinâmico:

```json
{
  "detail": {
    "code": "invalid_form_values",
    "message": "Há campos do formulário com valores inválidos.",
    "fields": [
      { "location": "body", "field": "values.method_title", "code": "required", "message": "Campo obrigatório." }
    ]
  }
}
```

## Antes → depois

| Situação | Antes | Depois |
|---|---|---|
| Sem sessão | `{"detail": "Not authenticated"}` | `{"detail": {"code": "not_authenticated", ...}}` |
| Origem não confiável | `{"detail": "Invalid origin"}` | `code: invalid_origin` |
| Sem permissão | `{"detail": "Forbidden"}` | `code: forbidden` |
| Login inválido | `{"detail": "Invalid credentials"}` | `code: invalid_credentials` |
| Recurso inexistente | `{"detail": "User not found"}` / `"Processo não encontrado."` | `code: not_found`, mensagem em português |
| Rota inexistente, método não permitido | formato do framework | `code: not_found` / `method_not_allowed` |
| Validação | lista `loc`/`msg`/`type`/`input` | `code: validation_error` + `fields` |
| Senha inválida | `{"detail": "Invalid password"}` | `code: validation_error`, campo `password` com `code: invalid` |
| Formulário | `{"detail": {"code": "invalid_form_values", "errors": [...]}}` | `errors` vira `fields` e ganha `message` |
| Erro inesperado | `Internal Server Error` (texto) | `code: internal_error` |
| Códigos específicos existentes | `{"detail": {"code", "message"}}` | igual |

## Documentação

- `ErrorResponse`, `ErrorDetail` e `FieldError` em `components.schemas`, com descrições.
- As respostas `422` das rotas apontam para `ErrorResponse`; `HTTPValidationError` e `ValidationError` saem dos componentes.
