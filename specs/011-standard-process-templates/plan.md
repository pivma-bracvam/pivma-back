# Implementation Plan: 011 - Processos Padrão do Sistema (5 Pipelines Oficiais e Fase 1: Submissão, Avaliação por IA e Deliberação BraCVAM)

**Branch**: `011-standard-process-templates` | **Date**: 2026-09-09 | **Spec**: [specs/011-standard-process-templates/spec.md](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/specs/011-standard-process-templates/spec.md)

**Input**: Feature specification from `specs/011-standard-process-templates/spec.md`

---

## Summary

Descontinuar o arquivo e template mock `full_validation_v1.yaml` (`full_validation`) e introduzir os 5 processos oficiais padronizados do BraCVAM:
1. `pre_validated_method`: Método Pré-Validado (Candidato à Validação Interlaboratorial);
2. `scope_extension`: Extensão de Escopo de Aplicação (Validação para Nova Finalidade de Uso);
3. `me_too_validation`: Validação Me-Too (Transferência / Semelhança de Sistema-Teste);
4. `validated_method_dossier`: Método Validado – Dossiê Submetido (Revisão por Pares Concluída);
5. `proof_of_concept`: Prova de Conceito (PoC) (Método Conceitual / Em Desenvolvimento).

Para todos os 5 processos, o template restringe o ciclo estritamente à **Fase 1 (Submissão e Triagem)**, estruturada em 3 etapas sequenciais integradas:
1. Elaboração e envio da proposta pelo Proponente (`proposal_submission`);
2. Avaliação técnica automatizada pelo motor de IA simulado da Feature 010 ([`FormAIPipelineEngine`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/src/pivma/ai/pipeline.py)) retornando por padrão resultado negativo simulado (`NEEDS_ADJUSTMENT` / `REPROVED`) com lista de inconformidades e recomendações;
3. Validação e deliberação final pelo BraCVAM (`triage_evaluation` por `TRIAGE_LEAD`), gerando decisão (`APPROVED`, `NEEDS_REVISION` ou `REJECTED`).

---

## Technical Context

**Language/Version**: Python 3.12+ (requisito pyproject: `>=3.14,<4.0` com suporte de execução local)

**Primary Dependencies**:
- FastAPI (roteamento e injeção de dependências)
- SQLAlchemy 2.0 (ORM assíncrono com PostgreSQL)
- Pydantic v2 (validação de schemas e serialização)
- PyYAML (leitura declarativa dos templates)
- structlog (logging estruturado JSONL)

**Storage**: PostgreSQL 16 (tabelas existentes: `process_templates`, `process_template_versions`, `form_templates`, `form_fields`, `process_instances`, `phases`, `activity_instances`, `activity_runs`, `tasks`, `artifacts`, `decisions`, `audit_events`)

**Testing**: pytest, pytest-asyncio, testcontainers, factory_boy, httpx

**Target Platform**: Linux server (Docker / Cloud Native)

**Project Type**: REST API / Web service backend

**Performance Goals**: Tempo de bootstrap de todos os 5 templates < 500ms; consulta de templates < 50ms; submissão e processamento de IA mock < 200ms.

**Constraints**:
- Total desacoplamento entre backend (`src/`) e interfaces de demonstração (`demos/`), conforme [AGENTS.md](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/AGENTS.md).
- Nenhuma adição de endpoints facilitadores exclusivamente para demos.
- Preservação da máquina de estados e auditoria da Feature 004.

**Scale/Scope**: 5 templates de processo, 5 formulários dedicados em YAML, integração direta com pipeline de IA existente, migração de testes e sementes.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Arquitetura Declarativa**: Todos os processos e formulários continuam parametrizados em arquivos declarativos YAML sob `src/pivma/templates_data/`. (PASS)
- **Desacoplamento e AGENTS.md**: Código em `demos/` permanece estritamente consumidor das APIs públicas de domínio. Seeds em `scripts/seeds/` viabilizam a execução das demonstrações. (PASS)
- **Metodologia de Testes (fastapi-testing-methodology)**: Testes de unidade, integração e router são mantidos isolados e com uso de factories e transações limpas sem concorrência destrutiva. (PASS)
- **Imutabilidade e Auditoria**: Cada transição de estado, parecer ou reexecução por diligência gera registros em `audit_events` e nos arquivos de log JSONL. (PASS)

---

## Project Structure

### Documentation (this feature)

```text
specs/011-standard-process-templates/
├── plan.md              # Este arquivo
├── research.md          # Decisões de arquitetura e mitigação de impactos
├── data-model.md        # Especificação dos templates, entidades e estados
├── quickstart.md        # Roteiro de validação ponta a ponta
├── checklists/
│   └── requirements.md  # Checklist de qualidade da especificação
└── contracts/
    ├── templates_contract.md # Definição detalhada dos 5 arquivos YAML
    └── api_contract.md       # Contratos dos endpoints de ciclo de vida
```

### Source Code (repository root)

```text
src/pivma/
├── templates_data/
│   ├── 01_pre_validated_method.yaml      # Processo 1
│   ├── 02_scope_extension.yaml           # Processo 2
│   ├── 03_me_too_validation.yaml         # Processo 3
│   ├── 04_validated_method_dossier.yaml  # Processo 4
│   └── 05_proof_of_concept.yaml          # Processo 5
├── bootstrap_process_templates.py        # Carregador declarativo assíncrono
├── core/
│   ├── process_engine.py                 # Orquestração do ciclo da Fase 1 + trigger IA
│   └── database/models.py                # Modelos ORM existentes
├── ai/
│   └── pipeline.py                       # FormAIPipelineEngine (Spec 010)
└── routers/
    ├── processes.py                      # Instanciação e consulta de processos
    └── forms.py                          # Submissão e consulta de formulários

tests/
├── api/routers/
│   ├── test_process_router.py            # Validação dos 5 templates
│   └── test_form_submission.py           # Submissão com novos templates
├── integration/
│   └── test_form_ai_evaluation_api.py    # Teste integrado do pipeline de IA
└── unit/core/
    ├── test_template_loader.py           # Validação da carga dos 5 YAMLs
    └── test_process_engine.py            # Transições e deliberação BraCVAM

scripts/seeds/
├── seed_forms.py                         # Atualizado para os novos templates
├── seed_triage.py                        # Atualizado para os novos templates
└── seed_form_ai_demo.py                  # Atualizado para os novos templates

demos/
├── index.html                            # Catálogo central atualizado com os 5 processos
└── operational-index/                    # Visualização de logs operacionais
```

---

## Complexity Tracking

Nenhuma violação aos princípios do projeto. O escopo é estritamente redutor/organizador: remove o arquivo demonstrativo `full_validation_v1.yaml`, reduz os templates para conter exclusivamente a Fase 1 (Submissão e Triagem) e introduz os 5 processos canônicos reais com os formulários dedicados.
