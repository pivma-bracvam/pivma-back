# Contract — Configuração de Avaliações (biblioteca, versões, critérios, referências, assistente, teste)

Router: `src/pivma/routers/ai_evaluations.py` · Prefixo `/ai-evaluations` · Tag `AI Evaluations`.

Autorização: leitura → `ai_evaluations.read`; mutação → `ai_evaluations.manage` + `TrustedOrigin`. `401` sem sessão, `403` sem permissão. Erros de domínio seguem o padrão do projeto (`NotFoundError`→404, `ConflictError`→409, `ValidationError`→422).

Formatos abaixo são indicativos (Pydantic v2, `snake_case`).

---

## Biblioteca de definições

### `GET /ai-evaluations`
Lista definições da biblioteca. Query: `search?`, `offset?`, `limit?` (1–100, default 50).
`200` →
```json
{ "offset": 0, "limit": 50, "items": [
  { "id": "...", "name": "Verificação de estrutura de POP", "slug": "verificacao-estrutura-pop",
    "mode": "simple", "latest_version": { "version_number": 2, "status": "published" },
    "published_versions": 1, "assignments_count": 3 }
]}
```

### `POST /ai-evaluations`
Cria a definição + a versão 1 em `draft`.
Body: `{ "name": str, "description": str?, "mode": "simple"|"advanced", "objective": str }`
`201` → `{ "id": "...", "slug": "...", "draft_version": { "version_number": 1, "status": "draft" } }`
`409` se `slug` já ativo.

### `GET /ai-evaluations/{definition_id}`
`200` → definição + lista de versões (número, status, published_at, criteria_count).
`404` se inexistente / excluída.

### `DELETE /ai-evaluations/{definition_id}`
Exclusão lógica. `204`. Não afeta execuções passadas nem templates (assignments ficam `enabled=false` implicitamente via join com definição excluída). `409` se houver assignment ativo e `force` ausente (query `?force=true` para prosseguir).

---

## Versões

### `GET /ai-evaluations/{definition_id}/versions/{n}`
`200` →
```json
{ "version_number": 1, "status": "draft", "objective": "...", "test_run_count": 0,
  "references": [ { "reference_id": "...", "identifier": "OECD 442B", "version_label": "2024" } ],
  "criteria": [
    { "id": "...", "order_index": 0, "statement": "Deve possuir critérios de aceitação",
      "check_type": "conformity", "polarity": "positive",
      "required_evidence": "Seção que descreva controles e critérios de aceitação",
      "severity": "critical", "on_missing_info": "non_compliant",
      "recommendation_hint": "Especificar critérios de aceitação dos resultados" }
  ] }
```

### `PATCH /ai-evaluations/{definition_id}/versions/{n}`
Edita a versão **somente se `draft`**. Body parcial: `objective?`, `references?` (lista de `reference_id`), `criteria?` (lista completa — substitui; itens sem `id` são criados, `id` conhecidos atualizados, ausentes são logicamente removidos).
`200` → versão atualizada. `409` se a versão está `published`.

### `POST /ai-evaluations/{definition_id}/versions`
Clona a última versão para um novo `draft` (`version_number = max + 1`).
`201` → `{ "version_number": 3, "status": "draft" }`. `409` se já existe um `draft`.

### `POST /ai-evaluations/{definition_id}/versions/{n}/publish`
Valida ≥1 critério; congela objetivo/critérios/snapshot de referências; `status → published`.
`200` → `{ "version_number": 1, "status": "published", "published_at": "...", "test_warning": true|false }`
(`test_warning=true` quando `test_run_count == 0` — FR-020; não bloqueia).
`422` se nenhum critério. `409` se já `published`.

---

## Assistente de sugestão de critérios (sem estado)

### `POST /ai-evaluations/suggest-criteria`
Body: `{ "objective": str, "target_type": "field"|"field_set"|"document"|"form"|"process" }`
Executa a camada `reasoning` do provedor. Não persiste.
`200` →
```json
{ "suggestions": [
  { "statement": "Deve possuir identificação do documento", "check_type": "presence",
    "polarity": "positive", "suggested_severity": "low" },
  { "statement": "O procedimento deve permitir reprodução do método", "check_type": "quality",
    "polarity": "positive", "suggested_severity": "critical" }
] }
```
`503` (`{"detail": "Serviço de IA indisponível"}`) se `AI_PROVIDER=openai` sem chave.

---

## Modo de teste

### `POST /ai-evaluations/{definition_id}/versions/{n}/test`
Só para versão `draft`. Body: `{ "sample_content": str }`.
Roda o pipeline em memória; persiste `evaluation_test_runs` (incrementa `test_run_count`).
`200` →
```json
{ "results": [
  { "criterion_id": "...", "statement": "...", "check_type": "conformity",
    "conclusion": "non_compliant", "is_alert": false, "severity": "critical",
    "evidence_excerpt": "...", "evidence_location": "Seção 5",
    "justification": "Não identifica critérios de aceitação",
    "recommendation": "Especificar os critérios utilizados" }
], "consolidated_result": "negative", "real_cost": 0.0031 }
```
`409` se a versão está `published`.

---

## Catálogo de referências normativas

### `GET /ai-evaluations/references`
`200` → `{ "items": [ { "id": "...", "identifier": "OECD 442B", "label": "...", "version_label": "2024", "reference_date": "2024-06-01" } ] }`

### `POST /ai-evaluations/references`
Body: `{ "identifier": str, "label": str, "version_label": str, "reference_date": date? }`
`201` → referência criada. `409` se `(identifier, version_label)` já ativo.

### `GET /ai-evaluations/references/{id}/impact`
`200` → `{ "evaluation_versions": [ {definition_id, version_number} ], "runs_count": 12 }` (FR-015).

---

## Métricas de concordância

### `GET /ai-evaluations/agreement-metrics`
Query: `check_type?`, `from?`, `to?`.
`200` →
```json
{ "overall_agreement_rate": 0.82, "by_check_type": { "presence": 0.95, "quality": 0.68 },
  "most_contested_criteria": [ { "criterion_id": "...", "statement": "...", "disagree_rate": 0.4 } ],
  "runs_with_most_disagreements": [ { "run_id": "...", "disagreements": 3 } ] }
```
