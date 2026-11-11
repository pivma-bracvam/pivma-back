# Implementation Plan: Retorno ao Proponente

**Branch**: `feat/046-proponent-return` | **Date**: 2026-11-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/046-proponent-return/spec.md`

## Summary

Uma função em `process_engine.py` lê os pareceres de uma execução da submissão
e atende às duas consultas: `previous_reviews` no formulário e `reviews` na
versão devolvida. `open_return_review`, ponto único das três devoluções, pede
o e-mail na mesma transação. `cancel_open_return_review` cancela o envio
pendente e grava o evento do cancelamento, com o administrador como autor. A
exclusão do processo também cancela o envio pendente.

Os testes de concorrência vão provar as travas. A leitura do código já achou
uma lacuna no reprocessamento: `retry_run` não trava nada, aceita `in_progress`
e pode criar duas execuções. A correção entra aqui, com teste vermelho antes
(FR-016a, [research R5](research.md#r5-reprocessamento-da-ia)).

A entrega não cria tabela, migração nem rota.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2, base de notificações da Spec 036

**Storage**: PostgreSQL 17, sem mudança de esquema

**Testing**: Pytest, Testcontainers, canal `FakeEmailChannel`, provedor de IA fake

**Target Platform**: serviço Linux em contêiner

**Project Type**: web service

**Performance Goals**: uma consulta a mais em `GET .../form` da submissão e em `GET .../submission-versions/{run_number}`; a listagem de versões não muda

**Constraints**: campos só aditivos; envio na mesma transação da devolução; a devolução não depende do canal de e-mail

**Scale/Scope**: 56 campos no maior formulário; até dezenas de rodadas por processo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Antes | Depois do desenho |
|---|---|---|
| I. Requisitos e evidência | PASS: spec classificada; decisões em `docs/observacoes-e-pendencias.md` | PASS: FR-016a aprovado pelo usuário em 2026-11-06 |
| II. Rastreabilidade e auditoria | PASS: sem modelo novo; o worker grava os eventos de envio | PASS: `subject` liga o envio à execução do retorno; `RETURN_REVIEW_CANCELLED` registra o administrador, que a rota hoje descarta ([R5](research.md#r5-reprocessamento-da-ia)) |
| III. Segurança, autorização e sigilo | PASS: as rotas mantêm as checagens; `FieldReviewSummary` não tem autor | PASS: o payload do e-mail não leva justificativa, pareceres nem avaliador |
| IV. IA como apoio, decisão humana | PASS: a contestação segue disponível | PASS: o reprocessamento fica restrito ao retorno da IA, sem afetar a contestação nem o retorno da triagem |
| V. Testes orientados a jornadas | PASS: uma jornada por história, com testes focados | PASS: [quickstart](quickstart.md) lista as jornadas e as corridas |
| VI. Simples e cirúrgico | PASS: uma função de leitura e um renderizador; contratos aprovados na spec | PASS: `Settings()` em um ponto evita mudar oito chamadas ([R3](research.md#r3-onde-pedir-o-e-mail)) |
| VII. Documentação do estado atual | PASS: FR-018 lista as páginas | PASS: páginas do retry incluídas na estrutura abaixo |

Sem exceções.

## Project Structure

### Documentation (this feature)

```text
specs/046-proponent-return/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── submission-reviews.md
│   ├── submission-returned-email.md
│   └── pre-evaluation-retry.md
└── tasks.md             # gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── schemas.py                        # previous_reviews e reviews
├── routers/forms.py                  # previous_reviews na leitura do formulário
├── routers/pre_evaluation.py         # passa o administrador ao reprocessamento
├── notifications/renderers.py        # submission_returned_email
└── core/
    ├── process_engine.py             # submission_run_reviews, e-mail, cancelamento com trava e evento
    ├── pre_evaluation_service.py     # retry_run; remove o TODO
    └── return_review_service.py      # remove o TODO

tests/
├── conftest.py                       # return_email_settings, no_email_channel
├── factories/return_review_factory.py
├── unit/notifications/test_submission_returned_email_renderer.py
├── api/routers/test_return_review.py
├── api/routers/test_process_submission_update.py
├── integration/notifications/test_submission_returned_email.py
├── integration/database/test_return_review_concurrency.py
├── integration/database/test_pre_evaluation_concurrency.py
└── integration/journeys/etapa_1_submissao_triagem/
    ├── test_return_review_feedback.py
    ├── test_return_review_email.py
    └── test_return_review_conflicts.py

manual/
├── guias/responder-ao-retorno.md
├── guias/enviar-uma-proposta.md
├── guias/conduzir-a-triagem.md
├── tutorial/triagem-pede-ajustes.md
├── explicacao/notificacoes.md
├── explicacao/pre-avaliacao-ia.md
├── explicacao/escopo.md
└── referencia/                       # eventos.md, e rotas e erros onde mudarem
```

**Structure Decision**: serviço único, nas pastas atuais. Nenhum módulo novo em
`src/`.
