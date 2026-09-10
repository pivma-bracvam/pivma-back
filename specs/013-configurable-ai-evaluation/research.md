# Phase 0 — Research & Decisions

Feature: Avaliação Configurável por IA na Submissão e Triagem · Branch `013-configurable-ai-evaluation`

Todas as `NEEDS CLARIFICATION` foram resolvidas no `/speckit-clarify` (Sessions 2026-09-09 e 2026-09-10). Este documento fixa as decisões técnicas de implementação.

---

## D1. Mecanismo de execução assíncrona

- **Decisão**: `fastapi.BackgroundTasks` agendado no handler de submissão, **após** o `commit` e a resposta. A função de background abre a **própria** `AsyncSession` (a sessão da request já terá fechado). Uma varredura no startup (`lifespan`) marca como `failed` toda `evaluation_run` em `in_progress` há mais de 15 min.
- **Rationale**: satisfaz FR-021a/SC-014 (resposta imediata) sem broker nem worker; chamadas LLM são `await` (httpx async), não bloqueiam o event loop; escala suficiente para o volume do projeto. A varredura cobre reinício de processo no meio de uma execução.
- **Alternativas consideradas**:
  - Celery / RQ / arq — rejeitado: exige Redis/broker + processo worker; desproporcional (Constituição: "código não complexo demais").
  - `asyncio.create_task` solto — rejeitado: sem o ciclo de vida gerenciado do `BackgroundTasks`, mais fácil vazar tarefa.
  - Síncrono com timeout (opção C do clarify) — descartado pelo usuário em favor de assíncrono puro (opção B).
- **Implicação de dados**: `evaluation_runs.status ∈ {in_progress, completed, failed}`; a submissão fica marcada como enviada mas a triagem só é liberada ao fim do background.

## D2. Integração LangChain / OpenAI

- **Decisão**: `langchain-openai.ChatOpenAI` por camada, com `temperature=0`. Saída estruturada via `model.with_structured_output(PydanticSchema)` — o LLM devolve diretamente um objeto Pydantic validado (`CriterionVerdict`, `SuggestedCriteria`). Uso de tokens/custo capturado via `response.usage_metadata` (ou `langchain_core` callback) e persistido em `evaluation_runs.real_cost` + `models_used`.
- **Rationale**: `with_structured_output` elimina parsing frágil de JSON e alinha com "usuário não escreve prompt / não define schema". `temperature=0` maximiza reprodutibilidade, requisito para auditoria regulatória.
- **Alternativas**: SDK `openai` cru (rejeitado, ver Complexity Tracking); `instructor` (rejeitado: mais uma dependência para o que o LangChain já cobre).
- **Prompt building**: interno ao pipeline, montado a partir de objetivo + enunciado do critério + evidência exigida + polaridade + conteúdo submetido + metadados de referência. Nunca exposto ao usuário (FR-001, item 29 da conversa).

## D3. Provedor de modelos e camadas

- **Decisão**: `src/pivma/ai/provider.py`:
  - `class ModelProvider(ABC)` com `extraction() -> BaseChatModel`, `fast() -> BaseChatModel`, `reasoning() -> BaseChatModel` e `evaluate_criterion(...) -> CriterionVerdict`, `suggest_criteria(...) -> list[SuggestedCriterion]`.
  - `OpenAIModelProvider(settings)` — instancia `ChatOpenAI` por camada a partir de `AI_MODEL_EXTRACTION` / `AI_MODEL_FAST` / `AI_MODEL_REASONING` e `OPENAI_API_KEY`.
  - `FakeModelProvider` — determinístico (ver D8).
  - `get_model_provider(settings: SettingsDependency) -> ModelProvider` escolhe por `settings.AI_PROVIDER` (`openai` | `fake`). Se `openai` sem `OPENAI_API_KEY`, levanta erro claro **no momento da chamada** (não no import), tratado como execução `failed`.
  - `dependencies.py`: `ModelProviderDep = Annotated[ModelProvider, Depends(get_model_provider)]`.
- **Seleção de camada por trabalho**:
  | Trabalho | Camada |
  |---|---|
  | Preparação/extração de evidência do conteúdo | `extraction` |
  | Critério `presence`, `conformity` (classificação) | `fast` |
  | Critério `quality`, `comparison`, `cross_field_consistency` | `reasoning` |
  | Assistente de sugestão de critérios | `reasoning` |
- **Nomenclatura**: `extraction` / `fast` / `reasoning` são nomes internos (o usuário autorizou adaptar). Documentados no código: `fast` = classificação barata, `reasoning` = avaliação de julgamento.
- **Defaults de modelo** (ajustáveis por env depois): `AI_MODEL_EXTRACTION=gpt-5.4-nano`, `AI_MODEL_FAST=gpt-5.4-nano`, `AI_MODEL_REASONING=gpt-5.4-mini`.

## D4. Settings — compatibilidade retroativa

- **Decisão**: adicionar em `Settings` com defaults seguros para não quebrar `.env`/testes existentes:
  - `OPENAI_API_KEY: str | None = None`
  - `AI_PROVIDER: str = 'openai'`
  - `AI_MODEL_EXTRACTION: str = 'gpt-5.4-nano'`, `AI_MODEL_FAST: str = 'gpt-5.4-nano'`, `AI_MODEL_REASONING: str = 'gpt-5.4-mini'`
- **Testes**: `tests/conftest.py` define `AI_PROVIDER=fake` via `os.environ.setdefault`; adicionalmente cada teste pode `app.dependency_overrides[get_model_provider]` para um fake customizado (verdicts encenados).
- **Rationale**: campos atuais são `Field(init=False)` obrigatórios; introduzir um obrigatório novo quebraria todos os ambientes. Defaults + provider `fake` em CI = zero fricção.

## D5. Regra de consolidação (fixa, embutida)

- **Decisão** (`src/pivma/ai/consolidation.py`):
  - Ordem de severidade: `info < low < medium < high < critical`.
  - Conclusão normalizada por item: `compliant | non_compliant | partial | indeterminate`.
  - **`consolidated_result = negative` sse existe ≥1 item com `conclusion == non_compliant` e `severity ∈ {high, critical}`**; senão `positive`.
  - Todo item que não seja `compliant` e não dispare o negativo é marcado `is_alert = true` e exibido na triagem.
  - Item `indeterminate` nunca torna o resultado negativo.
- **Rationale**: decisão Q (Session 2026-09-10, opção B). Não pune o proponente por capacidades mockadas (documento/OCR sempre `indeterminate`).
- **Roteamento** (`pre_evaluation_service`): `positive` → desbloqueia triagem + `process.status='TRIAGE'`; `negative` → cria nova `ActivityRun` de submissão para o proponente (padrão de `_handle_needs_revision`, `execution_reason='Pré-avaliação automática'`), `process.status='SUBMISSION'`; `failed` → volta ao proponente com flag de falha + as duas opções da US3.

## D6. Modelo de configuração: versionamento e imutabilidade

- **Decisão**:
  - `evaluation_definitions` (biblioteca) 1—N `evaluation_versions`.
  - `evaluation_versions.status ∈ {draft, published}`. Só existe **1 draft** por definição por vez. Editar via `PATCH` só em `draft`; `PATCH` em `published` → `409` com instrução de criar nova versão.
  - `POST /versions` clona a última versão para um novo `draft` (nº incrementado).
  - `publish`: valida ≥1 critério, congela `objective`, `criteria`, snapshot de `references` (JSONB: `[{reference_id, identifier, version_label}]`), grava `published_at/by`, muda status.
  - `evaluation_runs` guardam `evaluation_version_id` (a versão publicada usada) e cada `evaluation_run_items` guarda **snapshot** do enunciado/tipo/severidade do critério — reconstrução independe de edições futuras.
- **Rationale**: FR-012/FR-013/FR-046. Snapshot no item evita JOIN histórico frágil.
- **Alternativa**: versionar por cópia integral de linhas de critério a cada execução — rejeitado, redundante; o snapshot no item já basta.

## D7. Referências normativas

- **Decisão**: `evaluation_references` = catálogo simples (`identifier`, `label`, `version_label`, `reference_date`). A versão da avaliação guarda um **snapshot JSONB** das referências escolhidas. Consulta de impacto (FR-015) = `WHERE references @> '[{"reference_id": "..."}]'` sobre `evaluation_versions` e `evaluation_run_items`/`runs`.
- **Rationale**: sem tabela de associação e sem ingestão de texto/embedding nesta versão (Q3). `pgvector` permanece sem uso.
- **Alternativa**: tabela `evaluation_version_references` — rejeitada por simplicidade; JSONB containment cobre a única consulta requerida.

## D8. Fake provider para testes

- **Decisão**: `FakeModelProvider` determinístico, sem rede:
  - `evaluate_criterion`: heurística sobre o texto do conteúdo e a polaridade — ex.: para `positive`, `compliant` se o conteúdo contém termos-chave derivados do enunciado, senão `non_compliant`; conteúdo vazio → `indeterminate`; alvo documento/imagem → sempre `indeterminate`.
  - `suggest_criteria`: devolve lista canônica por `target_type` (ex.: POP → 10 critérios do item 30 da conversa).
  - Verdicts totalmente encenáveis por teste via `dependency_overrides` (injeta um fake que retorna a lista exata esperada).
- **Rationale**: mantém `unit`/`api`/CI offline (SC-011) e os testes significativos (asserção sobre consolidação, roteamento, imutabilidade).
- **Teste real opt-in**: `tests/integration/ai/test_openai_live.py` com `@pytest.mark.skipif(not os.getenv('RUN_OPENAI_TESTS'))`.

## D9. RBAC e autorização

- **Decisão**: a migração cria `ai_evaluations.read` e `ai_evaluations.manage` e as concede **apenas ao perfil `Administrador`** — consistente com o invariante do catálogo (todos os demais perfis recebem permissões via API RBAC, nunca por migração; o teste `test_rbac_migration` valida `non_admin_compositions == 0`). Endpoints de configuração usam `require_permission('ai_evaluations.manage')`; consulta usa `ai_evaluations.read`. Todas as mutações declaram `TrustedOrigin`. Um membro do Grupo Gestor que precise consultar avaliações recebe `ai_evaluations.read` por atribuição via API, ou acessa a pré-avaliação pelo escopo de participante do processo.
  - Proponente: `GET /processes/{id}/pre-evaluation` e `POST /processes/{id}/submission/direct-review` autorizados pelo vínculo de participante `proponent` (padrão da Spec 004/006).
  - Feedback e decisão de triagem: bloqueados por conflito de interesse vigente (`_guard_against_current_conflict`, já existente) — FR-043.
- **Rationale**: consistente com Spec 012 (Q1) e com o catálogo de permissões estrito da Spec 003.

## D10. Reuso do fluxo de retorno ao proponente

- **Decisão**: extrair de `_handle_needs_revision` (process_engine) a parte "criar nova `ActivityRun` de submissão + `FormInstance` + copiar `FormValue` + `Task` PROPONENT" para um helper reutilizável (`_open_new_submission_run(session, process_id, reason, user_id)`), chamado tanto pela diligência de triagem quanto pelo roteamento negativo da pré-avaliação.
- **Rationale**: evita duplicação; mantém a máquina de estados única (Constituição II — sem endpoints/atalhos paralelos).

## D11. Observabilidade (extensão da Spec 010)

- **Decisão**: manter `logs/application/events.jsonl` e `logs/ai/ai_steps.jsonl` + `broadcaster`. Estender:
  - `OperationalEventIndex.metadata` com `provider`, `models_used`, `real_cost`, `consolidated_result`.
  - `AIStepExecutionLog` ganha `model_name` e `real_cost` (substitui/compl. `simulated_cost`).
  - Nova operação `FORM_AI_PRE_EVALUATION` (substitui `FORM_AI_FIELD_EVALUATION`).
  - `correlation_id` = `evaluation_runs.correlation_id`; endpoint admin de IA agrupa por ele (já existe em `admin_logs`).
- **Rationale**: FR-047; reaproveita toda a infra da Spec 010.

## D12. Assistente de configuração — endpoint sem estado

- **Decisão**: `POST /ai-evaluations/suggest-criteria` recebe `{objective, target_type}` e devolve `list[SuggestedCriterion]` (sem persistir). O front (modo simples/assistente) exibe, o usuário aceita/edita e envia via `PATCH` da versão draft.
- **Rationale**: separa "sugerir" (efêmero, custa tokens) de "salvar" (persistente) — item 22 da conversa (configuração ≠ execução).

## D13. Modo de teste

- **Decisão**: `POST /ai-evaluations/{id}/versions/{n}/test` (só `draft`) recebe `{sample_content}`, roda o `EvaluationPipeline` em memória contra o provider atual, persiste `evaluation_test_runs` (para o alerta de "nunca testada" na publicação — FR-020) e devolve o resultado por critério. Não cria `evaluation_run` nem toca submissões.
- **Rationale**: FR-017–FR-020; `evaluation_test_runs` é a fonte do aviso de publicação.

## D14. Dependências novas — pyproject

- Adicionar em `[project.dependencies]`: `langchain-openai`, `langchain-core` (versões pinadas no padrão do projeto `(>=x,<y)`).
- `openai` entra transitivamente por `langchain-openai`.
- Nenhuma dependência de fila/broker.
