# Data Model: Token de Acesso no Corpo da Resposta de Login

Nenhuma tabela, coluna ou migração. A feature acrescenta só um schema de resposta.

## LoginResponse (schema de resposta, não persistido)

| Campo | Tipo | Obrigatório | Regra |
|-------|------|-------------|-------|
| `access_token` | string | sim | Mesmo JWT gravado no cookie `access_token` da resposta (FR-002) |
| `token_type` | string, constante `bearer` | sim | Sempre `bearer` (FR-003) |
| `expires_in` | inteiro | sim | Segundos de validade, de `ACCESS_TOKEN_TTL` (hoje 28800) (FR-004) |

Emitido apenas em login bem-sucedido (HTTP 200). Respostas de erro mantêm o formato `{"detail": {"code", "message"}}` da Spec 034 e não trazem token.

## Credencial da requisição (regra, não entidade)

| Cookie `access_token` | `Authorization: Bearer` | Credencial usada | Checagem de `Origin` nas mutações |
|-----------------------|-------------------------|------------------|-----------------------------------|
| presente | ausente | cookie | exigida |
| presente | presente | cookie | exigida |
| ausente | presente | Bearer | dispensada |
| ausente | ausente | parâmetro `token`, se houver; senão 401 | exigida |
