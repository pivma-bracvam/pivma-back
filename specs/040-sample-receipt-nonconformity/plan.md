# Implementation Plan: Recebimento de amostras, inconformidades e cadastro expandido

**Branch**: `feat/040-sample-receipt-nonconformity` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/040-sample-receipt-nonconformity/spec.md`

## Summary

Amplia o cadastro de substâncias (gabarito, faixa térmica, frasco, reserva,
GHS) com consulta de sugestões ao PubChem; cria a Etapa 3 nos cinco
templates com a confirmação de recebimento por laboratório (registro por
frasco, conclusão automática do lote) e a resolução de inconformidades pelo
Grupo de Seleção (aceitar com ressalva, reenviar com código novo e débito da
reserva, desclassificar pela dispensa da Spec 036), com tarefa, e-mail,
fotos e trilha sem identidade química.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2,
Alembic, `httpx` (já instalado via `httpx2`), `segno`

**Storage**: PostgreSQL 17; anexos em disco (`ATTACHMENTS_DIR`)

**Testing**: pytest, pytest-asyncio, Testcontainers, `httpx.MockTransport`
para o PubChem

**Target Platform**: servidor Linux (Docker)

**Project Type**: web-service (backend)

**Performance Goals**: listas de frascos e inconformidades com poucas dezenas
de itens por processo; consulta externa limitada por `PUBCHEM_TIMEOUT_SECONDS`

**Constraints**: cegamento e isolamento por laboratório (constituição III);
transação única por operação, inclusive o e-mail na fila

**Scale/Scope**: até dezenas de substâncias × dezenas de laboratórios por
processo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
| --- | --- |
| I. Requisitos e evidência | PASS. Fontes: RF040, RF044, RF046, seção 2 do Plano; issues #28, #71, #72; decisões do usuário de 2026-10-04 em Clarifications. Conflitos (código no reenvio, leitura do gabarito, reserva, fotos) perguntados antes. |
| II. Rastreabilidade e auditoria | PASS. Tabelas novas com `AuditMixin`; exclusão lógica do código substituído; eventos em research R12; fotos não são apagadas. |
| III. Segurança, autorização e sigilo | PASS. Checagens no backend por requisição; `404` para frasco/foto de outro laboratório; respostas e eventos do laboratório sem nome, CAS, SDS, gabarito ou justificativa; escrita com `CurrentUser` e `TrustedOrigin`; conflito de interesse bloqueia pela `require_activity_access`. |
| IV. IA como apoio | N/A. Sem IA. A consulta ao PubChem só sugere; o humano confirma (FR-016). |
| V. Testes orientados a jornadas | PASS. Uma jornada por história no `tasks.md`, mais testes focados por risco (isolamento, erros, concorrência, paginação). |
| VI. Mudanças simples e cirúrgicas | PASS. Reuso do motor (dispensa, desbloqueio), anexos e notificações; extrações no motor só onde necessário: `_finish_laboratory_run` (R3) e o conjunto de tipos abertos por evento (R2). Contratos existentes de amostras só ganham campos. |
| VII. Documentação | PASS. Manual atualizado no mesmo PR (rotas, erros, estados, eventos, templates, ambiente, escopo, guia e tutorial). |

Re-check pós-design: PASS, sem exceções. Sem entradas em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/040-sample-receipt-nonconformity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/http-api.md
└── tasks.md
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── database/models.py          # colunas novas, SampleReceipt, SampleReceiptNonconformity
│   ├── process_engine.py           # EVENT_OPENED_ACTIVITY_TYPES; _finish_laboratory_run
│   ├── sample_service.py           # campos novos, faixa térmica, visão cega por laboratório
│   ├── sample_receipt_service.py   # novo: registro, fotos, inconformidades, decisão
│   ├── pubchem.py                  # novo: consulta de sugestões
│   └── settings.py                 # PUBCHEM_BASE_URL, PUBCHEM_TIMEOUT_SECONDS
├── notifications/renderers.py      # sample_receipt_nonconformity_email
├── routers/
│   ├── samples.py                  # lookup; visão cega
│   └── sample_receipt.py           # novo
├── schemas.py
├── templates_data/0[1-5]_*.yaml    # Etapa 3
└── __init__.py                     # registra o router
migrations/versions/<rev>_sample_receipt_nonconformity.py

tests/
├── factories/sample_receipt_factory.py (novo)
├── unit/core/test_sample_temperature.py, test_pubchem_parse.py
├── api/routers/test_samples_router.py, test_sample_lookup.py,
│   test_sample_receipt_router.py, test_sample_receipt_isolation.py,
│   test_sample_nonconformity_router.py, test_sample_receipt_photos.py,
│   test_sample_receipt_concurrency.py
├── integration/bootstrap/test_template_phase_3.py
├── integration/migrations/test_sample_receipt_migration.py
└── integration/journeys/
    ├── etapa_2_planejamento_preparacao/test_sample_registration_journey.py
    └── etapa_3_execucao_validacao/test_sample_receipt_journey.py

manual/
├── referencia/{rotas,erros,estados,eventos,templates,ambiente}.md
├── explicacao/{amostras-cegas,escopo,notificacoes}.md
├── guias/{definir-amostras-cegas,receber-amostras}.md
└── tutorial/recebimento-com-avaria.md
```

**Structure Decision**: backend único existente (`src/pivma`), com um serviço
e um router novos para o recebimento, no padrão de `sample_service`/`samples`.
