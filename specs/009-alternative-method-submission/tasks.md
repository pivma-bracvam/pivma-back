---
description: "Tarefas da Feature 009: Submissão de Método Alternativo"
---

# Tasks: 009 - Submissão de Método Alternativo

**Input**: Artefatos em `/specs/009-alternative-method-submission/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/submission-api.md` e `quickstart.md`

**Escopo**: Reutilizar o motor e os modelos existentes. Não criar endpoint, tabela, migração, dependência ou abstração paralela. O envio formal preserva seu fluxo atual; recebe somente a guarda contextual para impedir acesso de terceiros.

**Testes**: Cada tarefa de teste cobre um comportamento observável. Testes de API usam `TestClient`; o predicado de autorização recebe teste de integração de banco. Reutilizar fixtures e factories existentes.

## Phase 1: Setup

**Purpose**: Confirmar o ponto de extensão e a massa de teste já disponível, sem criar infraestrutura nova.

- [X] T001 Mapear as fixtures e factories reutilizáveis para processos, participantes e usuários em `tests/conftest.py`, `tests/factories/process_factory.py` e `tests/factories/participant_factory.py`

---

## Phase 2: Foundational

**Purpose**: Disponibilizar as duas regras compartilhadas que bloqueiam as histórias: participação de proponente eficaz e geração segura do `crCode`.

- [X] T002 [P] Testar que a consulta de proponente considera ativa uma designação `proponent` não revogada nem excluída em `tests/integration/database/test_participant_authorization.py`
- [X] T003 [P] Testar que a consulta de proponente rejeita designação revogada em `tests/integration/database/test_participant_authorization.py`
- [X] T004 [P] Testar que a consulta de proponente rejeita participante ativo com papel diferente de `proponent` em `tests/integration/database/test_participant_authorization.py`
- [X] T005 Implementar o predicado de proponente ativo e eficaz em `src/pivma/core/authorization.py`
- [X] T006 Testar que duas criações concorrentes recebem `code` distintos em `tests/integration/database/test_process_code_generation.py`
- [X] T007 Substituir a geração por contador pelo `crCode` aleatório `VAL-{ano}-{token}` em `src/pivma/core/process_engine.py`

**Checkpoint**: A policy de acesso e o identificador único estão prontos para uso pelos routers e pelo motor existente.

---

## Phase 3: User Story 1 - Iniciar e registrar uma proposta (Priority: P1) 🎯 MVP

**Goal**: O proponente cria uma submissão identificada, registra um rascunho parcial válido e conserva a proposta em elaboração.

**Independent Test**: Com uma definição `full_validation` disponível, o proponente cria a instância, salva valores válidos no formulário inicial e os relê sem transição para triagem.

### Tests for User Story 1

- [X] T008 [P] [US1] Testar que `POST /processes` cria a instância com `crCode`, proponente e status `SUBMISSION` em `tests/api/routers/test_process_router.py`
- [X] T009 [P] [US1] Testar que `PUT /processes/{process_id}/activities/proposal_submission/form` persiste um rascunho parcial válido em `tests/api/routers/test_form_submission.py`
- [X] T010 [P] [US1] Testar que salvar rascunho não submete o formulário nem move o processo para triagem em `tests/api/routers/test_form_submission.py`

**Checkpoint**: A criação e o salvamento parcial do proponente funcionam sem documento ou envio formal.

---

## Phase 4: User Story 2 - Consultar o formulário definido para a proposta (Priority: P2)

**Goal**: O proponente renderiza o formulário e os valores a partir da definição persistida vinculada à instância.

**Independent Test**: O proponente lê o formulário da própria proposta e recebe campos ativos na ordem configurada, metadados de apresentação e valores persistidos da instância.

### Tests for User Story 2

- [X] T011 [P] [US2] Testar que `GET /processes/{process_id}/activities/proposal_submission/form` retorna os campos ativos na ordem persistida em `tests/api/routers/test_form_submission.py`
- [X] T012 [P] [US2] Testar que a leitura do formulário retorna valores ligados às respectivas `field_key` em `tests/api/routers/test_form_submission.py`
- [X] T013 [P] [US2] Testar que uma proposta existente continua vinculada à versão de formulário inicial após publicação de versão posterior em `tests/api/routers/test_form_submission.py` — **nota**: `FormTemplate.key` é único no modelo atual e não existe versionamento de definição de formulário no código hoje; não há mecanismo para publicar uma "versão posterior" do mesmo formulário. O cenário 3 da US2 é hoje vacuamente satisfeito (não existe caminho para violá-lo) e nenhum teste automatizado cobre esta task. Escrever esse teste exigiria criar a infraestrutura de versionamento de formulário, o que está fora do escopo de RF007.

### Implementation for User Story 2

- [X] T014 [US2] Restringir a serialização da leitura aos `FormField` ativos da versão vinculada à execução em `src/pivma/core/process_engine.py` e `src/pivma/routers/forms.py`

**Checkpoint**: O frontend pode montar o formulário pela resposta existente, sem endpoint ou modelo adicional.

---

## Phase 5: User Story 3 - Impedir dados inválidos e acesso indevido (Priority: P3)

**Goal**: O backend rejeita entradas incompatíveis de forma atômica e restringe todos os recursos da submissão ao proponente eficaz.

**Independent Test**: Um payload inválido recebe `422` sem alterar valores. Um terceiro, um participante com outro papel ou um proponente revogado não obtém dados nem executa operações com identificadores conhecidos.

### Tests for User Story 3

- [X] T015 [P] [US3] Testar que o rascunho rejeita uma `field_key` desconhecida com `422` e não grava o payload em `tests/api/routers/test_form_submission.py`
- [X] T016 [P] [US3] Testar que o rascunho rejeita tipo incompatível com `422` em `tests/api/routers/test_form_submission.py`
- [X] T017 [P] [US3] Testar que o rascunho rejeita opção não configurada com `422` em `tests/api/routers/test_form_submission.py`
- [X] T018 [P] [US3] Testar que o rascunho rejeita valor fora de `min` ou `max` com `422` em `tests/api/routers/test_form_submission.py`
- [X] T019 [P] [US3] Testar que o rascunho persiste `false` como valor booleano presente em `tests/api/routers/test_form_submission.py`
- [X] T020 [P] [US3] Testar que o rascunho persiste `0` como valor numérico presente em `tests/api/routers/test_form_submission.py`
- [X] T021 [P] [US3] Testar que o rascunho rejeita valor enviado para campo `file_upload` com `422` sem criar `FormValue` ou `Artifact` em `tests/api/routers/test_form_submission.py`
- [X] T022 [P] [US3] Testar que `GET /processes` exclui submissões de outro usuário da lista e da contagem em `tests/api/routers/test_process_router.py`
- [X] T023 [P] [US3] Testar que `GET /processes/{process_id}` retorna `404` para terceiro sem participação em `tests/api/routers/test_process_router.py`
- [X] T024 [P] [US3] Testar que `GET /processes/{process_id}/timeline` retorna `404` para terceiro sem participação em `tests/api/routers/test_process_router.py`
- [X] T025 [P] [US3] Testar que a leitura do formulário retorna `404` para terceiro sem participação em `tests/api/routers/test_form_submission.py`
- [X] T026 [P] [US3] Testar que o salvamento de rascunho retorna `404` para terceiro sem participação em `tests/api/routers/test_form_submission.py`
- [X] T027 [P] [US3] Testar que o envio formal retorna `404` para terceiro sem participação em `tests/api/routers/test_form_submission.py`
- [X] T028 [P] [US3] Testar que a leitura do formulário retorna `404` para proponente revogado em `tests/api/routers/test_form_submission.py`
- [X] T029 [P] [US3] Testar que o rascunho retorna `404` para proponente revogado em `tests/api/routers/test_form_submission.py`
- [X] T030 [P] [US3] Testar que a leitura do formulário retorna `404` para participante ativo com papel diferente de proponente em `tests/api/routers/test_form_submission.py`
- [X] T031 [P] [US3] Testar que o rascunho retorna `404` para participante ativo com papel diferente de proponente em `tests/api/routers/test_form_submission.py`

### Implementation for User Story 3

- [X] T032 [US3] Validar e normalizar o payload completo de rascunho contra `FormField` antes de gravar valores em `src/pivma/core/process_engine.py`
- [X] T033 [US3] Aplicar a policy de proponente eficaz à lista, detalhe e timeline de processos em `src/pivma/routers/processes.py`
- [X] T034 [US3] Aplicar a policy de proponente eficaz à leitura, ao rascunho e ao envio formal de formulário em `src/pivma/routers/forms.py`
- [X] T035 [US3] Expor o erro estruturado `invalid_form_values` por `field_key` no contrato de formulário em `src/pivma/routers/forms.py`

**Checkpoint**: O backend preserva dados anteriores diante de erro e não revela submissões a usuários fora da participação permitida.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Executar as verificações proporcionais e confirmar que o contrato documentado continua sendo o único necessário ao frontend.

- [X] T036 Executar os cenários do fluxo principal descritos em `specs/009-alternative-method-submission/quickstart.md`
- [X] T037 Testar que falha antes do commit na instanciação não deixa processo, atribuição, execução ou formulário persistidos em `tests/integration/database/test_process_code_generation.py`
- [X] T038 Testar que a criação registra o evento auditável do processo com o autor em `tests/api/routers/test_process_router.py`
- [X] T039 Testar que o salvamento de rascunho registra o evento auditável com o autor em `tests/api/routers/test_form_submission.py`
- [X] T040 Testar que o proponente substitui um valor de rascunho já persistido em `tests/api/routers/test_form_submission.py`
- [X] T041 Testar que `null` limpa um valor parcial já persistido em `tests/api/routers/test_form_submission.py`
- [X] T042 Executar a suíte focal `tests/api/routers/test_process_router.py`, `tests/api/routers/test_form_submission.py`, `tests/integration/database/test_participant_authorization.py` e `tests/integration/database/test_process_code_generation.py` com `poetry run pytest`
- [X] T043 Executar a análise estática de `src` e `tests` com `poetry run ruff check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: não depende de outra tarefa.
- **Phase 2**: começa após T001 e bloqueia as histórias.
- **US1**: depende de T005 e T007.
- **US2**: depende de T005; pode confirmar a infraestrutura existente após a fundação.
- **US3**: depende de T005 e T007; T015 a T021 definem os testes antes de T032, T022 a T024 definem os testes antes de T033 e T025 a T031 definem os testes antes de T034.
- **Polish**: depende das três histórias concluídas; T037 a T041 completam as evidências de atomicidade, auditoria e edição parcial antes da suíte focal.

### User Story Dependencies

- **US1 (P1)**: entrega o MVP de criação e rascunho.
- **US2 (P2)**: usa a instância de US1, mas não acrescenta modelo, endpoint ou formulário paralelo.
- **US3 (P3)**: consolida validação e autorização sobre os mesmos endpoints de US1 e US2.

### Parallel Opportunities

- T002, T003 e T004 podem ser escritos em paralelo, pois verificam casos isolados do mesmo predicado.
- T008, T009 e T010 podem ser preparados em paralelo após a fundação.
- T011, T012 e T013 podem ser preparados em paralelo após a fundação.
- T015 a T031 podem ser preparados em paralelo por comportamento, mas tarefas que editam o mesmo arquivo devem ser integradas sequencialmente para evitar conflitos.

## Parallel Example: User Story 3

```text
Task: "T015 Testar rejeição de field_key desconhecida em tests/api/routers/test_form_submission.py"
Task: "T022 Testar ocultação de lista de outro usuário em tests/api/routers/test_process_router.py"
Task: "T023 Testar 404 de detalhe para terceiro em tests/api/routers/test_process_router.py"
```

## Implementation Strategy

### MVP First

1. Concluir T001 a T007.
2. Concluir US1 e executar seus testes.
3. Validar criação, rascunho parcial e permanência em elaboração antes de avançar.

### Incremental Delivery

1. US1 fornece criação e rascunho da submissão.
2. US2 confirma a leitura dinâmica que o frontend consome.
3. US3 fecha as fronteiras de integridade e autorização exigidas por RF004 e RF007.

## Notes

- Não implementar upload, `Artifact`, triagem, IA, notificações, versionamento ou regras completas de envio formal.
- `ProcessInstance.code` é o único `crCode`; a restrição única existente no banco permanece a proteção final de integridade.
- Testes de `false` e `0` exigem campos configurados para esses tipos; adaptar somente a massa de teste, nunca o router a um campo científico específico.
