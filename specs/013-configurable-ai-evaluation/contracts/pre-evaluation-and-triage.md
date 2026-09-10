# Contract — Pré-avaliação, Retorno ao Proponente e Triagem Assistida

Routers:
- `src/pivma/routers/pre_evaluation.py` (novo) — consulta, intervenção direta, feedback.
- `src/pivma/routers/forms.py` (editado) — o `POST` de submissão passa a agendar a pré-avaliação assíncrona.
- `src/pivma/routers/pre_evaluation.py` — `/admin/pre-evaluations/{run_id}/retry`.

---

## 1. Submissão dispara a pré-avaliação (editado)

### `POST /processes/{id}/activities/{activity_key}/form` — submeter formulário
Comportamento novo quando o template tem `evaluation_assignments` ativos:
1. valida e persiste os valores; marca `FormInstance.is_submitted=true`.
2. cria `evaluation_runs` com `status=in_progress`, `correlation_id` novo.
3. agenda `BackgroundTasks(run_pre_evaluation, run_id)`.
4. **não** desbloqueia a triagem; `process.status` permanece `SUBMISSION`; a atividade de triagem permanece `BLOCKED` com `blocked_reason='Aguardando pré-avaliação automática'`.
5. responde imediatamente:
```json
{ "activity_key": "proposal_submission", "run_number": 1, "status": "COMPLETED",
  "pre_evaluation": { "run_id": "...", "status": "in_progress" } }
```
Sem assignments: comportamento atual preservado (avança direto para `TRIAGE`, `pre_evaluation: null`).

`run_pre_evaluation(run_id)` (background, sessão própria):
- carrega assignments → resolve versão efetiva (pinned ou última publicada) → monta alvos.
- para cada critério: seleciona a camada do provedor por `check_type`, executa, grava `evaluation_run_items` (com snapshot). Alvo documento/OCR/imagem → `conclusion=indeterminate` sem chamar modelo.
- consolida (`src/pivma/ai/consolidation.py`) → `consolidated_result`.
- grava `real_cost`, `models_used`, `provider_name`, `finished_at`, `status=completed`.
- cria `Artifact key='ai_pre_evaluation_report'`.
- **roteia**:
  - `positive` → desbloqueia triagem, `process.status='TRIAGE'`, `AuditEvent AI_PRE_EVALUATION_COMPLETED`.
  - `negative` → `_open_new_submission_run(...)` (nova run de submissão + cópia de valores + Task PROPONENT), `process.status='SUBMISSION'`.
- em exceção do provedor: `status=failed`, `error_summary` genérico, `AuditEvent AI_PRE_EVALUATION_FAILED`, retorna ao proponente com flag de falha (mesmo tratamento do `negative` quanto a abrir nova run, porém marcada como falha para a UI).

---

## 2. Consulta da pré-avaliação

### `GET /processes/{id}/pre-evaluation`
Autorização: participante `proponent` do processo **ou** `ai_evaluations.read` / gestor. Escopo de leitura conforme papel (proponente vê o próprio; gestor vê tudo).
Query: `run_id?` (default = última execução).
`200` →
```json
{
  "run_id": "...", "correlation_id": "...", "status": "completed",
  "consolidated_result": "negative",
  "evaluation": { "definition_name": "Verificação de estrutura de POP", "version_number": 2 },
  "provider": "openai", "models_used": {"extraction":"gpt-5.4-nano","fast":"gpt-5.4-nano","reasoning":"gpt-5.4-mini"},
  "started_at": "...", "finished_at": "...",
  "summary": { "total": 10, "compliant": 6, "partial": 1, "non_compliant": 2, "indeterminate": 1 },
  "attention_points": [
    { "item_id": "...", "criterion_statement": "Deve possuir critérios de aceitação",
      "check_type": "conformity", "severity": "critical", "conclusion": "non_compliant",
      "is_alert": false, "evidence_excerpt": "...", "evidence_location": "Seção 5",
      "justification": "...", "recommendation": "...",
      "reference": { "identifier": "OECD 442B", "version_label": "2024" },
      "evidence_completeness": "partial", "inference_confidence": 0.71 }
  ],
  "direct_review_request": null
}
```
`status=in_progress` → devolve `summary`/`attention_points` vazios e `202`-like payload (HTTP `200` com `status`). `status=failed` → inclui `error_summary`.
Nota: `inference_confidence` presente mas a UI **não** o usa como indicador primário (FR-026).

---

## 3. Proponente ignora a IA e pede intervenção direta

### `POST /processes/{id}/submission/direct-review`
Autorização: participante `proponent` + `TrustedOrigin`.
Pré-condições: a última `evaluation_run` do processo está `completed` com `consolidated_result=negative` **ou** `failed`; não existe `direct_review_requests` para ela.
Body: `{ "justification": str? }`
Efeito: cria `direct_review_requests`; encerra a run de submissão aberta pelo roteamento negativo; desbloqueia a triagem; `process.status='TRIAGE'`; `AuditEvent DIRECT_REVIEW_REQUESTED`; o `Artifact` da pré-avaliação segue anexado e imutável.
`200` → `{ "process_status": "TRIAGE", "direct_review_request_id": "..." }`
`409` se já solicitado ou se o estado não permite. `422` se a última pré-avaliação foi `positive` (não aplicável).

---

## 4. Feedback do triador por critério

### `POST /processes/{id}/pre-evaluation/{run_id}/feedback`
Autorização: gestor/triador do processo + `TrustedOrigin`. Bloqueado por conflito de interesse vigente (`_guard_against_current_conflict`) → `403`.
Body:
```json
{ "items": [
  { "item_id": "...", "verdict": "disagree", "reason": "O documento traz os critérios na seção 7" },
  { "item_id": "...", "verdict": "agree" }
] }
```
Efeito: upsert em `reviewer_feedback` por `(run_item_id, reviewer_id)`; não altera `evaluation_run_items`. `AuditEvent AI_CRITERION_FEEDBACK_RECORDED`.
`200` → `{ "recorded": 2 }`. `404` se `item_id` não pertence à run. `422` verdict inválido.

A decisão de triagem em si continua via `POST /processes/{id}/triage/decision` (Spec 004) — inalterado, permanece 100% humano.

---

## 5. Reprocessamento administrativo

### `POST /admin/pre-evaluations/{run_id}/retry`
Autorização: `AdminUser`.
Pré-condição: run em `failed` **ou** `in_progress` há > 15 min (presa).
Efeito: cria uma **nova** `evaluation_runs` (a antiga permanece imutável para auditoria), reprocessa em background, reaplica o roteamento.
`202` → `{ "new_run_id": "...", "status": "in_progress" }`. `409` se a run atual está `completed`.

### Varredura no startup (`lifespan`)
Marca como `failed` toda `evaluation_runs` `in_progress` com `started_at` > 15 min e devolve a submissão ao proponente com flag de falha. Sem endpoint — roda uma vez ao subir a aplicação.
