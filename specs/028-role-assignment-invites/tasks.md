# Tasks: Atribuição de Cargo por Convite com Link Compartilhável

**Input**: Artefatos em `specs/028-role-assignment-invites/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/invites.openapi.yaml`, `quickstart.md`

**Tests**: Obrigatórios (convenção já estabelecida pelo projeto — ver `tasks.md` da Spec 006 e a skill `fastapi-testing-methodology`). Cada tarefa de teste cobre um único comportamento observável; parametrização é usada só quando varia a entrada sob o mesmo contrato.

**Organization**: As tarefas estão agrupadas pelas três histórias da spec. A Fase 2 (Fundação) cria só a superfície compartilhada (migração, modelo, autorização, motor, template, schemas) sem expor comportamento; cada história liga essa superfície a uma rota.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode ser executada em paralelo porque usa arquivo distinto e não depende de tarefa incompleta.
- **[Story]**: associa a tarefa a `US1`, `US2` ou `US3`.
- Tarefas de setup, fundação e polimento não recebem rótulo de história.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar só a superfície de módulo prevista no plano, sem implementar comportamento.

- [X] T001 Criar o router vazio (sem rotas) `src/pivma/routers/invites.py`, prefixo `''` (rotas próprias `/invites/...`, fora de `/processes`, conforme `plan.md`)
- [X] T002 Registrar `invites.router` em `src/pivma/__init__.py`, ao lado dos demais `app.include_router(...)`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Criar a tabela, o modelo, a autorização por papel, o gatilho de fechamento de etapa, o conteúdo do template e os schemas — nada disso expõe rota ainda.

**CRITICAL**: Nenhuma história deve ser implementada antes da conclusão desta fase.

### Tests for Foundational Persistence

> Escrever cada teste primeiro e confirmar que falha pela ausência da evolução correspondente.

- [X] T003 Testar F-M01: o upgrade cria a tabela `role_assignment_invites` com as colunas de `data-model.md §1` (`process_instance_id`, `role_key VARCHAR(64)`, `laboratory_id` nullable, `email VARCHAR(320) NOT NULL`, `channel VARCHAR(32) NOT NULL DEFAULT 'link'`, `token_hash VARCHAR(64) NOT NULL`, `status VARCHAR(16) NOT NULL DEFAULT 'pending'`, `expires_at NOT NULL`, `accepted_at`/`accepted_by`/`revoked_at`/`revoked_by` nullable, colunas de `AuditMixin`) em `tests/integration/migrations/test_role_assignment_invite_migration.py`
- [X] T004 Testar F-M02: o upgrade cria o índice único parcial `uq_role_assignment_invites_pending` em `(process_instance_id, role_key, email)` `WHERE status = 'pending' AND deleted_at IS NULL` em `tests/integration/migrations/test_role_assignment_invite_migration.py`
- [X] T005 Testar F-M03: o upgrade cria o índice único (não parcial) em `token_hash` em `tests/integration/migrations/test_role_assignment_invite_migration.py`
- [X] T006 Testar F-M04: o upgrade cria as FKs de `process_instance_id`, `laboratory_id`, `created_by`, `accepted_by`, `revoked_by` para suas tabelas de origem em `tests/integration/migrations/test_role_assignment_invite_migration.py`
- [X] T007 Testar F-M05: o downgrade remove somente a tabela e os índices desta feature, preservando `assignments`/`activity_instances`/`process_instances` intactos, em `tests/integration/migrations/test_role_assignment_invite_migration.py`
- [X] T008 Testar F-D01 em PostgreSQL real: duas linhas `status='pending'` para o mesmo `(process_instance_id, role_key, email)` são rejeitadas pelo índice único parcial em `tests/integration/database/test_role_assignment_invite_constraints.py`
- [X] T009 Testar F-D02 em PostgreSQL real: duas linhas `pending` para o mesmo `(processo, papel)` com e-mails diferentes são aceitas — sem titularidade única, FR-019 — em `tests/integration/database/test_role_assignment_invite_constraints.py`
- [X] T010 Testar F-D03 em PostgreSQL real: revogar uma linha `pending` e criar outra para o mesmo `(processo, papel, e-mail)` é aceito (a revogada não conta para o índice parcial) em `tests/integration/database/test_role_assignment_invite_constraints.py`
- [X] T011 Testar F-D04 em PostgreSQL real: `laboratory_id` inexistente é rejeitado pela FK em `tests/integration/database/test_role_assignment_invite_constraints.py`
- [X] T012 Testar F-D05 em PostgreSQL real: `token_hash` duplicado entre dois convites de processos diferentes é rejeitado pelo índice único (não parcial) em `tests/integration/database/test_role_assignment_invite_constraints.py`

### Implementation for Foundational Persistence

- [X] T013 Implementar upgrade/downgrade da tabela `role_assignment_invites` (DDL puro, encadeada após o head atual `fa506675d3f9`) com todas as colunas, os dois índices únicos e as FKs de `data-model.md §1`, em `migrations/versions/<hash>_role_assignment_invites.py`
- [X] T014 [P] Adicionar a classe mapeada `RoleAssignmentInvite(AuditMixin)` em `src/pivma/core/database/models.py`, com `status` restrito a `'pending'|'accepted'|'revoked'` na camada de aplicação (sem CHECK de banco, mesmo padrão de `role_key` em `Assignment`) e o índice único parcial via `__table_args__` (mesmo padrão de `Assignment`, `models.py:1001-1011`)
- [X] T015 [P] Criar `InviteFactory` (mesmo padrão de `AssignmentFactory`, `tests/factories/participant_factory.py`: `Params` com `process`/`laboratory`, `lazy_attribute` para as FKs, `status='pending'` e `expires_at` padrão de 1h à frente) em `tests/factories/invite_factory.py`
- [X] T016 [P] Exportar `InviteFactory` em `tests/factories/__init__.py`
- [X] T017 [P] Adicionar `INVITE_EXPIRATION_HOURS: int = Field(default=1)` em `src/pivma/core/settings.py` (mesmo padrão de `ATTACHMENT_MAX_SIZE_MB`, FR-008)
- [X] T018 [P] Implementar `generate_invite_token() -> str` (`secrets.token_urlsafe(32)`) e `hash_invite_token(token: str) -> str` (`hashlib.sha256(token.encode()).hexdigest()`) em `src/pivma/core/invite_service.py` (research.md R1)
- [X] T019 [P] Implementar `PROPONENT_MANAGEABLE_ROLE_KEYS = frozenset({'sponsor', 'group_manager'})` e `async def can_manage_role_assignment(session, user_id, process_id, role_key) -> bool` (compõe `can_manage_participants` e `is_active_effective_proponent`, ver `data-model.md §6`) em `src/pivma/core/authorization.py`
- [X] T020 Implementar `async def _maybe_close_role_assignment_activity(session, process, role_key, user_id)` em `src/pivma/core/process_engine.py`: resolve a `ActivityInstance` cujo `a_data['activity_type'] == 'role_assignment' and a_data.get('target_role_key') == role_key` a partir do `definition_payload` já carregado (mesmo padrão de `_advance_dependent_activities`); no-op se não encontrar, se já `COMPLETED`, ou se `get_current_activity_run` levantar `NotFoundError` (ainda `BLOCKED`); não fecha se existir `RoleAssignmentInvite` com `status='pending'` para `(process_id, role_key)` (FR-017); senão chama `_complete_activity_run` + `_advance_dependent_activities` (research.md R4)
- [X] T021 [P] Adicionar as 8 atividades `activity_type: "role_assignment"` na fase de Planejamento do template — chave, `assigned_role` (executor), `target_role_key` (papel concedido) e dependências exatamente como a tabela de `data-model.md §4` — em `src/pivma/templates_data/04_validated_method_dossier.yaml` (nova `version` incrementada; decidir em code review se substitui ou estende a Fase 2 placeholder da Spec 017)
- [X] T022 [P] Implementar `InviteCreate` (`email: EmailStr` obrigatório, `role_key: ParticipantRole`, `laboratory_id` com o mesmo validador condicional de `ParticipantAssignmentCreate`, `channel: Literal['link'] = 'link'`), `InvitePublic`, `InviteCreatedResponse` (`InvitePublic` + `token`), `InvitePreview`, `InviteAcceptResponse` em `src/pivma/schemas.py` (`data-model.md §7`)

**Checkpoint**: tabela, modelo, autorização, gatilho de fechamento, template e schemas existem; nenhuma rota ainda expõe comportamento.

---

## Phase 3: User Story 1 - Preencher um papel do processo com alguém que já tem conta (Priority: P1) 🎯 MVP

**Goal**: Designação direta (Spec 006, inalterada) para os 8 papéis, com a nova matriz de autorização por papel (Proponente ganha `sponsor`/`group_manager`), fecha sozinha a etapa `role_assignment` correspondente e destrava as dependentes.

**Independent Test**: Um Proponente efetivo designa um usuário ativo para `group_manager`; a etapa "Definir os integrantes do Grupo Gestor" some das pendências abertas do roteiro sem nenhuma ação manual de "concluir", e as etapas que dependiam dela saem de `BLOCKED`.

### Tests for User Story 1

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história.
>
> **Nota de execução**: o projeto não tem convenção de chamar `process_engine`
> diretamente com uma sessão nua para exercitar o ciclo de vida completo do
> processo (submissão → triagem) — só via API (`tests/api/routers/`). Por
> isso T027-T029 e T033/T035/T036 (que precisam de um processo real na Fase
> 2) foram implementadas em `tests/api/routers/test_participant_router.py`,
> não em `tests/integration/database/test_role_assignment_activity_closure.py`
> como o caminho original sugeria — mesmo comportamento coberto, camada
> ajustada à convenção real do repositório.

- [X] T023 [US1] Testar U-A01: `can_manage_role_assignment` — permissão global (`process.participants.manage`) autoriza qualquer um dos 8 papéis, parametrizado, em `tests/unit/core/test_role_assignment_authorization.py`
- [X] T024 [US1] Testar U-A02: `group_manager` efetivo do processo autoriza qualquer um dos 8 papéis, parametrizado, em `tests/unit/core/test_role_assignment_authorization.py`
- [X] T025 [US1] Testar U-A03: Proponente efetivo autoriza somente `sponsor`/`group_manager`; os outros 6 papéis são negados para o mesmo usuário, parametrizado, em `tests/unit/core/test_role_assignment_authorization.py`
- [X] T026 [US1] Testar U-A04: usuário sem nenhuma das três autorizações é negado para os 8 papéis, parametrizado, em `tests/unit/core/test_role_assignment_authorization.py`
- [X] T027 [US1] Testar I-E01 em PostgreSQL real: designar diretamente para um papel com etapa `role_assignment` pendente e sem convite emitido fecha essa etapa e destrava as dependentes (`ACTIVITY_UNBLOCKED`) em `tests/integration/database/test_role_assignment_activity_closure.py`
- [X] T028 [US1] Testar I-E02 em PostgreSQL real: uma segunda designação para um papel cuja etapa já está `COMPLETED` não reprocessa a conclusão (idempotência — nenhum `ACTIVITY_UNBLOCKED` duplicado) em `tests/integration/database/test_role_assignment_activity_closure.py`
- [X] T029 [US1] Testar I-E03 em PostgreSQL real: designar um papel sem etapa `role_assignment` declarada na versão do template do processo não falha — apenas não fecha nada em `tests/integration/database/test_role_assignment_activity_closure.py`
- [X] T030 [US1] Testar A-P01 via TestClient: Proponente efetivo designa usuário ativo para `sponsor` e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T031 [US1] Testar A-P02 via TestClient: Proponente efetivo designa usuário ativo para `group_manager` e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T032 [US1] Testar A-P03 via TestClient: Proponente tenta designar para `statistician` (fora de `sponsor`/`group_manager`) e recebe 403 em `tests/api/routers/test_participant_router.py`
- [X] T033 [US1] Testar A-P04 via TestClient: depois da designação de `group_manager`, `GET /tasks?process_id={id}` deixa de listar a tarefa da etapa "Definir os integrantes do Grupo Gestor" como pendente (status `COMPLETED`) em `tests/api/routers/test_participant_router.py`
- [X] T034 [US1] Testar A-P05 via TestClient: duas designações ativas simultâneas para o mesmo papel (dois usuários diferentes) são aceitas — sem titularidade única, FR-019 — em `tests/api/routers/test_participant_router.py`
- [X] T035 [US1] Testar A-P06 via TestClient: revogar uma designação de `sponsor`/`group_manager` também usa `can_manage_role_assignment` — Proponente efetivo consegue revogar a própria designação nesses dois papéis em `tests/api/routers/test_participant_router.py`
- [X] T036 [P] [US1] Testar A-R03: a suíte de regressão já existente da Spec 006 (`tests/api/routers/test_participant_router.py`, `test_participant_security.py`, `test_participant_task_blocking.py`) permanece com as mesmas asserções e resultados (SC-008) — nenhuma alteração de comportamento para quem já tinha `group_manager` ou permissão global

### Implementation for User Story 1

- [X] T037 [US1] Substituir a checagem `can_manage_participants(session, current_user.id, process_id)` por `can_manage_role_assignment(session, current_user.id, process_id, payload.role_key)` em `create_participant` (`POST /processes/{process_id}/participants`) em `src/pivma/routers/process_participants.py`
- [X] T038 [US1] Aplicar a mesma substituição em `revoke_participant` (`DELETE /processes/{process_id}/participants/{assignment_id}`), resolvendo `role_key` a partir da `Assignment` encontrada antes da checagem, em `src/pivma/routers/process_participants.py`
- [X] T039 [US1] Chamar `_maybe_close_role_assignment_activity(session, process, payload.role_key, current_user.id)` ao final de `create_participant`, na mesma transação da designação e do `AuditEvent` `PARTICIPANT_ASSIGNED`, em `src/pivma/routers/process_participants.py`

**Checkpoint**: US1 funciona como MVP — designação direta para os 8 papéis, com a nova matriz de autorização, fecha a etapa do roteiro sozinha. Testável sem nenhum convite.

---

## Phase 4: User Story 2 - Convidar por link alguém que ainda não tem conta (Priority: P1)

**Goal**: Gerar um convite de uso único sempre associado a um e-mail; ao ser aceito por uma sessão autenticada com o mesmo e-mail, concede o papel pelo mesmo mecanismo de designação direta e fecha a etapa quando aplicável.

**Independent Test**: Criar convite para um e-mail sem conta, cadastrar uma conta nova com esse e-mail (endpoint de Spec 001 inalterado), aceitar o convite autenticado e confirmar a designação criada e a etapa fechada.

### Tests for User Story 2

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história.

- [X] T040 [US2] Testar U-I01: `InviteCreate` rejeita `channel` fora de `'link'` em `tests/unit/schemas/test_invite_schemas.py`
- [X] T041 [US2] Testar U-I02: `InviteCreate` rejeita `laboratory_id` ausente para `lead_laboratory`/`participating_laboratory`, parametrizado pelos dois papéis, em `tests/unit/schemas/test_invite_schemas.py`
- [X] T042 [US2] Testar U-I03: `InviteCreate` rejeita `laboratory_id` presente para os 6 papéis não laboratoriais, parametrizado, em `tests/unit/schemas/test_invite_schemas.py`
- [X] T043 [US2] Testar U-I04: `InviteCreate` rejeita e-mail malformado e rejeita corpo sem `email` em `tests/unit/schemas/test_invite_schemas.py`
- [X] T044 [US2] Testar U-T01: `hash_invite_token` é determinístico (mesma entrada → mesmo hash) e `generate_invite_token` produz valores distintos a cada chamada em `tests/unit/core/test_invite_token.py`
- [X] T045 [US2] Testar A-I01 via TestClient: pessoa autorizada para o papel cria convite e recebe 201 com `token` bruto presente só nesta resposta (nunca em `GET`) em `tests/api/routers/test_invites_router.py`
- [X] T046 [US2] Testar A-I02 via TestClient: pessoa sem autorização para o `role_key` do convite recebe 403 ao criar em `tests/api/routers/test_invites_router.py`
- [X] T047 [US2] Testar A-I03 via TestClient: segundo convite `pending` para o mesmo `(processo, papel, e-mail)` recebe 409 (índice único parcial) em `tests/api/routers/test_invites_router.py`
- [X] T048 [US2] Testar A-I04 via TestClient: convite para papel de laboratório sem `laboratory_id`, ou com laboratório sem vínculo institucional vigente do e-mail associado (quando aplicável na criação), recebe 422/409, parametrizado pela causa, em `tests/api/routers/test_invites_router.py`
- [X] T049 [US2] Testar A-I05 via TestClient: criar convite em processo logicamente excluído ou em status imutável recebe 409 em `tests/api/routers/test_invites_router.py`
- [X] T050 [US2] Testar A-I06 via TestClient: `GET /processes/{id}/participants/invites` retorna só os convites cujo `role_key` o usuário autenticado tem autorização para gerir em `tests/api/routers/test_invites_router.py`
- [X] T051 [US2] Testar A-V01 via TestClient: `GET /invites/{token}` sem autenticação devolve pré-visualização com e-mail mascarado em `tests/api/routers/test_invite_acceptance.py`
- [X] T052 [US2] Testar A-V02 via TestClient: `GET /invites/{token}` com token inexistente ou já aceito/revogado recebe 404 em `tests/api/routers/test_invite_acceptance.py`
- [X] T053 [US2] Testar A-V03 via TestClient: `GET /invites/{token}` de convite pendente e expirado devolve `expired: true` (não 404 — FR-009 exige informar, não esconder) em `tests/api/routers/test_invite_acceptance.py`
- [X] T054 [US2] Testar A-A01 via TestClient: aceite com sessão cujo e-mail bate com o do convite cria a `Assignment` e recebe 200 com `assignment_id` em `tests/api/routers/test_invite_acceptance.py`
- [X] T055 [US2] Testar A-A02 via TestClient: aceite com e-mail de sessão diferente do convite recebe 403 e não altera `status`/`accepted_at` do convite em `tests/api/routers/test_invite_acceptance.py`
- [X] T056 [US2] Testar A-A03 via TestClient: aceite de convite expirado (`pending` mas `expires_at` no passado) recebe 409 em `tests/api/routers/test_invite_acceptance.py`
- [X] T057 [US2] Testar A-A04 via TestClient: aceite de convite já `accepted` ou `revoked` recebe 409, parametrizado pelo estado em `tests/api/routers/test_invite_acceptance.py`
- [X] T058 [US2] Testar A-A05 via TestClient: aceite para papel de laboratório sem vínculo institucional vigente do usuário autenticado recebe 409 e o convite permanece `pending` em `tests/api/routers/test_invite_acceptance.py`
- [X] T059 [US2] Testar A-A06 via TestClient: aceite bem-sucedido grava `INVITE_ACCEPTED` e `PARTICIPANT_ASSIGNED` na mesma transação, ambos consultáveis via timeline do processo (Spec 006) em `tests/api/routers/test_invite_acceptance.py`
- [X] T060 [US2] Testar A-A07 via TestClient: aceite de um convite fecha a etapa `role_assignment` correspondente quando não sobrar nenhum outro convite `pending` para o papel; permanece aberta se sobrar outro convite `pending` (FR-017) em `tests/api/routers/test_invite_acceptance.py`
- [X] T061 [P] [US2] Testar A-X02 em PostgreSQL real: dois aceites concorrentes do mesmo `token` resultam em um 200 e um 409, com uma única `Assignment` criada e o convite terminando `accepted` uma única vez, em `tests/api/routers/test_participant_concurrency.py`

### Implementation for User Story 2

- [X] T062 [P] [US2] Implementar `async def create_invite(session, process, payload, actor_id) -> RoleAssignmentInvite` em `src/pivma/core/invite_service.py`: valida processo ativo/mutável e laboratório ativo (quando o papel exigir, sem checar vínculo institucional ainda — ninguém está identificado por usuário nesse momento), gera token/hash/`expires_at` (`INVITE_EXPIRATION_HOURS`), grava a linha e o `AuditEvent` `INVITE_CREATED`
- [X] T063 [US2] Extrair de `create_participant` a validação/criação de `Assignment` (usuário ativo, laboratório ativo, vínculo institucional vigente, duplicidade) para uma função reaproveitável (ex. `_create_assignment_or_raise`) em `src/pivma/routers/process_participants.py` ou `src/pivma/core/participant_service.py`, sem alterar o contrato/comportamento observável de `POST /processes/{process_id}/participants`
- [X] T064 [US2] Implementar `async def accept_invite(session, token, current_user) -> Assignment` em `src/pivma/core/invite_service.py`: busca por `hash_invite_token(token)`, valida `status='pending'` e `expires_at` não vencido, compara `current_user.email` com `invite.email` (403 se diferente), reaproveita a função do T063 para criar a `Assignment`, marca o convite `accepted`, grava `INVITE_ACCEPTED`, chama `_maybe_close_role_assignment_activity`
- [X] T065 [US2] Implementar `POST /processes/{process_id}/participants/invites` e `GET /processes/{process_id}/participants/invites` em `src/pivma/routers/process_participants.py`, usando `can_manage_role_assignment` na criação e filtrando a listagem por papel autorizado por item
- [X] T066 [US2] Implementar `GET /invites/{token}` (público, sem `CurrentUser`, e-mail mascarado) e `POST /invites/{token}/accept` (exige `CurrentUser` + `TrustedOrigin`) em `src/pivma/routers/invites.py`, chamando `invite_service.accept_invite`

**Checkpoint**: US1 + US2 funcionam juntas — convite por link preenche papel sem exigir designação manual, sem tocar nos endpoints de cadastro/login (Spec 001/002).

---

## Phase 5: User Story 3 - Reenviar ou revogar um convite pendente (Priority: P2)

**Goal**: Quem tem autorização para o papel-alvo renova o prazo de um convite pendente (novo token, prazo novo, mesma identidade) ou o revoga, enquanto a etapa correspondente não tiver se encerrado.

**Independent Test**: Reenviar um convite expirado e confirmar que o link renovado funciona; revogar um convite pendente e confirmar que o link antigo para de conceder o papel.

### Tests for User Story 3

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história.

- [X] T067 [US3] Testar A-N01 via TestClient: reenvio por quem tem autorização gera novo `token`, novo `expires_at`, e recebe 200 em `tests/api/routers/test_invites_router.py`
- [X] T068 [US3] Testar A-N02 via TestClient: o `token` anterior ao reenvio passa a receber 404 em `GET /invites/{token_antigo}` em `tests/api/routers/test_invite_acceptance.py`
- [X] T069 [US3] Testar A-N03 via TestClient: reenvio de convite já `accepted`/`revoked` recebe 409, parametrizado pelo estado, em `tests/api/routers/test_invites_router.py`
- [X] T070 [US3] Testar A-N04 via TestClient: reenvio depois que a etapa `role_assignment` correspondente já se encerrou recebe 409 em `tests/api/routers/test_invites_router.py`
- [X] T071 [US3] Testar A-N05 via TestClient: revogação por quem tem autorização marca `status='revoked'`, `revoked_at`/`revoked_by`, e recebe 200 em `tests/api/routers/test_invites_router.py`
- [X] T072 [US3] Testar A-N06 via TestClient: com dois convites `pending` para o mesmo papel, aceitar um e revogar o outro fecha a etapa (FR-017 — nenhum `pending` restante, ao menos uma designação ativa) em `tests/api/routers/test_invites_router.py`
- [X] T073 [US3] Testar A-N07 via TestClient: pessoa sem autorização para o `role_key` do convite recebe 403 ao reenviar ou revogar, parametrizado pela ação, em `tests/api/routers/test_invites_router.py`
- [X] T074 [US3] Testar A-N08 via TestClient: reenvio e revogação sem `Origin` confiável (`AUTH_ALLOWED_ORIGINS`) recebem 403, parametrizado pela ação, em `tests/api/routers/test_invites_router.py`

### Implementation for User Story 3

- [X] T075 [US3] Implementar `async def resend_invite(session, invite, actor_id) -> RoleAssignmentInvite` em `src/pivma/core/invite_service.py`: rejeita se `status != 'pending'`; gera novo token/hash/`expires_at` na mesma linha (não cria nova linha, research.md R2); grava `INVITE_RESENT` com `previous_expires_at`/`new_expires_at`
- [X] T076 [US3] Implementar `async def revoke_invite(session, invite, actor_id) -> RoleAssignmentInvite` em `src/pivma/core/invite_service.py`: rejeita se `status != 'pending'`; grava `revoked_at`/`revoked_by` e o `AuditEvent` `INVITE_REVOKED`
- [X] T077 [US3] Implementar `POST /processes/{process_id}/participants/invites/{invite_id}/resend` e `POST .../{invite_id}/revoke` em `src/pivma/routers/process_participants.py`, usando `can_manage_role_assignment(role_key_do_convite)`; a revogação chama `_maybe_close_role_assignment_activity` em seguida (pode ser o gatilho que finalmente fecha a etapa, T072)

**Checkpoint**: as três histórias funcionam de ponta a ponta, cada uma independentemente testável.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [X] T078 [P] Estender o seed do roteiro (Issue #23: seed a estender) com um processo na fase de Planejamento, um usuário Proponente e um usuário BraCVAM autenticáveis, em `scripts/seeds/` (novo script ou extensão do existente, seguindo o padrão de `scripts/seeds/seed_*.py` e registrado em `seed_all.py`)
- [X] T079 (removida — a demo estática `demos/` foi descartada pelo usuário; não desenvolver demos)
- [X] T080 [P] Atualizar `docs/domain/rbac.md` com a nova capacidade do Proponente sobre `sponsor`/`group_manager` na Matriz de Governança RBAC
- [X] T081 Executar os 18 passos de `quickstart.md` manualmente contra a API real (não mocada) e confirmar o critério de conclusão
- [X] T082 Rodar a suíte completa (`poe test`) e confirmar 100% verde — regressão explícita da Spec 006 (SC-008) e não interferência com os demais `activity_type` da Spec 017/026
- [X] T083 Rodar `ruff` e `typos` sobre todos os arquivos tocados por esta feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA as três histórias.
- **User Stories (Phase 3-5)**: todas dependem da conclusão da Fase 2.
  - US1 (P1) não depende de US2/US3 — é o MVP.
  - US2 (P1) depende de US1 estar implementada o bastante para `_maybe_close_role_assignment_activity`/`can_manage_role_assignment` existirem (Fase 2), mas não depende das rotas de US1 em si — pode ser desenvolvida em paralelo por outra pessoa depois da Fase 2.
  - US3 (P2) depende do modelo/serviço de convite existir (US2) — não é independente de US2 como US1/US2 são entre si (reenviar/revogar um convite exige que convites já possam ser criados).
- **Polish (Final Phase)**: depende das três histórias desejadas estarem completas.

### Dentro de cada história

- Testes (obrigatórios) escritos e falhando antes da implementação.
- Modelo/serviço antes de rota.
- US1 completa antes de validar US2 (US2 reaproveita a designação criada por US1 no aceite).

### Parallel Opportunities

- Todas as tarefas `[P]` da Fase 2 (T014-T019, T021-T022) tocam arquivos distintos e podem rodar em paralelo depois de T013 (migração).
- Dentro de cada história, as tarefas de teste marcadas `[P]` (arquivos de regressão/concorrência) podem rodar em paralelo com o resto da fase de testes daquela história.
- US2 e US3 podem ser feitas por pessoas diferentes depois que a Fase 2 e a Fase 3 (US1) estiverem concluídas, já que US3 só precisa do serviço de convite que US2 cria — não pode começar antes de US2.

---

## Parallel Example: Foundational

```bash
# Depois de T013 (migração), em paralelo:
Task: "Adicionar RoleAssignmentInvite em src/pivma/core/database/models.py"
Task: "Adicionar INVITE_EXPIRATION_HOURS em src/pivma/core/settings.py"
Task: "Implementar generate_invite_token/hash_invite_token em src/pivma/core/invite_service.py"
Task: "Implementar can_manage_role_assignment em src/pivma/core/authorization.py"
Task: "Adicionar as 8 atividades role_assignment no template YAML"
Task: "Implementar InviteCreate/InvitePublic/... em src/pivma/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Fase 1: Setup.
2. Completar Fase 2: Foundational (CRÍTICO — bloqueia as três histórias).
3. Completar Fase 3: US1.
4. **PARAR e VALIDAR**: designação direta para os 8 papéis, com a nova matriz de
   autorização, fecha a etapa do roteiro sozinha — testável sem nenhum convite.
5. Validar via API real antes de prosseguir.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → testar independentemente (MVP).
3. US2 → testar independentemente (inclui US1 como pré-condição de cenário, não de
   código).
4. US3 → testar independentemente.
5. Polish → seeds, docs, `quickstart.md`, regressão completa.

### Notas

- `[P]` = arquivos diferentes, sem dependência entre si.
- Cada história deve ser completável e testável de forma independente.
- Confirmar que cada teste falha antes de implementar.
- Rodar `poe test` (ou o arquivo específico) depois de cada tarefa de implementação, não
  só ao final da fase.
- Parar em qualquer checkpoint para validar a história isoladamente antes de seguir.
