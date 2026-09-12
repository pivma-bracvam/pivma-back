# Implementation Plan: 021 - Atualização de Instância de Submissão

**Branch**: `021-update-process-submission` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/021-update-process-submission/spec.md`

## Summary

Disponibilizar `PUT` e `PATCH` para atualizar, em uma única transação, o
título da instância e os valores não-arquivo do formulário de submissão da
execução atual. A edição só ocorre enquanto esta execução for rascunho; o
envio formal a congela. Quando a triagem devolve a proposta, a `ActivityRun`
já aberta pelo fluxo é a próxima versão editável. O histórico será derivado de
runs submetidas e do dossiê já persistido, acrescentando somente o título ao
snapshot existente — sem tabela, mecanismo ou endpoint de transição paralelo.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2

**Storage**: PostgreSQL; tabelas existentes `process_instances`,
`activity_runs`, `form_instances`, `form_values`, `artifacts` e `audit_events`

**Testing**: pytest (API, unidade e integração) e Ruff

**Target Platform**: API REST Linux/Docker

**Project Type**: serviço web

**Performance Goals**: uma atualização e leituras de histórico usam as
consultas relacionais já indexadas por processo/run; sem processamento assíncrono
ou varredura de catálogo.

**Constraints**: atualização atômica; nenhum campo após submissão formal;
nenhuma alteração de estado/template/participantes; autorização contextual e
cegamento existentes; anexos permanecem no fluxo próprio.

**Scale/Scope**: um router, schemas e serviço de domínio existentes; ajuste
pontual do snapshot de submissão; testes de regressão; uma demo e seed mínimo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Requisitos e classificação**: passa. A spec separa fatos confirmados do
  fluxo existente e a proposta de expor suas runs como versões.
- **Rastreabilidade**: passa. O snapshot ocorre no envio formal; edição de
  rascunho cria somente evento de auditoria, não versões por salvamento.
- **Segurança e cegamento**: passa. Escrita e histórico reutilizam autorização
  efetiva e `process_visibility_clause`; recurso fora do escopo retorna 404.
- **Mudança pequena e verificável**: passa. Não há tabela de versões, nova
  permissão, reabertura de processo encerrado, diff/merge ou alteração de
  workflow.
- **Demonstração**: passa no desenho. A implementação adicionará uma página
  desacoplada em `demos/`, indexada e exercitando a API real, com massa mínima
  em `scripts/seeds/`.

## Project Structure

### Documentation (this feature)

```text
specs/021-update-process-submission/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code Impacted

```text
src/pivma/
├── schemas.py                    # payloads e respostas de atualização/histórico
├── routers/
│   └── processes.py              # PUT/PATCH e leitura de versões
└── core/
    └── process_engine.py         # serviço transacional, snapshot e guarda de anexo

tests/
├── api/routers/
│   ├── test_process_submission_update.py  # novo contrato e segurança
│   ├── test_form_submission.py             # snapshot no envio
│   └── test_form_attachments.py            # retenção do anexo histórico
└── unit/core/
    └── test_process_engine.py              # runs devolvidas e invariantes

demos/
├── index.html                    # catálogo
└── submission-update/index.html  # página descartável, conectada à API

scripts/seeds/
└── seed_submission_update.py     # usuário/processo rascunho mínimo da demo
```

**Structure Decision**: manter a fronteira atual: router fino, schemas em
`schemas.py` e regra transacional no motor de processo. A versão é uma leitura
das entidades existentes; portanto não haverá módulo, repositório ou tabela
nova.

## Design Summary

1. `PUT /processes/{id}` recebe `title` e o mapa completo `values`; `PATCH`
   recebe ao menos um dos dois. Ambos rejeitam atributos extras e valores de
   campos de arquivo.
2. O serviço localiza exclusivamente `proposal_submission` na maior
   `run_number`, valida tudo antes de escrever e verifica que o formulário não
   foi submetido. Só então atualiza `ProcessInstance.title` e `FormValue`,
   atualiza auditoria e grava um único `AuditEvent` sem valores sensíveis.
3. O envio formal acrescenta o título ao `Artifact` dossiê já criado. Assim,
   run submetida + dossiê é o snapshot imutável de título, valores, anexos e
   data; `REVISION_REQUESTED` já contém a justificativa e a run seguinte.
4. `GET /processes/{id}/submission-versions` e
   `GET /processes/{id}/submission-versions/{run_number}` apenas consultam
   snapshots devolvidos. A leitura padrão do formulário atual permanece a
   visão vigente. Não existe escrita sobre versão nem rota para reabrir um
   processo encerrado.
5. Ao trocar/remover anexo em um rascunho reaberto, a remoção física/lógica do
   artefato só é permitida se ele não estiver referenciado por `FormValue` de
   formulário submetido; isso impede quebrar o snapshot anterior sem duplicar
   arquivos.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Nenhuma violação ou complexidade adicional a justificar.
