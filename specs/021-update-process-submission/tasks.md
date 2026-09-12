---

description: "Tarefas executáveis para a atualização e o histórico de submissões"
---

# Tasks: 021 - Atualização de Instância de Submissão

**Branch**: `021-update-process-submission` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Input**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/process-submission.openapi.yaml` e `quickstart.md`.

**Escopo confirmado**: editar somente o título e valores não-anexo da maior run de submissão ainda não enviada; o envio formal congela o conteúdo. A devolução já abre a próxima `ActivityRun`; não criar tabela de versões, nova permissão, reabertura de processo fechado, comparação de versões ou endpoint exclusivo de demonstração.

## Phase 1: Setup

**Purpose**: Preparar a massa de teste reutilizável para uma submissão em rascunho com tipos dinâmicos e anexo.

- [X] T001 Criar helpers de teste para processo em rascunho e template dinâmico em `tests/api/routers/test_process_submission_update.py`

---

## Phase 2: Foundational (Contratos e proteções obrigatórias)

**Purpose**: Disponibilizar os contratos e as guardas de domínio antes de expor qualquer endpoint de escrita.

- [X] T002 Definir payloads estritos de substituição, alteração parcial e respostas de submissão/versão em `src/pivma/schemas.py`
- [X] T003 Implementar carregamento contextual da instância visível e da maior run `proposal_submission` em `src/pivma/core/process_engine.py`
- [X] T004 Implementar serialização do estado vigente da submissão a partir da run e da definição histórica do formulário em `src/pivma/core/process_engine.py`
- [X] T005 Aplicar autorização de proponente efetivo ou acesso BraCVAM antes da escrita em `src/pivma/core/process_engine.py`
- [X] T006 Bloquear escrita quando a run atual estiver submetida ou o processo não estiver em `SUBMISSION` em `src/pivma/core/process_engine.py`

**Checkpoint**: Contratos, autorização e imutabilidade básica estão prontos; nenhum endpoint de escrita será exposto sem essas guardas.

---

## Phase 3: User Story 1 - Substituir uma submissão completa (Priority: P1) 🎯 MVP

**Goal**: Permitir que o proponente substitua de forma atômica título e todos os valores não-anexo do rascunho atual usando `PUT /processes/{id}`.

**Independent Test**: Criar um processo em rascunho com campos de tipos distintos, executar PUT completo e consultar o formulário atual; a resposta e a consulta exibem somente os valores enviados.

### Tests for User Story 1

- [X] T007 [US1] Testar que PUT persiste valor de campo `text` em `tests/api/routers/test_process_submission_update.py`
- [X] T008 [US1] Testar que PUT persiste valor de campo `textarea` em `tests/api/routers/test_process_submission_update.py`
- [X] T009 [US1] Testar que PUT persiste opção válida de campo `select` em `tests/api/routers/test_process_submission_update.py`
- [X] T010 [US1] Testar que PUT persiste valor de campo `integer` em `tests/api/routers/test_process_submission_update.py`
- [X] T011 [US1] Testar que PUT persiste valor de campo `float` em `tests/api/routers/test_process_submission_update.py`
- [X] T012 [US1] Testar que PUT persiste data ISO de campo `date` em `tests/api/routers/test_process_submission_update.py`
- [X] T013 [US1] Testar que PUT persiste valor `false` de campo `boolean` em `tests/api/routers/test_process_submission_update.py`
- [X] T014 [US1] Testar que PUT remove valor anterior de campo opcional declarado como nulo em `tests/api/routers/test_process_submission_update.py`
- [X] T015 [US1] Testar que PUT sem campo obrigatório retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T016 [US1] Testar que PUT com chave de campo desconhecida retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T017 [US1] Testar que PUT com valor incompatível retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T018 [US1] Testar que PUT com valor incompatível preserva o título anterior em `tests/api/routers/test_process_submission_update.py`
- [X] T019 [US1] Testar que PUT com valor inline para campo de anexo retorna 422 em `tests/api/routers/test_process_submission_update.py`

### Implementation for User Story 1

- [X] T020 [US1] Implementar validação de completude do PUT contra campos não-anexo da definição histórica em `src/pivma/core/process_engine.py`
- [X] T021 [US1] Implementar substituição atômica de título e valores não-anexo do rascunho atual em `src/pivma/core/process_engine.py`
- [X] T022 [US1] Expor `PUT /processes/{id}` com o contrato de atualização integral em `src/pivma/routers/processes.py`

**Checkpoint**: PUT atualiza um rascunho completo sem tocar em anexos, estado, template, participantes ou fluxo.

---

## Phase 4: User Story 2 - Corrigir parte de uma submissão (Priority: P2)

**Goal**: Permitir que proponente ou gestão BraCVAM altere somente o título ou um subconjunto de valores do rascunho atual usando `PATCH /processes/{id}`.

**Independent Test**: Com valores já gravados, alterar um campo e depois só o título; os atributos omitidos continuam idênticos aos valores anteriores.

### Tests for User Story 2

- [X] T023 [US2] Testar que PATCH de um campo preserva cada valor omitido em `tests/api/routers/test_process_submission_update.py`
- [X] T024 [US2] Testar que PATCH somente de título preserva os valores do formulário em `tests/api/routers/test_process_submission_update.py`
- [X] T025 [US2] Testar que PATCH com título e um campo retorna a representação atualizada em `tests/api/routers/test_process_submission_update.py`
- [X] T026 [US2] Testar que PATCH sem título nem valores retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T027 [US2] Testar que PATCH com chave desconhecida retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T028 [US2] Testar que PATCH com chave desconhecida preserva o campo válido do mesmo pedido em `tests/api/routers/test_process_submission_update.py`
- [X] T029 [US2] Testar que PATCH com valor abaixo do limite numérico retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T030 [US2] Testar que PATCH com valor abaixo do limite numérico preserva o estado anterior em `tests/api/routers/test_process_submission_update.py`
- [X] T031 [US2] Testar que usuário com gestão BraCVAM efetiva atualiza o rascunho por PATCH em `tests/api/routers/test_process_submission_update.py`

### Implementation for User Story 2

- [X] T032 [US2] Implementar validação de payload parcial não vazio e preservação de campos omitidos em `src/pivma/core/process_engine.py`
- [X] T033 [US2] Expor `PATCH /processes/{id}` com o contrato de atualização parcial em `src/pivma/routers/processes.py`

**Checkpoint**: PATCH entrega correções pontuais sem substituir valores omitidos e sem ampliar as permissões existentes.

---

## Phase 5: User Story 3 - Consultar submissões devolvidas (Priority: P3)

**Goal**: Expor a versão vigente por padrão e snapshots somente leitura de versões devolvidas, usando as runs e artefatos já persistidos.

**Independent Test**: Submeter a run 1, devolvê-la, editar e reenviar a run 2; a consulta histórica da run 1 conserva seu título e conteúdo, enquanto a leitura vigente apresenta a run 2.

### Tests for User Story 3

- [X] T034 [P] [US3] Testar que o dossiê criado no envio formal contém o título da instância em `tests/api/routers/test_form_submission.py`
- [X] T035 [P] [US3] Testar que o dossiê criado no envio formal contém referências dos anexos da run em `tests/api/routers/test_form_attachments.py`
- [X] T036 [US3] Testar que devolução para revisão mantém a run anterior submetida em `tests/api/routers/test_triage_decision.py`
- [X] T037 [US3] Testar que reenvio após devolução conserva o título congelado da run anterior em `tests/api/routers/test_process_submission_update.py`
- [X] T038 [US3] Testar que reenvio após devolução conserva os valores congelados da run anterior em `tests/api/routers/test_process_submission_update.py`
- [X] T039 [US3] Testar que a leitura padrão do formulário apresenta a maior run vigente em `tests/api/routers/test_process_submission_update.py`
- [X] T040 [US3] Testar que GET de lista retorna apenas versões devolvidas em `tests/api/routers/test_process_submission_update.py`
- [X] T041 [US3] Testar que GET de lista ordena versões devolvidas por número decrescente em `tests/api/routers/test_process_submission_update.py`
- [X] T042 [US3] Testar que GET de versão devolvida retorna o snapshot histórico completo em `tests/api/routers/test_process_submission_update.py`
- [X] T043 [P] [US3] Testar que substituição de anexo na run devolvida não soft-deleta o artefato referenciado pela run submetida em `tests/api/routers/test_form_attachments.py`

### Implementation for User Story 3

- [X] T044 [US3] Incluir o título no `metadata_payload` do artefato `proposal_dossier` durante o envio formal em `src/pivma/core/process_engine.py`
- [X] T045 [US3] Implementar projeção de versões devolvidas a partir de runs submetidas, dossiês e eventos `REVISION_REQUESTED` em `src/pivma/core/process_engine.py`
- [X] T046 [US3] Expor GET `/processes/{id}/submission-versions` em `src/pivma/routers/processes.py`
- [X] T047 [US3] Expor GET `/processes/{id}/submission-versions/{run_number}` em `src/pivma/routers/processes.py`
- [X] T048 [US3] Impedir soft-delete de anexo ainda referenciado por `FormValue` de formulário submetido em `src/pivma/core/process_engine.py`

**Checkpoint**: Uma devolução produz histórico somente leitura baseado no snapshot do envio; alterações da run nova não reescrevem a run anterior.

---

## Phase 6: User Story 4 - Proteger a integridade da submissão (Priority: P4)

**Goal**: Garantir autenticação, autorização contextual, imutabilidade após envio, bloqueio de estados não editáveis e auditoria sem valores sensíveis.

**Independent Test**: Tentar PUT/PATCH sem sessão, como terceiro, após envio e em processo encerrado; confirmar que nenhum dado muda. Em atualização válida, consultar o evento de auditoria.

### Tests for User Story 4

- [X] T049 [US4] Testar que PUT sem autenticação retorna 401 em `tests/api/routers/test_process_submission_update.py`
- [X] T050 [US4] Testar que PATCH por usuário fora da visibilidade retorna 404 em `tests/api/routers/test_process_submission_update.py`
- [X] T051 [US4] Testar que PATCH por usuário fora da visibilidade preserva a submissão em `tests/api/routers/test_process_submission_update.py`
- [X] T052 [US4] Testar que PUT após envio formal retorna 409 em `tests/api/routers/test_process_submission_update.py`
- [X] T053 [US4] Testar que PATCH em processo encerrado retorna 409 em `tests/api/routers/test_process_submission_update.py`
- [X] T054 [US4] Testar que PATCH com atributo de instância não editável retorna 422 em `tests/api/routers/test_process_submission_update.py`
- [X] T055 [US4] Testar que PUT de rascunho não cria versão histórica em `tests/api/routers/test_process_submission_update.py`
- [X] T056 [US4] Testar que PATCH de rascunho não cria versão histórica em `tests/api/routers/test_process_submission_update.py`
- [X] T057 [US4] Testar que PUT não altera o status do processo em `tests/api/routers/test_process_submission_update.py`
- [X] T058 [US4] Testar que PATCH não altera a run atual em `tests/api/routers/test_process_submission_update.py`
- [X] T059 [US4] Testar que atualização válida cria `SUBMISSION_UPDATED` com autor em `tests/api/routers/test_process_submission_update.py`
- [X] T060 [US4] Testar que evento `SUBMISSION_UPDATED` registra a modalidade da operação em `tests/api/routers/test_process_submission_update.py`
- [X] T061 [US4] Testar que evento `SUBMISSION_UPDATED` registra nomes afetados sem valores de formulário em `tests/api/routers/test_process_submission_update.py`
- [X] T062 [US4] Testar que leitura histórica fora da visibilidade contextual retorna 404 em `tests/api/routers/test_process_submission_update.py`
- [X] T063 [US4] Testar que endpoint de versão não aceita método PATCH em `tests/api/routers/test_process_submission_update.py`

### Implementation for User Story 4

- [X] T064 [US4] Registrar `SUBMISSION_UPDATED` com ator, modalidade e chaves afetadas sem valores em `src/pivma/core/process_engine.py`
- [X] T065 [US4] Aplicar `process_visibility_clause` à consulta de versões em `src/pivma/routers/processes.py`

**Checkpoint**: As regras de imutabilidade e acesso são aplicadas pelo backend; o histórico não amplia a visibilidade do processo.

---

## Phase 7: Demonstração e verificação transversal

**Purpose**: Cumprir o critério de conclusão do projeto com uma demonstração descartável, seed mínimo e evidência de qualidade sobre a API real.

- [X] T066 Criar seed idempotente com processo em rascunho e pelo menos cinco campos de dados em `scripts/seeds/seed_submission_update.py`
- [X] T067 Criar página desacoplada que carrega o rascunho e executa PUT pela API real em `demos/submission-update/index.html`
- [X] T068 Atualizar a página de demonstração para executar PATCH pela API real em `demos/submission-update/index.html`
- [X] T069 Registrar a demonstração e o comando do seed em `demos/index.html`
- [X] T070 Validar manualmente PUT e PATCH da demonstração em até dois minutos em `demos/submission-update/index.html`
- [X] T071 Executar os cenários de atualização em `tests/api/routers/test_process_submission_update.py`
- [X] T072 Executar as regressões do snapshot de envio em `tests/api/routers/test_form_submission.py`
- [X] T073 Executar as regressões de devolução em `tests/api/routers/test_triage_decision.py`
- [X] T074 Executar as regressões de retenção de anexo em `tests/api/routers/test_form_attachments.py`
- [X] T075 Executar a verificação estática dos arquivos alterados com `poetry run ruff check src tests scripts` a partir de `pyproject.toml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: pode iniciar imediatamente.
- **Phase 2**: depende de T001 e bloqueia os incrementos de escrita e leitura.
- **US1**: depende de T002–T006 e é o MVP técnico.
- **US2**: depende da substituição transacional de US1, pois amplia a mesma operação para preservação de valores omitidos.
- **US3**: depende do envio e da abertura de runs já existentes; integra a versão vigente produzida por US1/US2.
- **US4**: depende dos endpoints de escrita e leitura, pois audita e comprova suas garantias.
- **Phase 7**: depende das histórias entregues.

### User Story Completion Order

`Setup → Foundational → US1 → US2 → US3 → US4 → Demo e verificação`

### Parallel Opportunities

- T034 e T035 podem ser escritos em paralelo por estarem em arquivos de regressão distintos.
- T043 pode avançar em paralelo com T045–T047 depois que a regra de retenção estiver definida, pois cobre outro arquivo e outro fluxo.
- T066 pode ser desenvolvido em paralelo com T067 depois que o contrato HTTP estiver estável; T068 depende de T067.

## Implementation Strategy

### MVP First

1. Concluir T001–T006.
2. Concluir US1 (T007–T022).
3. Executar T071 para os casos de PUT.
4. Validar o rascunho por PUT somente com as guardas de segurança já ativas.

### Incremental Delivery

1. Acrescentar PATCH sem duplicar serviço ou regra de validação.
2. Acrescentar snapshot e leitura de versões devolvidas com as entidades existentes.
3. Fechar auditoria e provas de imutabilidade.
4. Publicar a demo real e o seed mínimo; executar os portões de teste e lint.

## Format Validation

Todos os itens acima seguem `- [ ] TNNN [P?] [US?] descrição com caminho`. As tarefas de histórias têm rótulo de história; setup, fundação e verificação transversal não têm rótulo. Cada tarefa de teste descreve um comportamento observável único.

## Phase 8: Convergence

- [X] T076 Executar os cenários de integração e validar PUT/PATCH da demonstração contra a API real quando o ambiente Docker estiver disponível, registrando a evidência de aceite per FR-017, FR-025 e SC-006 (partial)
