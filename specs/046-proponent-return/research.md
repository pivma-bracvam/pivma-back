# Research: Retorno ao Proponente

Não restou `NEEDS CLARIFICATION`. As referências de linha valem para o commit
`de4a614`.

## R1. Leitura dos pareceres de uma execução

**Decision**: nova função `submission_run_reviews(session, process_id,
run_number)` em `process_engine.py`. Uma consulta liga `FieldReview`,
`FormField`, `FormInstance`, `ActivityRun` e `ActivityInstance` e devolve um
dicionário por `field_key`, com `status`, `comments` e `reviewed_at`.

Só entram pareceres de execução da triagem `COMPLETED`, ligada por
`FieldReview.activity_run_id`, para a versão devolvida não mostrar rascunho
depois de uma contestação.

A consulta usa `skip_soft_delete_filter=True` e filtra `deleted_at` à mão em
todas as tabelas, menos `FormField`. O filtro global de soft delete
(`core/database/__init__.py`) alcança as entidades unidas, então sem essa
opção o parecer de um campo removido sumiria (FR-004). A ordem por
`reviewed_at` faz o parecer mais recente vencer se houver mais de uma execução
da triagem sobre o mesmo formulário.

**Rationale**: `form_inst.reviews` carrega só o ID do campo e `field_map` traz
só campos ativos. A nova função atende às duas rotas, e `reviews` da leitura
atual fica como está (FR-001).

**Alternatives considered**: reaproveitar `get_current_form_instance(...,
run_number=n-1)` perde o campo removido e carrega valores à toa. Montar
`reviews` em `_load_submission_version_rows` adicionaria custo à listagem, que
não muda (FR-003). Por isso `get_returned_submission_version` chama a função
só no detalhe.

## R2. Execução anterior no formulário

**Decision**: o router chama a função com `run.run_number - 1` só quando
`activity_key == 'proposal_submission'`. Na primeira rodada a busca pela
execução 0 volta vazia, sem desvio no código. Com `?run_number=N`, a execução
anterior é `N-1`.

**Rationale**: a regra usa a execução já resolvida pela rota, e o acesso já foi
conferido por `get_current_form_instance`.

## R3. Onde pedir o e-mail

**Decision**: em `open_return_review`, depois do evento
`RETURN_REVIEW_OPENED`. A função lê `Settings()` e retorna sem pedir envio se
`email_channel_available` for falso. O assunto do envio é
`(RETURN_REVIEW_KEY, run.id)`.

**Rationale**: as três origens passam por essa função, então um gatilho basta.
O caminho da IA roda fora da requisição e já usa `Settings()`
(`pre_evaluation_service.py:101`). Receber `settings` por parâmetro mudaria
`execute_triage_decision`, `TriageContext`, o router e oito chamadas em testes
e factories, sem ganho.

**Teste**: `monkeypatch.setattr('pivma.core.process_engine.Settings', lambda:
settings)`, com uma instância fixa de `email_settings()`. Assim a chave de
criptografia é a mesma do worker e o `.env` local não interfere.

**Alternatives considered**: `AuditEvent` adicional para o pedido de envio:
desnecessário, porque os recebimentos de amostras não gravam e o worker registra
`NOTIFICATION_SENT` ou `NOTIFICATION_FAILED`.

## R4. Destinatários e conteúdo

**Decision**: `_active_proponent_emails` segue `_selection_group_emails`:
`Assignment` com `role_key == PROPONENT_ROLE_KEY`, `revoked_at` e `deleted_at`
nulos, e `User.deleted_at` nulo. Conta ativa, no projeto, é conta sem exclusão
lógica (`_is_active_user`).

O prazo vem de `task.due_date` em ISO e sai por `_format_deadline`, o mesmo
formato em UTC do convite. As duas devoluções da IA usam a mesma origem, então
o e-mail não revela se houve falha ou reprovação (FR-011).

## R5. Reprocessamento da IA

**Achado**, por leitura de código, a confirmar com teste vermelho:

- `retry_run` lê a execução sem trava e só recusa `completed`, ao contrário do
  que `research.md` R8 da Spec 030 presumia.
- Dois reprocessamentos da mesma execução `failed` criam duas execuções novas.
- Reprocessar uma execução `in_progress` deixa as duas rodando, cada uma com o
  próprio efeito.
- `cancel_open_return_review` lê as execuções sem trava. Depois de uma
  contestação vencedora, ele sobrescreve `COMPLETED` com `CANCELLED`, e os dois
  efeitos acontecem.
- Reprocessar depois de `REVISE` ou da contestação, mesmo em sequência, roda a
  IA sobre uma submissão que já seguiu adiante.

**Decision**:

1. `cancel_open_return_review` trava as execuções `IN_PROGRESS` de origem
   `AI_PRE_EVALUATION` com `with_for_update` e `populate_existing`, e devolve
   `True` se cancelou alguma.
2. `retry_run` chama o cancelamento, depois trava a `EvaluationRun` filtrando
   `status == 'failed'`, e confere se ela é a mais recente do processo.
   Se faltar qualquer condição, faz `rollback` e lança `ConflictError`. A rota
   já traduz para `409`.

3. `retry_run` recebe o administrador e o repassa ao cancelamento, que grava
   `RETURN_REVIEW_CANCELLED` com `source` e `run_number`. A nova execução mantém
   `old.created_by`, porque `_execute` usa esse valor como autor dos eventos da
   IA. A rota hoje descarta o administrador e passa `run.created_by`, então o
   evento do envio cancelado sairia com o autor errado e, sem envio pendente,
   nada ficaria registrado.

Toda execução `failed` abriu um retorno da IA, então "retorno da IA aberto"
cobre o segundo reprocessamento, a contestação e `REVISE`. O filtro por origem
é necessário: depois de uma contestação, a triagem pode devolver a submissão e
abrir um retorno `TRIAGE`, enquanto a última execução segue `failed`. Sem o
filtro, o reprocessamento cancelaria uma decisão humana. O teste da execução
mais recente cobre o ID antigo, de uma rodada anterior.

**Ordem de travas**: decisão do proponente e reprocessamento travam primeiro a
execução do retorno. `_execute` trava só a `EvaluationRun` e só atua em
`in_progress`, estado em que não há retorno aberto. Assim não há espera
circular.

**Rationale**: a contestação só entra por `decide_return_review`, já travada na
execução do retorno, e o índice único de `DirectReviewRequest` segue como
garantia final. Basta alinhar o outro lado da disputa.

**Alternatives considered**: travar `ProcessInstance` nas três operações
contraria a decisão R8 da Spec 030. Travar `EvaluationRun` também em
`request_direct_review` inverteria a ordem de travas do reprocessamento e abriria
risco de deadlock.

**Efeito de contrato**: `retry` de execução `in_progress` passa de `202` para
`409`. A varredura de inicialização marca execuções presas como `failed`, e
elas podem ser reprocessadas depois.

## R6. Testes de concorrência

**Decision**: dois módulos em `tests/integration/database/`, com dados
commitados, `AsyncSession(engine)` por concorrente, `asyncio.gather` e purga no
`finally`, como `test_per_laboratory_concurrency.py`.

As disputas com `_execute` precisam de um critério bloqueante publicado. Sem
critérios, `consolidate([])` dá positivo, nenhum retorno abre e a contestação
não tem como vencer.

| Disputa | Resultado esperado |
|---|---|
| `REVISE` contra `WITHDRAW` | Um vencedor, um `ConflictError`, um `RETURN_REVIEW_DECIDED` |
| Dois `REVISE` | Uma nova execução da submissão |
| Dois `retry_run` da mesma falha | Uma nova `EvaluationRun`, um e-mail cancelado no máximo uma vez |
| `retry_run` contra `CONTEST_AI` | Ou nova `EvaluationRun`, ou `DirectReviewRequest`, nunca os dois |
| `_execute` contra `retry_run` | `ConflictError` no retry e um relatório |
| `_execute` negativo contra `CONTEST_AI` | Um relatório e no máximo um `DirectReviewRequest` |

## R7. Decisões de escopo

- Um e-mail pendente continua valendo se o proponente decidir o retorno antes
  do envio. A spec só pede cancelamento no reprocessamento, e o worker envia em
  segundos. A desistência segue a mesma regra.
- A exclusão do processo cancela o envio pendente de todas as execuções do
  retorno, em `delete_process`. Fazer isso em `_cancel_pending_children` deixaria
  de fora o retorno já decidido, contra o cenário 6 da US2, e essa função também
  atende à desistência, que não cancela o envio.
- `_sweep_stale_runs` fica fora, registrada em `docs/observacoes-e-pendencias.md`.
- A duplicação da busca de eventos em `list_returned_submission_versions` e
  `get_returned_submission_version` fica como está (constituição VI).
