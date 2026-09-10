# Quickstart — Validação da Spec 014

## Pré-requisitos

- Postgres de dev de pé; `uv run alembic upgrade head` (aplica as 2 migrações
  novas).
- `uv run python -m scripts.seeds.seed_all` (o seed dá o perfil `bracvam` a
  `triage_evaluator` e não usa mais o contorno `group_manager`).
- API em `http://localhost:8000` (`uv run fastapi dev src/pivma/__init__.py`).
- Autenticação: `POST /auth/login` `{identifier, password}` grava cookie;
  `Origin: http://localhost:8000` nas mutações.

Contas: `admin` / `Admin@123456` · `proponent_user` / `Proponent@123456` ·
`triage_evaluator` / `Triage@123456` (perfil **BraCVAM**) ·
`mariana_gestora` / `Mariana@123456` (perfil **Grupo Gestor**).

## Cenário A — Triagem só pelo BraCVAM (US1)

1. Login `triage_evaluator`. `GET /processes` → o processo `[DEMO IA]` aparece
   (em `TRIAGE`).
2. `GET /processes/{demo_ia}/pre-evaluation` → **200** com pontos de atenção.
3. `POST /processes/{demo_ia}/pre-evaluation/{run}/feedback` `{items:[...]}` →
   **200** `{recorded: N}`.
4. `POST /processes/{demo_ia}/triage/reviews` `{reviews:[...]}` → **200**.
5. Login `mariana_gestora` (Grupo Gestor). Repetir passos 2–4 → **403** em todos.
6. Login `proponent_user`. `GET` da pré-avaliação do **próprio** processo → 200;
   de outro → 403; `feedback`/`reviews`/`decision` → 403.
7. Ver `contracts/triage-authorization.md` para a matriz completa.

Esperado: só `bracvam` e `administrator` conduzem a triagem; conflito de
interesse continua bloqueando feedback/decisão mesmo com a permissão.

## Cenário B — Uma única esteira (US2)

1. Login `admin`. Criar um template de formulário **sem** avaliações por IA
   associadas (ou usar `me_too_validation`).
2. Login `proponent_user`. Criar processo desse template, preencher, submeter.
3. Resposta da submissão: **sem** campo `ai_evaluation`; `pre_evaluation` é `null`;
   `status` do processo → `TRIAGE` direto.
4. `GET /processes/{id}/activities/proposal_submission/form` → sem `ai_evaluation`.
5. `POST /forms/instances/{qualquer}/evaluate-ai` → **404**.
6. `demos/ai-pipeline/` não tem mais botão de disparo; observa o stream.

## Cenário C — Snapshot do conteúdo avaliado (US3)

1. Login `admin`. Publicar avaliação e associá-la a um campo de um template.
2. Login `proponent_user`. Submeter → a pré-avaliação roda (provider real ou
   `fake` conforme `.env`).
3. Login `triage_evaluator`. `GET .../pre-evaluation` → anotar
   `evaluated_content`.
4. Login `admin`. `PUT` do template removendo o campo avaliado (ou `PUT` das
   associações trocando a definição).
5. Login `triage_evaluator`. `GET .../pre-evaluation` da **mesma** execução →
   `evaluated_content` **idêntico** ao passo 3.

## Cenário D — Compatibilidade de execuções antigas (US3 / SC-007)

Em teste de integração: criar uma `EvaluationRun` concluída com
`evaluated_content_snapshot = NULL`; `GET .../pre-evaluation` retorna
`evaluated_content` pela reconstrução, sem erro.

## Cenário E — Observabilidade (US4)

1. Disparar uma pré-avaliação (Cenário C, passo 2).
2. `GET` da observabilidade de IA (rota de `admin_logs`) → as etapas
   `criterion_evaluation` da execução agrupadas por um único `correlation_id`,
   com `pipeline_name`, provedor, modelo por camada e custo real.
3. Nenhuma entrada no formato legado (`verdict_synthesis` / `verdict`).

## Cenário F — Migrações reversíveis (SC-008)

```
uv run alembic upgrade head
uv run alembic downgrade -1        # remove snapshot; evaluation_runs intactas
uv run alembic downgrade -1        # remove perfil bracvam + triage.review, sem órfãos
uv run alembic upgrade head
```

Testes dedicados em `tests/integration/migrations/`.

## Portões

`uv run ruff format --check` · `uv run ruff check` · `uv run pytest` — verdes.
Suíte esperada ≥ atual (novos testes de US1/US3/US4; menos os 2 arquivos
legados removidos).
