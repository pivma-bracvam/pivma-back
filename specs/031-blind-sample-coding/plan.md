# Implementation Plan: Definição e Preparação das Amostras — estudo cego

**Branch**: `feat/031-blind-sample-coding` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/031-blind-sample-coding/spec.md`

## Summary

Uma atividade nova, `sample_definition`, entra na Fase 2 dos cinco
templates. Os templates 01, 02, 03 e 05 ganham a Fase 2 completa do
template 04. A atividade abre pelo motor genérico quando as atribuições do
Grupo de Seleção de Amostras e dos laboratórios participantes fecham.

O Grupo de Seleção cadastra substâncias (CAS único no processo, com dígito
verificador) e anexa a SDS em PDF. Cada cadastro gera um código opaco de 8
caracteres por laboratório participante. A conclusão completa as combinações
que faltam, descarta laboratórios que saíram e congela o conjunto. O backend
entrega os dados de etiqueta com QR code em SVG e uma rota de visão cega do
frasco.

Todo o conteúdo exige a concessão de **edição** da atividade. Isso deixa
admin e BraCVAM vendo só a atividade e seu status, e bloqueia laboratórios
e Grupo Gestor, sem regra de autorização nova (research R3).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Alembic,
Pydantic v2; nova: `segno` (QR code em SVG, Python puro)

**Storage**: PostgreSQL 17; tabelas novas `study_substances` e
`blind_sample_codes` com índices únicos parciais; SDS em `artifacts` +
disco (`ATTACHMENTS_DIR`)

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy,
`TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: listagem e etiquetas de um processo em uma consulta
por tabela (sem N+1); escala esperada de dezenas de substâncias × dezenas de
laboratórios por processo

**Constraints**: nenhuma resposta, QR code ou evento de auditoria pode
associar código cego a nome químico ou CAS fora do Grupo de Seleção;
migração com upgrade e downgrade testados; processos existentes intactos

**Scale/Scope**: 5 YAMLs de template, 1 serviço novo, 1 roteador novo, 2
modelos, 1 migração, 1 setting, cerca de 5 arquivos de teste novos e 1 teste
existente ajustado

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template sem preencher. Os gates
são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ RF038 e RF050 do Plano de Trabalho; protótipo seção 5 (`CONFIRMADO NO MATERIAL`); issue #24 |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ 7 decisões em Clarifications; nenhum marcador aberto |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ conteúdo sob concessão de edição (R3); auditoria só com ids (R9); invariante da Spec 030 (admin/BraCVAM veem toda atividade) mantido |
| Mudança cirúrgica, sem abstração preventiva | ✅ motor de atividades sem alteração (R1); congelamento = status da atividade (R10); SDS em `Artifact` (R7); Fase 2 copiada em vez de mecanismo de inclusão (R2) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ tarefa final do `tasks.md` |

**Re-check pós-design**: sem violações. Pontos de atenção:

- Dependência nova (`segno`), justificada em R8.
- O caminho de frontend gravado no QR (`/amostras/{process_id}/frascos/{code}`)
  precisa ser combinado com o frontend (R8).
- A Fase 2 duplicada em cinco YAMLs pode divergir; um teste de estrutura
  compara as oito atividades entre os templates.

## Project Structure

### Documentation (this feature)

```text
specs/031-blind-sample-coding/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # R1–R10
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
├── core/
│   ├── sample_service.py          # novo: CAS, geração de código, laboratórios ativos, cadastro, conclusão, etiquetas, visão cega (R3–R10)
│   ├── settings.py                # SAMPLE_QR_BASE_URL (R8)
│   └── database/models.py         # StudySubstance, BlindSampleCode
├── routers/
│   └── samples.py                 # novo: /processes/{id}/samples/... (contrato)
├── schemas.py                     # SampleSubstance*, SampleLabel, BlindVial, SampleCompletion*
├── __init__.py                    # include_router(samples.router)
└── templates_data/0[1-5]_*.yaml   # Fase 2 em todos + sample_definition (R1, R2)

migrations/versions/<rev>_blind_sample_coding.py   # down_revision 7e21b4c0a9d3

pyproject.toml / poetry.lock       # segno

tests/
├── factories/sample_factory.py                     # substância e código
├── unit/core/test_sample_service.py                # CAS, alfabeto/formato do código, colisão
├── api/routers/test_samples_router.py              # cadastro, edição, remoção, SDS, conclusão, etiquetas, vial
├── api/routers/test_samples_access.py              # matriz de acesso por perfil, isolamento entre processos
├── api/routers/test_activity_type_extension.py     # ajuste: templates legados agora têm Fase 2
├── integration/bootstrap/test_template_phase_2.py  # Fase 2 idêntica nos 5 templates; versões antigas preservadas
├── integration/journeys/test_sample_definition_journey.py  # 4 substâncias × 3 laboratórios → 12 códigos
└── integration/migrations/test_blind_sample_migration.py   # upgrade/downgrade
```

**Structure Decision**: estrutura existente de projeto único. O serviço
segue o padrão de `return_review_service.py` (erros de domínio de
`process_engine`, sem `HTTPException`) e o roteador segue
`routers/return_review.py` e `routers/forms.py` (tradução de erros, anexos).

## Ordem de implementação sugerida

1. **Templates** (US6): Fase 2 nos templates 01, 02, 03 e 05, `sample_definition`
   nos cinco, versões novas. Ajuste do teste legado e teste de estrutura.
2. **Modelos e migração**: `StudySubstance`, `BlindSampleCode`, índices,
   migração com upgrade e downgrade.
3. **Serviço puro** (US1): validação de CAS e gerador de código, com testes
   unitários.
4. **Cadastro e códigos** (US1): criar, alterar, remover, listar; geração por
   laboratório ativo; trava na atividade; auditoria.
5. **SDS** (US1/US2): upload e download reaproveitando `attachment_service`.
6. **Conclusão** (US2): validações, combinações faltantes, descarte,
   congelamento.
7. **Isolamento** (US5): matriz de acesso completa em todas as rotas.
8. **Etiquetas e visão cega** (US3, US4): `segno`, setting, rotas.
9. Jornada 4 × 3, README.

## Complexity Tracking

Sem violações a justificar.
