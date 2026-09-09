# Tasks: 012 - Editor e Customização de Templates de Formulários de Processo (Versão 1.1)

**Input**: Design documents from `/specs/012-form-template-editor/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `research.md`, `quickstart.md`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparação do ambiente e verificação das estruturas de dados e schemas

- [x] T001 [P] Verificar e validar dependências do projeto e ambiente de execução em `pyproject.toml`
- [x] T002 [P] Validar integridade dos esquemas declarativos atuais de templates em `src/pivma/templates_data/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Estruturas de dados, contratos Pydantic e lógica central de sincronização atômica que bloqueiam as User Stories

- [x] T003 [P] Criar esquemas DTOs `FormFieldUpdateDefinition`, `UpdateFormTemplateRequest` e `FormTemplateDetailResponse` em `src/pivma/schemas.py` com suporte a `section`, `ai_evaluation_enabled`, `ai_context_instructions` e validações
- [x] T004 Implementar função de serviço `update_form_template_definition` em `src/pivma/core/process_engine.py` para sincronizar atomicamente `FormTemplate`, `FormField` e o `definition_payload` de `ProcessTemplateVersion`
- [x] T005 [P] Implementar verificação de autorização administrativa da equipe BraCVAM para edição de templates em `src/pivma/core/authorization.py`

**Checkpoint**: Base de dados, schemas e serviços de sincronização prontos para implementação dos endpoints e interfaces.

---

## Phase 3: User Story 1 - Edição e Persistência de Templates de Formulários pelo BraCVAM (Priority: P1) 🎯 MVP

**Goal**: Permitir que usuários autenticados da equipe BraCVAM consultem e salvem modificações estruturais em templates de formulários (campos, tipos, obrigatoriedade, seções e parâmetros simplificados de IA).

**Independent Test**: Usuário autenticado como BraCVAM chama `PUT /processes/templates/{key}/forms/{form_key}` com novos campos e seções; a API retorna HTTP 200 OK com o formulário persistido no banco e rejeita requisições de usuários não autorizados com HTTP 403.

### Tests for User Story 1
- [x] T006 [P] [US1] Criar testes de integração para `GET` e `PUT /processes/templates/{key}/forms/{form_key}` validando persistência e regras de autorização em `tests/api/routers/test_process_template_editor.py`
- [x] T007 [P] [US1] Criar testes unitários para a sincronização e validação de chaves duplicadas e regras de campo em `tests/unit/core/test_form_template_sync.py`

### Implementation for User Story 1
- [x] T008 [US1] Implementar endpoint `GET /processes/templates/{key}/forms/{form_key}` em `src/pivma/routers/processes.py` retornando os campos e seções do template
- [x] T009 [US1] Implementar endpoint `PUT /processes/templates/{key}/forms/{form_key}` em `src/pivma/routers/processes.py` com controle de permissão BraCVAM, atualização de versão e persistência atômica
- [x] T010 [US1] Adicionar tratamento de erros e validação de unicidade de `field_key` no endpoint de atualização em `src/pivma/routers/processes.py`

**Checkpoint**: User Story 1 concluída e testável de forma independente via API REST.

---

## Phase 4: User Story 2 - Instanciação de Processo com Formulário Customizado pelo Proponente (Priority: P2)

**Goal**: Assegurar que ao instanciar um novo processo a partir de um template modificado, o formulário de submissão do proponente carregue imediatamente a estrutura, campos e seções vigentes, preservando imutabilidade de instâncias anteriores.

**Independent Test**: Instanciar um novo processo a partir de um template modificado e verificar que `GET /processes/{id}/activities/proposal_submission/form` renderiza com fidelidade os novos campos e obrigatoriedades; verificar que processos anteriores permanecem inalterados.

### Tests for User Story 2
- [x] T011 [P] [US2] Criar teste de integração para instanciação de processo pós-edição de template e verificação de imutabilidade histórica em `tests/api/routers/test_process_template_instantiation.py`

### Implementation for User Story 2
- [x] T012 [US2] Ajustar função de instanciação de processos em `src/pivma/core/process_engine.py` para garantir que `FormInstance` herde todos os atributos customizados vigentes do `FormTemplate`
- [x] T013 [US2] Validar preenchimento e submissão com os novos campos obrigatórios em `src/pivma/routers/forms.py`

**Checkpoint**: User Stories 1 e 2 plenamente operacionais e integradas.

---

## Phase 5: User Story 3 - Demonstração Interativa Completa e Validação Operacional (Priority: P3)

**Goal**: Fornecer a interface interativa em `demos/forms/index.html` em conformidade com `AGENTS.md` comprovando o ciclo: seleção do processo -> edição e salvamento do template pelo BraCVAM via API real -> instanciação pelo proponente -> visualização do formulário customizado.

**Independent Test**: Executar o roteiro de `quickstart.md` no navegador em `http://localhost:8000/demos/forms/` cobrindo o fluxo completo com resposta transparente no Inspetor de API.

### Implementation for User Story 3
- [x] T014 [US3] Atualizar `demos/forms/index.html` com catálogo de templates oficiais de processo e seus formulários vinculados
- [x] T015 [US3] Implementar na demo o painel de edição estruturada de templates com suporte a seções, campos, tipos, obrigatoriedade e parâmetros de IA (Spec 010)
- [x] T016 [US3] Integrar ação de salvamento real na demo chamando `PUT /processes/templates/{key}/forms/{form_key}` e exibindo payload no inspetor
- [x] T017 [US3] Implementar na demo o painel do Proponente para instanciação de novo processo a partir do template editado e conferência imediata do formulário gerado
- [x] T018 [US3] Validar e harmonizar o catálogo central de demonstrações em `demos/index.html`

**Checkpoint**: Demonstração 100% funcional validando o comportamento desenvolvido de ponta a ponta contra a API real.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificação de qualidade, testes finais e validação de não-regressão

- [x] T019 [P] Executar suíte completa de testes automatizados com `poetry run pytest`
- [x] T020 Executar roteiro de validação ponta a ponta descrito em `specs/012-form-template-editor/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 (Setup)**: Sem dependências.
- **Phase 2 (Foundational)**: Depende da Fase 1 - BLOQUEIA todas as User Stories.
- **Phase 3 (User Story 1 - P1)**: Depende da Fase 2.
- **Phase 4 (User Story 2 - P2)**: Depende da Fase 3 (US1).
- **Phase 5 (User Story 3 - P3)**: Depende das Fases 3 e 4.
- **Phase 6 (Polish)**: Depende da conclusão das User Stories.

### Parallel Opportunities
- `T001` e `T002` podem rodar em paralelo.
- `T003` e `T005` podem rodar em paralelo na Fase Foundational.
- `T006` e `T007` (testes de US1) podem ser criados em paralelo.
- `T014`, `T015` e `T018` possuem independência de tela antes da integração de backend.
