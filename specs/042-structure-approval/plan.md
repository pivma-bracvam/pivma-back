# Implementation Plan: Homologação da estrutura do estudo

**Branch**: `feat/042-structure-approval` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/042-structure-approval/spec.md`

## Summary

Põe um portão do BraCVAM entre a Etapa 2 e a Etapa 3 (issue #27):

- Os cinco templates ganham a atividade `structure_approval` no fim da fase
  2. Ela depende das dez atividades da etapa, e o recebimento de amostras
  passa a depender dela (research R1).
- Um painel lista os pontos (as dependências da homologação), as
  designações, as contagens das amostras, as pendências calculadas na hora e
  o histórico de decisões (R2, R3).
- O BraCVAM aprova, com justificativa, e a Etapa 3 abre. Ou reprova pontos
  com motivo, e cada ponto ganha uma execução nova (R4, R6).
- A decisão fica em `decisions`, com os pontos numa coluna JSONB nova (R5).
- A atribuição de cargo reaberta conclui só quando quem gere o cargo
  declara que terminou (R8, R14). O template de coleta trava pelo início da
  Etapa 3 (R9).
- O plano estatístico é uma atividade de formulário da Etapa 2 e um ponto da
  homologação. O envio de formulário só aciona dossiê, IA e triagem na
  proposta (R13). Revisão do PR #76, 2026-10-16.

O desenho reaproveita o motor de dependências, `_activate_activity`,
`_complete_activity_run` e o padrão de decisão da triagem. Não cria
permissão, tabela nem mecanismo de liberação novos.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2,
Alembic. Nenhuma dependência nova.

**Storage**: PostgreSQL 17. Uma coluna nova (`decisions.rejected_points`,
JSONB anulável).

**Testing**: pytest, pytest-asyncio, Testcontainers, factory-boy. As três
jornadas da homologação partem de `bootstrap_fresh_deploy` e usam cadastro,
logout/login, RBAC e cadastro institucional públicos. Factories ficam nos
testes focados. Um teste focado prova que convite adicional após a
conclusão não reabre o cargo nem impede a aprovação (FR-008, T059).

**Target Platform**: servidor Linux (Docker)

**Project Type**: web-service (backend)

**Performance Goals**: painel com dez pontos e poucas dezenas de
designações; consultas por processo, sem paginação

**Constraints**: uma decisão por execução da homologação, mesmo com envios
simultâneos (FR-018); nada do cegamento no painel (FR-006); erros no formato
da Spec 034; processos das versões anteriores do template sem mudança de
fluxo (FR-003)

**Scale/Scope**: 2 rotas novas; 2 rotas de revogação com efeito ajustado;
5 YAML; 1 migração

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
| --- | --- |
| I. Requisitos e evidência | PASS. Fontes: issue #27 e RF024, RF026, RF027 e RF034. As quatro lacunas (plano estatístico, pontos obrigatórios, trava do template, fechamento da reexecução) foram perguntadas ao usuário e estão em Clarifications e em `docs/observacoes-e-pendencias.md`. O protótipo não é usado. |
| II. Rastreabilidade e auditoria | PASS. Nenhum modelo novo; `decisions` já usa `AuditMixin`. A decisão guarda autor, data, justificativa e pontos, sem rota de alteração. A linha do tempo grava `STRUCTURE_APPROVED`, `STRUCTURE_REJECTED` e `ACTIVITY_REOPENED`. Execuções anteriores não mudam. |
| III. Segurança, autorização e sigilo | PASS. A autorização sai da concessão da atividade, consultada no banco a cada requisição (R7): 404 para quem não vê, 403 para quem vê sem editar ou tem conflito de interesse. A decisão exige `CurrentUser` e `TrustedOrigin`. O painel mostra só contagens das amostras. Os erros não repetem valores enviados. |
| IV. IA como apoio | N/A. Sem IA. |
| V. Testes orientados a jornadas | PASS. Jornada por história no `tasks.md`; a da User Story 2 é o critério de conclusão da issue. Testes focados para cada pendência, cada erro, autorização, conflito de interesse, concorrência, cegamento do painel, fechamento na revogação, trava do template e migração. |
| VI. Mudanças simples e cirúrgicas | PASS. Reaproveita o motor (R1, R4, R6). A condição nova no fechamento da atribuição (R8) também corrige o caso em que revogar o único convite fechava o cargo vazio; ganha teste de regressão. A trava na liberação por dependências (R12) corrige uma corrida que a reprovação tornaria comum; fica num ponto só do motor e ganha teste de concorrência. Contratos novos aprovados nesta spec; o único contrato existente alterado é o momento da trava do template, decidido pelo usuário. |
| VII. Documentação do estado atual | PASS. Tutorial novo e páginas de referência no mesmo PR, com `poe docs-build`. Decisões em `docs/observacoes-e-pendencias.md`. |

Reavaliação após o desenho (Phase 1): PASS em todos os princípios. O
desenho não acrescentou tabela, permissão nem abstração.

## Project Structure

### Documentation (this feature)

```text
specs/042-structure-approval/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── templates_data/0[1-5]_*.yaml          # versão seguinte: structure_approval e dependência do recebimento
├── templates_data/README.md              # fase 2 e fase 3
├── core/
│   ├── structure_approval_service.py     # novo: painel, pendências e decisão
│   ├── process_engine.py                 # fechamento exige designação ativa (R8); liberação sob trava (R12)
│   ├── collection_template_service.py    # trava pela fase 3 iniciada
│   └── database/models.py                # Decision.rejected_points
├── routers/
│   ├── structure_approval.py             # novo: GET painel, POST decisão
│   └── process_participants.py           # revogação de designação chama o fechamento
├── schemas.py                            # schemas do painel e da decisão
└── __init__.py                           # registra o router

migrations/versions/<rev>_decision_rejected_points.py

tests/
├── integration/journeys/
│   ├── sample_steps.py                                   # equipe completa e aprovação
│   ├── etapa_2_planejamento_preparacao/test_structure_approval_journey.py   # novo
│   ├── etapa_2_planejamento_preparacao/test_collection_template_journey.py  # passa pela homologação
│   └── etapa_3_execucao_validacao/test_sample_receipt_journey.py            # passa pela homologação
├── api/routers/test_structure_approval_*.py               # novos: focados
├── integration/bootstrap/test_template_phase_2.py, test_template_phase_3.py
├── integration/migrations/test_decision_rejected_points_migration.py      # novo
└── factories/sample_receipt_factory.py, structure_approval_factory.py     # ajuste e nova

manual/
├── tutorial/homologacao-da-estrutura.md  # novo
├── tutorial/index.md, tutorial/recebimento-com-avaria.md, tutorial/equipe-e-amostras.md
├── referencia/{rotas,estados,eventos,erros,templates,templates-yaml}.md
├── explicacao/{escopo,modelo-de-processo}.md
└── guias/{designar-participantes,montar-template-de-coleta}.md

mkdocs.yml                                # nav do tutorial novo
```

**Structure Decision**: o serviço novo fica em `core/` ao lado de
`sample_service.py` e `sample_receipt_service.py`, que seguem o mesmo padrão
(serviço de domínio que importa funções do motor). O router novo segue
`routers/sample_receipt.py`. `process_engine.py` já tem 3.785 linhas; o
código da homologação não entra nele.

## Complexity Tracking

Sem violações a justificar.
