---
description: "Task list — Spec 014: Semântica BraCVAM e autorização da triagem"
---

# Tasks: Semântica BraCVAM e autorização da triagem

**Input**: `specs/014-bracvam-triage-authorization/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: incluídos — exigidos pela Constituição (Princípio IV) e por SC-009.

**Organization**: por user story (P1→P4), cada uma entregável e testável isolada.

## Status: 37/37 concluídas (2026-09-10)

- **US1**: perfil `bracvam` + permissão `triage.review`; migração `d3f9a1c47b28` (up/down verificados); guardas em `triage.py` (+`TrustedOrigin`) e `pre_evaluation.py`; seeds; `test_triage_authorization.py` (matriz) + `test_bracvam_rbac_migration.py`; ajustes em ~7 arquivos de teste existentes.
- **US2**: removidos `ai/pipeline.py`, `ai/steps/`, `_run_legacy_field_ai_mock`, endpoint `evaluate-ai`, campo `ai_evaluation` (2 schemas), 2 arquivos de teste; `contracts.py`/`log_service.py` podados; ramo "sem associações" → TRIAGE direto; demos `submission/` e `ai-pipeline/` ajustadas.
- **US3**: `evaluation_runs.evaluated_content_snapshot` (JSONB) + migração `e5c2f8a41d90`; captura em `_execute`; leitura com fallback; `test_evaluation_run_snapshot*.py`.
- **US4**: `test_log_grouping.py` + `test_pre_evaluation_observability.py` (fecha M4).
- **Suíte**: 530 passed, 1 skipped. `ruff` + `format` verdes.

## Format: `[ID] [P?] [Story] Descrição com caminho`

- **[P]**: paralelizável (arquivo distinto, sem dependência pendente)
- Trabalho segue em `develop` (padrão do projeto; a branch da feature é só rótulo)

---

## Phase 1: Setup

- [X] T001 Adicionar `TRIAGE_REVIEW = 'triage.review'` em `src/pivma/core/authorization.py`, junto de `AI_EVALUATIONS_READ`/`AI_EVALUATIONS_MANAGE`
- [X] T002 [P] Adicionar fixtures de RBAC em `tests/conftest.py`: incluir `'triage.review'` nos códigos concedidos a `ai_eval_admin`; nova fixture `bracvam_user` (perfil `system_key='bracvam'` + permissões `triage.review`, `ai_evaluations.read`, `ai_evaluations.manage`); nova fixture `non_triage_user` (perfil `system_key='management_group'`, sem permissões de triagem)

**Checkpoint**: constante e fixtures disponíveis.

---

## Phase 2: Foundational

**Nenhuma tarefa bloqueante compartilhada.** As user stories são independentes:
US1 traz a migração de RBAC, US3 a de snapshot, US2 e US4 não têm migração. Prossiga direto para a Phase 3.

---

## Phase 3: User Story 1 — Triagem restrita ao BraCVAM e à Administração (P1) 🎯 MVP

**Goal**: só os perfis `bracvam` e `administrator` conduzem a triagem (parecer de campo, decisão, consulta e feedback da pré-avaliação); Grupo Gestor e proponentes de outros processos são recusados; conflito de interesse mantém precedência.

**Independent Test**: `quickstart.md` Cenário A — percorrer a triagem completa como `triage_evaluator` (perfil BraCVAM); repetir como `mariana_gestora` (Grupo Gestor) e como proponente e confirmar 403 em cada ação.

### Testes US1

- [X] T003 [P] [US1] `tests/integration/migrations/test_bracvam_rbac_migration.py` — upgrade cria 1 `access_profile` (`bracvam`), 1 `permission` (`triage.review`) e 4 `access_profile_permissions`; downgrade remove tudo sem deixar órfãos (contagens antes/depois iguais ao baseline). Espelhar o estilo de `tests/integration/migrations/test_rbac_migration.py`
- [X] T004 [P] [US1] `tests/api/routers/test_triage_authorization.py` — matriz de `contracts/triage-authorization.md`: `bracvam_user` e `ai_eval_admin` → 200 em reviews/decision/GET pre-eval/feedback; `bracvam_user` com conflito de interesse vigente → 403 em feedback e decision, 200 no GET; `non_triage_user` (Grupo Gestor) → 403 nas quatro; usuário `reviewer` → 403 nas quatro; proponente ativo → 200 só no GET do próprio processo, 403 no resto e no GET de outro; usar `TRUSTED_ORIGIN`/header `Origin`

### Implementação US1

- [X] T005 [US1] Migração `migrations/versions/<rev>_bracvam_profile_triage_permission.py` — `down_revision` = a atual head. `upgrade`: inserir `access_profiles` (`id=UUID('00000000-0000-0000-0000-00000000000a')`, `system_key='bracvam'`, `name='BraCVAM'`, `description='Equipe do BraCVAM: coordena submissões e conduz a triagem de métodos candidatos.'`), `permissions` (`id=UUID('...010c')`, `code='triage.review'`, `description='Conduzir a triagem: parecer de campo, decisão, e ver/comentar a pré-avaliação por IA.'`), e `access_profile_permissions` com ids fixos para: `bracvam→triage.review`, `bracvam→ai_evaluations.read` (`...010a`), `bracvam→ai_evaluations.manage` (`...010b`), `administrator` (`...0009`)`→triage.review`. Colunas de auditoria via helper (ver `_audit_columns` em `8b701d7bfeae`). `downgrade` na ordem de `data-model.md` §1
- [X] T006 [US1] `src/pivma/routers/triage.py` — adicionar `Depends(require_permission(TRIAGE_REVIEW))` e `_origin: TrustedOrigin` a `submit_field_reviews` e `submit_triage_decision`; importar de `pivma.dependencies`/`pivma.core.authorization`
- [X] T007 [US1] `src/pivma/routers/pre_evaluation.py` — `_ensure_can_read`: substituir `is_effective_group_manager(...) or has_permission(..., AI_EVALUATIONS_READ)` por `has_permission(session, user_id, TRIAGE_REVIEW)` (mantendo o ramo `is_active_effective_proponent`); `record_feedback`: o check inline passa a `has_permission(session, current_user.id, TRIAGE_REVIEW)`; atualizar as mensagens `detail` (remover "gestores do BraCVAM" → "Apenas o BraCVAM registra feedback da pré-avaliação."); remover imports agora não usados (`is_effective_group_manager`, `AI_EVALUATIONS_READ`) se não houver outro uso no arquivo
- [X] T008 [US1] `scripts/seeds/seed_users.py` — `triage_evaluator` passa a receber `ensure_profile_by_name(session, evaluator.id, 'BraCVAM')` em vez de `'Revisor'`
- [X] T009 [US1] `scripts/seeds/seed_ai_evaluations.py` — remover `_grant_group_manager`, suas duas chamadas, o parâmetro `evaluator` de `_demo_process_in_triage` e o import `Assignment` se ficar sem uso; `run_seed_ai_evaluations` deixa de buscar `triage_evaluator`
- [X] T010 [US1] Ajustar testes existentes de triagem/pré-avaliação para o novo RBAC: `tests/api/routers/test_triage_decision.py`, `tests/api/routers/test_pre_evaluation_get.py`, `tests/api/routers/test_pre_evaluation_feedback.py`, `tests/api/routers/test_direct_review.py`, `tests/api/routers/test_pre_evaluation_submit.py` — autenticar as ações de triagem/feedback com `ai_eval_admin` (agora tem `triage.review`) ou `bracvam_user`; adicionar header `Origin` nas mutações de `triage.py`; qualquer teste que dependia de `group_manager` para ler a pré-avaliação passa a usar `triage.review`

**Checkpoint US1**: matriz de acesso da triagem fechada; `seed_all` roda; `[DEMO IA]` funciona sem o contorno `group_manager`.

---

## Phase 4: User Story 2 — Uma única esteira de avaliação por IA (P2)

**Goal**: remover a esteira mock da Spec 010; a pré-avaliação da Spec 013 é a única; formulário sem avaliações → triagem direta com relatório vazio; endpoint `evaluate-ai` deixa de existir.

**Independent Test**: `quickstart.md` Cenário B — submeter formulário sem avaliações → resposta sem `ai_evaluation`, processo em `TRIAGE`; `POST /forms/instances/{x}/evaluate-ai` → 404.

### Testes US2

- [X] T011 [P] [US2] Remover `tests/unit/test_ai_pipeline.py` e `tests/integration/test_form_ai_evaluation_api.py`
- [X] T012 [US2] `tests/api/routers/test_form_submission.py` — remover asserts de `ai_evaluation` na resposta; formulário sem avaliações → `status` do processo `TRIAGE`, `pre_evaluation` `null`, sem artefato de parecer; ajustar qualquer teste que valide `get_activity_form` com `ai_evaluation`

### Implementação US2

- [X] T013 [P] [US2] Excluir `src/pivma/ai/pipeline.py` e o diretório `src/pivma/ai/steps/` (inclui `context_extraction.py`, `mock_evaluation.py`, `verdict_synthesis.py`, `__init__.py`)
- [X] T014 [US2] `src/pivma/ai/contracts.py` — remover `AIEvaluationVerdict`, `PipelineContext`, `StepResult`; em `PipelineExecutionGroup` remover o campo `verdict` e trocar o default `pipeline_name` de `'form_ai_field_evaluation'` para `'form_ai_pre_evaluation'`
- [X] T015 [US2] `src/pivma/core/log_service.py` — remover o import de `AIEvaluationVerdict` e o bloco de extração de `verdict` (step `verdict_synthesis`) em `_build_pipeline_group`; `PipelineExecutionGroup(...)` deixa de passar `verdict`
- [X] T016 [US2] `src/pivma/core/process_engine.py` — remover `_run_legacy_field_ai_mock` e os imports `FormAIPipelineEngine`/`PipelineContext`; no `submit_proposal_form`, o ramo `else` (sem `EvaluationAssignment`) passa a apenas `await _unblock_triage_activity(...)` + `process.status = 'TRIAGE'` + `process.set_update_audit(user_id)` (o `AuditEvent('SUBMISSION_SUBMITTED')` já existe após o `if/else`); retorno segue 4-tupla `(act, current_run, artifact, None)`
- [X] T017 [US2] `src/pivma/routers/forms.py` — remover `direct_forms_router`, a rota `POST /instances/{instance_id}/evaluate-ai` e os imports `FormAIPipelineEngine`/`PipelineContext`; em `get_activity_form` remover a leitura de `art.metadata_payload['ai_evaluation']` e do artefato `key == 'ai_evaluation_report'`, e o kwarg `ai_evaluation=` do `FormInstanceResponse(...)`
- [X] T018 [US2] `src/pivma/__init__.py` — remover `app.include_router(forms.direct_forms_router)`
- [X] T019 [US2] `src/pivma/schemas.py` — remover `ai_evaluation` de `ActivityCompletionResponse` e de `FormInstanceResponse`
- [X] T020 [US2] `demos/submission/index.html` — em `renderTransition` remover o ramo `else if (data.ai_evaluation)`; remover a função `renderAiReportBox` e suas chamadas; ajustar `submitProposalForm` que ainda referencia `data.ai_evaluation`
- [X] T021 [US2] `demos/ai-pipeline/app.js` — remover o disparo via `POST /forms/instances/{id}/evaluate-ai` (bloco "disparar pipeline interativo") e os controles associados no HTML; o painel mantém o stream SSE e o agrupamento por `correlation_id`; texto passa a orientar disparar pela demo de submissão
- [X] T022 [P] [US2] Varredura: `grep -rn` por `evaluate-ai`, `FormAIPipelineEngine`, `_run_legacy_field_ai_mock`, `AIEvaluationVerdict`, `PipelineContext`, `StepResult`, `ai_evaluation_report`, `'ai_evaluation'` em `src/`, `tests/`, `demos/` — zero referências vivas (fora de artefatos históricos comentados)

**Checkpoint US2**: uma única esteira; `ruff` e `pytest` verdes; demos ajustadas.

---

## Phase 5: User Story 3 — Registro fiel do que a IA avaliou (P3)

**Goal**: snapshot imutável do conteúdo avaliado por execução; leitura prefere o snapshot; execuções antigas caem no fallback sem erro.

**Independent Test**: `quickstart.md` Cenário C — executar pré-avaliação, alterar a associação do template, reabrir → `evaluated_content` inalterado. Cenário D — execução com snapshot `NULL` → fallback funciona.

### Testes US3

- [X] T023 [P] [US3] `tests/integration/migrations/test_evaluation_run_snapshot_migration.py` — upgrade adiciona a coluna `evaluated_content_snapshot` a `evaluation_runs`; downgrade a remove; linhas de `evaluation_runs` preservadas em ambos
- [X] T024 [P] [US3] `tests/integration/database/test_evaluation_run_snapshot.py` — após `_execute`, `run.evaluated_content_snapshot` é uma lista `[{field_key,label,value}]` com os campos cobertos; alterar a associação/definição/remover o campo do template e reconsultar `get_pre_evaluation` → `evaluated_content` idêntico; execução com `evaluated_content_snapshot = None` → `get_pre_evaluation` retorna a reconstrução, sem erro
- [X] T025 [US3] `tests/api/routers/test_pre_evaluation_get.py::test_payload_carries_evaluated_content` — confirmar que continua verde pelo caminho do snapshot

### Implementação US3

- [X] T026 [US3] `src/pivma/core/database/models.py` — em `EvaluationRun`: `evaluated_content_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True, default=None)` (usar o mesmo import de `JSONB` já usado no arquivo)
- [X] T027 [US3] Migração `migrations/versions/<rev>_evaluation_run_content_snapshot.py` — `down_revision` = head após T005; `upgrade`: `op.add_column('evaluation_runs', sa.Column('evaluated_content_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))`; `downgrade`: `op.drop_column('evaluation_runs', 'evaluated_content_snapshot')`
- [X] T028 [US3] `src/pivma/core/pre_evaluation_service.py` — em `_execute`, imediatamente antes de `run.status = 'completed'`, gravar `run.evaluated_content_snapshot` com o conteúdo coberto pelas associações ativas (reaproveitar a lógica de `_evaluated_content`: extrair uma função pura `_content_fields(fields_by_key, values, assignments)` usada pelos dois caminhos, já que `_execute` tem `fields_by_key`/`values`/`assignments` em mãos)
- [X] T029 [US3] `src/pivma/core/pre_evaluation_service.py` — `get_pre_evaluation`: `evaluated_content = run.evaluated_content_snapshot if run.evaluated_content_snapshot is not None else await _evaluated_content(session, run)`

**Checkpoint US3**: snapshot gravado e servido; compatibilidade de execuções antigas garantida por teste.

---

## Phase 6: User Story 4 — Observabilidade da pré-avaliação (P4)

**Goal**: garantir por teste de regressão que as etapas de uma execução de pré-avaliação são agrupadas por `correlation_id`, com o formato atual (sem `verdict` legado).

**Independent Test**: `quickstart.md` Cenário E.

### Testes US4

- [X] T030 [P] [US4] `tests/unit/ai/test_log_grouping.py` — `log_service._build_pipeline_group` com uma lista de `AIStepExecutionLog` de `criterion_evaluation`: retorna `PipelineExecutionGroup` com `correlation_id`, `pipeline_name='form_ai_pre_evaluation'`, custo somado; nenhum campo `verdict`
- [X] T031 [P] [US4] `tests/integration/ai/test_pre_evaluation_observability.py` — rodar `pre_evaluation_service._execute` com `fake_provider`; consultar `LogQueryService.get_ai_pipeline_groups` (ou equivalente de `routers/admin_logs.py`) e asseverar que os steps da execução aparecem agrupados sob um único `correlation_id` (= `run.correlation_id`), com provedor e `models_used`; nenhuma entrada no formato `verdict_synthesis`

**Checkpoint US4**: observabilidade coberta; achado M4 da Spec 013 fechado.

---

## Phase 7: Polish & Cross-Cutting

- [X] T032 [P] `specs/013-configurable-ai-evaluation/spec.md` — nota em FR-022 de que a esteira legada foi removida na Spec 014 (débito fechado); `tasks.md` da 013 — T041 marcado como concluído pela Spec 014; registrar L1 do `/speckit-analyze` como fechado
- [X] T033 [P] `demos/DESIGN.md` §5 — refletir o perfil `BraCVAM` e a permissão `triage.review`; remover a nota de "restrição conhecida" sobre `group_manager`
- [X] T034 [P] `demos/RELATORIO-REVISAO-CICLO-IA.md` §6 — marcar Q1/Q3/Q5/M4 como entregues pela Spec 014; atualizar §3 (RBAC resolvido)
- [X] T035 [P] `README.md` — tabela de permissões de IA: acrescentar `triage.review`; remover menção residual a `evaluate-ai`/esteira legada, se houver
- [X] T036 `seed_all` roda limpo; migrações up/down verificadas na base de dev; validação curl da matriz de triagem contra `:8000`. Percurso visual dos Cenários A–F fica para a retestagem do usuário (mesmo padrão de T067/T073 da Spec 013).
- [X] T037 `ruff format --check` + `ruff check` verdes; `pytest` → **530 passed, 1 skipped**.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)**: sem dependências.
- **Phase 2 (Foundational)**: vazia.
- **US1 (P1)**: após Setup. Independente. **MVP.**
- **US2 (P2)**: após Setup. Independente de US1 (não compartilha arquivos além de `process_engine.py`/`__init__.py`, sem conflito lógico). Pode ser feita em paralelo a US1.
- **US3 (P3)**: após Setup. Independente. A migração de T027 encadeia após a de T005 (`down_revision`) — se US3 for antes de US1, ajustar a ordem das revisões.
- **US4 (P4)**: **depois de US2** (T014/T015 mudam o shape que T030/T031 verificam). Independente de US1 e US3.
- **Polish (Phase 7)**: após as user stories desejadas.

### Dentro de cada story

Testes escritos antes; falham; então implementação. Migração antes do código que a usa. `ruff`/`pytest` verdes ao fim de cada story (Princípio IV).

### Oportunidades de paralelismo

- T002/T003/T004 (fixtures e testes de US1) em paralelo entre si.
- US1 e US2 podem ser tocadas por pessoas diferentes; US3 idem. US4 aguarda US2.
- Dentro de US2, T011 e T013 são deleções independentes ([P]); T022 é a varredura final.

---

## Implementation Strategy

### MVP (só US1)

1. Phase 1 (Setup) → 2. US1 completa → 3. **Validar Cenário A do quickstart** → 4. Commit/demo.

O MVP já entrega a correção de segurança e de semântica (BraCVAM ≠ Grupo Gestor), que é a motivação da feature.

### Entrega incremental

US1 → US2 → US3 → US4, cada uma com `pytest` verde e commit próprio. US2 pode preceder US1 se conveniente (não há dependência real).

---

## Notes

- `[P]` = arquivos distintos, sem dependência pendente.
- Migrações: nome descritivo, teste de upgrade **e** downgrade (Constituição, Restrições).
- Skills `karpathy-guidelines` / `fastapi-testing-methodology` não instaladas neste ambiente — princípios aplicados manualmente (lacuna registrada no CLAUDE.md).
- Commit após cada task ou grupo lógico; parar em cada checkpoint para validar a story.
