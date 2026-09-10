# Implementation Plan: Pacote de Baseline do Primeiro Deploy

**Branch**: `015-first-deploy-baseline` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-first-deploy-baseline/spec.md`

## Summary

Alinhar o estado inicial pós-deploy em três frentes que hoje divergem: (1) os cinco
formulários de submissão em `src/pivma/templates_data/` — mínimos nos processos 1‑3,
exemplo raso de IA no processo 4, Formulário Preliminar (FP) do BraCVAM no processo 5;
(2) os scripts de seed em `scripts/seeds/`, que passam a funcionar com os formulários
novos e a bastar em uma única execução de `seed_all` para exercer todas as demos; (3)
as seis páginas de `demos/`, reescritas sobre um padrão visual comum, com o catálogo
limpo e um único comando de carga citado em todo lugar.

Abordagem técnica: mudança de **dados declarativos + scripts + páginas estáticas**, sem
alterações no schema do banco nem em contratos de API. O único ajuste possível no
código de domínio é a poda de `FormField` órfãos no bootstrap (soft-delete), tratada
como item opcional de robustez com teste próprio. O reposicionamento da pré-avaliação
por IA (do formulário 2 para o formulário 4) exige atualizar helpers e testes que hoje
acoplam a forma antiga dos formulários.

## Technical Context

**Language/Version**: Python >=3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic,
PostgreSQL + pgvector, PyYAML, structlog

**Storage**: PostgreSQL (dados de template/processo já modelados; sem novas tabelas)

**Testing**: pytest + pytest-asyncio, Testcontainers (`pgvector/pgvector:pg17`),
factory-boy; skill `fastapi-testing-methodology` obrigatória ao tocar testes

**Target Platform**: Servidor Linux (API) + páginas estáticas servidas em `/demos/`

**Project Type**: Single project (web service + páginas de demonstração descartáveis)

**Performance Goals**: N/A (carga de seed e páginas de demo; sem metas de throughput)

**Constraints**:
- Sem alteração de schema → sem migração Alembic.
- Sem endpoint novo nem parâmetro de API para viabilizar demo (Constituição II).
- `demos/` permanece 100% desacoplado de `src/`.
- Tipos de campo limitados aos suportados: `text`, `textarea`, `integer`, `float`,
  `boolean`, `date`, `select`, `file_upload`; agrupamento por seção só via
  `validation_rules.section` no YAML (lido por `get_activity_form`).
- `bootstrap_process_templates` faz *upsert* de campos e **não** remove campos ausentes
  do YAML — relevante para re-seed sobre banco não vazio.

**Scale/Scope**: 5 arquivos YAML (só o formulário de submissão de cada), 4 scripts de
seed + 1 removido, 6 páginas de demo + 1 folha de estilo compartilhada + catálogo,
~6 arquivos de teste/helper a re-apontar.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Status |
| :-- | :-- | :-- |
| I. Especificação antes da implementação | `spec.md` + `## Clarifications` concluídos; este `plan.md` segue o fluxo. | PASS |
| II. Domínio puro, demos descartáveis | Nenhum endpoint/parâmetro novo. `demos/` continua servido estaticamente e removível. Seeds só com massa necessária. Poda de `FormField` órfão (se adotada) é higiene de domínio, não facilitador de demo. | PASS |
| III. Demonstração como critério de conclusão | A feature entrega demos + seeds funcionais contra a API real; `quickstart.md` define a validação ponta a ponta. | PASS |
| IV. Qualidade verificável | `poe format` + `poe lint` + `poe test` verdes. Testes seguem a estrutura em níveis e a skill `fastapi-testing-methodology`. **Lacuna:** `andrej-karpathy-skills:karpathy-guidelines` não está instalada neste ambiente (ver Riscos); princípios aplicados manualmente. | PASS c/ ressalva |
| V. Auditabilidade e rastreabilidade | Nenhuma remoção física. Poda de `FormField` usa `deleted_at`. Sem novos modelos. | PASS |
| VI. Segurança por padrão | Sem mudança em auth, RBAC, cookies ou rotas de mutação. | PASS |

Sem violações → **Complexity Tracking** vazio.

## Project Structure

### Documentation (this feature)

```text
specs/015-first-deploy-baseline/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — decisões e alternativas
├── data-model.md        # Fase 1 — campos dos 5 formulários + mapeamento do FP
├── quickstart.md        # Fase 1 — roteiro de validação ponta a ponta
├── contracts/
│   └── demo-standard.md  # Contrato de UI compartilhado das demos + comando de carga
├── checklists/
│   └── requirements.md   # Checklist de qualidade da spec (já existente)
└── tasks.md             # Fase 2 — gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── templates_data/
│   ├── 01_pre_validated_method.yaml      # form submission → 1 campo (method_title)
│   ├── 02_scope_extension.yaml           # form submission → 1 campo (method_title)
│   ├── 03_me_too_validation.yaml         # form submission → 1 campo (method_title)
│   ├── 04_validated_method_dossier.yaml  # form submission → exemplo raso de IA
│   ├── 05_proof_of_concept.yaml          # form submission → Formulário Preliminar (FP)
│   └── README.md                         # atualizar exemplos se necessário
└── bootstrap_process_templates.py        # (opcional) poda de FormField ausente do YAML

scripts/seeds/
├── seed_all.py             # ajustar texto de saída (links/contas)
├── seed_forms.py           # rótulos [DEMO n]; instancia os 5 processos
├── seed_triage.py          # DEMO 1 → TRIAGE submetendo só method_title
├── seed_ai_evaluations.py  # reposiciona avaliação/atribuição p/ o formulário 4
└── seed_form_ai_demo.py    # REMOVER (órfão, fora de seed_all)

demos/
├── index.html              # catálogo: sem link p/ DESIGN.md, comando único de carga
├── assets/base.css         # NOVO — padrão visual compartilhado
├── assets/base.js          # NOVO (opcional) — componente de status da API compartilhado
├── forms/                  # reescrever sobre o padrão
├── submission/             # reescrever sobre o padrão
├── triage/                 # reescrever sobre o padrão
├── ai-pipeline/            # reescrever sobre o padrão
├── users/                  # reescrever sobre o padrão
├── operational-index/      # reescrever sobre o padrão
└── README.md               # NOVO (opcional) — diretriz de padrão (substitui DESIGN.md)

tests/
├── ai_eval_helpers.py                              # re-apontar p/ formulário 4 (fix central: 15 consumidores)
├── unit/core/test_process_engine.py                # ajustar rascunho/submissão (usa endpoint_target, scientific_justification)
├── integration/database/test_evaluation_library_reuse.py  # re-apontar template/field
├── api/routers/test_evaluation_assignments.py      # re-apontar AI_FIELD/template locais
├── api/routers/test_evaluation_library.py          # re-apontar URL de template
├── unit/core/test_template_loader.py               # provável: nenhuma mudança (só checa nomes/keys de template, não campos)
└── unit/core/test_first_deploy_forms.py            # NOVO — cobre a forma dos 5 formulários pós-bootstrap
```

**Structure Decision**: Single project já estabelecido. A feature não cria pacotes
nem camadas novas; concentra-se em `src/pivma/templates_data/`, `scripts/seeds/`,
`demos/` e nos testes acoplados. Um único arquivo de código de domínio
(`bootstrap_process_templates.py`) pode receber a poda opcional de campos órfãos.

## Phase 0: Research

Ver [research.md](./research.md). Perguntas resolvidas:

1. Como preservar o agrupamento por seções do FP só via YAML.
2. Qual processo carrega a pré-avaliação por IA para as demos de triagem e
   observabilidade após a simplificação dos formulários 1‑3.
3. Como mapear cada elemento do FP para os tipos de campo suportados (aproximação).
4. Como remediar o acoplamento dos testes à forma antiga dos formulários.
5. O que fazer com `FormField` órfão ao reduzir um formulário (re-seed sobre banco não
   vazio) e limites por número de palavras do FP.
6. Comando de carga canônico e itens do padrão visual compartilhado das demos.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md): definição campo a campo dos cinco formulários de
  submissão, incluindo o mapeamento completo do FP e a lista de aproximações/pendências.
- [contracts/demo-standard.md](./contracts/demo-standard.md): contrato de interface
  compartilhado pelas seis páginas de demonstração (cabeçalho, tokens visuais,
  componente de status da API, regra de idioma, comando único de carga, mensagem de
  "dados ausentes").
- [quickstart.md](./quickstart.md): roteiro executável — banco limpo → migração →
  `seed_all` → percorrer cada demo → rodar a suíte — com os resultados esperados.

### Post-Design Constitution Re-check

Sem novas tabelas, endpoints ou dependências introduzidas no design. `demos/assets/`
é conteúdo estático dentro de `demos/`, sem import de `src/`. A poda de `FormField`
permanece opcional e coberta por teste de upgrade/estado. **Resultado: PASS**, mantida
a ressalva sobre a skill `karpathy-guidelines` ausente.

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
| :-- | :-- | :-- |
| Testes/helpers acoplam a forma antiga de `submission_pre_validated_v1` (campo `scientific_justification`). | Suíte vermelha ao simplificar o formulário 1. | Re-apontar `tests/ai_eval_helpers.py` e os testes de avaliação para o formulário 4 (`submission_validated_dossier_v1`); rodar `poe test` como portão. |
| `bootstrap` não remove `FormField` ausente do YAML; re-seed sobre banco não vazio deixa campos antigos visíveis. | Formulário "simplificado" ainda mostra campos legados após re-seed. | `quickstart` assume banco migrado e vazio. Item opcional: poda por `deleted_at` no bootstrap, com teste dedicado. |
| `seed_ai_evaluations` cria processo com título fora de `OFFICIAL_DEMO_PROCESSES`, que `seed_forms`/`seed_triage` soft-deletam por não constar na lista. | Processo da demo de IA some conforme a ordem de execução. | Reposicionar a pré-avaliação sobre a instância oficial `[DEMO 4] …` já criada por `seed_forms`, em vez de um processo `[DEMO IA]` separado. |
| Limites por número de palavras do FP ("máx. 150 palavras") não são aplicáveis (só `min_length` em caracteres). | Fidelidade parcial ao FP. | Registrar como pendência; orientar via `help_text`. |
| Skill `andrej-karpathy-skills:karpathy-guidelines` não instalada. | Portão de qualidade da Constituição IV parcialmente não verificável por ferramenta. | Declarar a lacuna (feito aqui e no `spec.md`); aplicar os princípios manualmente: diffs mínimos, sem abstração prematura, seguir o estilo vizinho. |
| Skill `stop-slop` ausente para a prosa dos `README`/`demo-standard`. | Textos de documentação sem o portão de prosa. | Declarar a lacuna; manter textos curtos e factuais. |

## Complexity Tracking

*Sem violações da Constituição — seção não aplicável.*
