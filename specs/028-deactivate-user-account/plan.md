# Implementation Plan: Desativação de Conta de Usuário

**Branch**: `028-deactivate-user-account` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Especificação da feature em `specs/028-deactivate-user-account/spec.md`.

## Summary

Adicionar `DELETE /users/{user_id}` ao router de usuários para desativar uma conta ativa. A rota reutilizará a autorização `users.manage`, a validação de origem, a auditoria de exclusão lógica e a invariante administrativa existentes. A operação bloqueará a conta alvo, registrará `deleted_at` e `deleted_by`, validará que resta uma pessoa administradora ativa na mesma transação e responderá 204. Não haverá migração, campos, eventos de auditoria ou mecanismo novo de revogação de sessão.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, SQLAlchemy assíncrono 2.0, Pydantic 2, PyJWT

**Storage**: PostgreSQL; tabela existente `users` e campos de `AuditMixin`

**Testing**: Pytest 9, pytest-asyncio, TestClient e PostgreSQL de teste via testcontainers

**Target Platform**: Serviço web FastAPI em Linux

**Project Type**: Serviço web de backend

**Performance Goals**: Uma desativação atualiza uma única conta e usa as consultas de autorização já existentes. A feature não acrescenta meta de latência ou processamento em lote.

**Constraints**: Exigir sessão, `users.manage` e origem confiável; preservar os contratos HTTP existentes; executar a alteração e a checagem da invariante na mesma transação; não excluir dados físicos nem criar estruturas de sessão ou auditoria.

**Scale/Scope**: Uma conta por requisição; um endpoint, o router de usuários e testes de integração relacionados.

## Constitution Check

| Gate | Status antes da pesquisa | Evidência e decisão |
|---|---|---|
| Requisitos oficiais e evidência classificada | PASS | A issue #42 confirma endpoint, autorização, auditoria, bloqueios e cenários. HTTP 409 e 404 seguem as classificações PROPOSTA e INFERÊNCIA já registradas na spec. |
| Rastreabilidade e auditoria | PASS | A alteração usa exclusivamente `AuditMixin.set_deletion_audit`, preservando `deleted_at` e `deleted_by`. Não adiciona evento ou campo de auditoria. |
| Segurança e autorização | PASS | A rota usa `UserManager`, `TrustedOrigin` e a consulta de conta ativa em `get_current_user`. |
| Autoridade científica e IA | N/A | A feature não usa IA nem trata decisão científica. |
| Mudança pequena e verificável | PASS | O plano limita o código ao endpoint e à integração com a invariante existente. Os testes cobrem sucesso, autorização, sessão, listagem, conflitos e concorrência. |

## Project Structure

### Documentation (this feature)

```text
specs/028-deactivate-user-account/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── users-deactivation.openapi.yaml
└── tasks.md                 # criado por speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── routers/
│   └── users.py             # endpoint DELETE e contrato OpenAPI
├── core/
│   ├── authorization.py     # invariante administrativa já existente
│   └── database/models.py   # AuditMixin e User já existentes
└── dependencies.py          # autenticação e origem já existentes

tests/api/routers/
└── test_user_router.py      # cenários de integração da issue #42
```

**Structure Decision**: O endpoint pertence ao router de usuários. A feature reutiliza os componentes de autorização, auditoria e sessão já presentes; não introduz serviço, repositório, migração ou módulo adicional.

## Implementation Approach

1. Declarar `DELETE /users/{user_id}` com o mesmo contrato de segurança do PATCH: `UserManager` e `TrustedOrigin`, incluindo respostas OpenAPI 401, 403, 404 e 409.
2. Buscar somente a conta ativa com bloqueio de linha. Se não houver conta, responder 404. Se a conta alvo for a da pessoa autora, responder 409 antes de qualquer alteração.
3. Na transação corrente, chamar `set_deletion_audit(actor.id)`, executar `flush` e chamar `ensure_administrator_remains`. Em caso de `ValueError`, executar rollback e devolver 409. Com a invariante satisfeita, confirmar a transação e responder 204 sem corpo.
4. Estender `tests/api/routers/test_user_router.py` com os cenários da issue, incluindo sessões independentes para provar que duas desativações concorrentes não removem todas as contas administrativas.

## Debt Avoidance

- Usar a invariante e o bloqueio do perfil administrativo que já sincronizam alterações RBAC; não criar lock, tabela ou constraint paralelos.
- Não usar atualização em massa: ela não recebe o filtro global de soft-delete e não preserva o fluxo de auditoria e invariante.
- Não desativar vínculos de perfil, afiliações, designações ou histórico. A conta inativa perde autenticação pelo controle existente.
- Não criar blacklist, versão de token, limpeza de cookie ou migração. `get_current_user` e o login já rejeitam contas com `deleted_at` preenchido.

## Constitution Check (Post-Design)

| Gate | Status | Evidência de design |
|---|---|---|
| Requisitos e evidência | PASS | [research.md](./research.md) registra as decisões e alternativas; [contract](./contracts/users-deactivation.openapi.yaml) limita a interface à issue. |
| Auditoria e rastreabilidade | PASS | [data-model.md](./data-model.md) usa os campos e o método de auditoria existentes, sem registro paralelo. |
| Segurança e autorização | PASS | O contrato exige autenticação, `users.manage` e origem confiável; [quickstart.md](./quickstart.md) valida 401 e 403. |
| Mudança pequena e verificável | PASS | Não há componente ou persistência nova. A validação cobre o endpoint, rollback, sessão, listagem e concorrência. |

## Complexity Tracking

Nenhuma violação de complexidade ou exceção constitucional exige justificativa.
