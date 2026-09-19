# Tasks: 026 - Regra de Consolidação: Todos os Campos Conformes para Avançar à Triagem

**Branch**: `026-all-fields-compliant-routing` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Input**: Design documents from `specs/026-all-fields-compliant-routing/` (plan.md, research.md, data-model.md, contracts/consolidation-rule.md, quickstart.md)

**Tests**: Incluídos. A mudança altera uma regra de negócio de risco **Alto** (roteamento automático triagem/proponente), o que exige, pela metodologia de testes do projeto, cobertura nas camadas Unit + Integration + API.

---

## Phase 1: Setup

**Purpose**: Confirmar baseline verde antes de alterar a regra de negócio

- [x] T001 Rodar `poetry run pytest tests/unit/ai/test_consolidation.py tests/integration/ai/test_run_pre_evaluation.py tests/api/routers/test_pre_evaluation_get.py tests/api/routers/test_direct_review.py -v` e confirmar 100% verde antes de qualquer alteração

---

## Phase 2: Foundational (Nova regra de consolidação — bloqueia todas as user stories)

**Purpose**: Implementar a mudança de regra em si; todas as user stories dependem desta função

**⚠️ CRITICAL**: Nenhuma task de user story pode ser validada antes desta fase estar completa

- [x] T002 Reescrever `_is_blocking` em `src/pivma/ai/consolidation.py` para `return item.conclusion != 'compliant'` (bloqueia `non_compliant`, `partial` e `indeterminate`; remove a checagem de `item.severity in BLOCKING_SEVERITIES`), e atualizar o docstring do módulo (linhas 1–12) para descrever a nova regra "positivo somente se todos os critérios forem `compliant`" (FR-001, FR-002, FR-003)
- [x] T003 [P] Remover a constante `BLOCKING_SEVERITIES` (linha 24, não mais utilizada após T002) em `src/pivma/ai/consolidation.py`; manter `SEVERITY_ORDER` intacto (fora de escopo desta feature)

**Checkpoint**: `consolidate()` implementa a regra "todos conformes"; as user stories abaixo passam a ser testes de regressão/aceite sobre essa mudança.

---

## Phase 3: User Story 1 - Submissão só chega à triagem quando 100% conforme (Priority: P1) 🎯 MVP

**Goal**: O resultado consolidado da pré-avaliação é positivo se e somente se todos os critérios forem `compliant`; qualquer `non_compliant`, `partial` ou `indeterminate`, de qualquer severidade, torna o resultado negativo.

**Independent Test**: Submeter um formulário com um único critério `non_compliant` de severidade **baixa** (resto `compliant`) e confirmar que a submissão não avança para a triagem.

### Tests for User Story 1

- [x] T004 [P] [US1] Em `tests/unit/ai/test_consolidation.py`, renomear `test_low_and_medium_non_conformities_stay_positive_as_alerts` para `test_low_and_medium_non_conformities_now_block` e ajustar a asserção para `result.result == 'negative'` (prova FR-001)
- [x] T005 [P] [US1] Em `tests/unit/ai/test_consolidation.py`, renomear `test_only_indeterminate_is_positive` para `test_only_indeterminate_is_negative` e ajustar para `result.result == 'negative'` e `result.alerts == [False, False]` (prova FR-003)
- [x] T006 [P] [US1] Em `tests/unit/ai/test_consolidation.py`, renomear `test_partial_does_not_block_and_is_alerted` para `test_partial_blocks_and_is_not_alerted` e ajustar para `result.result == 'negative'` e `result.alerts == [False]` (prova FR-001)
- [x] T007 [P] [US1] Adicionar `test_single_low_severity_non_compliant_among_compliant_blocks` em `tests/unit/ai/test_consolidation.py`: vários critérios `compliant` + um único `non_compliant` de severidade `low` → `result.result == 'negative'` (Acceptance Scenario 1.2). Também ajustado `test_blocking_item_is_not_flagged_as_mere_alert` (alerts agora `[False, False]`) e adicionado `test_all_compliant_is_positive` como prova direta do caminho positivo (FR-001)
- [x] T008 [US1] Adicionar parâmetro `target_type: str = 'field'` em `publish_evaluation_and_assign` (`tests/ai_eval_helpers.py`), repassando-o para o campo `target_type` do payload de `PUT /form-templates/{template}/evaluation-assignments` (hoje fixo em `'field'`), permitindo `target_type='document'` nos testes
- [x] T009 [US1] Adicionar `test_low_severity_non_compliant_now_routes_negative` em `tests/integration/ai/test_run_pre_evaluation.py` usando `severity='low'` e `NON_COMPLIANT_STATEMENT`: confirmar `run.consolidated_result == 'negative'` e `process.status == 'SUBMISSION'` (mudança de comportamento fim a fim vs. Spec 013) (depende de T002)
- [x] T010 [US1] Adicionar `test_document_target_indeterminate_routes_negative` em `tests/integration/ai/test_run_pre_evaluation.py` usando `target_type='document'` (via T008): confirmar que o critério conclui `indeterminate` e `run.consolidated_result == 'negative'`, mesmo sem nenhum critério `non_compliant` (Edge Case "campo do tipo documento") (depende de T002, T008)

**Checkpoint**: User Story 1 completa e testável isoladamente — a regra "todos conformes" está implementada e coberta em unit + integration.

---

## Phase 4: User Story 2 - Proponente entende exatamente por que a submissão voltou (Priority: P2)

**Goal**: A síntese da pré-avaliação identifica qualquer critério não conforme (de qualquer severidade) como motivo do bloqueio, com a mesma evidência/justificativa/recomendação já fornecidas hoje.

**Independent Test**: Provocar um retorno negativo causado exclusivamente por um critério de severidade baixa e confirmar que `GET /processes/{id}/pre-evaluation` lista esse critério em `attention_points`.

### Tests for User Story 2

- [x] T011 [US2] Adicionar `test_attention_points_include_low_severity_blocking_reason` em `tests/api/routers/test_pre_evaluation_get.py` usando `severity='low'` e `NON_COMPLIANT_STATEMENT`: confirmar `consolidated_result == 'negative'` e que `attention_points` inclui o critério de severidade baixa com `conclusion == 'non_compliant'` e `justification` preenchida (prova FR-008; `recommendation`/`evidence_excerpt` dependem do veredito do provedor e não são garantidos pelo fake nesse cenário) (depende de T002)

**Checkpoint**: User Stories 1 e 2 funcionam de ponta a ponta — o proponente vê exatamente qual campo bloqueou, mesmo em severidade baixa.

---

## Phase 5: User Story 3 - Intervenção direta continua disponível (Priority: P3)

**Goal**: O proponente continua podendo solicitar intervenção direta do BraCVAM quando a nova regra bloquear o avanço automático, preservando o relatório original.

**Independent Test**: Provocar um retorno negativo causado por severidade baixa (nova causa de bloqueio) e confirmar que a intervenção direta ainda encaminha a submissão para a triagem preservando o relatório.

### Tests for User Story 3

- [x] T012 [US3] Adicionar `test_direct_review_after_low_severity_negative_moves_to_triage` em `tests/api/routers/test_direct_review.py`, reproduzindo `test_direct_review_after_negative_moves_to_triage` com `severity='low'` em vez de `'critical'`: confirmar que a solicitação de intervenção direta ainda move o processo para `TRIAGE` preservando o relatório original da IA (prova FR-005, não regressão) (depende de T002)

**Checkpoint**: Todas as user stories funcionam de forma independente; a válvula de escape da Spec 013 continua íntegra sob a nova regra.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Qualidade, rastreabilidade entre specs e validação final

- [x] T013 [P] Rodar `poetry run ruff check .` e `poetry run ruff format .`. Achado: `ruff format .` também reformatou `scripts/seeds/seed_kanban.py`, `tests/api/routers/test_tasks_router.py` e `tests/unit/core/test_activity_due_date.py` (arquivos não tocados por esta feature, com formatação já desatualizada em relação ao `ruff` atual); essas 3 mudanças foram revertidas via `git checkout` para manter o diff restrito à Spec 026 — `ruff check .` continua limpo sem elas
- [x] T014 Rodar `poetry run pytest` completo e confirmar 100% verde, sem chamadas externas à OpenAI. Achado durante a execução: `tests/unit/ai/test_pipeline_targets.py::test_document_target_is_indeterminate_without_model_call` também fixava a regra antiga (`consolidated_result == 'positive'` para indeterminado isolado) e não estava listado nas tasks originais; corrigido para `'negative'` (Spec 026, FR-003)
- [ ] T015 Executar o roteiro manual do `quickstart.md` (seção 3, passos 1–7) contra a API real em `http://localhost:8000` — **não executado nesta sessão**: exige autenticação interativa com contas BraCVAM/proponente e cria dados de teste persistentes no banco de dev; os mesmos cenários (severidade baixa bloqueando, critério de documento indeterminado bloqueando, intervenção direta preservando o relatório) já estão provados end-to-end por T009–T012 contra Postgres real via Testcontainers
- [x] T016 [P] Adicionar nota em `specs/013-configurable-ai-evaluation/spec.md` junto a FR-030/FR-030a registrando que a regra de consolidação foi substituída pela Spec 026 (mesmo padrão usado pela Spec 014, FR-019, ao encerrar débitos de specs anteriores)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: depende do Setup; **bloqueia** todas as user stories (T004–T012 dependem de T002).
- **User Stories (Phase 3–5)**: todas dependem apenas da Foundational; são independentes entre si (T004–T010 [US1], T011 [US2], T012 [US3] não dependem umas das outras, só de T002/T008).
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas.

### Parallel Opportunities

- T004, T005, T006, T007 (todos em `tests/unit/ai/test_consolidation.py`, funções independentes) podem ser feitos em paralelo entre si, mas sequencialmente em relação ao mesmo arquivo se editados por mãos diferentes — marcados `[P]` pois não têm dependência lógica entre si.
- T003 pode rodar em paralelo com T004–T007 (arquivos diferentes), mas T002 deve estar concluído antes de qualquer teste ser executado com sucesso.
- Após T002/T008, T009, T010, T011 e T012 tocam arquivos de teste diferentes e podem ser feitos em paralelo.
- T013 e T016 são independentes do restante do Polish e entre si.

---

## Parallel Example: Foundational + User Story 1

```bash
# Depois de T002 (mudança da regra):
Task: "Renomear test_low_and_medium_non_conformities_stay_positive_as_alerts em tests/unit/ai/test_consolidation.py"
Task: "Renomear test_only_indeterminate_is_positive em tests/unit/ai/test_consolidation.py"
Task: "Renomear test_partial_does_not_block_and_is_alerted em tests/unit/ai/test_consolidation.py"
Task: "Adicionar test_single_low_severity_non_compliant_among_compliant_blocks em tests/unit/ai/test_consolidation.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 (Setup) e Phase 2 (Foundational — a mudança de regra em si).
2. Completar Phase 3 (User Story 1) — regra e cobertura unit + integration.
3. **PARAR e VALIDAR**: rodar `tests/unit/ai/test_consolidation.py` e `tests/integration/ai/test_run_pre_evaluation.py`.
4. Isso já entrega o valor de negócio pedido pelo usuário.

### Incremental Delivery

1. Setup + Foundational → regra implementada.
2. User Story 1 → regra provada em unit + integration (MVP).
3. User Story 2 → prova de que o proponente vê o motivo do bloqueio na API.
4. User Story 3 → prova de que a intervenção direta não regrediu.
5. Polish → lint, suíte completa, quickstart manual, nota de rastreabilidade na Spec 013.

## Notes

- Não há tasks de modelo/migração — a feature não altera schema (`data-model.md`).
- `[P]` = arquivos diferentes ou funções independentes no mesmo arquivo sem dependência lógica entre si.
- Cada task de teste referencia o arquivo exato e, quando aplicável, o nome da função (antiga e nova) para minimizar ambiguidade na implementação.
- Commitar após cada task ou grupo lógico, conforme convenção do projeto.
