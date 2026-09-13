---

description: "Tarefas executáveis para a revisão de exclusão (soft-delete) e arquivamento de processos"
---

# Tasks: Exclusão (Soft-Delete) e Arquivamento de Processos

**Input**: Artefatos de design em `specs/022-process-retirement/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/process-lifecycle.openapi.yaml` e `quickstart.md` (todos revisados em 2026-09-13)

**Contexto**: Esta é uma **revisão** de uma feature já implementada e mesclada como PR #19. As tarefas abaixo descrevem a migração do desenho anterior (4 endpoints: `DELETE`, `/withdrawal`, `/cancellation`, `/archive`; exclusão física de rascunho) para o desenho revisado (2 endpoints: `DELETE` como soft-delete universal e `/archive`; ver Clarifications de 2026-09-13 em `spec.md`). **Status: implementado em 2026-09-13** — todas as fases abaixo foram executadas; ver Phase 7 para correções adicionais que o filtro global de soft-delete exigiu fora do escopo original destas tarefas.

**Classificação**: **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: `DELETE` passa a ser soft-delete universal (proponente efetivo OU perfil global Admin/BraCVAM), aceito em qualquer estado não-terminal, preservando sempre os documentos em disco; `/withdrawal` e `/cancellation` são removidos; um único `event_type` (`PROCESS_DELETED`) cobre toda exclusão; um filtro de soft-delete é aplicado globalmente a toda entidade `AuditMixin` via `do_orm_execute`/`with_loader_criteria`. **DECISÃO TÉCNICA REGISTRADA**: a simplificação de cargos globais (RBAC) é uma dependência externa (Feature 023), fora do escopo destas tarefas.

**Tests**: Obrigatórios. A feature altera autorização, transações e execução assíncrona, classificados como risco alto. Ajuste cada teste afetado antes ou junto da tarefa de implementação que ele cobre; confirme que o teste falha antes da mudança e passa depois.

**Sem migração**: nenhuma coluna nova é necessária (`deleted_at`/`deleted_by` já existem via `AuditMixin`). Não criar migration, tabela, perfil RBAC ou estado `DELETED`.

## Formato

Cada linha de tarefa usa `- [ ] T### [P?] [US?] descrição com caminho`. `[P]` indica arquivos distintos e ausência de dependência entre as tarefas.

## Phase 1: Preparação

**Purpose**: Ajustar a massa de teste reutilizável para o novo modelo, em que o histórico de submissão deixa de determinar autorização.

- [X] T001 [P] Em `tests/factories/process_retirement_factory.py`, adicionar/ajustar uma factory de usuário com perfil global `administrator`/`bracvam` distinto do proponente do processo, para os testes de exclusão administrativa (US1)
- [X] T002 Em `tests/factories/process_retirement_factory.py`, remover ou generalizar os helpers que hoje distinguem "rascunho nunca submetido" de "processo com submissão formal" apenas para fins de exclusão (a distinção deixou de afetar `DELETE`); preservar os helpers usados por outras specs (ex.: `REVISION_REQUESTED`) se ainda forem referenciados por elas

---

## Phase 2: Fundamentos compartilhados

**Purpose**: Remover os caminhos de código exclusivos de `/withdrawal` e `/cancellation`, unificar os códigos de ação e instalar o filtro global de soft-delete — tudo isso bloqueia as histórias de usuário abaixo.

- [X] T003 Em `src/pivma/core/process_engine.py`, remover as constantes `LIFECYCLE_WITHDRAW` e `LIFECYCLE_CANCEL`; renomear `LIFECYCLE_DELETE_DRAFT` para `LIFECYCLE_DELETE = 'DELETE'`
- [X] T004 Em `src/pivma/core/process_engine.py`, reescrever `lifecycle_available_actions()` para aceitar apenas `status`, `can_delete` e `can_review` (remover os parâmetros `never_submitted` e `revision_pending`) e retornar somente `LIFECYCLE_DELETE` (quando o processo não é terminal e `can_delete`) e `LIFECYCLE_ARCHIVE` (quando `status in {CLOSED, CANCELLED}` e `can_review`)
- [X] T005 Em `src/pivma/core/process_engine.py`, verificar todos os chamadores de `_has_formal_submission` e `_has_pending_revision`; remover essas funções apenas se nenhum outro fluxo (ex.: Feature 021, devolução para correção) ainda depender delas — caso contrário, apenas parar de usá-las para gating de `DELETE`
- [X] T006 [P] Em `src/pivma/core/database/__init__.py`, registrar um listener `sqlalchemy.event.listens_for(Session, 'do_orm_execute')` (import de `sqlalchemy.orm.Session`) que aplica `with_loader_criteria(AuditMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)` a toda consulta `SELECT` cujo `execution_options` não contenha `skip_soft_delete_filter=True`
- [X] T007 Em `src/pivma/schemas.py` (linhas ~426-427 e ~439-443), trocar `Literal['DELETE_DRAFT', 'WITHDRAW', 'CANCEL', 'ARCHIVE']` por `Literal['DELETE', 'ARCHIVE']` nas duas ocorrências (`ProcessInstanceDetail`/listagem e `ProcessLifecycleResponse`)

**Checkpoint**: O domínio só reconhece dois códigos de ação; o filtro global de soft-delete está ativo; nenhuma rota ainda foi alterada.

---

## Phase 3: User Story 1 - Excluir (soft-delete) um processo (Priority: P1) 🎯 MVP

**Goal**: Permitir ao proponente efetivo, ou a um usuário com perfil global Admin/BraCVAM, excluir logicamente um processo em qualquer estado não-terminal, preservando registros e documentos.

**Independent Test**: Excluir um processo em cada estágio (nunca submetido, em validação, devolvido) como proponente e, em outro caso, como Admin/BraCVAM; confirmar `deleted_at`/`deleted_by`, `status=CANCELLED`, cascata de filhos pendentes e arquivos intactos em `ATTACHMENTS_DIR/{process_id}/`.

### Tests for User Story 1

- [X] T008 [US1] Em `tests/api/routers/test_process_retirement.py`, atualizar os testes que hoje restringem `DELETE` a rascunho nunca submetido: o proponente efetivo deve poder excluir o processo em qualquer estado não-terminal (inclusive já submetido ou devolvido), recebendo `204`
- [X] T009 [US1] Em `tests/api/routers/test_process_retirement.py`, adicionar teste: usuário com perfil global `administrator` ou `bracvam` executa `DELETE` em processo de outro proponente e recebe `204`
- [X] T010 [US1] Em `tests/api/routers/test_process_retirement.py`, manter/ajustar o teste de que um usuário comum (nem proponente efetivo, nem Admin/BraCVAM) recebe `403 forbidden` ao tentar `DELETE`
- [X] T011 [US1] Em `tests/api/routers/test_process_retirement.py`, substituir o teste de `DELETE` em processo com `SUBMISSION_SUBMITTED` (hoje espera `invalid_transition` por ser "não-rascunho") por um teste de que `DELETE` é aceito nesse caso
- [X] T012 [US1] Em `tests/api/routers/test_process_retirement.py`, atualizar o teste de `DELETE` em processo já terminal (`CLOSED`/`CANCELLED`/`ARCHIVED`) para esperar `409 invalid_transition` com o processo ainda visível (não mais `404`, já que o processo não é mais removido fisicamente)
- [X] T013 [US1] Em `tests/integration/database/test_process_retirement_deletion.py`, substituir as asserções de remoção física por asserções de soft-delete: `deleted_at`/`deleted_by` preenchidos, `status=CANCELLED`, e o processo, seus registros vinculados e seus documentos em `ATTACHMENTS_DIR/{process_id}/` permanecendo intactos no banco e no disco
- [X] T014 [US1] Em `tests/integration/database/test_process_retirement_concurrency.py`, ajustar os cenários de concorrência para a autorização unificada (proponente vs. Admin/BraCVAM disputando a mesma exclusão)
- [X] T015 [US1] Em `tests/api/routers/test_process_retirement.py`, migrar os testes de cascata seletiva (tarefa, atividade, `ActivityRun`, fase e `EvaluationRun` pendentes cancelados; itens concluídos preservados; formulário pendente não submetido artificialmente) do fluxo `/cancellation` para o novo `DELETE`
- [X] T016 [US1] Em `tests/integration/ai/test_process_retirement_pre_evaluation.py`, ajustar os testes de conclusão tardia e de `retry_run` para disparar a exclusão via `DELETE` em vez de `/cancellation`
- [X] T017 [US1] Em `tests/api/routers/test_process_retirement.py`, adicionar teste: tanto a exclusão pelo proponente quanto pelo Admin/BraCVAM produzem o mesmo `event_type` `PROCESS_DELETED` (nenhum evento distingue o ator no tipo)
- [X] T018 [US1] Em `tests/api/routers/test_process_retirement.py`, adicionar teste: `GET /processes` nunca retorna um processo soft-deletado, mesmo para o proponente efetivo ou para Admin/BraCVAM
- [X] T019 [P] [US1] Em `tests/integration/database/test_process_retirement_deletion.py`, adicionar teste de infraestrutura: uma consulta comum via ORM (`select(ProcessInstance)`) omite um processo soft-deletado; a mesma consulta com `execution_options(skip_soft_delete_filter=True)` o retorna

### Implementation for User Story 1

- [X] T020 [US1] Em `src/pivma/core/process_engine.py`, implementar `delete_process(session, process_id, user_id)`: bloquear a linha via `_locked_lifecycle_process`, autorizar com `await is_active_effective_proponent(...) or await has_platform_wide_access(...)`, reaproveitar a cascata de `_cancel_process_locked` (sem a guarda `_has_formal_submission`), chamar `process.set_deletion_audit(user_id)` e registrar `event_type='PROCESS_DELETED'`
- [X] T021 [US1] Em `src/pivma/core/process_engine.py`, remover `delete_unsubmitted_draft`, `withdraw_process`, `cancel_process` e `_delete_process_aggregate` (substituídos por `delete_process` em T020); remover a chamada a `remove_process_attachments` do caminho de exclusão
- [X] T022 [US1] Em `src/pivma/routers/processes.py`, trocar a implementação do handler `DELETE /processes/{id}` para chamar `delete_process` (mantendo resposta `204 No Content`); remover os handlers das rotas `/{id}/withdrawal` e `/{id}/cancellation`
- [X] T023 [US1] Em `src/pivma/routers/processes.py`, remover os imports agora não utilizados (`withdraw_process`, `cancel_process`, `delete_unsubmitted_draft`) e adicionar o import de `delete_process`

**Checkpoint**: `DELETE /processes/{id}` soft-deleta qualquer processo não-terminal do proponente efetivo ou de Admin/BraCVAM, preservando registros e anexos; `/withdrawal` e `/cancellation` não existem mais.

---

## Phase 4: User Story 2 - Arquivar um processo terminal (Priority: P2)

**Goal**: Preservar o arquivamento existente, agora também aceitando um `CANCELLED` produzido pela exclusão unificada.

**Independent Test**: Arquivar um processo `CLOSED` e outro `CANCELLED` (este último produzido pelo novo `DELETE`); confirmar que ambos saem da listagem padrão e entram na consulta histórica autorizada.

### Tests for User Story 2

- [X] T024 [US2] Em `tests/api/routers/test_process_retirement.py`, adicionar teste: arquivar um processo cujo `CANCELLED` foi produzido pelo novo `DELETE` (US1) é aceito e resulta em `ARCHIVED`
- [X] T025 [US2] Em `tests/api/routers/test_process_retirement.py`, revisar os testes já existentes de arquivamento (`CLOSED`→`ARCHIVED`, processo ativo rejeitado, usuário sem `triage.review` recusado, `GET /processes?status=ARCHIVED` restrito a `triage.review`) para não dependerem mais de cenários criados via `/withdrawal`/`/cancellation`

### Implementation for User Story 2

- [X] T026 [US2] Em `src/pivma/core/process_engine.py`, confirmar que `archive_process` não precisa de mudança funcional (mantém `triage.review`, precondição `status in {CLOSED, CANCELLED}`); atualizar apenas docstrings/comentários que mencionem `/withdrawal` ou `/cancellation`
- [X] T027 [US2] Em `src/pivma/routers/processes.py`, confirmar que o handler `PATCH /processes/{id}/archive` não é afetado além da remoção das rotas vizinhas (T022)

**Checkpoint**: Arquivamento funciona igualmente sobre `CANCELLED` histórico e sobre `CANCELLED` produzido pela nova exclusão.

---

## Phase 5: User Story 3 - Front-end conhece as ações permitidas (Priority: P3)

**Goal**: `available_actions` expõe somente `DELETE`/`ARCHIVE`, sempre revalidados no backend.

**Independent Test**: Consultar processos em estados variados como proponente e como Admin/BraCVAM e comparar `available_actions` com o resultado real das operações.

### Tests for User Story 3

- [X] T028 [US3] Em `tests/api/routers/test_process_retirement.py`, atualizar todos os testes de `available_actions` para o conjunto `{DELETE, ARCHIVE}` (remover asserções sobre `DELETE_DRAFT`, `WITHDRAW`, `CANCEL`)
- [X] T029 [US3] Em `tests/api/routers/test_process_retirement.py`, manter/ajustar o teste de que uma chamada a `DELETE` fora de `available_actions` ainda é revalidada e recusada pelo backend (o cliente não pode contornar a regra)

### Implementation for User Story 3

- [X] T030 [US3] Em `src/pivma/routers/processes.py`, confirmar que as três projeções que chamam `available_lifecycle_actions` (linhas ~372, ~438, ~485) usam a versão revisada de `lifecycle_available_actions` (T004) sem lógica adicional local

**Checkpoint**: A interface só recebe `DELETE`/`ARCHIVE`; o backend continua autoritativo.

---

## Phase 6: Demonstração, seed, documentação e validação transversal

**Purpose**: Alinhar demo, seed e README ao novo contrato, e fechar a qualidade da revisão.

- [X] T031 [P] Em `demos/process-retirement/index.html`, remover os botões/fluxos de desistência e cancelamento administrativo; manter exclusão (como proponente e como Admin/BraCVAM) e arquivamento, refletindo `204` para `DELETE`
- [X] T032 Em `demos/index.html`, ajustar a descrição da demonstração de retirement se ela mencionar as quatro ações antigas
- [X] T033 [P] Em `scripts/seeds/seed_process_retirement.py`, reduzir para três cenários: processo excluível pelo proponente, processo excluível por Admin/BraCVAM (de outro proponente) e processo `CLOSED` arquivável — mais um caso bloqueado (processo já `ARCHIVED` recusando `DELETE`)
- [X] T034 Em `scripts/seeds/seed_all.py`, ajustar a chamada ao seed de retirement se a assinatura ou os cenários exportados mudarem
- [X] T035 [P] Em `README.md` (linhas ~389-392), atualizar a tabela de rotas do módulo de processos: uma linha para `DELETE /processes/{id}` descrevendo soft-delete universal (proponente efetivo ou Admin/BraCVAM) e remover as linhas de `/withdrawal` e `/cancellation`
- [X] T036 Varrer `src/`, `tests/`, `demos/` e `scripts/seeds/` por referências residuais a `DELETE_DRAFT`, `WITHDRAW`, `CANCEL`, `/withdrawal` ou `/cancellation` e removê-las ou atualizá-las
- [X] T037 Executar `poetry run ruff check src tests scripts/seeds` e corrigir problemas
- [X] T038 Executar `poetry run pytest -q tests/api/routers/test_process_retirement.py`
- [X] T039 Executar `poetry run pytest -q tests/unit/core/test_process_retirement.py tests/integration/database/test_process_retirement_deletion.py tests/integration/database/test_process_retirement_concurrency.py tests/integration/ai/test_process_retirement_pre_evaluation.py`
- [X] T040 Reexecutar os passos de `specs/022-process-retirement/quickstart.md` contra a API local e registrar ajustes necessários

---

## Phase 7: Correções fora do escopo original, exigidas pelo filtro global (Clarification 2026-09-13, Q5)

**Purpose**: A primeira execução de T037-T039 (lint + suítes da própria feature) passou, mas rodar a suíte completa do repositório revelou que o filtro global de soft-delete (T006) quebrava 11 testes em 3 specs sem nenhuma relação com a 022, porque parte do sistema depende de enxergar registros soft-deletados por padrão (não é comportamento incorreto dessas specs — é a decisão explícita da 022 de aplicar o filtro a **todo** `AuditMixin`, não só a `ProcessInstance`, colidindo com esses casos). Registrado aqui porque essas correções não faziam parte de nenhuma tarefa acima.

- [X] T041 Em `src/pivma/routers/institutional.py`, `get_institution`/`get_laboratory` (consulta por id que mostra o registro mesmo inativo, expondo `active: false`) passam `execution_options={'skip_soft_delete_filter': True}` em `session.get(...)`
- [X] T042 Em `src/pivma/core/authorization.py`, `active_institutional_affiliations` passa `execution_options(skip_soft_delete_filter=True)`: o filtro global, ao ser injetado automaticamente no `outerjoin` com `Laboratory`, colidia com o `or_(laboratory_id.is_(None), Laboratory.deleted_at.is_(None))` escrito à mão para tratar o caso de afiliação sem laboratório — produzindo resultado **errado** (não apenas vazio): a afiliação sem laboratório desaparecia e uma afiliação com laboratório desativado voltava a aparecer. É o único `outerjoin` do repositório (verificado por varredura); não há evidência de outros pontos com essa mesma fragilidade
- [X] T043 Em `src/pivma/routers/users.py`, `list_users` passa `execution_options(skip_soft_delete_filter=True)` na consulta principal: `GET /users?active=false` lista contas inativas por desenho, e o filtro global as escondia
- [X] T044 Em `tests/integration/database/test_form_value_attachment_link.py`, as duas consultas que verificam soft-delete de `Artifact` diretamente passam `execution_options(skip_soft_delete_filter=True)`, já que verificar o soft-delete exige enxergar o registro soft-deletado

**Checkpoint**: Suíte completa (`poetry run pytest -q`, sem filtro de caminho) executada do zero: 686 passed, 1 skipped, 0 failed — nenhuma regressão fora do escopo desta feature.

**Risco residual não coberto por T041-T044** (reportar ao usuário, não decidir sozinho): a varredura acima foi guiada pelos testes que **falharam**; não houve auditoria exaustiva de todo `session.get()`/consulta a `AuditMixin` do repositório em busca de rotas que mostram registro inativo por id sem um teste que capture a regressão hoje. Um exemplo real já encontrado (`get_laboratory`) só apareceu porque havia um teste cobrindo exatamente esse caminho; é plausível que existam outras rotas com o mesmo padrão "mostrar registro inativo por id" em specs ainda não testadas dessa forma, que ficariam silenciosamente quebradas em produção sem nenhum teste acusando.

---

## Dependencies & Execution Order

```text
Preparação → Fundamentos → US1 (MVP) → US2 → US3 → Demonstração, seed, docs e validação
```

- A Phase 2 bloqueia todas as histórias: remove os códigos de ação antigos, reescreve `lifecycle_available_actions` e instala o filtro global de soft-delete antes de qualquer rota mudar de comportamento.
- US1 entrega o `DELETE` unificado e remove `/withdrawal`/`/cancellation`.
- US2 depende de US1 apenas para o cenário "arquivar um `CANCELLED` produzido por exclusão"; a mecânica de arquivamento em si não muda.
- US3 depende de US1 e US2 estarem com as pré-condições finais para que `available_actions` reflita o comportamento real.
- T031-T035 podem começar após US1 (a exclusão unificada já existe); T036-T040 fecham a revisão.

## Parallel Opportunities

```text
Após T002:
  T003, T004 e T006 tocam funções/arquivo distintos e podem começar em paralelo.

Após US1 (T023):
  T031 (demo), T033 (seed) e T035 (README) podem ocorrer em paralelo.

Após T036:
  T037, T038 e T039 podem executar em paralelo.
```

## Implementation Strategy

### MVP

1. Execute T001-T007 (preparação e fundamentos).
2. Execute os testes de US1 (T008-T019) antes da implementação (T020-T023) para confirmar que falham no comportamento antigo.
3. Valide soft-delete, preservação de anexos e as duas vias de autorização antes de seguir para arquivamento.

### Incremental delivery

1. US1 entrega a exclusão unificada e remove os dois endpoints descontinuados.
2. US2 confirma que o arquivamento continua correto sobre o novo `CANCELLED`.
3. US3 fecha a projeção para o front-end.
4. A fase final atualiza demo, seed, README e roda a validação completa.
