# Specification Quality Checklist: Execução de atividades por laboratório participante

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-02
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

- A spec cita `sample_definition`, `participating_laboratory` e
  `group_manager` porque a issue #58 e as specs anteriores usam esses nomes
  como vocabulário do domínio. Não há decisão de implementação (módulos,
  colunas, consultas, rotas) na spec.
- Iteração 1: o cenário 5 da história 1 não dizia qual operação era recusada.
  Corrigido para "a conclusão da dependência que tenta abrir a atividade".
- Nenhum marcador [NEEDS CLARIFICATION]: as decisões estão na seção
  Clarifications, em duas sessões de 2026-10-02 (a segunda resolve os
  achados do `/speckit-analyze`).
- Os quatro pressupostos pendentes foram confirmados pelo usuário em
  2026-10-02 e estão na seção Clarifications (FR-019, FR-020a, FR-028).
- O cenário 5 da história 1 (conjunto congelado vazio) não é alcançável pelos
  fluxos atuais, porque `sample_definition` recusa concluir sem laboratório.
  Fica porque a issue pede essa recusa explicitamente.
- `/speckit-analyze` (2026-10-02): 1 crítico (C1, identidade de laboratório
  exposta em `/tasks` e na trilha), 3 altos (C2 estados terminais no
  cancelamento, C3 regra de conclusão divergente, C4 dispensa antes do
  congelamento), 3 médios e 6 baixos. Todos tratados na spec (FR-004,
  FR-004a, FR-013, FR-017a, FR-021, FR-035 a FR-039, SC-009, SC-010), na
  pesquisa (R5, R6, R9 a R11, R13, R14), no data-model, no contrato e no
  `tasks.md`.
- Segundo `/speckit-analyze` (2026-10-02): 0 críticos, 1 alto (G1, atividade
  por laboratório sem desbloqueio após reabertura de dependência única), 3
  médios (I1 visão do grupo gestor no template de teste, I2 premissa errada
  sobre arquivamento, U1 prazo contado da execução bloqueada) e 7 baixos.
  Todos tratados: FR-011, FR-025, Assumptions, R6, R10, contrato, quickstart
  e quatro testes novos no `tasks.md` (173 tarefas).

## Validação da implementação (2026-10-02)

- Jornada de aceite (quickstart, passos 0 a 8):
  `tests/integration/journeys/etapa_3_execucao_validacao/test_per_laboratory_journey.py`.
- Suíte completa verde (1539 passed, 1 skipped), medida na branch da Spec 037.
  A `develop` saiu do merge desta spec com duas heads de migração (esta e a
  de notificações, #67); a revisão `5af69c71be3c` as une.
- A Spec 037 trocou o erro de "laboratório A conclui a execução de B" de 403
  para 404 (FR-001 dela); a jornada e `test_laboratory_run_access.py` foram
  ajustados lá.
- README: seção "Execução por Laboratório".
