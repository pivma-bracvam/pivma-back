# Tasks: Perfil do Usuário

**Input**: Design documents from `specs/045-user-profile/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/user-profile.md, quickstart.md

**Tests**: a constituição exige jornada por história e testes focados pela
matriz de risco. Acesso a dados de outra conta é risco crítico: cada perfil
negado e cada erro têm teste próprio. A listagem de cargos locais é risco
médio: filtro, ordenação e paginação têm testes próprios.

## Format: `[ID] [P?] [Story] Description`

## Convenções dos testes desta feature

- Jornadas: `tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py`,
  a partir de `bootstrap_fresh_deploy`, só pela API pública, com `journey_client`,
  `sign_up`, `log_in` e `log_out`. A descrição em prosa vai na docstring do
  módulo, com "Spec 045" e a história de cada teste. Os passos ficam numerados
  em comentários, na ordem da descrição.
- Testes focados: `tests/api/routers/test_user_profile.py`, com as factories de
  `tests/factories/` e autenticação por cookie, como em
  `tests/api/routers/test_user_listing.py`. Cada teste verifica um único
  resultado. Nos erros, os testes verificam `detail.code`, não a mensagem.
- O PostgreSQL fixa `now()` na transação do teste, então
  `user_access_profiles.created_at` sai igual em todas as linhas. Os testes de
  ordem preenchem `created_at` e `assigned_at` explicitamente.

## Phase 1: Foundational

**Purpose**: schemas e apoio de teste que as três histórias usam.

- [X] T001 Criar em src/pivma/schemas.py, todos com `extra='forbid'`:
  - `GlobalProfileAssignment` (`id`, `name`, `assigned_at`).
  - `UserProfile` (`id`, `full_name: str | None`, `email` com `format: email`, `active`, `created_at`, `global_profiles`).
  - `UserProcessRef(ProcessRef)` com `status`.
  - `UserProcessRole` (`id`, `role_key`, `laboratory: LaboratoryRef | None`, `assigned_at`, `revoked_at: datetime | None`).
  - `UserProcessRoles` (`process`, `roles`).
  - `UserProcessRoleFilters` (`active: bool`).
  - `UserProcessRoleListResponse(ListPage[UserProcessRoles, UserProcessRoleFilters])`.

  `ProcessRef` não muda.
- [X] T002 Criar tests/api/routers/test_user_profile.py com:
  - O helper `authenticate(client, user)`.
  - A fixture `profile_reader`: conta com um perfil não canônico (`system_key=None`) que tem só `users.read`, para provar que o acesso vem da permissão e não do perfil Administrador.
  - As contas comuns, sem perfil global, são as fixtures `user` e `other_user` do conftest.

**Checkpoint**: `poe lint` passa com os schemas novos.

## Phase 2: User Story 1 - Ver o próprio perfil (Priority: P1) 🎯 MVP

**Goal**: a pessoa autenticada abre `GET /users/{seu_id}` e vê os dados da
conta sem `username` e os cargos globais vigentes, com a data de atribuição.

**Independent Test**: cadastrar uma conta, dar a ela um cargo global e
consultar o próprio perfil com o `id` de `GET /auth/me`.

### Tests for User Story 1

- [X] T003 [US1] Jornada `test_pessoa_ve_o_proprio_perfil_com_cargos_globais_vigentes` em tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py:
  1. A pessoa se cadastra e entra.
  2. Ela abre o próprio perfil com o `id` de `GET /auth/me` e vê nome, e-mail, `active: true`, `created_at`, `global_profiles: []` e nenhum `username`.
  3. O Administrador entra e concede o perfil BraCVAM pela rota pública de RBAC.
  4. A pessoa entra de novo e vê o BraCVAM com `assigned_at`.
  5. O Administrador revoga o perfil.
  6. A pessoa entra de novo e vê `global_profiles: []`.
- [X] T004 [P] [US1] As chaves da resposta são exatamente `id`, `full_name`, `email`, `active`, `created_at` e `global_profiles`, sem `username` nem `password_hash` (FR-001, FR-002, SC-002), em tests/api/routers/test_user_profile.py
- [X] T005 [P] [US1] Conta comum, sem `users.read`, consulta o próprio perfil e recebe 200 (FR-011), em tests/api/routers/test_user_profile.py
- [X] T006 [P] [US1] Dois perfis globais com `created_at` diferentes saem em ordem crescente de `assigned_at`, e dois com o mesmo `created_at` saem em ordem de `id` (FR-003), em tests/api/routers/test_user_profile.py
- [X] T007 [P] [US1] Atribuição com `deleted_at` preenchido fica fora de `global_profiles` (FR-004), em tests/api/routers/test_user_profile.py
- [X] T008 [P] [US1] Atribuição vigente de um perfil de acesso desativado fica fora de `global_profiles` (FR-004), em tests/api/routers/test_user_profile.py
- [X] T009 [P] [US1] Perfil revogado e concedido de novo aparece uma vez, com o `created_at` da atribuição nova (edge case), em tests/api/routers/test_user_profile.py
- [X] T010 [P] [US1] Sem sessão, `GET /users/{id}` responde 401 (FR-014), em tests/api/routers/test_user_profile.py
- [X] T011 [P] [US1] Sessão de conta desativada em `GET /users/{id}` responde 401 (FR-014), em tests/api/routers/test_user_profile.py
- [X] T012 [P] [US1] Conta comum que consulta o perfil de outra conta existente recebe 403 `forbidden`, sem dados da conta no corpo (FR-012), em tests/api/routers/test_user_profile.py
- [X] T013 [P] [US1] `user_id` sem formato UUID responde 422 `validation_error`, em tests/api/routers/test_user_profile.py
- [X] T014 [US1] Rodar T003 a T013 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que falham antes da implementação

### Implementation for User Story 1

- [X] T015 [US1] Criar `authorize_profile_read(session, actor, user_id)` em src/pivma/routers/users.py. Nesta fase, ela só libera `actor.id == user_id`; nos demais casos, levanta 403 `forbidden` com a mensagem padrão de `require_permission`, antes de qualquer consulta (FR-012, FR-015).
- [X] T016 [US1] Criar `GET /users/{user_id}` (`operation_id='getUserProfile'`, `response_model=UserProfile`) em src/pivma/routers/users.py.
  - A rota chama `authorize_profile_read` antes de tudo.
  - A conta vem de `select(User).where(User.id == user_id).execution_options(skip_soft_delete_filter=True)`, porque a administração consulta contas desativadas (US3). Nesta fase, a conta é sempre a do ator e sempre existe.
  - Uma consulta busca `AccessProfile.id`, `AccessProfile.name` e `UserAccessProfile.created_at`, em ordem de `UserAccessProfile.created_at` e depois de `AccessProfile.id`. O filtro global de exclusão lógica já tira as atribuições e os perfis excluídos; a consulta não repete `deleted_at`.
  - O retorno monta `UserProfile` com `active = user.deleted_at is None`.
  - `responses` descreve 401 e 403, como em `list_users`, sem `x-required-permission`.
- [X] T017 [US1] Rodar T003 a T013 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que passam

**Checkpoint**: a pessoa vê o próprio perfil; qualquer outra conta recebe 403.

## Phase 3: User Story 2 - Ver os próprios cargos locais por processo (Priority: P1)

**Goal**: a pessoa vê, em `GET /users/{seu_id}/process-roles`, um item por
processo com os seus cargos e datas, e consulta os revogados com
`active=false`.

**Independent Test**: designar a conta em dois processos, com dois cargos em
um deles, revogar um cargo e consultar ativos e revogados.

### Tests for User Story 2

- [X] T018 [US2] Jornada `test_proponente_ve_cargos_ativos_e_revogados_por_processo` em tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py:
  1. A pessoa se cadastra, entra e cria dois processos com `POST /processes`.
  2. Ela abre os próprios cargos locais e vê dois itens, o segundo processo primeiro, cada um com `proponent` e `revoked_at: null`.
  3. O Administrador entra e designa a pessoa como `statistician` no primeiro processo, por `POST /processes/{id}/participants`.
  4. A pessoa entra de novo. O primeiro processo passa à frente, com `statistician` antes de `proponent`.
  5. O Administrador revoga a designação de `statistician`.
  6. A pessoa entra de novo. Em `active=true`, o primeiro processo tem só `proponent`. Em `active=false`, ele aparece só com `statistician`, com `revoked_at` preenchido.
- [X] T019 [P] [US2] Dois cargos ativos no mesmo processo saem num único item, com os dois cargos (FR-006), em tests/api/routers/test_user_profile.py
- [X] T020 [P] [US2] Cada item traz `process` com exatamente `id`, `code`, `title` e `status`, e cada cargo com exatamente `id`, `role_key`, `laboratory`, `assigned_at` e `revoked_at` (FR-006), em tests/api/routers/test_user_profile.py
- [X] T021 [P] [US2] Cargo `lead_laboratory` traz `laboratory` com `id`, `name`, `active` e `institution`; cargo sem laboratório traz `laboratory: null` (FR-006), em tests/api/routers/test_user_profile.py
- [X] T022 [P] [US2] Sem `active`, a listagem traz só cargos com `revoked_at` nulo e ecoa `filters_applied: {"active": true}` (FR-007, FR-009), em tests/api/routers/test_user_profile.py
- [X] T023 [P] [US2] Com `active=false`, a listagem traz só cargos revogados e ecoa `filters_applied: {"active": false}` (FR-007, FR-009), em tests/api/routers/test_user_profile.py
- [X] T024 [P] [US2] Processo só com cargos revogados fica fora de `active=true` (FR-007), em tests/api/routers/test_user_profile.py
- [X] T025 [P] [US2] Processos saem pela designação mais recente do item, decrescente, e no empate de data pelo `id` do processo, crescente; `sort` vale `{"by": "last_assigned_at", "order": "desc"}` (FR-008, FR-009), em tests/api/routers/test_user_profile.py
- [X] T026 [P] [US2] Cargos de um item saem por `assigned_at` decrescente e, no empate, por `id` crescente (FR-008), em tests/api/routers/test_user_profile.py
- [X] T027 [P] [US2] Com três processos e `per_page=2`, a página 1 traz dois itens, a 2 traz um, e `total_items` é 3 mesmo com quatro designações (FR-009, SC-003), em tests/api/routers/test_user_profile.py
- [X] T028 [P] [US2] Página além da última traz `data: []` com os totais (FR-009), em tests/api/routers/test_user_profile.py
- [X] T029 [P] [US2] Designação com `deleted_at` preenchido não aparece em `active=true` nem em `active=false` (FR-010), em tests/api/routers/test_user_profile.py
- [X] T030 [P] [US2] Designação de processo com `deleted_at` preenchido não aparece (FR-010), em tests/api/routers/test_user_profile.py
- [X] T031 [P] [US2] Processo `CLOSED` aparece com `status: "CLOSED"` (edge case), em tests/api/routers/test_user_profile.py
- [X] T032 [P] [US2] Cargos de outra pessoa no mesmo processo não aparecem no item (isolamento), em tests/api/routers/test_user_profile.py
- [X] T033 [P] [US2] Conta sem designações recebe `data: []` e `total_items: 0`, tanto em `active=true` quanto em `active=false` (teste parametrizado pelo filtro; edge case), em tests/api/routers/test_user_profile.py
- [X] T034 [P] [US2] Sem sessão, `GET /users/{id}/process-roles` responde 401 (FR-014), em tests/api/routers/test_user_profile.py
- [X] T035 [P] [US2] Conta comum que consulta os cargos locais de outra conta existente recebe 403 `forbidden`, sem itens no corpo (FR-012), em tests/api/routers/test_user_profile.py
- [X] T036 [P] [US2] `user_id` sem formato UUID em `GET /users/{id}/process-roles` responde 422 `validation_error`, em tests/api/routers/test_user_profile.py
- [X] T037 [US2] Rodar T018 a T036 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que falham antes da implementação

### Implementation for User Story 2

- [X] T038 [US2] Criar `GET /users/{user_id}/process-roles` (`operation_id='listUserProcessRoles'`, `response_model=UserProcessRoleListResponse`) em src/pivma/routers/users.py, com `active: bool = True`, `PageQuery` e `PerPageQuery`. A rota chama `authorize_profile_read` antes de tudo e faz quatro passos:
  1. **Predicados comuns**: `Assignment.user_id == user_id`, `revoked_at` nulo ou não nulo conforme `active`, e join com `ProcessInstance`. O filtro global de exclusão lógica já tira as designações e os processos excluídos; os predicados não repetem `deleted_at`.
  2. **Página de processos**: `paginate_query` sobre `select(Assignment.process_instance_id)` com esses predicados e `group_by(Assignment.process_instance_id)`, com `order_by=(func.max(Assignment.assigned_at).desc(), Assignment.process_instance_id.asc())`.
  3. **Dados da página**: com os mesmos predicados e `process_instance_id` entre os da página, uma consulta traz as designações (ordem `assigned_at` desc, `id` asc) e outra os `ProcessInstance`. `laboratory_refs` traz os laboratórios.
  4. **Montagem**: os itens seguem a ordem da página, com `filters_applied=UserProcessRoleFilters(active=active)` e `sort=SortApplied(by='last_assigned_at', order='desc')`.

  `responses` descreve 401 e 403, sem `x-required-permission`.
- [X] T039 [US2] Rodar T018 a T036 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que passam

**Checkpoint**: as histórias 1 e 2 funcionam para a própria pessoa.

## Phase 4: User Story 3 - Administração consulta o perfil de outra pessoa (Priority: P2)

**Goal**: quem tem `users.read` vê o perfil e todos os cargos locais de
qualquer conta, ativa ou desativada, e recebe 404 para id inexistente.

**Independent Test**: como Administrador, abrir o perfil e os cargos de uma
conta achada em `GET /users`; como conta comum, receber 403.

### Tests for User Story 3

- [X] T040 [US3] Jornada `test_administrador_abre_perfil_de_pessoa_achada_na_listagem` em tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py:
  1. A pessoa se cadastra, entra, cria um processo e guarda o próprio perfil e os próprios cargos locais.
  2. O Administrador entra, acha a pessoa em `GET /users?search=` e abre o perfil e os cargos locais dela, que são iguais aos que a pessoa viu (SC-005).
  3. O Administrador desativa a conta com `DELETE /users/{id}`.
  4. Ele abre o perfil de novo e vê `active: false`; os cargos locais continuam listados.
  5. Uma segunda pessoa comum se cadastra, entra e tenta abrir o perfil do Administrador: recebe 403.
- [X] T041 [P] [US3] Conta com `profile_reader` consulta o perfil de outra conta e recebe 200 com os mesmos campos de T004 (FR-011), em tests/api/routers/test_user_profile.py
- [X] T042 [P] [US3] Conta com `profile_reader` consulta os cargos locais de outra conta e recebe todos os processos dela, inclusive um em que o leitor não participa nem gere participantes (FR-011), em tests/api/routers/test_user_profile.py
- [X] T043 [P] [US3] Conta com `profile_reader` consulta um UUID inexistente em `GET /users/{id}` e recebe 404 `not_found` (FR-013), em tests/api/routers/test_user_profile.py
- [X] T044 [P] [US3] Conta com `profile_reader` consulta um UUID inexistente em `GET /users/{id}/process-roles` e recebe 404 `not_found` (FR-013), em tests/api/routers/test_user_profile.py
- [X] T045 [P] [US3] Conta com `profile_reader` consulta uma conta desativada e recebe 200 com `active: false` (FR-013), em tests/api/routers/test_user_profile.py
- [X] T046 [P] [US3] Conta comum recebe resposta idêntica (status e corpo) para outra conta existente e para um UUID inexistente, em `GET /users/{id}` (SC-004), em tests/api/routers/test_user_profile.py
- [X] T047 [P] [US3] Conta comum recebe resposta idêntica (status e corpo) para outra conta existente e para um UUID inexistente, em `GET /users/{id}/process-roles` (SC-004), em tests/api/routers/test_user_profile.py
- [X] T048 [P] [US3] O OpenAPI publica `getUserProfile` e `listUserProcessRoles` com 401 e 403 documentados, e 404 documentado nas duas, em tests/api/routers/test_user_profile.py
- [X] T049 [US3] Rodar T040 a T048 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que falham antes da implementação

### Implementation for User Story 3

- [X] T050 [US3] Em `authorize_profile_read`, liberar também quem tem `users.read` (`has_permission(session, actor.id, USERS_READ)`), em src/pivma/routers/users.py
- [X] T051 [US3] Mover a leitura da conta de T016 para `_get_user_or_404(session, user_id)`, que responde 404 `not_found` ("Usuário não encontrado.") quando a conta não existe. As duas rotas chamam a função logo depois de `authorize_profile_read`. Acrescentar 404 em `responses` nas duas rotas, em src/pivma/routers/users.py
- [X] T052 [US3] Rodar T040 a T048 com `poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py` e confirmar que passam

**Checkpoint**: as três histórias funcionam de forma independente.

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T053 [P] Descrever as duas rotas, a regra de acesso (própria pessoa ou `users.read`) e a ausência de `username` no perfil em manual/guias/administrar-usuarios-e-acessos.md
- [X] T054 [P] Documentar a listagem `GET /users/{id}/process-roles` (filtro `active`, ordem por `last_assigned_at`, paginação por processo) em manual/referencia/listagens-e-referencias.md
- [X] T055 Rodar `poe lint`, `poe test` e `poe docs-build`. Confirmar que as suítes de usuários, autenticação e participantes passam sem asserção alterada (FR-016, SC-006) e que `git diff --stat develop -- migrations/ src/pivma/bootstrap_system.py` sai vazio, sem migração nem permissão nova (FR-017)
- [X] T056 Seguir specs/045-user-profile/quickstart.md contra a API local e marcar o Status de specs/045-user-profile/spec.md como Implemented

## Dependencies

- T001 e T002 precedem todas as histórias.
- US1 (T003 a T017) precede US2, porque T038 usa `authorize_profile_read` de T015.
- US3 depende de US1 e US2: T050 e T051 alteram a função e as duas rotas.
- Em cada história, a jornada e os testes focados vêm antes da implementação, e
  a tarefa "confirmar que falham" separa as duas partes.
- O Polish vem depois das três histórias.

## Parallel Example

Os testes focados [P] de cada história ficam no mesmo arquivo, mas cobrem
cenários independentes e podem ser escritos em qualquer ordem. T053 e T054 não
dependem um do outro. A jornada de cada história fica em outro arquivo e pode
ser escrita junto com os testes focados.

## Implementation Strategy

1. **MVP**: Foundational e US1. A pessoa vê o próprio perfil.
2. **US2**: cargos locais da própria pessoa. O frontend já monta a página de
   perfil inteira para a conta logada.
3. **US3**: abre o perfil para a administração e corrige a falta de
   `GET /users/{user_id}` apontada pelo frontend.
4. **Polish**: manual, suíte completa e quickstart.

## Coverage notes

- O limite de `per_page` (1 a 100) vem de `PerPageQuery`, que as listagens
  existentes já testam. A feature não cria teste repetido para ele.
- A contagem de consultas por requisição não ganha teste. O desenho dispensa
  laço por processo, e um teste de contagem amarraria a implementação.
- Não há teste de concorrência: as duas rotas só leem dados.
- Não há teste de auditoria nem de linha do tempo: a feature não escreve no
  banco.
