# Tasks: Vinculação Institucional

**Input**: Design documents from `/specs/005-institutional-affiliations/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/institutional.openapi.yaml`, `quickstart.md`

**Tests**: FR-029 exige testes de schemas, API, segurança, isolamento, persistência, concorrência, migração e regressão. As tarefas de teste aparecem antes da implementação correspondente.

**Organization**: As tarefas estão agrupadas pelas quatro histórias da especificação. Setup e fundação contêm somente elementos compartilhados.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode ser executada em paralelo com tarefas indicadas, pois altera arquivos distintos e não depende de trabalho ainda incompleto.
- **[Story]**: identifica a história atendida por `[US1]`, `[US2]`, `[US3]` ou `[US4]`.
- Cada tarefa informa os arquivos que deve alterar ou validar.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: registrar o único router novo na estrutura atual, sem dependências ou camadas adicionais.

- [X] T001 Criar `src/pivma/routers/institutional.py` com `APIRouter(prefix='/institutional', tags=['institutional'])` e registrar seu router em `src/pivma/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: criar persistência, seeds de permissão e dados de teste compartilhados por todas as histórias.

**CRITICAL**: nenhuma história começa antes desta fase.

- [X] T002 [P] Escrever primeiro os testes de upgrade, preservação de usuários e RBAC, ausência de vínculos implícitos, seeds exclusivos do Administrador e downgrade em `tests/integration/migrations/test_institutional_migration.py`
- [X] T003 [P] Escrever primeiro os testes PostgreSQL para nomes ativos, FK composta laboratório-instituição, vínculos ativos com e sem laboratório e reutilização após inativação em `tests/integration/database/test_institutional_constraints.py`
- [X] T004 Criar a migração `migrations/versions/5e31a8c7d204_institutional_affiliations.py` após `1bd1b3d5ddad`, com quatro tabelas, auditoria, constraints, índices, permissões `104` a `106`, composições `204` a `206` e downgrade restrito à feature 005
- [X] T005 [P] Adicionar `Institution`, `Laboratory`, `UserInstitutionalAffiliation` e `InstitutionalChange`, com `AuditMixin` e constraints equivalentes à migração, em `src/pivma/core/database/models.py`
- [X] T006 Criar factories para as quatro entidades institucionais em `tests/factories/institutional_factory.py` e exportá-las em `tests/factories/__init__.py`
- [X] T007 [P] Adicionar somente as constantes `INSTITUTIONAL_READ`, `INSTITUTIONAL_CATALOGS_MANAGE` e `INSTITUTIONAL_AFFILIATIONS_MANAGE` em `src/pivma/core/authorization.py`, sem ampliar `ADMINISTRATIVE_PERMISSIONS`

**Checkpoint**: migração, modelos, factories e catálogo de permissões estão prontos para as histórias.

---

## Phase 3: User Story 1 - Manter instituições e laboratórios (Priority: P1)

**Goal**: permitir que uma pessoa com `institutional.catalogs.manage` crie, consulte, renomeie e inative instituições e laboratórios, preservando auditoria e histórico.

**Independent Test**: criar uma instituição e um laboratório, listar e consultar ambos, alterar os nomes e inativá-los; confirmar identificadores estáveis, estado, auditoria e bloqueio de novas mutações sobre registros inativos.

### Tests for User Story 1

- [X] T008 [P] [US1] Escrever testes unitários de normalização, limites, campos obrigatórios e rejeição de campos extras dos schemas de instituição e laboratório em `tests/unit/schemas/test_institutional_schemas.py`
- [X] T009 [P] [US1] Escrever testes HTTP dos dez contratos de catálogo, incluindo ordenação, ativos e inativos, auditoria, 404, 409 e 422, em `tests/api/routers/test_institutional_router.py`
- [X] T010 [P] [US1] Escrever testes de 401, origem confiável, `institutional.catalogs.manage`, negação antes da consulta do alvo e confirmar que perfis somente `institutional.read` ou `institutional.affiliations.manage` recebem 403 nas mutações de catálogo em `tests/api/routers/test_institutional_security.py`
- [X] T011 [P] [US1] Escrever teste HTTP concorrente que aceite uma única instituição entre nomes ativos equivalentes em `tests/api/routers/test_institutional_concurrency.py`

### Implementation for User Story 1

- [X] T012 [US1] Implementar `InstitutionCreate`, `InstitutionUpdate`, `InstitutionSummary`, `InstitutionPublic`, `LaboratoryCreate`, `LaboratoryUpdate`, `LaboratorySummary` e `LaboratoryPublic` em `src/pivma/schemas.py`
- [X] T013 [US1] Implementar serialização, conflito transacional, evento institucional e os cinco endpoints de instituição do contrato em `src/pivma/routers/institutional.py`
- [X] T014 [US1] Implementar os cinco endpoints de laboratório, mantendo `institution_id` imutável e registrando cada mutação na mesma transação, em `src/pivma/routers/institutional.py`

**Checkpoint**: US1 funciona e pode ser validada sem criar vínculos de usuário.

---

## Phase 4: User Story 2 - Vincular usuários (Priority: P1)

**Goal**: permitir múltiplos vínculos ativos, institucionais ou laboratoriais, e encerrar cada vínculo sem apagar seu ciclo.

**Independent Test**: criar vínculos somente institucionais e laboratoriais para uma conta ativa, rejeitar alvos inativos ou incompatíveis, impedir duplicação concorrente, inativar um vínculo e criar um novo ciclo equivalente com outro identificador.

### Tests for User Story 2

- [X] T015 [P] [US2] Escrever testes de integração para união de múltiplos vínculos e exclusão do escopo por usuário, vínculo, instituição ou laboratório inativo em `tests/integration/database/test_institutional_scope.py`
- [X] T016 [P] [US2] Acrescentar testes de `AffiliationCreate`, `AffiliationPublic` e `SelfAffiliationPublic`, incluindo laboratório opcional e campos extras, em `tests/unit/schemas/test_institutional_schemas.py`
- [X] T017 [P] [US2] Escrever testes HTTP de criação, listagem administrativa, inativação, correção por novo ciclo, alvos ausentes ou inativos e laboratório de outra instituição em `tests/api/routers/test_institutional_router.py`
- [X] T018 [P] [US2] Acrescentar testes de `institutional.affiliations.manage`, origem confiável e confirmar que perfis somente `institutional.read` ou `institutional.catalogs.manage` recebem 403 nas mutações de vínculo em `tests/api/routers/test_institutional_security.py`
- [X] T019 [P] [US2] Acrescentar teste HTTP concorrente que mantenha um único vínculo ativo equivalente em `tests/api/routers/test_institutional_concurrency.py`

### Implementation for User Story 2

- [X] T020 [P] [US2] Implementar `AffiliationCreate`, `AffiliationPublic` e `SelfAffiliationPublic` em `src/pivma/schemas.py`
- [X] T021 [P] [US2] Implementar a consulta reutilizável de vínculos efetivamente ativos, filtrando usuário, vínculo, instituição e laboratório opcional, em `src/pivma/core/authorization.py`
- [X] T022 [US2] Implementar listagem administrativa, criação e inativação de vínculo em `src/pivma/routers/institutional.py`, aplicando a permissão de cada operação, validando alvos persistidos e gravando `InstitutionalChange` na mesma transação

**Checkpoint**: US1 e US2 entregam o cadastro e a vinculação central de RF003.

---

## Phase 5: User Story 3 - Consultar somente o escopo autorizado (Priority: P2)

**Goal**: permitir autoconsulta de vínculos efetivamente ativos e reservar catálogos e vínculos de outras contas a `institutional.read`.

**Independent Test**: preparar duas contas em laboratórios distintos; confirmar que cada conta sem leitura global recebe somente os próprios vínculos ativos e não descobre os vínculos da outra, enquanto uma conta com `institutional.read` consulta os ciclos autorizados.

### Tests for User Story 3

- [X] T023 [US3] Escrever testes HTTP de autoconsulta, múltiplos vínculos, efeito no pedido seguinte, campos reduzidos, 403 sem leitura global, leitura de outra conta e negação antes do lookup em `tests/api/routers/test_institutional_security.py`

### Implementation for User Story 3

- [X] T024 [US3] Implementar `GET /institutional/me/affiliations` com a identidade autenticada e a consulta persistida de escopo ativo em `src/pivma/routers/institutional.py`

**Checkpoint**: US3 prova isolamento e atualização do escopo sem nova autenticação.

---

## Phase 6: User Story 4 - Consultar o histórico de vínculos (Priority: P3)

**Goal**: permitir que `institutional.read` consulte ações concluídas com alvo, ator, momento e ordem determinística.

**Independent Test**: criar, alterar e inativar registros; consultar o histórico paginado e confirmar os eventos dos dois ciclos de um vínculo, sem evento para tentativa negada, inválida ou revertida.

### Tests for User Story 4

- [X] T025 [P] [US4] Acrescentar testes de `InstitutionalChangePublic` e `InstitutionalChangePage`, incluindo limites de paginação e campos extras, em `tests/unit/schemas/test_institutional_schemas.py`
- [X] T026 [P] [US4] Escrever testes HTTP de histórico, ordem `created_at DESC, id DESC`, paginação, separação de `institutional.read` e ausência de evento para falhas em `tests/api/routers/test_institutional_router.py` e `tests/api/routers/test_institutional_security.py`

### Implementation for User Story 4

- [X] T027 [US4] Implementar `InstitutionalChangePublic` e `InstitutionalChangePage` em `src/pivma/schemas.py`
- [X] T028 [US4] Implementar `GET /institutional/changes` com `offset`, `limit` máximo 100 e ordenação determinística em `src/pivma/routers/institutional.py`

**Checkpoint**: as quatro histórias possuem comportamento e testes independentes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentar a API e executar a validação completa sem ampliar o escopo.

- [X] T029 [P] Documentar as três permissões, os oito caminhos, as quinze operações e a autoconsulta institucional em `README.md`
- [ ] T030 Executar o fluxo manual cronometrado de até 3 minutos e registrar data, duração e resultado em `specs/005-institutional-affiliations/quickstart.md` — **BACKLOG**: exige uma sessão de navegador autenticada contra o ambiente alvo, que só existe após o deploy e a integração do front-end. Não é uma lacuna de implementação desta feature; ver seção "Backlog" do quickstart.
- [X] T031 Executar os testes focados e a regressão com `poetry run pytest`, além de `poetry run ruff check`, `poetry run alembic heads` e `poetry run alembic check`, registrando os resultados em `specs/005-institutional-affiliations/quickstart.md` (testes, ruff e `alembic heads` passaram; `alembic check` foi executado e registrou uma divergência estrutural pré-existente e transversal a todas as tabelas com `AuditMixin`, não específica da feature 005 — ver seção "Backlog" do quickstart)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: inicia sem dependências.
- **Foundational (Phase 2)**: depende de T001 e bloqueia todas as histórias.
- **US1 (Phase 3)**: depende da fundação e entrega os catálogos usados pelos vínculos.
- **US2 (Phase 4)**: depende de US1 porque cria vínculos com instituições e laboratórios persistidos.
- **US3 (Phase 5)**: depende de US2 para consultar escopos reais.
- **US4 (Phase 6)**: depende das mutações de US1 e US2; pode avançar em paralelo com US3 depois de US2.
- **Polish (Phase 7)**: depende das quatro histórias.

### Foundational Dependencies

- T002 e T003 podem ser escritas em paralelo e devem falhar antes da persistência.
- T004 depende de T002.
- T005 depende de T003 e pode avançar em paralelo com T004.
- T006 depende de T005.
- T007 pode avançar em paralelo com T002 a T006.

### User Story Dependencies

```text
Setup -> Foundational -> US1 -> US2 -> US3
                                  \-> US4
US3 + US4 -> Polish
```

### Within Each User Story

- Escrever e executar os testes da história antes da implementação.
- Criar schemas e consultas compartilhadas antes dos endpoints que os usam.
- Implementar a mutação e seu evento na mesma tarefa e transação.
- Executar os testes focados no checkpoint antes da próxima história.

## Parallel Opportunities

- Fundação: T002 e T003; T004 e T005; T007 com os demais arquivos da fase.
- US1: T008, T009, T010 e T011.
- US2: T015, T016, T017, T018 e T019; depois T020 e T021.
- US4: T025 e T026.
- Após US2: US3 e US4 podem avançar em paralelo em arquivos coordenados; alterações simultâneas em `src/pivma/routers/institutional.py` e nos mesmos testes exigem integração sequencial.
- Polish: T029 pode avançar enquanto a equipe prepara a validação manual de T030.

## Parallel Examples

### User Story 1

```text
Task T008: schemas de catálogo em tests/unit/schemas/test_institutional_schemas.py
Task T009: contratos de catálogo em tests/api/routers/test_institutional_router.py
Task T010: autorização de catálogo em tests/api/routers/test_institutional_security.py
Task T011: concorrência de catálogo em tests/api/routers/test_institutional_concurrency.py
```

### User Story 2

```text
Task T015: consulta de escopo em tests/integration/database/test_institutional_scope.py
Task T016: schemas de vínculo em tests/unit/schemas/test_institutional_schemas.py
Task T017: jornada de vínculo em tests/api/routers/test_institutional_router.py
Task T018: autorização de vínculo em tests/api/routers/test_institutional_security.py
Task T019: concorrência de vínculo em tests/api/routers/test_institutional_concurrency.py
```

### User Story 4

```text
Task T025: schemas de histórico em tests/unit/schemas/test_institutional_schemas.py
Task T026: contrato e segurança do histórico em tests/api/routers/test_institutional_router.py e tests/api/routers/test_institutional_security.py
```

## Implementation Strategy

### Minimum Functional Scope

As duas histórias P1 formam o menor incremento funcional de RF003:

1. concluir Setup e Foundational;
2. concluir US1 e validar os catálogos;
3. concluir US2 e validar vínculos, inativação e concorrência;
4. interromper e revisar o incremento antes de iniciar US3.

### Incremental Delivery

1. Setup + Foundational estabelecem persistência e permissões.
2. US1 entrega instituições e laboratórios.
3. US2 entrega a vinculação institucional.
4. US3 restringe consultas ao escopo autorizado.
5. US4 expõe o histórico autorizado.
6. Polish executa regressão e registra as evidências.

## Notes

- As tarefas mantêm o padrão atual de router, schemas, modelos e autorização; não criam service, repository, cache ou dependência.
- Testes de API usam `TestClient`; testes relacionais e de migração usam PostgreSQL/pgvector real.
- Factories criam entidades persistíveis e fixtures existentes fornecem sessões, usuários, tokens e savepoints.
- SQL direto fica restrito ao teste de migração e, se necessário, às constraints específicas do PostgreSQL; a preparação comum usa ORM.
- RF005, RF006, refresh token, 2FA e mensageria não aparecem como implementação em nenhuma tarefa.

---

## Phase 8: Convergence

- [X] T032 Cobrir `POST /institutional/users/{user_id}/affiliations` concorrente com duas sessões independentes, aceitando uma criação e retornando conflito para a duplicação, por FR-009 e US2/AC4 (partial)
- [X] T033 Alinhar `AffiliationPublic.active` ao estado efetivo que inclui usuário, instituição e laboratório, e testar o efeito da inativação de cada alvo no pedido seguinte, por FR-011 e SC-003 (partial)
- [X] T034 Completar os testes de migração, contratos, autorização e histórico previstos em FR-029, incluindo preservação de usuário e RBAC, respostas 404/409/422, paginação, negação sem vazamento e ausência de evento para falhas
- [ ] T035 Executar o fluxo manual cronometrado e `PYTHONPATH=src poetry run alembic check` contra PostgreSQL disponível; registrar as evidências no quickstart, por SC-006 e T030/T031 (partial) — **BACKLOG registrado, não lacuna de implementação**: `alembic check` já foi executado contra PostgreSQL disponível e sua divergência está registrada no quickstart como decisão pendente e transversal (não específica da 005). O fluxo manual cronometrado depende de uma conta autenticada em um navegador real, o que só existe depois do deploy e da integração do front-end. Reavaliar esta tarefa somente quando essas dependências existirem.
