# Phase 0 Research: Helper Único de Conclusão de Atividade

## 1. Onde fica o helper único e o que ele encapsula

**Decision**: Um único helper em `core/process_engine.py`,
`_complete_activity_run(session, run, act, user_id)`, encapsulando o bloco
hoje duplicado em `submit_proposal_form` (linhas ~1918-1931) e
`execute_triage_decision` (linhas ~2292-2302): marcar `run.status =
'COMPLETED'` + `completed_at`, `act.status = 'COMPLETED'`, e todas as `Task`
daquela run como `'COMPLETED'` + `completed_at`. O avanço de dependentes
continua uma função separada (`_advance_dependent_activities`, já existente),
chamada depois do helper pelos pontos que precisam avançar algo — nem todo
ponto que conclui uma atividade tem dependentes a destravar no mesmo
instante (ex.: `NEEDS_REVISION` conclui a run de triagem mas não destrava
nada, reabre a submissão).

**Rationale**: Mantém a mesma separação de responsabilidades que já existe
hoje (concluir vs. avançar) em vez de fundir as duas em uma função só —
`_handle_rejected_decision` já mostra um caso real onde a triagem conclui sem
avançar nada. Fundir forçaria um parâmetro booleano ou callback artificial só
para esse caso raro.

**Alternatives considered**: (a) Uma função só "conclua e avance", com
avanço opcional via flag — rejeitada por criar uma assinatura confusa para o
caso comum (quase sempre quer avançar) vs. o caso raro (rejeição). (b) Manter
duas cópias do bloco de conclusão mas extrair só o loop de `Task` — rejeitada
por não resolver a duplicação real apontada na issue (o bloco inteiro, não só
o loop).

---

## 2. Como absorver `_unblock_triage_activity` no motor genérico

**Decision**: Remover `_unblock_triage_activity` por completo. Os três
pontos que a chamam (`submit_proposal_form` sem avaliação por IA associada,
`pre_evaluation_service._execute` com resultado positivo,
`pre_evaluation_service.request_direct_review`) passam a chamar
`_advance_dependent_activities(session, process, submission_act, user_id)`
depois de concluir a run/atividade da submissão via `_complete_activity_run`
— exatamente o padrão que `_handle_approved_decision` já usa para destravar o
que vem depois da triagem. A dependência declarativa da triagem sobre a
submissão (`required_activity_key: proposal_submission`, `required_status:
COMPLETED`) já existe em todos os 5 templates YAML, então `_dependency_satisfied`
já resolve isso sem mudança de dado de template.

**Rationale**: Elimina o segundo tipo de duplicação identificado (dois
mecanismos de "avançar dependente") e corrige o bug de reaproveitamento de
run/task, porque `_activate_activity` (usada por `_advance_dependent_activities`)
sempre cria uma `ActivityRun` e uma `Task` novas — nunca reaproveita.

**Alternatives considered**: Manter `_unblock_triage_activity` e só corrigir
seu bug internamente (fazer criar run/task novas mesmo quando já existe uma)
— rejeitada porque perpetuaria o segundo tipo de duplicação que a issue pede
para eliminar (dois mecanismos de avanço, resolvendo por chave fixa em vez do
motor genérico), sem ganho adicional de segurança.

---

## 3. Risco de escopo: texto do título da tarefa de triagem

**Achado durante a pesquisa**: `_unblock_triage_activity` cria a `Task` com
`title='Realizar Triagem da Proposta'` (texto fixo, escrito à mão). Já
`_activate_activity` (motor genérico) cria a `Task` com `title=act.name`, que
para a atividade `triage_evaluation` é `"Triagem e Decisão BraCVAM"` (nome
declarado no template). Se a substituição for ingênua, o texto da tarefa de
triagem muda **em toda primeira rodada de todo processo** — não só nas
rodadas de diligência, que é o que foi discutido e aceito com o usuário.

**Decision**: `_activate_activity` ganha um parâmetro opcional
`task_title: str | None = None` (default `None` → usa `act.name`, comportamento
atual preservado para todo o resto do motor). A chamada feita para destravar
a triagem passa explicitamente `task_title='Realizar Triagem da Proposta'`,
preservando o texto exibido hoje em toda rodada — inclusive a primeira.
Mantém o blast radius desta mudança restrito exatamente ao que foi
especificado (spec, FR-003 a FR-006): comportamento de rodadas múltiplas, não
o texto da primeira rodada.

**Rationale**: Nenhum teste hoje trava esse literal (`grep` não encontrou
asserts sobre o texto), mas é texto visível a quem faz a triagem em produção
— mudar sem necessidade nem discussão prévia seria escopo não combinado.
Preservar por parâmetro é uma mudança de uma linha e não reintroduz
duplicação (a lógica de criação continua uma só, só o texto varia).

**Alternatives considered**: Aceitar o novo texto (`act.name`) para todas as
rodadas — rejeitada por ampliar o raio de impacto observável além do que foi
acordado nesta conversa; fica registrado aqui para o usuário confirmar se
prefere essa opção mais simples (uma linha a menos) antes da implementação.

---

## 4. Evento de auditoria no desbloqueio da triagem

**Decision**: Ao passar a usar `_advance_dependent_activities` para destravar
a triagem, o evento `ACTIVITY_UNBLOCKED` (já emitido por essa função para
qualquer outra atividade dependente) passa a ser emitido também para a
triagem — hoje `_unblock_triage_activity` não emite nenhum evento. Nenhum
código novo é necessário para isso: é um efeito colateral automático de usar
o mecanismo genérico (spec, FR-006).

**Rationale**: Consistência de auditoria entre atividades — hoje só a
triagem é uma exceção silenciosa. Risco de UI desconhecida é baixo (evento
aditivo a uma lista já aberta), mas fica registrado no CHANGELOG orientado a
usuário (spec, User Story 3) para quem acompanha a linha do tempo de perto.

---

## 6. Achados durante a implementação (não previstos no plano)

**`_activate_activity` tinha `run_number=1` hardcoded.** Inofensivo enquanto
só era chamada uma vez por atividade (todo dependente hoje só é desbloqueado
uma vez); quebraria o FR-004 (incremento de rodada da triagem) se não
corrigido. Corrigido junto com T002: `run_number` passa a ser
`max(run_numbers existentes da atividade, default=0) + 1`.

**`triage_act.status` mudava de `'READY'` para `'IN_PROGRESS'`.** O caminho
bespoke (`_unblock_triage_activity`) usava `'READY'`; o motor genérico
(`_activate_activity`) usa `'IN_PROGRESS'` — o mesmo valor já usado por toda
outra atividade do sistema quando ativa (`proposal_submission`,
`planning_preview`, conferido em `tests/unit/core/test_process_engine.py` e
`tests/api/routers/test_activity_type_extension.py`). Nenhum consumidor de
API distingue `'READY'` de `'IN_PROGRESS'` — só `'BLOCKED'` e `'COMPLETED'`
são tratados de forma especial em `classify_kanban_column` e nos endpoints de
tasks (`TaskDetail.is_blocked`, `KanbanCardItem.column`). **Decisão**: alinhar
a triagem à convenção já usada em todo o resto do motor, em vez de preservar
`'READY'` como um terceiro caso especial — manteria viva exatamente a
exceção que a issue pede para eliminar. Sem efeito de API observável; 4
testes que travavam o literal `'READY'` precisaram de ajuste (tasks.md,
T014b).

## 5. Testes a atualizar

**Decision**: `tests/api/routers/test_triage_decision.py::test_triage_decision_needs_revision_and_resubmission`
precisa de um novo assert explícito confirmando `run_number == 2` (ou maior)
para a `ActivityRun` da **triagem** depois do reenvio — hoje o teste só
confere o `run_number` da submissão. Um teste novo (unitário, FR-009) cobre
`_complete_activity_run` isoladamente. A fase de `/speckit-tasks` detalha a
lista completa após varredura por `_unblock_triage_activity` e pelo bloco de
conclusão duplicado em todo `tests/`.

**Rationale**: Mapeamento de testes afetados é responsabilidade da fase de
tasks (mais granular), não do plano; aqui só se registra o caso já conhecido
por análise anterior desta conversa.
