---

description: "Task list for feature 015 — Pacote de Baseline do Primeiro Deploy"
---

# Tasks: Pacote de Baseline do Primeiro Deploy

**Input**: Design documents from `specs/015-first-deploy-baseline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/demo-standard.md, quickstart.md

**Tests**: Incluídos. A Constituição IV exige `pytest` verde; a refatoração dos
formulários quebra testes acoplados que precisam ser corrigidos, e a spec (User Story 3)
define um teste de forma de formulário.

**Organization**: Fase 2 (Foundational) reescreve os 5 formulários — substrato
compartilhado por seeds, demos e testes. As três user stories são fatias entregáveis
sobre esse substrato.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1 / US2 / US3 (fases de user story apenas)

## Path Conventions

Single project: `src/pivma/`, `scripts/seeds/`, `demos/`, `tests/` na raiz do repo.

---

## Phase 1: Setup

- [x] T001 [P] Invocar `Skill(fastapi-testing-methodology)` antes de qualquer edição de teste; registrar na descrição do PR as lacunas de skill `andrej-karpathy-skills:karpathy-guidelines` e `stop-slop` (não instaladas), conforme `specs/015-first-deploy-baseline/plan.md` › Riscos.
- [x] T002 [P] Validar stack local: `docker compose down -v && docker compose up db -d` e `uv run alembic upgrade head` concluem em banco limpo (`specs/015-first-deploy-baseline/quickstart.md` §1).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Reescrever os formulários de submissão e restaurar a suíte verde. Nenhuma user story começa antes deste checkpoint.

**⚠️ CRITICAL**: `phases:` e o formulário `triage_review_v1` de cada YAML **não** são alterados (spec FR-016).

### Formulários (`src/pivma/templates_data/`)

- [x] T003 Reescrever o `fields:` do formulário `submission_pre_validated_v1` em `src/pivma/templates_data/01_pre_validated_method.yaml` para **exatamente 1 campo**: `field_key: method_title`, `label: "Título do método"`, `field_type: text`, `is_required: true`, `order_index: 1`, `help_text: "Nome do método alternativo proposto."` (data-model.md §1).
- [x] T004 [P] Mesmo campo único para `submission_scope_extension_v1` em `src/pivma/templates_data/02_scope_extension.yaml` (data-model.md §2).
- [x] T005 [P] Mesmo campo único para `submission_me_too_v1` em `src/pivma/templates_data/03_me_too_validation.yaml` (data-model.md §3).
- [x] T006 Reescrever o `fields:` de `submission_validated_dossier_v1` em `src/pivma/templates_data/04_validated_method_dossier.yaml` para 2 campos (data-model.md §4): `method_title` (`text`, `is_required: true`, `order_index: 1`) e `terminology_notes` (`textarea`, `is_required: true`, `order_index: 2`, `ai_evaluation_enabled: true`, `ai_context_instructions:` = "Verificar se os termos usados para descrever o conceito estão alinhados à nomenclatura científica e regulatória atual (OCDE, IATA, NAM). Apontar termos desatualizados e sugerir equivalentes modernos.", `ai_validation_rules: { min_length: 30 }`, `help_text: "Descreva o conceito central em 1–2 parágrafos."`).
- [x] T007 Reescrever o `fields:` de `submission_proof_of_concept_v1` em `src/pivma/templates_data/05_proof_of_concept.yaml` com **todos** os campos de data-model.md §5 (Formulário Preliminar), regras verbatim:
  - `order_index` sequencial na ordem das tabelas de data-model.md §5.
  - Cada campo com `validation_rules: { section: "<nome exato da seção>" }` — 9 seções: "1. Informações Gerais", "2. Informações do Método de Teste", "3. Resumo do Método de Teste", "4. Avaliação Preliminar do Nível de Otimização do Protocolo", "5. Avaliação Preliminar da Confiabilidade", "6. Avaliação Preliminar da Capacidade Preditiva", "7. Referências", "8. Declaração sobre Informação Confidencial", "9. Solicitação do Método de Teste para BraCVAM".
  - `is_required: true` **apenas** em: `proponent_organization`, `contact_first_name`, `contact_last_name`, `contact_email`, `method_name`. Todos os demais `is_required: false`.
  - `contact_title` e `additional_contact_title`: `field_type: select`, `options` com `value`/`label` para `mr` ("Mr."), `ms` ("Ms."), `dr` ("Dr."), `prof` ("Prof.").
  - `sop_files`: `field_type: file_upload`, `validation_rules: { section: "4. Avaliação Preliminar do Nível de Otimização do Protocolo", allowed_extensions: ["pdf"], max_size_mb: 25 }`.
  - Campos com limite do FP recebem `help_text: "Máx. 150 palavras (orientação; não validada)."` (ou "100 palavras" em `confidential_items`).
  - Sem nenhum campo `ai_*` no formulário 5.
- [x] T008 Revisar `src/pivma/templates_data/README.md`: remover/atualizar exemplos que citem `field_key` agora inexistentes; confirmar que a forma `validation_rules: { section: ... }` está documentada (§5.3).

### Remediação de testes acoplados (`tests/`)

- [x] T009 Re-apontar `tests/ai_eval_helpers.py` para o formulário 4: `SUBMISSION_TEMPLATE = 'submission_validated_dossier_v1'`, `AI_FIELD = 'terminology_notes'`, `create_and_submit_process` com `template_key='validated_method_dossier'`, e `FULL_VALUES = {'method_title': 'Método validado', 'terminology_notes': '<texto ≥30 caracteres contendo a palavra-chave de COMPLIANT_STATEMENT>'}` (research.md R4).
- [x] T010 [P] Corrigir `tests/unit/core/test_process_engine.py`: rascunho/submissão usam só `method_title` (campo real de `submission_pre_validated_v1`); o caso "fail submit sem obrigatórios" omite `method_title`; `reviews` referenciam apenas `method_title`.
- [x] T011 [P] Corrigir `tests/api/routers/test_evaluation_assignments.py`: constantes locais `TEMPLATE_KEY`/`AI_FIELD` → `submission_validated_dossier_v1` / `terminology_notes`.
- [x] T012 [P] Corrigir `tests/api/routers/test_evaluation_library.py`: URLs de template → `/form-templates/submission_validated_dossier_v1/evaluation-assignments`.
- [x] T013 [P] Corrigir `tests/integration/database/test_evaluation_library_reuse.py`: alvo de atribuição → `submission_validated_dossier_v1` / `terminology_notes`.
- [x] T014 [P] Criar `tests/unit/core/test_first_deploy_forms.py` (skill `fastapi-testing-methodology`; fixture `session` + `bootstrap_all_templates`): assert forms 1‑3 têm exatamente 1 `FormField` (`method_title`, `is_required is True`); form 4 tem `terminology_notes` com `ai_evaluation_enabled is True`; form 5 expõe 9 valores distintos de `validation_rules['section']` e contém `method_name`, `contains_confidential`, `bracvam_validation_request`; `triage_review_v1` inalterado (2 campos: `regulatory_adherence_score`, `triage_summary_notes`).
- [x] T015 Rodar `uv run poe format && uv run poe lint && uv run poe test` — tudo verde. **Checkpoint: substrato pronto.**

---

## Phase 3: User Story 1 - Carga única habilita todas as demonstrações (Priority: P1) 🎯 MVP

**Goal**: Banco vazio → um comando (`seed_all`) → todas as 6 demos operáveis, sem passo manual.

**Independent Test**: `quickstart.md` §1–§4 — em banco limpo, `seed_all` conclui, e cada demo do catálogo carrega seus dados (triagem com painel de IA para `[DEMO 4]`, ai-pipeline com ≥1 execução).

- [x] T016 [US1] Em `scripts/seeds/seed_forms.py`, atualizar os `title` de `OFFICIAL_DEMO_PROCESSES` para refletir os novos propósitos (ex.: `[DEMO 4] Dossiê Validado — Exemplo de IA`, `[DEMO 5] Prova de Conceito — Formulário Preliminar (FP)`); manter as 5 `key` e a lógica de instanciação/soft-delete.
- [x] T017 [US1] Em `scripts/seeds/seed_triage.py`, submeter `[DEMO 1]` com `values = {'method_title': 'Ensaio BCOP de opacidade e permeabilidade corneana'}` apenas (remover chaves ausentes de `submission_pre_validated_v1`); manter avanço a `TRIAGE` e guard de idempotência.
- [x] T018 [US1] Reescrever `scripts/seeds/seed_ai_evaluations.py` (research.md R2): `FORM_TEMPLATE_KEY = 'submission_validated_dossier_v1'`, `AI_FIELD = 'terminology_notes'`, `FORM_VALUES` com `method_title` + `terminology_notes`; publicar definição "Atualidade da terminologia" (modo `simple`, 2–3 critérios sobre nomenclatura moderna) + referência normativa; `replace_assignments('submission_validated_dossier_v1', [...field_keys=['terminology_notes']...])`; conduzir a instância oficial `[DEMO 4]` (criada por `seed_forms`) por `submit_proposal_form` → `presvc._execute` → roteamento a `TRIAGE`. **Não** criar processo `[DEMO IA]` separado.
- [x] T019 [US1] Remover `scripts/seeds/seed_form_ai_demo.py`; `grep -rn "seed_form_ai_demo" .` deve ficar vazio (sem imports/refs).
- [x] T020 [US1] Atualizar a saída impressa de `scripts/seeds/seed_all.py`: contas com perfil, os 6 links de demo (4 do ciclo + `users` + `operational-index`), e o comando canônico `uv run python -m scripts.seeds.seed_all`.
- [x] T021 [US1] Validar `quickstart.md` §2–§4: banco limpo → `seed_all` → abrir as 6 demos; rodar `seed_all` 2× e confirmar zero duplicação de usuários/processos/avaliações (SC‑001, SC‑002, SC‑003).

**Checkpoint**: MVP entregue — `seed_all` sozinho habilita a demonstração completa.

---

## Phase 4: User Story 2 - Demonstrações com padrão visual e narrativo consistente (Priority: P2)

**Goal**: As 6 páginas de `demos/` parecem um único produto, texto enxuto, rótulos em português, catálogo limpo.

**Independent Test**: `contracts/demo-standard.md` C1–C9 — abrir as 6 páginas + catálogo e conferir cabeçalho/paleta/tipografia/status/idioma/comando único/links.

- [x] T022 [US2] Criar `demos/assets/base.css`: tokens de cor, tipografia, cabeçalho, cartões, botões, tabelas e badge de status (contracts/demo-standard.md › "Assets compartilhados"). Sem dependência de build; sem `@import` externo.
- [x] T023 [US2] Criar `demos/assets/base.js`: componente compartilhado de status da API (`GET /` → online/offline/erro), substituindo a duplicação por página.
- [x] T024 [US2] Reescrever `demos/index.html` (catálogo): lista das 6 páginas com descrição de 1 linha cada; `<link>` para `/demos/assets/base.css`; **remover** o link para `DESIGN.md`; comando de carga único `uv run python -m scripts.seeds.seed_all`; manter a tabela de contas de teste; atualizar a tabela "5 Processos Padrão" para os novos títulos.
- [~] T025 [P] [US2] Reescrever `demos/forms/index.html` e `demos/forms/ai-config.html` no esqueleto compartilhado (cabeçalho+status → 1 frase de propósito → passos numerados → chamada de ação; PT-BR; mensagem "sem dados" citando o comando canônico).
- [~] T026 [P] [US2] Reescrever `demos/submission/index.html` no esqueleto compartilhado.
- [~] T027 [P] [US2] Reescrever `demos/triage/index.html` no esqueleto compartilhado.
- [~] T028 [P] [US2] Reescrever `demos/ai-pipeline/index.html` e `demos/ai-pipeline/app.js` no esqueleto compartilhado.
- [~] T029 [P] [US2] Reescrever `demos/users/index.html` no esqueleto compartilhado.
- [~] T030 [P] [US2] Reescrever `demos/operational-index/index.html` e `demos/operational-index/app.js` no esqueleto compartilhado.
- [x] T031 [US2] Criar `demos/README.md` curto com a diretriz de padrão (substitui o `DESIGN.md`; **não** recriar `DESIGN.md`); texto factual e enxuto (lacuna `stop-slop` registrada).
- [~] T032 [US2] Verificar contrato: `grep -rn "DESIGN.md" demos/` vazio (SC‑005/C7); `grep -rn "seed_all" demos/` — todas as ocorrências idênticas (SC‑006/C4); abrir catálogo + 6 páginas, zero link quebrado (C6); mensagem "sem dados" com banco vazio (C5).

**Checkpoint**: Demos padronizadas e catálogo consistente.

---

## Phase 5: User Story 3 - Formulários de submissão redesenhados por propósito de demo (Priority: P2)

**Goal**: Cada formulário de submissão reflete o papel da sua demo; o FP está completo e as aproximações estão documentadas.

**Independent Test**: Instanciar cada processo e abrir `GET /processes/{id}/activities/proposal_submission/form` — conferir contagem de campos, obrigatoriedade, rótulos e seções.

- [x] T033 [US3] Instanciar os 5 processos (via app/API) e abrir o formulário de `proposal_submission` de cada um: forms 1‑3 = 1 campo `method_title` obrigatório; form 4 mostra `terminology_notes` como campo avaliável; form 5 retorna as 9 seções na ordem de data-model.md §5 (spec US3 cenários 1‑3).
- [x] T034 [US3] Conferir que **todo** elemento do FP sem representação nativa está listado em `spec.md` › "Pendências e Lacunas Conhecidas" e em `data-model.md` › "Pendências do FP"; acrescentar qualquer item descoberto durante a transcrição (spec US3 cenário 4, SC‑008).
- [x] T035 [US3] Rodar `quickstart.md` §5 e `tests/unit/core/test_first_deploy_forms.py`; confirmar que `poe test` segue verde (SC‑007, SC‑009).

**Checkpoint**: Todos os formulários entregam seu propósito de demonstração.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T036 [P] (Opcional, robustez) Adicionar poda de `FormField` órfão em `src/pivma/bootstrap_process_templates._sync_form_fields`: após o upsert, `deleted_at` nos campos do formulário cujo `field_key` não está no YAML, **apenas** se não houver `FormValue` ativo referenciando-os (senão manter + `structlog`). Cobrir com teste em `tests/integration/` de estado antes/depois (research.md R5).
- [x] T037 [P] Atualizar quaisquer textos remanescentes em `demos/` que citem os títulos/propósitos antigos das 5 demos.
- [~] T038 Executar `quickstart.md` §1–§7 ponta a ponta e marcar todos os checkboxes de critério de aceite (SC‑001…SC‑010).
- [x] T039 [P] `uv run poe format && uv run poe lint && uv run poe test` verdes; `git status` mostra `scripts/seeds/seed_form_ai_demo.py` removido e nenhum `demos/DESIGN.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende do Setup. **Bloqueia todas as user stories.** Checkpoint T015 (suíte verde) é obrigatório.
- **US1 (Phase 3)**: depende da Fase 2 (seeds consomem os `field_key` novos dos formulários).
- **US2 (Phase 4)**: depende apenas de T022/T023 dentro da própria fase; **independente de US1 e US3** (as demos são genéricas e leem o que estiver no banco). Pode rodar em paralelo com US1.
- **US3 (Phase 5)**: depende da Fase 2; T033 fica mais simples após US1 (massa instanciada), mas pode instanciar processos do zero.
- **Polish (Phase 6)**: depende das user stories desejadas concluídas.

### User Story Dependencies

- US1 (P1) — MVP. Requer Fase 2.
- US2 (P2) — independente. Requer Fase 2.
- US3 (P2) — independente de US1/US2 no teste; compartilha o substrato da Fase 2.

### Parallel Opportunities

- Fase 1: T001, T002.
- Fase 2: T004 + T005 (formulários 2 e 3); T010–T014 (arquivos de teste distintos) após T009.
- Fase 3: majoritariamente sequencial (seeds interdependentes); T019 em paralelo.
- Fase 4: T025–T030 (6 páginas, arquivos distintos) após T022/T023.
- Fase 6: T036, T037, T039.

---

## Parallel Example: Phase 2 (test remediation)

```bash
# Após T009 (helper central):
Task: "T010 corrigir tests/unit/core/test_process_engine.py"
Task: "T011 corrigir tests/api/routers/test_evaluation_assignments.py"
Task: "T012 corrigir tests/api/routers/test_evaluation_library.py"
Task: "T013 corrigir tests/integration/database/test_evaluation_library_reuse.py"
Task: "T014 criar tests/unit/core/test_first_deploy_forms.py"
```

## Parallel Example: Phase 4 (demo pages)

```bash
# Após T022 (base.css) + T023 (base.js):
Task: "T025 reescrever demos/forms/"
Task: "T026 reescrever demos/submission/"
Task: "T027 reescrever demos/triage/"
Task: "T028 reescrever demos/ai-pipeline/"
Task: "T029 reescrever demos/users/"
Task: "T030 reescrever demos/operational-index/"
```

---

## Implementation Strategy

### MVP (User Story 1)

1. Fase 1: Setup.
2. Fase 2: Foundational — formulários + testes verdes (T015).
3. Fase 3: US1 — seeds.
4. **PARAR e VALIDAR**: `quickstart.md` §1–§4 em banco limpo. Demo pronta.

### Entrega incremental

1. Setup + Foundational → substrato pronto.
2. US1 → validar → demo do "um comando" (MVP).
3. US2 → validar contrato de UI → demo padronizada.
4. US3 → validar formas dos formulários.
5. Polish → poda opcional + quickstart completo.

---

## Notes

- `[P]` = arquivos diferentes, sem dependência pendente.
- `phases:` e `triage_review_v1` dos YAML **nunca** são tocados (FR-016).
- `submit_proposal_form` ignora chaves desconhecidas e só valida obrigatórios — testes que enviam campos extras não quebram; o que quebra é rascunho com chave removida, atribuição a `field_key` inexistente e asserts sobre campos de IA.
- Sem migração Alembic (sem mudança de schema), inclusive na tarefa opcional T036.
- Commit após cada tarefa ou grupo lógico; atribuição de commit conforme o system-reminder da sessão.


---

## Status da implementação (Spec 015)

- **Fase 2 (Foundational) — completa.** 5 formulários reescritos; `ai_eval_helpers`
  re-apontado; testes acoplados corrigidos; `test_first_deploy_forms.py` criado.
  **Suíte cheia: 540 passed, 1 skipped, 0 failed.** `ruff check`/`format` limpos.
- **Fase 3 (US1) — completa.** Seeds reescritos; `seed_form_ai_demo.py` removido.
  `seed_all` validado em banco limpo: 5 processos, DEMO 1 e DEMO 4 em TRIAGE, DEMO 4
  com `evaluation_run` concluída (4 itens, 1 ponto de atenção). Idempotente
  (2ª execução: 0 duplicações). API `/…/proposal_submission/form` do FP retorna
  79 campos em 9 seções; `/…/pre-evaluation` do DEMO 4 retorna relatório completo.
- **Fase 4 (US2) — parcial (marcada `[~]`).** Entregue: `assets/base.css` +
  `assets/base.js`, catálogo `index.html` reescrito sobre o padrão, `demos/README.md`,
  comando de carga unificado em todas as páginas, zero referência a `DESIGN.md`,
  `:root`/`*`/`body` duplicados removidos das 6 páginas (tokens só via `base.css`).
  **Pendente:** reescrita do esqueleto (cabeçalho→frase→passos→CTA) de cada página e
  troca do widget de status próprio pelo componente compartilhado `data-api-status`;
  hoje as 6 páginas mantêm o layout anterior (já consistente entre si) sobre o
  `base.css` comum.
- **Fase 5 (US3) — completa.** Formas dos 5 formulários validadas por API e por
  `test_first_deploy_forms.py`; pendências do FP consolidadas em `spec.md` e
  `data-model.md`.
- **Fase 6 — T036 (poda de FormField órfão) não implementada** (opcional; `quickstart`
  assume banco limpo). T037/T039 feitos.
