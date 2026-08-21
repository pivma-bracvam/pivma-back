# Implementation Plan: Estrutura Base de Processos e Fase 1: Submissão e Triagem

**Branch**: `feat/process-submission-triage` | **Date**: 2026-08-21 | **Spec**: [spec.md](spec.md)

**Input**: Especificação da feature 004 e contexto arquitetural consolidado (Fase 1 operacional com entidades base extensíveis para todo o ciclo de vida).

## Summary

Implementar o núcleo de execução de processos do PIVMA (`ProcessTemplate`, `ProcessTemplateVersion`, `ProcessInstance`, `Phase`, `ActivityInstance`, `ActivityRun`, `Task`, `FormTemplate`, `FormField`, `FormInstance`, `FormValue`, `FieldReview`, `Artifact`, `ActivityDependency`, `Assignment`, `Decision`, `AuditEvent`) e tornar 100% operacional a **Fase 1: Submissão e Triagem**.

A implementação fornecerá:
1. Carregamento declarativo de templates e formulários via YAML (`full_validation_v1.yaml`).
2. Instanciação e ciclo de vida de processos, fases e atividades.
3. Preenchimento estruturado, validação e salvamento de rascunhos em formulários dinâmicos.
4. Revisão campo a campo (`FieldReview`) e deliberação de triagem (`Decision`) com suporte a Aprovação, Rejeição e Diligência (gerando `ActivityRun #2` sem sobrescrever histórico).
5. Painel de tarefas operacionais com bloqueio explicável por dependências e timeline auditável.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg 3, Alembic 1.19, PyYAML

**Storage**: PostgreSQL com pgvector existente; tabelas normalizadas para templates, instâncias, fases, atividades, execuções, tarefas, formulários, avaliações, artefatos, dependências, decisões e auditoria.

**Testing**: Pytest, TestClient, Testcontainers, pytest-asyncio e Factory Boy.

**Target Platform**: Serviço HTTP Python em servidor Linux; PostgreSQL 17 no ambiente local e de testes.

**Project Type**: Serviço web de API RESTful.

**Performance Goals**: Consultas de tarefas e timeline indexadas; listagens paginadas sem N+1 queries.

**Constraints**: Preservação estrita de histórico (sem hard deletes em dados de processo); `AuditMixin` em todas as tabelas; instâncias fixadas na versão do template de criação; concorrência tratada em transições de estado.

**Scale/Scope**: 1 template completo inicial (Validação Completa), 2 formulários estruturados (Submissão e Triagem), 15 entidades de domínio, endpoints para ciclo de vida de processo, submissão, triagem, tarefas e timeline.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pré-pesquisa: APROVADO.**
- **Requisitos e Evidência**: Atende aos requisitos da Fase 1 (Submissão e Triagem) do PIVMA, respeitando o princípio de não implementar funcionalidades das fases posteriores prematuramente, mas fornecendo as abstrações necessárias.
- **Rastreabilidade e Imutabilidade**: Adoção de `ActivityRun` e `FieldReview` garantindo que reexecuções e diligências criem novas tentativas sem apagar o histórico anterior.
- **Mudança Mínima e Sem Over-engineering**: Rejeitada a construção de um motor BPMN arbitrário genérico; adotado modelo orientado a atividades, tarefas, dependências e templates declarativos em YAML.

**Pós-design: APROVADO.**
- Os artefatos `research.md`, `data-model.md`, `contracts/processes.openapi.yaml`, `contracts/declarative_template_schema.md` e `quickstart.md` delimitam claramente os contratos e a persistência.
- O isolamento entre proponente e triador é preservado e auditado.

## Project Structure

### Documentation (this feature)

```text
specs/004-process-submission-triage/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── processes.openapi.yaml
│   └── declarative_template_schema.md
└── tasks.md             # gerado por $speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                         # Registro de routers
├── schemas.py                          # Schemas Pydantic para processos, tarefas, formulários e triagem
├── bootstrap_process_templates.py      # Script/serviço para carregar templates YAML no banco
├── templates_data/
│   └── full_validation_v1.yaml         # Definição declarativa do pipeline de Validação Completa
├── core/
│   ├── process_engine.py               # Lógica de transição de estados, dependências e reexecução
│   └── database/
│       └── models.py                   # Entidades SQLAlchemy (ProcessTemplate, ProcessInstance, ActivityRun, etc.)
└── routers/
    ├── processes.py                    # Endpoints /processes (criação, listagem, timeline)
    ├── forms.py                        # Endpoints de formulários (rascunho, submissão, campos)
    ├── tasks.py                        # Endpoints /tasks (tarefas operacionais)
    └── triage.py                       # Endpoints de triagem (revisão de campos e decisão)

migrations/versions/
└── <revision>_process_submission_triage_core.py

tests/
├── factories/
│   └── process_factory.py              # Factories para ProcessTemplate, ProcessInstance, FormInstance, etc.
├── unit/core/
│   ├── test_process_engine.py          # Testes unitários do motor de dependências e reexecução
│   └── test_template_loader.py         # Testes de parsing e validação de templates YAML
├── integration/
│   ├── database/test_process_constraints.py
│   └── migrations/test_process_migration.py
└── api/routers/
    ├── test_process_router.py          # Ciclo de vida e listagem de processos
    ├── test_form_submission.py         # Validação de campos e envio de formulários
    ├── test_triage_router.py           # Revisão campo a campo e decisões (aprovação, rejeição, diligência)
    └── test_task_router.py             # Painel operacional e bloqueio explicável
```

**Structure Decision**: Concentrar a lógica do motor de processos em `core/process_engine.py` para isolar as regras de transição e cálculo de dependências dos routers HTTP, preservando a simplicidade e evitando camadas artificiais de repository.

## Complexity Tracking

| Decisão | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| Múltiplos `ActivityRun` por atividade | Suportar reexecuções e diligências preservando histórico imutável | Reabrir status do mesmo registro destruiria o histórico exigido para fins regulatórios e auditoria. |
| Separação `FormValue` e `FieldReview` | Triadores precisam revisar e emitir parecer campo a campo de forma independente do valor submetido | Armazenar pareceres dentro do mesmo JSONB do formulário dificultaria auditoria temporal e diff entre versões. |
| Definições declarativas em YAML | Facilitar versionamento e permitir futura importação de formulários legados | Inserção puramente via migração SQL manual tornaria formulários com muitos campos quase ilegíveis e difíceis de evoluir. |
