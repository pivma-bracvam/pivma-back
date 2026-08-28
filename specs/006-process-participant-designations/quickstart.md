# Quickstart: Designações e Conflito de Interesse

## Pré-requisitos

- Docker com o serviço PostgreSQL/pgvector disponível.
- Dependências instaladas pelo Poetry.
- Spec, plano, [modelo de dados](data-model.md) e [contrato HTTP](contracts/process-participants.openapi.yaml) revisados.
- Feature 005 aplicada, com instituições, laboratórios e vínculos disponíveis para cenários laboratoriais.

## Ordem mínima de implementação

1. Criar a migração após `5e31a8c7d204`, cobrindo coluna laboratorial, declarações, normalização de `proponent` e seed da permissão.
2. Evoluir os modelos e factories sem alterar os papéis legados de `Task`.
3. Adicionar schemas com testes unitários e predicates de autorização com testes de integração em PostgreSQL real.
4. Implementar o router com transações atômicas e proteção de origem.
5. Aplicar a guarda de conflito às revisões e decisões de triagem.
6. Filtrar os três novos tipos de evento na timeline.
7. Executar testes focados, regressão, lint e verificação da cadeia Alembic.
8. Atualizar o README com permissão, operações e exemplos mínimos.

## Contrato de granularidade dos testes

Cada linha abaixo representa um comportamento observável. `$speckit-tasks` deve criar uma tarefa de teste por linha ou um teste parametrizado quando somente a entrada varia sob o mesmo contrato. Um teste não deve acumular auditoria, autorização, concorrência ou paginação com o caminho de sucesso da operação.

### Schemas, unidade

| ID | Comportamento único |
|---|---|
| U-S01 | Cada um dos oito papéis aprovados é aceito pelo schema de designação; usar parametrização. |
| U-S02 | Papel fora do catálogo é rejeitado. |
| U-S03 | Papel laboratorial sem `laboratory_id` é rejeitado; parametrizar os dois papéis. |
| U-S04 | Papel não laboratorial com `laboratory_id` é rejeitado; parametrizar os seis papéis. |
| U-S05 | Justificativa composta somente por espaços é rejeitada. |
| U-S06 | Schemas de designação e declaração rejeitam campo extra; parametrizar os dois contratos. |

### Autorização e conflito, PostgreSQL real

| ID | Comportamento único |
|---|---|
| I-A01 | Permissão global ativa autoriza gestão em qualquer processo. |
| I-A02 | `group_manager` efetivo autoriza gestão somente no próprio processo. |
| I-A03 | `group_manager` revogado não autoriza gestão. |
| I-A04 | Ciclo `group_manager` de usuário inativo não autoriza gestão. |
| I-A05 | Participante comum recebe escopo próprio de leitura, sem gestão. |
| I-A06 | Pessoa externa recebe ausência de escopo de participantes. |
| I-C01 | Ausência de declaração não gera conflito. |
| I-C02 | Última declaração verdadeira de um ciclo ativo gera conflito. |
| I-C03 | Declaração falsa posterior retira o conflito do mesmo ciclo. |
| I-C04 | Conflito verdadeiro em outro ciclo ativo prevalece sobre declaração falsa. |
| I-C05 | Conflito de ciclo revogado não participa do cálculo. |
| I-C06 | Empate de `declared_at` usa o maior identificador como registro mais recente. |

### Persistência e consulta, PostgreSQL real

| ID | Comportamento único |
|---|---|
| I-D01 | FK rejeita laboratório inexistente na designação. |
| I-D02 | Índice parcial rejeita duplicidade ativa para processo, usuário e papel mesmo quando as duas designações informam laboratórios diferentes. |
| I-D03 | Novo ciclo equivalente é aceito após revogação. |
| I-D04 | Exclusão física da designação referenciada por declaração é rejeitada pela FK. |
| I-Q01 | Consulta atual marca designação laboratorial como efetiva com vínculo vigente. |
| I-Q02 | Consulta atual marca designação como inefetiva após inativação de vínculo, laboratório ou usuário; parametrizar a origem da inativação. |
| I-Q03 | Consulta de última declaração usa ordenação por momento e identificador. |

### Migração, PostgreSQL real

| ID | Comportamento único |
|---|---|
| I-M01 | Upgrade adiciona a coluna opcional `assignments.laboratory_id`. |
| I-M02 | Upgrade adiciona a FK de `assignments.laboratory_id` sem cascata. |
| I-M03 | Upgrade cria a tabela `conflict_interest_declarations`. |
| I-M04 | Upgrade cria o índice determinístico de última declaração. |
| I-M05 | Upgrade normaliza designação legada `PROPONENT` para `proponent`. |
| I-M06 | Upgrade preserva cada tipo de registro preexistente da feature 004; parametrizar processo, tarefa, designação e evento sob a mesma regra de preservação. |
| I-M07 | Upgrade não cria laboratório, declaração ou evento implícito; parametrizar o tipo de registro sob a mesma regra de ausência de backfill. |
| I-M08 | Upgrade insere a nova permissão e a concede somente ao perfil Administrador. |
| I-M09 | Downgrade remove somente as estruturas e o seed da feature 006. |
| I-M10 | Downgrade restaura designações locais `proponent` para `PROPONENT`. |
| I-M11 | Downgrade preserva processo, tarefa, designação e evento anteriores; parametrizar o tipo de registro sob a mesma regra. |

### API de designações

| ID | Comportamento único |
|---|---|
| A-D01 | Administrador cria designação individual válida e recebe 201. |
| A-D02 | `group_manager` cria designação válida no próprio processo e recebe 201. |
| A-D03 | Gestor cria designação laboratorial com vínculo vigente e recebe 201. |
| A-D04 | Usuário ou laboratório inexistente produz 404 para gestor autorizado; parametrizar o tipo de alvo. |
| A-D05 | Usuário ou laboratório inativo produz 409; parametrizar o tipo de alvo. |
| A-D06 | Processo inexistente produz 404 para gestor global autorizado. |
| A-D07 | Processo logicamente excluído produz 409 para gestor global autorizado. |
| A-D08 | Ausência de vínculo laboratorial vigente produz 409. |
| A-D09 | Duplicidade ativa sequencial produz 409; a constraint específica com laboratórios diferentes pertence a I-D02. |
| A-D10 | `group_manager` efetivo do processo conclui revogação válida e recebe 204. |
| A-D11 | Revogação repetida produz 409. |
| A-D12 | Nova designação equivalente após revogação produz outro ciclo e 201. |
| A-D13 | Listagem do gestor retorna todos os ciclos ativos do processo. |
| A-D14 | Listagem do participante retorna somente os ciclos próprios. |
| A-D15 | Listagem sinaliza `has_conflict = null` sem declaração. |
| A-D16 | Listagem sinaliza `effective = false` após perda de vínculo. |
| A-D17 | Listagem do gestor sinaliza `has_conflict = true` após declaração vigente com conflito. |

### API de conflito e histórico

| ID | Comportamento único |
|---|---|
| A-C01 | Titular declara conflito em designação ativa e recebe 201. |
| A-C02 | Titular declara ausência de conflito em nova linha e recebe 201. |
| A-C03 | Outro usuário não declara pelo titular e recebe 403. |
| A-C04 | Titular não declara em ciclo revogado e recebe 409. |
| A-C12 | Histórico do gestor expõe a justificativa da declaração. |
| A-C13 | Histórico do titular expõe a justificativa da própria declaração. |
| A-C05 | Histórico do gestor inclui ciclos ativos e revogados. |
| A-C06 | Histórico do participante inclui somente ciclos próprios. |
| A-C07 | Histórico ordena ciclos por atribuição e identificador. |
| A-C08 | Histórico ordena declarações por declaração e identificador. |
| A-C09 | Paginação rejeita `limit` acima de 200 com 422. |
| A-C10 | Paginação aplica `offset` e `limit` sem repetir ciclos. |
| A-C11 | Participante recebe a mesma resposta 403 para designação de outro usuário e identificador desconhecido. |

### Segurança, auditoria e timeline

| ID | Comportamento único |
|---|---|
| A-S01 | Cada operação da feature retorna 401 sem autenticação; parametrizar as cinco operações. |
| A-S02 | Pessoa externa recebe 403 ao listar participantes de processo conhecido. |
| A-S03 | Pessoa externa recebe a mesma resposta 403 para processo desconhecido. |
| A-S08 | Pessoa externa recebe a mesma resposta 403 no histórico de processo conhecido e desconhecido. |
| A-S04 | `group_manager` de outro processo recebe 403 ao designar. |
| A-S05 | Mutação sem origem confiável recebe 403; parametrizar designar, revogar e declarar. |
| A-S06 | `rbac.assignments.manage` e `institutional.affiliations.manage` não concedem gestão de participantes; parametrizar a permissão e as operações de designar e revogar sob a mesma fronteira. |
| A-S07 | `group_manager` de outro processo recebe 403 ao revogar. |
| A-A01 | Cada mutação concluída grava o tipo e contexto de evento exigidos; parametrizar designação, revogação e declaração. |
| A-A02 | Designação duplicada rejeitada não grava `PARTICIPANT_ASSIGNED`. |
| A-A03 | Revogação repetida rejeitada não grava outro `PARTICIPANT_REVOKED`. |
| A-A04 | Declaração por terceiro rejeitada não grava `CONFLICT_DECLARED`. |
| A-A05 | Criação de processo grava `PARTICIPANT_ASSIGNED` do proponente com `source = process_creation`. |
| A-A06 | Designação rejeitada por alvo inexistente ou vínculo laboratorial ausente não grava `PARTICIPANT_ASSIGNED`; parametrizar a causa. |
| A-T01 | Gestor vê todos os novos eventos na timeline. |
| A-T02 | Participante vê somente os próprios eventos de participante na timeline. |
| A-T03 | Pessoa externa não recebe os novos eventos na timeline. |
| A-T04 | Filtragem dos novos eventos não remove eventos anteriores da timeline. |
| A-T05 | Timeline ordena eventos com o mesmo `occurred_at` pelo identificador crescente. |

### Concorrência, bloqueio e regressão

| ID | Comportamento único |
|---|---|
| A-X01 | Duas designações equivalentes concorrentes resultam em 201 e 409 e um ciclo ativo. |
| A-B01 | Conflito vigente bloqueia gravação de revisão de triagem com 403. |
| A-B02 | Conflito vigente bloqueia decisão de triagem com 403. |
| A-B03 | Ausência de conflito preserva revisão de triagem existente. |
| A-B04 | Declaração falsa posterior restabelece decisão de triagem. |
| A-B05 | Revisão bloqueada não cria nem altera `FieldReview` ou evento de revisão. |
| A-B06 | Decisão bloqueada não cria `Decision` nem evento de decisão. |
| A-B07 | Conflito vigente em um papel bloqueia ação autorizada por outro papel ativo. |
| A-B08 | Revogação do ciclo conflitado restabelece a ação autorizada por outro ciclo ativo. |
| A-R01 | Criação de processo mantém uma única designação `proponent`. |
| A-R02 | Listagem de tarefas mantém `assigned_role = 'PROPONENT'`. |
| A-P01 | Após preparar 200 ciclos e executar uma chamada de aquecimento, pelo menos 19 de 20 listagens atuais medidas somente durante a requisição HTTP terminam em até 2 segundos. |
| A-P02 | Após preparar 200 ciclos e executar uma chamada de aquecimento, pelo menos 19 de 20 consultas históricas medidas somente durante a requisição HTTP terminam em até 2 segundos. |

## Rastreabilidade entre requisitos e evidências

| Requisito | Evidências principais |
|---|---|
| FR-001 | A-S01 |
| FR-002 | U-S01, U-S02 |
| FR-003 | U-S03, A-D03, A-D08 |
| FR-004 | U-S04 |
| FR-005 | A-D04, A-D05, A-D06, A-D07, A-D08 |
| FR-006 | I-D02, A-D09, A-X01 |
| FR-007 | I-D03, A-D10, A-D12 |
| FR-008 | I-Q02, A-D16 |
| FR-009 | I-M05, I-M10, A-R01 |
| FR-010 | I-A01, I-A02, I-A03, A-D10, A-S04, A-S07 |
| FR-011 | I-A01, I-A02, I-M08 |
| FR-012 | I-A03, I-A04, I-Q02 |
| FR-013 | A-D01, A-D10, A-D13, A-C05 |
| FR-014 | A-D13, A-D14, A-C05, A-C06, A-S02, A-S08 |
| FR-015 | A-C01, A-C03, A-C11 |
| FR-016 | U-S05, A-C01 |
| FR-017 | A-C02, A-C05 |
| FR-018 | I-C01, I-C02, I-C03 |
| FR-019 | I-C04, I-C05 |
| FR-020 | A-B01, A-B02, A-B05, A-B06, A-B07 |
| FR-021 | A-B01, A-B02, A-R02 |
| FR-022 | A-B04, A-B08, A-D10 |
| FR-023 | A-D15, A-D17, A-C12, A-C13, A-T01, A-T02 |
| FR-024 | A-A01, A-A05, A-A06 |
| FR-025 | A-A01, A-A05, A-T01 |
| FR-026 | A-C05, A-C06, A-T02, A-T03 |
| FR-027 | A-C07, A-C08, A-C09, A-C10, A-T05 |
| FR-028 | A-S05 |
| FR-029 | A-R01, A-R02 e regressão completa |
| FR-030 | I-M06, I-M07, I-M09, I-M11 |
| FR-031 | Matriz completa e comandos de verificação |
| FR-032 | Revisão de escopo do plano e ausência de contratos fora da feature |

## Cenários manuais mínimos

### Fluxo cronometrado de designação

1. Autenticar uma conta com `process.participants.manage`.
2. Criar uma designação individual e confirmar `201`.
3. Listar participantes e confirmar o ciclo ativo sem declaração.
4. Revogar a designação e confirmar `204` e ausência na listagem atual.

O fluxo de designar, confirmar e revogar deve ser concluído em até 2 minutos em validação manual cronometrada.

### Fluxo funcional de conflito

1. Criar uma designação ativa e autenticar seu titular.
2. Declarar conflito e confirmar `201`.
3. Tentar registrar revisão de triagem e confirmar `403`.
4. Autenticar o gestor e confirmar a sinalização na listagem, no histórico e na timeline.

Este fluxo valida comportamento e não integra a medição de 2 minutos de SC-007.

## Comandos de verificação

```bash
docker compose up -d db
PYTHONPATH=src poetry run alembic upgrade head
poetry run pytest -q tests/unit/schemas/test_participant_schemas.py
poetry run pytest -q tests/integration/database/test_participant_authorization.py
poetry run pytest -q tests/integration/database/test_participant_constraints.py
poetry run pytest -q tests/integration/migrations/test_participant_migration.py
poetry run pytest -q tests/api/routers/test_participant_router.py tests/api/routers/test_participant_security.py
poetry run pytest -q tests/api/routers/test_participant_concurrency.py tests/api/routers/test_participant_task_blocking.py tests/api/routers/test_participant_timeline.py
poetry run pytest -q tests/api/routers/test_participant_timed_acceptance.py
poetry run pytest -q
poetry run ruff check
poetry run alembic heads
```

Confira a saída direta do Pytest. O task `poetry test` não serve como evidência de sucesso porque ignora a falha da etapa.

## Critério de encerramento

- Cada requisito funcional relevante possui pelo menos um teste identificável na matriz.
- O caminho de designação, declaração, bloqueio e revogação está coberto por API.
- Predicates de elegibilidade, conflito e escopo têm testes isolados em PostgreSQL real.
- PostgreSQL real valida FK, unicidade parcial, última declaração, concorrência e migração.
- Autenticação, autorização global e local, origem confiável e exposição da timeline têm testes próprios.
- Regressão completa, lint e cadeia de migração passam sem ocultar falhas.
