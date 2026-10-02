# Data Model: Autogestão de Nome e Senha da Própria Conta

Esta feature não altera o banco: não há tabela, coluna, índice nem migração nova.

## Entidade existente: `User` (`src/pivma/core/database/models.py`)

| Campo | Efeito desta feature |
|---|---|
| `id`, `username`, `email` | Inalterados (FR-015). |
| `full_name` | Recebe o valor aparado quando `full_name` é enviado. |
| `password_hash` | Recebe o hash Argon2id de `new_password` quando a troca é válida. |
| `updated_at`, `updated_by` | Preenchidos por `set_update_audit(current_user.id)` em toda atualização válida (FR-012). |
| `created_*`, `deleted_*` | Inalterados. |

Relações com perfis, permissões, vínculos e designações não são lidas nem alteradas.

## Entrada não persistida: `SelfUserUpdate` (`src/pivma/schemas.py`)

`extra='forbid'`: qualquer campo fora da tabela retorna 422 (FR-004).

| Campo | Tipo | Regras |
|---|---|---|
| `full_name` | `FullNameValue`, opcional | Espaços externos removidos; 1 a 255 caracteres; `null` rejeitado (FR-006). |
| `current_password` | `str`, opcional | 1 a 128 caracteres; não passa pela política de cadastro; conferida com `password_hash` na rota (FR-008). |
| `new_password` | `str`, opcional | 8 a 128 caracteres; sem caractere de espaço (FR-007). |

### Combinações válidas (`model_validator`, FR-005 e FR-008)

O validador confere as regras de rejeição nesta ordem: primeiro `current_password` sem `new_password`, depois `new_password` sem `current_password` e por último o corpo sem `full_name` e sem `new_password` (research.md, item 3).

| `full_name` | `current_password` | `new_password` | Resultado |
|---|---|---|---|
| ✓ | — | — | Válido: altera o nome. |
| — | ✓ | ✓ | Válido: troca a senha após conferir a atual. |
| ✓ | ✓ | ✓ | Válido: altera ambos, ou nenhum se a senha atual estiver errada. |
| — | — | — | 422: "Informe o nome completo ou a nova senha." |
| — ou ✓ | ✓ | — | 422: "Informe a nova senha." |
| — ou ✓ | — | ✓ | 422: "Informe a senha atual para trocar a senha." |

Os erros 422 de `current_password` e `new_password` saem com a mensagem genérica "Senha inválida.", sem a regra violada (Spec 034, FR-010; ver `research.md`, item 7).

## Fluxo de estado da requisição

1. Sessão (`CurrentUser`) → 401 se ausente, inválida ou de conta inativa.
2. Origem (`TrustedOrigin`) → 403 se ausente ou não confiável.
3. Validação do corpo (`SelfUserUpdate`) → 422.
4. Se houver `new_password`: `verify_password(current_user.password_hash, current_password)` → 400 `invalid_current_password` se falhar. Até aqui, nenhum atributo foi alterado.
5. Atribuição de `full_name` e/ou `password_hash`, `set_update_audit`, commit → 200 com `UserPublic`.

A ordem real entre os passos 1 a 3 é decidida pelo FastAPI. O importante é que nenhum deles altera a conta.
