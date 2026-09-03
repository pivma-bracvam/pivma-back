---

description: "Tarefas de implementação do cadastro seguro de usuários"
---

# Tasks: Cadastro Seguro de Usuários

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/users.openapi.yaml`, `quickstart.md` e `checklists/readiness.md`

**Tests**: A spec exige testes para comportamento novo. Cada história começa pelos testes que devem
falhar antes da implementação correspondente.

**Organization**: Tarefas agrupadas por história. A Phase 1 bloqueia alterações de código até o
responsável aprovar a spec, o plano e as decisões operacionais restantes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: executável em paralelo após suas dependências, em arquivos distintos.
- **[Story]**: vínculo com US1, US2 ou US3.
- Setup, fundação e validação transversal não recebem rótulo de história.

## Phase 1: Aprovação e setup

**Purpose**: Fechar o gate documental e preparar dependência e recurso local.

- [x] T001 Registrar responsável e decisão sobre faixa de atualização do Argon2, janela operacional da migração, proveniência/licença do snapshot e branch de trabalho em `specs/001-secure-user-registration/plan.md`, `specs/001-secure-user-registration/research.md` e `specs/001-secure-user-registration/checklists/readiness.md`
- [x] T002 Registrar a aprovação explícita da spec e do plano, recalcular o Constitution Check e atualizar o estado do gate em `specs/001-secure-user-registration/spec.md`, `specs/001-secure-user-registration/plan.md` e `specs/001-secure-user-registration/checklists/readiness.md`
- [x] T003 [P] Adicionar e travar `argon2-cffi` na faixa aprovada e configurar a inclusão dos recursos não Python em `pyproject.toml` e `poetry.lock`
- [x] T004 [P] Implementar a derivação determinística e offline da blocklist a partir de snapshot local aprovado em `scripts/derive_password_blocklist.py`
- [x] T005 Gerar os 100.000 hashes SHA-1 ordenados e metadados com fonte, data, checksums, seleção, ferramenta e termos em `src/pivma/resources/password_blocklist/hashes.sha1` e `src/pivma/resources/password_blocklist/metadata.json`

**Checkpoint**: Gate aprovado; dependência e blocklist rastreável disponíveis sem rede em runtime.

---

## Phase 2: Fundação compartilhada

**Purpose**: Adaptar persistência e fixtures para todas as histórias.

**CRITICAL**: Nenhuma história começa antes desta fase.

- [x] T006 Escrever testes de migração para tabela vazia ou com Argon2id válido, aborto sem mutação diante de credencial legada, colisões ativo/ativo, ativo/excluído e excluído/excluído, diagnósticos sem segredos e downgrade em `tests/migrations/test_secure_user_registration.py`
- [x] T007 Atualizar `User.password` para `User.password_hash` e declarar índices únicos globais sobre `lower(username)` e `lower(email)` em `src/pivma/core/database/models.py`
- [x] T008 Implementar preflight abortivo, renomeação da coluna e índices globais na revisão `migrations/versions/2d7f9a4c6b81_secure_user_registration.py`, sem converter ou invalidar credenciais
- [x] T009 Atualizar `UserFactory` e fixtures para `password_hash`, entradas válidas e sessões independentes de concorrência em `tests/conftest.py`

**Checkpoint**: Modelo, migração e fixtures refletem FR-022 e FR-023; testes de migração passam no
PostgreSQL descartável.

---

## Phase 3: User Story 1 - Concluir cadastro válido (Priority: P1) 🎯 MVP

**Goal**: Criar usuário válido, armazenar somente Argon2id e devolver id, username e e-mail.

**Independent Test**: Enviar dados válidos; confirmar HTTP 201, uma conta, caixa preservada após
trim, Argon2id verificável e nenhuma senha ou representação na resposta.

### Tests for User Story 1

> Escrever primeiro e confirmar falha pela ausência do comportamento novo.

- [x] T010 [P] [US1] Cobrir trim, caixa, regex e limites do username, e-mail inválido, limites Unicode da senha e `str.isspace()` em `tests/test_schemas.py`
- [x] T011 [P] [US1] Cobrir integridade e consulta exata da blocklist, Argon2id real, salt variável, senha incorreta e 128 code points Unicode em `tests/core/test_security.py`
- [x] T012 [P] [US1] Atualizar senhas dos testes atuais e cobrir HTTP 201, corpo público, Argon2id persistido, HTTP 422 exato `{"detail": "Invalid password"}` e respostas sem segredo em `tests/routers/test_user.py`
- [x] T013 [P] [US1] Cobrir rollback e HTTP 500 genérico separadamente para falhas de hashing, `flush` e `commit`, sem criação parcial ou segredo, em `tests/routers/test_user_failures.py`
- [x] T014 [P] [US1] Cobrir blocklist ausente/corrompida, prontidão bloqueada e recuperação após restaurar o recurso e reiniciar em `tests/test_blocklist_readiness.py`
- [x] T015 [P] [US1] Verificar recursos, checksums, metadados e carregamento no wheel e sdist em `tests/test_package_resources.py`

### Implementation for User Story 1

- [x] T016 [P] [US1] Implementar trim e validações aprovadas de username, e-mail e senha, sem normalizar a senha, em `src/pivma/schemas.py`
- [x] T017 [P] [US1] Implementar blocklist validada em cache e hashing Argon2id no perfil aprovado em `src/pivma/core/security.py`
- [x] T018 [US1] Validar a blocklist na inicialização e sanitizar erros de senha para o contrato 422 sem alterar erros alheios à senha em `src/pivma/__init__.py`
- [x] T019 [US1] Integrar blocklist, hashing em worker thread, rollback e persistência de `password_hash` no `POST /users` em `src/pivma/routers/users.py`
- [x] T020 [US1] Executar a validação independente da US1 e registrar comandos e resultados em `specs/001-secure-user-registration/quickstart.md`

**Checkpoint**: US1 entrega cadastro válido seguro sem depender de US2 ou US3.

---

## Phase 4: User Story 2 - Impedir identificadores duplicados (Priority: P2)

**Goal**: Rejeitar identificadores equivalentes sem distinguir caixa, inclusive contra usuários
excluídos e sob concorrência, mantendo mensagens e precedência.

**Independent Test**: Repetir username, e-mail e ambos com variações de caixa contra usuários
ativos e excluídos; confirmar HTTP 409, precedência de username e, para dois pedidos simultâneos,
um HTTP 201, um HTTP 409 e uma conta.

### Tests for User Story 2

- [x] T021 [P] [US2] Cobrir conflitos isolados e simultâneos, trim, caixa, precedência e identificadores pertencentes a usuários excluídos em `tests/routers/test_user.py`
- [x] T022 [P] [US2] Cobrir exatamente dois pedidos simultâneos por caso de username e e-mail equivalentes, usando sessões independentes, em `tests/routers/test_user_concurrency.py`
- [x] T023 [P] [US2] Cobrir índices globais, preservação de caixa e prova de que `deleted_at` não libera username ou e-mail em `tests/core/database/test_user_constraints.py`

### Implementation for User Story 2

- [x] T024 [US2] Implementar consultas globais com `lower()` sem filtro de exclusão, precedência de username e tradução das violações esperadas após rollback em `src/pivma/routers/users.py`
- [x] T025 [US2] Executar a validação independente da US2 e registrar comandos, resultados e concorrência em `specs/001-secure-user-registration/quickstart.md`

**Checkpoint**: PostgreSQL e rota preservam unicidade global mesmo sob corrida.

---

## Phase 5: User Story 3 - Registrar a criação para auditoria (Priority: P3)

**Goal**: Preencher `created_at` e manter os cinco campos de autoria, atualização e exclusão nulos
no cadastro público, sem ampliar a resposta.

**Independent Test**: Concluir cadastro sem sessão; confirmar `created_at` preenchido,
`created_by`, `updated_at`, `updated_by`, `deleted_at` e `deleted_by` nulos e auditoria ausente da
resposta pública.

### Tests for User Story 3

- [x] T026 [US3] Cobrir estado inicial dos seis campos de auditoria e sua omissão no corpo público em `tests/routers/test_user_audit.py`
- [x] T027 [US3] Executar a validação independente da US3 e registrar comandos e resultados em `specs/001-secure-user-registration/quickstart.md`

**Checkpoint**: As três histórias têm critérios independentes cobertos por testes.

---

## Phase 6: Validação transversal

**Purpose**: Fechar rastreabilidade, distribuição, desempenho e regressão.

- [x] T028 [P] Relacionar FR-001–FR-027 e SC-001–SC-013 a cenários, decisões e testes em `specs/001-secure-user-registration/spec.md` e `specs/001-secure-user-registration/plan.md`
- [x] T029 [P] Executar upgrade limpo, abortos de preflight, inspeção de wheel/sdist e instalação do wheel; registrar evidências em `specs/001-secure-user-registration/quickstart.md`
- [x] T030 Executar no container o benchmark de dois cadastros válidos distintos em concorrência e registrar ambiente, parâmetros, latências, duração, memória, resultados e aprovação em `specs/001-secure-user-registration/benchmark-results.md`
- [x] T031 Executar `poetry run pytest -vv` e `poetry run ruff check`, conferir a saída real e registrar resultados e falhas em `specs/001-secure-user-registration/quickstart.md`
- [x] T032 Reavaliar os 49 itens e registrar a decisão final do gate em `specs/001-secure-user-registration/checklists/readiness.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: T002 precede código. T003 e T004 podem executar em paralelo depois da aprovação;
  T005 depende de T004.
- **Phase 2**: depende da Phase 1 e bloqueia histórias. T006 deve falhar antes de T007–T008; T009
  depende do modelo.
- **US1**: T010–T015 podem ser escritos em paralelo; T016 e T017 podem ser implementados em
  paralelo após seus testes; T018–T019 dependem deles.
- **US2**: depende da US1. T021–T023 podem ser escritos em paralelo; T024 implementa e T025 valida.
- **US3**: depende da US1, mas não da US2.
- **Phase 6**: começa após as histórias incluídas; T030 exige implementação funcional e T031 sucede
  todas as alterações de código.

### User Story Dependency Graph

```text
Aprovação e setup → Fundação → US1 (MVP) ─┬→ US2
                                          └→ US3
US2 + US3 → Validação transversal
```

### Requirement Traceability

| Escopo | Requisitos | Tarefas principais |
|---|---|---|
| Entrada e contrato público | FR-001–FR-005, FR-007, FR-009, FR-012 | T010, T012, T016, T018–T019 |
| Proteção, blocklist e prontidão | FR-006–FR-008, FR-017, FR-024, FR-026 | T003–T005, T011–T019 |
| Migração segura | FR-022 | T006–T009, T029 |
| Unicidade e concorrência | FR-010–FR-016, FR-023 | T006–T009, T021–T025 |
| Auditoria | FR-018–FR-019, FR-027 | T009, T019, T026–T027 |
| Escopo e regressão | FR-020–FR-021, FR-025 | T001–T002, T028, T031–T032 |
| Benchmark | SC-011 | T030 |

## Parallel Execution Examples

### User Story 1

```text
T010 tests/test_schemas.py
T011 tests/core/test_security.py
T012 tests/routers/test_user.py
T013 tests/routers/test_user_failures.py
T014 tests/test_blocklist_readiness.py
T015 tests/test_package_resources.py
```

### User Story 2

```text
T021 tests/routers/test_user.py
T022 tests/routers/test_user_concurrency.py
T023 tests/core/database/test_user_constraints.py
```

### User Story 3

US3 concentra sua prova em `tests/routers/test_user_audit.py`; não há tarefas independentes que
justifiquem execução paralela dentro da história.

## Implementation Strategy

### MVP First

1. Aprovar spec, plano e decisões operacionais da Phase 1.
2. Concluir a fundação e validar a migração.
3. Implementar T010–T020.
4. Parar e validar a US1 antes de US2 ou US3.

### Incremental Delivery

1. Aprovação e setup estabelecem dependência, recurso e limites.
2. Fundação prepara persistência sem converter dados legados.
3. US1 entrega cadastro protegido e falha fechada.
4. US2 adiciona unicidade global e concorrência.
5. US3 comprova auditoria inicial.
6. A Phase 6 fecha evidências e aprovação do benchmark.

## Notes

- Não implementar antes de T001–T002.
- Não criar login, JWT, cookies, perfis, permissões, vínculos, recuperação de senha, rate limiting
  ou endpoints adicionais.
- Nunca registrar senha ou Argon2id em resposta, log, erro ou diagnóstico.
- Confirmar que os testes novos falham antes da implementação correspondente.
- Conferir a saída direta do Pytest; `poetry test` ignora falhas na etapa do Pytest.

## Redução de escopo pós-implementação (2026-08-12)

Todas as tarefas acima (T001–T032) foram concluídas e validadas conforme registrado. Em seguida, a
pessoa solicitante — única aprovadora da spec original e, nesta feature, também quem a implementou
— identificou que a Session 2026-08-11 de clarifications gerou um conjunto de decisões
desproporcional a uma primeira feature em um projeto novo sem usuários reais em produção. Ver
`spec.md`, Clarifications, Session 2026-08-12, para o registro completo da decisão.

As seguintes entregas foram revertidas após T032, sem reabrir numeração de tarefas:

| Entrega revertida | Tarefas originais afetadas | Situação |
|---|---|---|
| Blocklist local de 100k hashes, prontidão fail-closed e ferramenta de derivação | T004, T005, parte de T017, T018 | Removida: `scripts/derive_password_blocklist.py`, `src/pivma/resources/password_blocklist/`, funções de blocklist em `security.py`, carregamento no lifespan de `__init__.py`, e os testes `test_blocklist_readiness.py`, `test_derive_password_blocklist.py`, `test_package_resources.py` |
| Inspeção de formato Argon2id na migração | parte de T008 | Removida da migração; o preflight de colisão de identificador entre usuários ativos permanece |
| Reserva de identificador após exclusão lógica | parte de T007, T008, T024 | Revertida: índices voltam a ser parciais (`deleted_at IS NULL`); `find_conflict` passa a filtrar usuários ativos |
| Gate formal de benchmark (T030) | T030 | Deixou de ser critério de aceite; `benchmark-results.md` preservado como registro histórico |

Os testes afetados (`tests/core/test_security.py`, `tests/routers/test_user.py`,
`tests/core/database/test_user_constraints.py`, `tests/migrations/test_secure_user_registration.py`)
foram ajustados para o comportamento revertido, incluindo casos novos que provam a liberação de
identificador após exclusão lógica. A suíte completa (`poetry run pytest -vv` e
`poetry run ruff check`) foi reexecutada após o corte; ver resultado em `quickstart.md`.
