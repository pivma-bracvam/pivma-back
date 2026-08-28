# Implementation Plan: Designações e Conflito de Interesse

**Branch**: `feat/process-participant-designations` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-process-participant-designations/spec.md`

## Summary

Implementar RF005, RF006 e a parcela de RF034 vinculada aos participantes com a menor extensão do backend atual. A solução evolui `Assignment` com contexto laboratorial, cria um histórico imutável de declarações, acrescenta uma capacidade global de gestão ao RBAC e expõe cinco operações sob o processo. A autorização combina a capacidade global, o papel local `group_manager`, vínculos institucionais vigentes e o conflito do participante. As revisões e decisões de triagem existentes recebem a guarda de conflito; a timeline filtra os novos eventos conforme o escopo do usuário.

## Classificação das decisões

- **CONFIRMADO:** `ProcessInstance`, `Assignment`, `Task`, `AuditEvent`, `UserInstitutionalAffiliation`, autenticação por cookie, RBAC persistido, proteção de origem e testes com PostgreSQL descartável existem no código atual.
- **DECISÃO DA ESPECIFICAÇÃO:** a feature usa oito papéis locais; papéis laboratoriais exigem usuário responsável e vínculo vigente; qualquer conflito vigente do usuário bloqueia tarefas avaliativas ou decisórias no processo.
- **DIVERGÊNCIA REGISTRADA:** RF005 cita especialistas, mas o catálogo aprovado para a feature 006 não inclui `specialist`. O plano não acrescenta esse papel.
- **DECISÃO TÉCNICA DESTE PLANO:** a implementação acrescenta uma coluna em `assignments`, uma tabela de declarações, uma permissão, um router e funções contextuais nos módulos existentes. Não cria repository, service genérico, mensageria ou nova abstração de workflow.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg e Alembic

**Storage**: PostgreSQL 17 com pgvector

**Testing**: Pytest, TestClient, pytest-asyncio, Factory Boy e Testcontainers

**Target Platform**: Serviço web executado em Linux e contêineres locais

**Project Type**: API web em projeto Python único

**Performance Goals**: Pelo menos 19 de 20 requisições medidas de participantes e histórico em um processo com 200 ciclos devem terminar em até 2 segundos; preparação da massa e uma chamada de aquecimento ficam fora da medição

**Constraints**: Preservar `AuditMixin`, contratos das features 001 a 005, tarefas legadas em maiúsculas, atomicidade entre mudança e `AuditEvent`, autorização no backend, histórico imutável e justificativas restritas; considerar `ProcessInstance` ativo quando `deleted_at` for nulo sem reinterpretar `status` ou `closed_at`

**Scale/Scope**: Oito papéis locais, uma nova permissão, uma nova tabela, uma coluna em `assignments`, quatro caminhos HTTP novos com cinco operações e filtragem dos três novos tipos de evento na timeline existente

## Constitution Check

*GATE: aprovado antes da pesquisa e revisto após o desenho.*

- A implementação mantém vínculo entre RF005, RF006, RF034, requisitos da spec, contratos, testes e arquivos alterados.
- O backend consulta permissão global, designação local, usuário, laboratório, vínculo institucional e conflito no pedido atual.
- Designações, inclusive a criação automática do proponente, revogação e declaração gravam o evento auditável na mesma transação da mudança.
- A declaração e os eventos não possuem operação de alteração ou exclusão.
- A timeline não expõe eventos de participantes fora do escopo do usuário nem justificativas de terceiros.
- A migração preserva processos, tarefas, designações e eventos existentes e não cria declarações ou laboratórios implícitos.
- O plano usa uma tabela e um router novos porque declaração e interface possuem ciclos próprios. Não adiciona dependências nem camadas genéricas.
- A matriz de testes segue risco e comportamento. Cada teste cobre um caminho de sucesso, erro, autorização, concorrência, migração ou desempenho.
- Não há violação constitucional que exija exceção de complexidade.

## Project Structure

### Documentation (this feature)

```text
specs/006-process-participant-designations/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── process-participants.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md                              # Criado somente por $speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                          # Registrar o router de participantes
├── schemas.py                           # Contratos de designação, conflito e histórico
├── core/
│   ├── authorization.py                 # Capacidade global, gestão local e conflito atual
│   ├── process_engine.py                # Guardar revisão e decisão de triagem
│   └── database/
│       └── models.py                    # Evoluir Assignment e criar ConflictInterestDeclaration
└── routers/
    ├── process_participants.py           # Cinco operações da feature
    ├── processes.py                      # Filtrar os novos eventos na timeline
    └── triage.py                         # Converter a negação de conflito em 403

migrations/versions/
└── *_process_participant_designations.py

tests/
├── factories/
│   ├── __init__.py
│   └── participant_factory.py
├── unit/
│   └── schemas/
│       └── test_participant_schemas.py
├── integration/
│   ├── database/
│   │   ├── test_participant_authorization.py
│   │   └── test_participant_constraints.py
│   └── migrations/
│       └── test_participant_migration.py
└── api/routers/
    ├── test_participant_router.py
    ├── test_participant_security.py
    ├── test_participant_concurrency.py
    ├── test_participant_task_blocking.py
    ├── test_participant_timeline.py
    └── test_participant_timed_acceptance.py

README.md                                 # Documentar permissão e operações públicas
```

**Structure Decision**: manter o projeto único e os padrões existentes. O novo router coordena consultas e transações; `authorization.py` concentra predicates reutilizáveis; `process_engine.py` aplica a guarda nos fluxos avaliativos existentes. A feature não demonstra necessidade de repository ou service separado.

## Phase 0: Research

As decisões e alternativas estão em [research.md](research.md). A pesquisa resolve compatibilidade de papéis, persistência, vínculo laboratorial, permissão global, gestão local, conflito atual, integração com tarefas, privacidade da timeline, migração e testes. Não restam lacunas abertas.

## Phase 1: Design and Contracts

- [data-model.md](data-model.md) define a evolução de `Assignment`, a declaração imutável, estados derivados, índices, eventos e seed do RBAC.
- [contracts/process-participants.openapi.yaml](contracts/process-participants.openapi.yaml) define as cinco operações e a filtragem dos eventos da feature na timeline.
- [quickstart.md](quickstart.md) registra a ordem de implementação, a matriz granular de testes e os comandos de validação.

## Estratégia e granularidade dos testes

- Autorização contextual e bloqueio de conflito têm risco crítico: cobrir os predicates com PostgreSQL real, os fluxos por integração HTTP e as fronteiras em testes de segurança. Não criar função pura ou camada adicional somente para produzir teste unitário.
- Unicidade ativa, relacionamento laboratorial, seleção da declaração vigente, migração e concorrência dependem de PostgreSQL real.
- Schemas usam testes unitários; casos equivalentes podem usar `pytest.mark.parametrize` sem misturar comportamentos.
- O teste de sucesso da operação não valida também auditoria, segurança ou concorrência. Cada contrato recebe um teste próprio.
- A guarda de conflito lança `AuthorizationError`; as rotas de triagem convertem somente essa exceção em 403. Os testes de bloqueio verificam esse contrato sem misturá-lo com a persistência negada ou com `ConflictError` legado.
- Fixtures e Factory Boy preparam estados recorrentes. SQL direto fica restrito à migração e às constraints que o ORM não representa.
- A preservação de registros no upgrade pode ser parametrizada pelo tipo de registro sob a mesma regra. O downgrade separa remoção da feature, restauração do papel legado e preservação dos dados anteriores.
- O teste de desempenho prepara 200 ciclos antes da medição, executa uma chamada de aquecimento e mede somente as 20 requisições HTTP com relógio monotônico; pelo menos 19 devem concluir em até 2 segundos.
- `$speckit-tasks` deve transformar cada linha da matriz de [quickstart.md](quickstart.md) em uma tarefa de teste independente ou em um teste parametrizado de um único comportamento.

## Constitution Check After Design

*GATE: aprovado.*

- O desenho mantém uma única fonte para o ciclo de designação e deriva processo da FK de declaração para `Assignment`.
- A solução adiciona somente o estado exigido: laboratório opcional na designação e declarações append-only.
- A permissão global pertence ao catálogo RBAC existente; `group_manager` permanece contextual ao processo.
- A autorização laboratorial reusa `UserInstitutionalAffiliation` e não cria vínculo paralelo.
- O bloqueio alcança as revisões e decisões existentes sem criar endpoints genéricos de tarefa ou fluxos futuros.
- A timeline preserva os eventos anteriores e filtra somente os eventos sensíveis introduzidos pela feature.
- O contrato limita histórico a 200 ciclos por pedido, com ordenação determinística.
- A matriz de testes cobre requisitos funcionais, caminhos críticos, branches, erros, segurança, concorrência, migração e regressão conforme o Definition of Done.
- Nenhum item fora do escopo da spec foi incluído.

## Complexity Tracking

Não há violações ou exceções a registrar.
