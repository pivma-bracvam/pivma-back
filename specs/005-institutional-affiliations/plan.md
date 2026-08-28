# Implementation Plan: Vinculação Institucional

**Branch**: `develop` | **Date**: 2026-08-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-institutional-affiliations/spec.md`

## Summary

Implementar RF003 com a menor extensão compatível com o backend atual: catálogos de instituições e laboratórios, múltiplos vínculos institucionais por usuário, inativação lógica, histórico consultável, três permissões independentes e consulta dos próprios vínculos ativos. A persistência acrescenta quatro tabelas relacionais e uma migração Alembic; a API acrescenta um único router institucional e reutiliza autenticação, autorização, auditoria, transações e infraestrutura de testes existentes.

## Classificação das decisões

- **CONFIRMADO:** stack, estrutura dos módulos, `AuditMixin`, autenticação por cookie, proteção de origem, RBAC persistido, migração atual e infraestrutura de testes foram verificados no código, nas configurações, nas migrações e nos testes de `develop`.
- **DECISÃO da especificação:** um laboratório pertence a uma instituição; o usuário pode ter vários vínculos ativos; todos os vínculos ativos formam o escopo; as três permissões institucionais são globais e independentes; a autoconsulta não exige permissão adicional.
- **DECISÃO TÉCNICA REGISTRADA, aprovada para a feature 005 em 2026-08-24:** a implementação usa quatro tabelas, oito caminhos HTTP, nomes ativos únicos, instituição imutável no laboratório, ausência de atualização direta do vínculo e estado efetivo calculado sem inativação em cascata.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg e Alembic

**Storage**: PostgreSQL 17 com pgvector

**Testing**: Pytest, TestClient, pytest-asyncio, Factory Boy e Testcontainers

**Target Platform**: Serviço web executado em Linux e contêineres locais

**Project Type**: API web em projeto Python único

**Performance Goals**: Não há meta numérica aprovada; consultas devem usar índices para nomes ativos, vínculos ativos, escopo institucional e histórico paginado

**Constraints**: Preservar `AuditMixin`, exclusão lógica, autorização no backend, atomicidade entre alteração e histórico, isolamento por vínculos ativos e contratos existentes

**Scale/Scope**: Quatro tabelas, três permissões, um router, oito caminhos HTTP e quinze operações; sem RF005, RF006, refresh token, 2FA ou mensageria

## Constitution Check

*GATE: aprovado antes da pesquisa e revisto após o desenho.*

- **CONFIRMADO:** a constituição 1.0.0 exige escopo verificável, testes proporcionais, segurança no backend, rastreabilidade e documentação das decisões.
- O plano preserva o padrão atual de FastAPI, SQLAlchemy assíncrono, Alembic e `AuditMixin`, sem dependências ou camadas novas.
- Autenticação e autorização permanecem no backend. Operações mutáveis reutilizam proteção de origem confiável.
- A cobertura proposta separa validação de schemas, persistência, API, segurança, concorrência e migração conforme o risco.
- Restrições de unicidade e integridade ficam no banco, evitando depender somente de validações da aplicação.
- O contrato limita paginação ao histórico e não estabelece metas de desempenho que não constam nas fontes.
- README e artefatos do Spec Kit serão mantidos como documentação operacional e de decisão.
- Não há violação constitucional que exija justificativa de complexidade.

## Project Structure

### Documentation (this feature)

```text
specs/005-institutional-affiliations/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── institutional.openapi.yaml
└── tasks.md                         # Criado somente por $speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                     # Registrar o router institucional
├── dependencies.py                 # Reutilizar autenticação e proteção de origem
├── schemas.py                      # Adicionar schemas institucionais
├── core/
│   ├── authorization.py            # Permissões e consulta de escopo ativo
│   └── database/
│       └── models.py               # Quatro modelos institucionais
└── routers/
    └── institutional.py            # Catálogos, vínculos próprios, gestão e histórico

migrations/versions/
└── 5e31a8c7d204_institutional_affiliations.py

tests/
├── factories/
│   ├── __init__.py
│   └── institutional_factory.py
├── unit/schemas/
│   └── test_institutional_schemas.py
├── integration/
│   ├── database/
│   │   ├── test_institutional_constraints.py
│   │   └── test_institutional_scope.py
│   └── migrations/
│       └── test_institutional_migration.py
└── api/routers/
    ├── test_institutional_concurrency.py
    ├── test_institutional_router.py
    └── test_institutional_security.py

README.md                            # Documentar os novos endpoints e permissões
```

**Structure Decision**: manter a estrutura atual de projeto único. O router coordena as operações transacionais, os modelos representam persistência, os schemas definem contratos e `core/authorization.py` concentra consultas reutilizáveis de autorização e escopo. Não será criada camada de serviço, repositório ou política genérica porque a feature não demonstra essa necessidade.

## Phase 0: Research

As decisões e alternativas estão registradas em [research.md](research.md). A pesquisa resolve persistência, cardinalidade, inativação efetiva, permissões, contratos HTTP, transações, migração e estratégia de testes sem deixar marcador de esclarecimento.

## Phase 1: Design and Contracts

- [data-model.md](data-model.md) define entidades, constraints, índices, estados e transições.
- [contracts/institutional.openapi.yaml](contracts/institutional.openapi.yaml) define os oito caminhos e quinze operações HTTP.
- [quickstart.md](quickstart.md) registra a sequência mínima de implementação e verificação.

## Constitution Check After Design

*GATE: aprovado.*

- O desenho continua limitado a quatro tabelas, um router e extensões nos módulos existentes.
- Todas as mutações geram histórico na mesma transação e mantêm os campos de auditoria.
- O banco garante que o laboratório pertença à instituição informada e impede duplicidades ativas, inclusive sob concorrência.
- A consulta própria não aceita identificador de usuário fornecido pelo cliente; deriva a identidade da autenticação.
- A consulta global, a gestão de catálogos e a gestão de vínculos usam permissões separadas.
- O histórico e as linhas inativas são preservados sem exclusão física ou reativação implícita.
- Não foram incluídos recursos excluídos pela especificação.

## Complexity Tracking

Não há violações ou exceções a registrar.
