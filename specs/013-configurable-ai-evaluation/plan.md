# Implementation Plan: Avaliação Configurável por IA na Submissão e Triagem

**Branch**: `013-configurable-ai-evaluation` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/013-configurable-ai-evaluation/spec.md`

## Summary

Substituir a esteira de IA de veredito fixo (Spec 010) por uma **avaliação dirigida por configuração**: o BraCVAM descreve em linguagem natural o que verificar, o sistema sugere critérios estruturados (tipo, evidência exigida, severidade), versiona a configuração de forma imutável e a associa a alvos de um formulário. Na submissão, uma **pré-avaliação assíncrona** roda um pipeline por critério usando modelos reais da OpenAI via LangChain (camadas *extraction / fast / reasoning* atrás de um provedor injetável), consolida um resultado por regra fixa de severidade (**negativo sse houver ≥1 não conformidade alta/crítica**) e aplica roteamento embutido (**positivo → triagem**, **negativo → volta ao proponente**). O proponente pode corrigir e reenviar ou **solicitar intervenção direta do BraCVAM**. Na triagem, o avaliador vê a pré-avaliação como evidência auxiliar, registra concordância/discordância por critério e toma a decisão regulatória — que permanece 100% humana. Tudo auditável e reconstruível.

Abordagem técnica: manter o padrão atual do repositório (routers finos → funções de serviço → SQLAlchemy async; `Depends` para injeção; `structlog` em duas camadas de log). Nenhuma infra nova de fila: a pré-avaliação roda em `BackgroundTasks` do FastAPI com uma varredura de execuções presas. Sem RAG / pgvector nesta versão.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async, `psycopg`), Pydantic v2 / `pydantic-settings`, Alembic, `structlog`. **Novas**: `langchain-openai` (`ChatOpenAI`, `.with_structured_output`), `langchain-core`.

**Storage**: PostgreSQL (extensão `pgvector` presente mas **não usada** nesta feature). ~10 tabelas novas, todas com `AuditMixin` e exclusão lógica.

**Testing**: `pytest` + `pytest-asyncio`, Testcontainers (`pgvector/pgvector:pg17`), Factory Boy, `httpx`, padrão AAA. Provedor de modelos substituído por **fake determinístico** em `unit`/`api`/CI — zero chamadas externas, zero tokens. Um teste real da OpenAI opt-in (`RUN_OPENAI_TESTS`).

**Target Platform**: Servidor Linux (contêiner Docker; `entrypoint.sh` aplica migrações e sobe Uvicorn).

**Project Type**: Web service (backend único) — estrutura `src/pivma/` já existente.

**Performance Goals**: Envio do formulário confirma em < 2 s independentemente da latência da OpenAI (SC-014). Pré-avaliação assíncrona: sem alvo rígido de latência; execução presa por > 15 min é marcada como falha por varredura.

**Constraints**: `OPENAI_API_KEY` apenas via `Settings` (FR-024b); nenhuma chamada externa em `unit`/`api`/CI (SC-011); execuções de pré-avaliação imutáveis (FR-046); mutações validam `CurrentUser` + `TrustedOrigin`; Ruff `line-length = 79`, aspas simples, `preview=true`.

**Scale/Scope**: Projeto pequeno (poucas dezenas de processos simultâneos). Otimização fina de modelos e de custo fica para depois (decisão do usuário).

## Constitution Check

*GATE: avaliado contra `.specify/memory/constitution.md` v1.0.0.*

| Princípio | Situação | Observação |
|---|---|---|
| I. Especificação antes da implementação | ✅ PASS | `spec.md` + Clarifications (2 sessões) aprovados; este plano deriva deles. |
| II. Domínio puro na API, demos descartáveis | ✅ PASS | Nenhum endpoint/atalho/dado só para demo. Os endpoints de configuração e de pré-avaliação são domínio legítimo. Demos em `demos/`, desacopladas de `src/`. |
| III. Demonstração como critério de conclusão | ✅ PASS | Dois módulos: `demos/ai-evaluation-form-editor/` e `demos/ai-evaluation-library/`, catalogados em `demos/index.html`, contra a API real em `:8000`, com `scripts/seeds/ai_evaluation_seed.py`. |
| IV. Qualidade verificável antes da entrega (NÃO NEGOCIÁVEL) | ✅ PASS | Camadas `unit`/`api`/`integration/{database,migrations}`; fake provider mantém CI offline; `ruff` + `pytest` no portão. `Skill(fastapi-testing-methodology)` será invocada antes de criar/alterar testes. |
| V. Auditabilidade e rastreabilidade | ✅ PASS | Todas as tabelas novas herdam `AuditMixin` + `deleted_at`. `evaluation_runs`/`evaluation_run_items` imutáveis; `reviewer_feedback` e `direct_review_requests` append-only; avaliações versionadas com snapshot na execução. Observabilidade da Spec 010 estendida (provedor, modelos, custo real). |
| VI. Segurança por padrão | ✅ PASS | Novas permissões RBAC (`ai_evaluations.read`, `ai_evaluations.manage`) criadas por migração; `TrustedOrigin` em todas as mutações; chave lida só de `Settings`; erros de LLM viram status `failed` genérico sem vazar detalhes. |
| Restrições de stack | ⚠️ JUSTIFICAR | Novas dependências de runtime `langchain-openai` + `langchain-core`. Ver Complexity Tracking. |
| Migrações com teste up/down | ✅ PASS | Uma migração autogerada com teste em `tests/integration/migrations/`. |

**Resultado do gate (pré-Fase 0): PASS** (uma justificativa registrada em Complexity Tracking).

### Re-check pós-design (Fase 1)

Revisado após `research.md`, `data-model.md`, `contracts/` e `quickstart.md`:

- **V. Auditabilidade** — reforçado: `evaluation_run_items` guarda snapshot do critério; `evaluation_runs` imutável pós-conclusão; `reviewer_feedback` e `direct_review_requests` com unicidade que impede sobrescrita; `AuditEvent` novos cobrem todo o ciclo.
- **II / III. Demos** — os contratos não introduzem nenhum endpoint exclusivo de demonstração; `GET /evaluable-fields` e `suggest-criteria` são domínio legítimo (usados também fora da demo).
- **IV. Testes offline** — `FakeModelProvider` + `conftest` com `AI_PROVIDER=fake` + `dependency_overrides` garantem `unit`/`api`/CI sem rede (SC-011); migração única com teste up/down.
- **VI. Segurança** — `suggest-criteria`/`test` exigem `ai_evaluations.manage`; erro de provedor → `503`/`failed` genérico; chave só em `Settings`.
- **Nº de tabelas (10)** — mantido sob justificativa; a simplificação de referências (catálogo + JSONB) já foi aplicada no design.

**Resultado do gate (pós-design): PASS.** Nenhuma violação nova.

## Project Structure

### Documentation (this feature)

```text
specs/013-configurable-ai-evaluation/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — decisões técnicas
├── data-model.md        # Fase 1 — entidades, enums, transições
├── quickstart.md        # Fase 1 — roteiro de validação ponta a ponta
├── contracts/
│   ├── ai-evaluation-config.md      # Biblioteca, versões, critérios, referências, assistente, teste
│   ├── evaluation-assignments.md    # Associação avaliação ↔ alvo de formulário
│   └── pre-evaluation-and-triage.md # Execução, consulta, intervenção direta, feedback, retry
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/pivma/
├── ai/
│   ├── contracts.py            # (existente) estender: EvaluationRun/Item, StepLog reaproveitado
│   ├── provider.py             # NOVO — ModelProvider (ABC) + OpenAIModelProvider + FakeModelProvider; camadas extraction/fast/reasoning
│   ├── schemas.py              # NOVO — modelos Pydantic de saída estruturada do LLM (verdict por critério, sugestão de critérios)
│   ├── pipeline.py             # REESCRITO — EvaluationPipeline: prepare → avaliar critério (por camada) → consolidar → relatório
│   ├── consolidation.py        # NOVO — regra fixa severidade → positivo/negativo + alertas
│   └── steps/                  # REFATORADO — context_preparation, criterion_evaluation, synthesis
├── core/
│   ├── evaluation_service.py       # NOVO — CRUD de definições/versões/critérios/referências; publish; suggest; test-run
│   ├── pre_evaluation_service.py   # NOVO — run_pre_evaluation() (background), roteamento pós-resultado, retry, varredura de presas
│   ├── process_engine.py          # EDITADO — submit_proposal_form: agenda background, NÃO desbloqueia triagem no envio
│   └── logging.py / log_service.py # EDITADO — expor consulta de execuções de IA por run
├── routers/
│   ├── ai_evaluations.py       # NOVO — /ai-evaluations/**, /ai-evaluations/references, /form-templates/{key}/evaluation-assignments, métricas
│   └── pre_evaluation.py       # NOVO — /processes/{id}/pre-evaluation, /submission/direct-review, /pre-evaluation/{run}/feedback; /admin/pre-evaluations/{run}/retry
├── dependencies.py             # EDITADO — ModelProviderDep = Annotated[ModelProvider, Depends(get_model_provider)]
├── schemas.py                  # EDITADO — request/response models desta feature
└── core/settings.py            # EDITADO — OPENAI_API_KEY (opcional), AI_PROVIDER, AI_MODEL_{EXTRACTION,FAST,REASONING} (com defaults)

migrations/versions/<hash>_configurable_ai_evaluation.py   # NOVO

demos/
├── index.html                          # EDITADO — catalogar os 2 módulos
├── ai-evaluation-form-editor/          # NOVO — configurar avaliações pelo editor de formulário
│   ├── index.html
│   └── app.js
└── ai-evaluation-library/              # NOVO — configurar pela biblioteca (criar, sugerir, testar, publicar, associar)
    ├── index.html
    └── app.js

scripts/seeds/ai_evaluation_seed.py     # NOVO — massa mínima p/ as demos

tests/
├── unit/ai/                            # consolidação, seleção de camada, factory do provider, schemas
├── unit/core/                          # regras de versionamento/publicação
├── api/routers/test_ai_evaluations_*.py, test_pre_evaluation_*.py
├── integration/database/               # imutabilidade de versão/run, unicidade, append-only
├── integration/migrations/             # up/down da nova migração
└── factories/                          # EvaluationDefinitionFactory, EvaluationVersionFactory, CriterionFactory, EvaluationRunFactory
```

**Structure Decision**: Projeto único já existente (`src/pivma/`). A feature adiciona um subpacote de provedor/pipeline em `src/pivma/ai/`, dois serviços em `src/pivma/core/`, dois routers, uma migração, dois módulos de demo e um seed. Nenhuma reorganização das pastas atuais.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| Novas dependências `langchain-openai` + `langchain-core` | O usuário exigiu explicitamente LangChain; ele abstrai cliente, retries e **saída estruturada** (`.with_structured_output`) das três camadas de modelo com uma interface única e trocável. | Usar o SDK `openai` cru foi rejeitado: exigiria reimplementar parsing estruturado, tratamento de erro e a troca de camadas à mão, além de contrariar a instrução do usuário. |
| 10 tabelas novas | O domínio separa 6 conceitos independentes (definição, versão, critério, referência, associação, execução) mais 3 registros append-only (item de execução, feedback, pedido de intervenção) e 1 de teste. Fundir qualquer par quebra imutabilidade (FR-012/FR-046) ou a consulta de feedback por critério (FR-040). | Guardar tudo em JSONB numa tabela de "avaliação" foi rejeitado: impede FK para feedback por critério, versionamento consultável e reconstrução de auditoria (FR-044/FR-045). Referências foram simplificadas para catálogo + snapshot JSONB na versão (sem tabela de associação). |
| Execução assíncrona via `BackgroundTasks` + varredura de presas | A spec exige assíncrono (FR-021a) com chamadas reais à OpenAI de latência imprevisível. | Celery/RQ/arq foi rejeitado: adiciona broker e worker — infra desproporcional a um projeto pequeno; a constituição pede "código não complexo demais". |
