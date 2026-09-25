# Research: Remover o Kanban de Pendências

Não havia `NEEDS CLARIFICATION` no Technical Context. As decisões abaixo
vêm da leitura do código da branch `chore/029-remove-activities-kanban`
(base: `028-role-assignment-invites`).

## 1. Base da branch

- **Decision**: a branch sai da `028-role-assignment-invites`.
- **Rationale**: a `main` não tem o Kanban. A `develop` tem, junto com
  `scripts/seeds/seed_kanban.py`, o perfil `--profile kanban` do runner,
  `tests/integration/test_seeds_runner.py` e páginas de documentação
  (`docs/features/kanban.md`, `mkdocs.yml`, `docs/index.md`). A 028 já remove
  tudo isso. Com a base na 028, a 029 mexe só em código e testes, sem conflito
  de modify/delete no merge.
- **Alternatives considered**: sair da `develop` e remover também seeds e
  docs. Rejeitada pelo usuário, porque conflitaria com a 028.

## 2. Símbolos que ficam órfãos

Verificado com `grep` em `src/` e `tests/`:

| Símbolo | Onde | Usos fora do Kanban | Decisão |
|---|---|---|---|
| `router` de `activities` | `routers/activities.py` | nenhum (única rota: `/kanban`) | remover o arquivo |
| `KanbanColumn`, `KanbanCardProcess`, `KanbanCardItem`, `KanbanPage` | `schemas.py` | nenhum | remover |
| `ActivityCargo` | `schemas.py` | só `KanbanCardItem`; `authorization.py` o cita em comentário | remover e ajustar o comentário |
| `GLOBAL_ACTIVITY_CARGOS` | `schemas.py` | nenhum (o domínio usa a cópia de `authorization.py`) | remover a cópia de `schemas.py` |
| `KANBAN_*`, `classify_kanban_column` | `core/process_engine.py` | só docstrings de `_compute_activity_due_date` e `_resolve_activity_cargo` | remover e ajustar docstrings |
| `resolve_activity_holders` | `core/authorization.py` | nenhum em produção; só o próprio teste | remover |
| `_GLOBAL_CARGO_SYSTEM_KEYS` | `core/authorization.py` | só `resolve_activity_holders` | remover |

- **Rationale**: a regra de mudanças cirúrgicas manda remover o que a
  própria mudança deixa sem uso, e nada além disso.
- **Alternatives considered**: manter `ActivityCargo` para a remodelagem
  futura. Rejeitada: seria código especulativo, e a remodelagem ainda não tem
  desenho.

## 3. O que permanece

- `ACTIVITY_CARGOS` e `GLOBAL_ACTIVITY_CARGOS` em `core/authorization.py`: usados
  por `_resolve_activity_cargo` para validar `assigned_role` de templates.
- `ADMINISTRATOR_SYSTEM_KEY` e `BRACVAM_SYSTEM_KEY`: usados em outras regras
  de autorização.
- `process_visibility_clause`, `utc_now`, `timedelta`: usados pelo motor e pelo
  `/tasks`.
- Factories de teste (`UserFactory`, `AssignmentFactory`, `AccessProfileFactory`,
  factories de processo) e o helper `authenticate`: usados por outros testes.
  Nenhum outro arquivo importa dos testes removidos.

## 4. Teste de regressão

- **Decision**: um arquivo novo,
  `tests/api/routers/test_activities_kanban_removed.py`, com dois testes: um
  para o 404 com usuário autenticado e outro para a ausência do caminho, da tag
  `Activities` e dos schemas `Kanban*` em `/openapi.json`.
- **Rationale**: é o único comportamento observável novo (FR-007). O padrão
  segue os testes existentes que leem `client.get('/openapi.json')`
  (`test_user_update.py`, `test_user_listing.py`) e usam `authenticate` de
  `test_rbac_router.py`.
- **Alternatives considered**: nenhum teste novo, confiando só na suíte
  existente. Rejeitada: a suíte não detectaria a volta acidental da rota.
