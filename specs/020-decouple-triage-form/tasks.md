# Tasks: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Branch**: `020-decouple-triage-form` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup

**Purpose**: Verificação de ambiente e ancoragem da spec

- [x] T001 Ancorar diretório da feature e metadados em `.specify/feature.json`

---

## Phase 2: Foundational (Limpeza Declarativa dos Arquivos YAML)

**Purpose**: Remover `form_template_key` e o template `triage_review_v1` de todos os templates YAML de processos

- [x] T002 [US2] Remover `form_template_key: "triage_review_v1"` e a definição `triage_review_v1` de `src/pivma/templates_data/01_pre_validated_method.yaml`
- [x] T003 [P] [US2] Remover `form_template_key: "triage_review_v1"` e a definição `triage_review_v1` de `src/pivma/templates_data/02_scope_extension.yaml`
- [x] T004 [P] [US2] Remover `form_template_key: "triage_review_v1"` e a definição `triage_review_v1` de `src/pivma/templates_data/03_me_too_validation.yaml`
- [x] T005 [P] [US2] Remover `form_template_key: "triage_review_v1"` e a definição `triage_review_v1` de `src/pivma/templates_data/04_validated_method_dossier.yaml`
- [x] T006 [P] [US2] Remover `form_template_key: "triage_review_v1"` e a definição `triage_review_v1` de `src/pivma/templates_data/05_proof_of_concept.yaml`
- [x] T007 [P] [US2] Atualizar documentação de sintaxe em `src/pivma/templates_data/README.md` destacando que atividades periciais/deliberativas não exigem formulário

---

## Phase 3: User Story 1 - Execução da Triagem sem Formulário Próprio (Priority: P1) 🎯 MVP

**Goal**: Permitir que a atividade de triagem seja desbloqueada e deliberada via `Decision` sem requerer nem instanciar `FormInstance`

**Independent Test**: Submeter uma proposta, verificar que a atividade de triagem é desbloqueada sem criar `FormInstance` e emitir decisão de aprovação via `POST /processes/{id}/triage/decision` com sucesso

- [x] T008 [US1] Refatorar `_unblock_triage_activity` em `src/pivma/core/process_engine.py` para criar `ActivityRun` e `Task` sem buscar ou instanciar `triage_review_v1`
- [x] T009 [US1] Refatorar `execute_triage_decision` em `src/pivma/core/process_engine.py` para obter a atividade e execução de triagem ativas diretamente, sem chamar `get_current_form_instance`
- [x] T010 [P] [US1] Criar teste unitário em `tests/unit/core/test_triage_decoupled_form.py` cobrindo o ciclo de triagem sem formulário

---

## Phase 4: User Story 2 - Definição Declarativa Limpa e Sincronização no Bootstrap (Priority: P2)

**Goal**: Garantir que o catálogo de formulários no banco de dados reflita estritamente os formulários ativos nos YAMLs, inativando `triage_review_v1`

**Independent Test**: Executar `bootstrap_all_templates` e verificar que `triage_review_v1` é marcado com `deleted_at` e apenas os 5 formulários de submissão continuam ativos

- [x] T011 [US2] Atualizar `bootstrap_all_templates` em `src/pivma/bootstrap_process_templates.py` para aplicar soft-delete em `FormTemplate` obsoletos
- [x] T012 [US2] Atualizar `tests/unit/core/test_first_deploy_forms.py` para validar a ausência de `triage_review_v1` entre os formulários ativos

---

## Phase 5: User Story 3 - Validação de Compatibilidade e Não Degradação (Priority: P3)

**Goal**: Assegurar que processos e ferramentas de demonstração continuam operando normalmente de ponta a ponta

**Independent Test**: Executar `seed_forms.py` e validar que as instâncias de processos são criadas e transitáveis pela UI de triagem

- [x] T013 [US3] Validar script de seed em `scripts/seeds/seed_forms.py` e verificar geração de processos em modo desacoplado
- [x] T014 [US3] Validar compatibilidade da interface em `demos/triage/index.html` com o backend atualizado

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificação de qualidade, formatação e suite completa de testes

- [x] T015 [P] Executar formatação e linters com `poetry run ruff check .` e `poetry run ruff format .`
- [x] T016 Executar suite completa de testes com `poetry run pytest tests/unit/core/`
