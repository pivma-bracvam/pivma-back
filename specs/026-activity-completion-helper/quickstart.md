# Quickstart: Validar o Helper Único de Conclusão de Atividade

**Feature**: 026-activity-completion-helper

Esta feature não introduz demo nova (AGENTS.md, Regra 1 — não é um módulo
novo). A validação reaproveita a demo de triagem já existente
(`demos/triage/`), que já expõe a ação "Solicitar Diligência"
(`NEEDS_REVISION`) contra a API real.

## Pré-requisitos

- API rodando localmente (`poe serve`); nenhuma migração nova a aplicar.
- Seeds já executados: `python -m scripts.seeds.seed_triage` (cria/reaproveita
  o processo `[DEMO 1] Método Pré-Validado` até `TRIAGE`) — não precisa de
  ajuste para esta feature, o ciclo de diligência é exercitado manualmente
  pela demo, não pelo seed.
- Navegador para abrir `demos/triage/index.html`.

## Passos

1. Abrir `demos/triage/index.html` e localizar o processo de demo em
   `TRIAGE`. Anotar seu `process_id`.
2. Clicar em "Solicitar Diligência" (`NEEDS_REVISION`) com uma justificativa
   qualquer. Confirmar que o processo volta para `SUBMISSION` (comportamento
   já existente, não deve mudar).
3. Chamar `GET /processes/{process_id}` como proponente e reenviar o
   formulário de submissão (via demo de submissão ou `POST
   /processes/{id}/activities/proposal_submission/form`) — leva o processo de
   volta a `TRIAGE`.
4. **Verificação principal desta feature** — chamar `GET
   /tasks?process_id={process_id}&status=READY` autenticado como usuário
   BraCVAM: deve retornar uma tarefa de triagem para **esta** rodada. Antes
   desta feature, essa chamada não retornava nada depois do passo 3 (bug
   corrigido — spec, User Story 1).
5. Chamar `GET /activities/kanban?process_id={process_id}` e confirmar que o
   card da triagem mostra `run_started_at` correspondente ao momento do
   reenvio (passo 3), não ao início do processo — e que a classificação de
   coluna (`EM_ANDAMENTO`/`EM_ATRASO`) usa esse novo início para os 72h de
   SLA (spec, SC-002).
6. Consultar a `ActivityRun` da triagem no banco (ou endpoint de detalhe, se
   existir) e confirmar `run_number = 2` (incrementado a partir da rodada
   anterior, que permanece `COMPLETED` — spec, FR-004).
7. Chamar `GET /processes/{process_id}/timeline` e confirmar um evento
   `ACTIVITY_UNBLOCKED` para `triage_evaluation`, ausente antes desta feature
   (spec, User Story 3 / FR-006).
8. Aprovar a triagem (`POST /processes/{id}/triage/decision`, outcome
   `APPROVED`) normalmente — confirmar que o restante do fluxo (avanço para
   `PLANNING`, conclusão da fase) continua idêntico ao comportamento atual
   (spec, FR-002 — nenhuma mudança nos três pontos que já usavam o motor
   genérico).

## Resultado esperado

Passos 1-3 e 8 reproduzem exatamente o comportamento de hoje (sem regressão).
Passos 4-7 são os únicos com resultado novo, e cada um corresponde a um FR/SC
específico da spec — servem como evidência de que a correção do bug (não só
a unificação de código) foi entregue de ponta a ponta contra a API real
(AGENTS.md, Regra 3).
