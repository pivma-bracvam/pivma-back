# Quickstart — Validação da Avaliação Configurável por IA

Guia para validar a feature ponta a ponta contra a API real. Detalhes de entidades em [data-model.md](./data-model.md); formatos em [contracts/](./contracts/).

## Pré-requisitos

- Postgres local: `docker compose up db -d`
- Migrações: `uv run alembic upgrade head` (ou `poetry run alembic upgrade head`)
- Templates: `uv run python -m pivma.bootstrap_process_templates`
- `.env` (mínimo + IA):
  ```
  OPENAI_API_KEY=sk-...            # necessário só para o fluxo com modelo real
  AI_PROVIDER=openai               # use 'fake' para validar sem gastar tokens
  # AI_MODEL_EXTRACTION / AI_MODEL_FAST / AI_MODEL_REASONING têm defaults
  ```
- API: `uv run fastapi dev src/pivma/__init__.py` (sobe em `http://localhost:8000`)
- Conta admin: registrar via `POST /users` e promover com `uv run python -m pivma.bootstrap_rbac --user-id <UUID>`
- Seed da feature: `uv run python -m scripts.seeds.seed_ai_evaluations` (ou `seed_all`)

Autenticação nas chamadas: `POST /auth/login` com `{identifier, password}` grava o cookie `access_token`; envie `Origin: http://localhost:8000` nas mutações. Contas semeadas: `admin` / `Admin@123456`, `proponent_user` / `Proponent@123456`, `triage_evaluator` / `Triage@123456`.

---

## Cenário A — Configurar uma avaliação pela biblioteca (US1, US5, US6)

1. **Criar definição + draft v1**
   `POST /ai-evaluations` `{ "name": "Verificação de estrutura de POP", "mode": "simple", "objective": "Verificar se o POP permite reprodução do método por outro laboratório" }`
   → `201`, guarda `definition_id`.

2. **Pedir critérios ao assistente**
   `POST /ai-evaluations/suggest-criteria` `{ "objective": "...", "target_type": "field" }`
   → `200` com lista de sugestões.

3. **Salvar critérios na v1 (aceitar/editar)**
   `PATCH /ai-evaluations/{definition_id}/versions/1` com `criteria: [...]` — inclua ao menos um `severity: "critical"`.
   → `200`.

4. **Associar referência normativa**
   `POST /ai-evaluations/references` `{ "identifier": "OECD 442B", "label": "...", "version_label": "2024" }` → `201`
   `PATCH .../versions/1` com `references: ["<reference_id>"]` → `200`.

5. **Testar antes de publicar**
   `POST /ai-evaluations/{definition_id}/versions/1/test` `{ "sample_content": "<texto de um POP de exemplo>" }`
   → `200` com resultado por critério + `consolidated_result`. Ajuste critérios e repita se necessário.

6. **Publicar**
   `POST /ai-evaluations/{definition_id}/versions/1/publish` → `200`, `status: "published"`, `test_warning: false`.

7. **Imutabilidade / nova versão**
   `PATCH .../versions/1` → `409`. `POST /ai-evaluations/{definition_id}/versions` → `201` cria v2 `draft`.
   **Esperado**: execuções feitas com a v1 continuam apontando para a v1.

---

## Cenário B — Associar ao formulário (US1 via editor, US7 módulo 1)

8. `PUT /form-templates/pre_validated_method/evaluation-assignments`
   `{ "assignments": [ { "definition_id": "<id>", "target_type": "field", "field_keys": ["standard_operating_procedure"] } ] }`
   → `200`. `GET` do mesmo endpoint confirma `effective_version_number`.
9. Perfil proponente tentando o mesmo `PUT` → `403`.

---

## Cenário C — Submissão, pré-avaliação assíncrona e retorno ao proponente (US2, US3)

10. Como **proponente**: `POST /processes` (instancia `pre_validated_method`), preenche e
    `POST /processes/{id}/activities/proposal_submission/form` com os valores.
    **Esperado**: resposta em < 2 s com `pre_evaluation.status: "in_progress"`; a triagem **não** aparece ainda.

11. Consultar: `GET /processes/{id}/pre-evaluation` — repita até `status: "completed"`.
    - Com `AI_PROVIDER=fake` ou dados de POP incompletos: `consolidated_result: "negative"` (há não conformidade `critical`).
    - **Esperado (negativo)**: `process.status` volta a `SUBMISSION`, nova `ActivityRun` de submissão com uma `Task` PROPONENT; o relatório fica anexado.

12. **Corrigir e reenviar**: repetir passo 10 → nova pré-avaliação dispara.
    **ou**
13. **Ignorar a IA**: `POST /processes/{id}/submission/direct-review` `{ "justification": "..." }`
    → `200`, `process_status: "TRIAGE"`. `GET /pre-evaluation` mostra `direct_review_request` preenchido e o relatório original intacto.

14. Tentar `direct-review` de novo → `409` (sem duplicidade).

---

## Cenário D — Triagem assistida (US4)

15. Como **gestor/triador**: abrir a tarefa de triagem; `GET /processes/{id}/pre-evaluation`
    mostra critérios, evidências, severidade, referência, `version_number`, `run_id`, timestamps.
16. `POST /processes/{id}/pre-evaluation/{run_id}/feedback`
    `{ "items": [ { "item_id": "...", "verdict": "disagree", "reason": "..." }, { "item_id": "...", "verdict": "agree" } ] }`
    → `200 { "recorded": 2 }`. O resultado da IA **não muda**.
17. Usuário com conflito de interesse vigente tentando o feedback → `403`.
18. `POST /processes/{id}/triage/decision` (Spec 004, inalterado) — a decisão é do humano.
19. `GET /ai-evaluations/agreement-metrics` → taxas de concordância por `check_type`.

---

## Cenário E — Falha e reprocessamento

20. Forçar falha (ex.: `AI_PROVIDER=openai` sem `OPENAI_API_KEY`), submeter.
    **Esperado**: `evaluation_run.status: "failed"`, submissão volta ao proponente com flag de falha; triagem não travada permanentemente.
21. Como **admin**: `POST /admin/pre-evaluations/{run_id}/retry` → `202`, nova run.

---

## Demonstrações (`demos/`, última etapa — AGENTS.md)

Ciclo básico de 4 módulos, catalogado em `demos/index.html`; consomem só
`http://localhost:8000`; nenhum endpoint/dado criado para viabilizá-los.

- `demos/forms/` — editor de formulário. Cada campo com `ai_evaluation_enabled`
  tem o botão **Configurar Avaliação por IA →**, que abre
  `demos/forms/ai-config.html?template=<k>&field=<f>`: criar/reaproveitar →
  `suggest-criteria` → editar → testar → publicar → associar ao campo (Cenários A/B).
- `demos/submission/` — proponente submete; a pré-avaliação assíncrona resolve e
  roteia; em caso negativo, corrigir/reenviar ou solicitar intervenção direta (Cenário C).
- `demos/triage/` — o triador (gestor do processo) inspeciona os pontos de
  atenção e registra concordância por critério; a decisão de triagem segue humana.
- `demos/ai-pipeline/` — observabilidade das execuções de pipeline.

Restrição conhecida: `GET .../pre-evaluation` e `POST .../feedback` exigem
proponente / gestor do processo / perfil Administrador. O seed designa
`triage_evaluator` como `group_manager` do processo `[DEMO IA] Extensão de
Escopo` para a demo de Triagem funcionar de ponta a ponta.

---

## Testes automatizados

```
uv run pytest tests/unit/ai tests/unit/core          # consolidação, seleção de camada, versionamento
uv run pytest tests/api/routers -k "ai_evaluations or pre_evaluation"
uv run pytest tests/integration/database -k evaluation
uv run pytest tests/integration/migrations
RUN_OPENAI_TESTS=1 uv run pytest tests/integration/ai/test_openai_live.py   # opcional, usa tokens
```
**Esperado**: suíte `unit`/`api`/`integration` verde **sem** `OPENAI_API_KEY` (provedor `fake` via `conftest` / `dependency_overrides`).
Portão antes de entregar: `uv run ruff check` · `uv run ruff format` · `uv run pytest`.
