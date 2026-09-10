# Specification Quality Checklist: Avaliação Configurável por IA na Submissão e Triagem

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-09
**Updated**: 2026-09-10 (clarifications Q1–Q3 da Session 2026-09-09 + 4 perguntas da Session 2026-09-10)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

### Session 2026-09-09
- **Q1** escopo do formulário dinâmico → consome o editor da Spec 012 como está; foco na configuração da IA (FR-049, FR-050).
- **Q2** regras institucionais → roteamento fixo embutido (positivo → triagem; negativo → proponente) (FR-030, FR-030a, FR-031).
- **Q3** referências normativas → apenas metadados versionados; sem RAG/banco vetorial (FR-007, FR-014, FR-015).

### Session 2026-09-10
- Análise de texto usa **modelo real da OpenAI via LangChain** (produção); documento/OCR/imagem seguem mockados como "não foi possível determinar" (FR-024, FR-024e).
- **Provedor de modelos** injetável (padrão `dependencies.py`), camadas extração/rápido/raciocínio, `AI_PROVIDER`, `temperature=0`, chave via `pydantic-settings`, fake nos testes (FR-024a–FR-024d, SC-011).
- Pré-avaliação **assíncrona**: envio confirma na hora, processa em background, proponente acompanha status (FR-021a–FR-021d, SC-014).
- Resultado consolidado **negativo sse houver ≥1 não conformidade de severidade alta/crítica**; o restante vira alerta na triagem (FR-030).
- Demonstrações: **dois módulos** em `demos/` (editor de formulário e biblioteca de avaliações) contra a API real em `:8000`, nada criado só para a demo (US7, SC-013).

### Direção de planejamento (não são requisitos funcionais)
- Nomes das camadas do provedor são indicativos e podem ser adaptados ao vocabulário do projeto.
- Mecanismo concreto de background (BackgroundTasks, worker, fila) fica a cargo do `plan.md`, respeitando "código não complexo demais".

**Pronta para `/speckit-plan`.**
