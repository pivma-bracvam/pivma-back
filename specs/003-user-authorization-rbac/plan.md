# Implementation Plan: Autorização de Usuários e RBAC

**Branch**: `feat/rbac-authorization` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Especificação da feature 003 e instrução para entregar somente RBAC global, sem antecipar autorização por instituição, laboratório ou participação em processo.

## Summary

Implementar RBAC global com nove perfis oficiais, perfis adicionais, três permissões administrativas e atribuição cumulativa de perfis a contas. O backend consultará as permissões atuais em cada pedido protegido, antes de buscar o recurso solicitado. A entrega acrescenta persistência normalizada, operações administrativas sob `/rbac`, uma trilha restrita às mudanças concluídas e um comando explícito para atribuir o primeiro Administrador. A solução reutiliza autenticação, banco e testes existentes, sem dependências novas.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg 3, Alembic 1.19 e PyJWT 2.13, todos existentes

**Storage**: PostgreSQL/pgvector existente; cinco tabelas novas para perfis, permissões, composição, atribuições e mudanças de RBAC

**Testing**: Pytest, TestClient, Testcontainers, pytest-asyncio e Factory Boy existentes

**Target Platform**: Serviço HTTP Python em servidor Linux; PostgreSQL 17 no ambiente local e de testes

**Project Type**: Serviço web de API

**Performance Goals**: A especificação não define carga numérica. Cada verificação de permissão usará uma consulta indexada e limitada por existência; listagens não executarão consultas por item.

**Constraints**: Mudanças de acesso valem no pedido seguinte; sem cache de permissões ou perfis no JWT; mutações exigem origem confiável; registros de domínio usam `AuditMixin` e exclusão lógica; somente recusas 403 após a verificação de permissão geram registro operacional; sem hard delete.

**Scale/Scope**: Nove perfis oficiais, três permissões iniciais, cinco tabelas, seis caminhos HTTP com nove operações e um comando de bootstrap; somente a lista de mudanças exige paginação nesta feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pré-pesquisa: APROVADO.**

- **Requisitos e evidência**: o plano atende ao RF002 e à dimensão global de perfil do RF004. A `spec.md` classifica decisões, inferências e limites.
- **Rastreabilidade**: perfis e relações preservam o padrão `AuditMixin`. Uma tabela estreita registra tipo, alvo, responsável e momento de cada mudança concluída, sem criar auditoria geral.
- **Segurança**: o backend autentica, valida origem nas mutações e verifica permissão antes de consultar o alvo. Uma resposta proibida não confirma a existência do recurso.
- **Isolamento e cegamento**: a entrega não concede acesso contextual. Instituição, laboratório, processo, conflito de interesse e revelação continuam bloqueados até especificações próprias.
- **Mudança mínima**: o desenho usa as camadas existentes, não adiciona biblioteca, cache, hierarquia, negação explícita, repository ou mecanismo genérico de policies.
- **Testes proporcionais**: autorização e preservação do último administrador recebem testes de unidade, API, persistência, migração, segurança e concorrência conforme o risco.

**Pós-design: APROVADO.** `research.md`, `data-model.md`, `contracts/` e `quickstart.md` mantêm os mesmos limites. Cada tabela corresponde a uma entidade ou obrigação de rastreabilidade da especificação. As interfaces não administram contas nem criam permissões livres.

## Project Structure

### Documentation (this feature)

```text
specs/003-user-authorization-rbac/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── rbac.openapi.yaml
│   └── bootstrap.md
└── tasks.md             # criado somente por $speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                       # registra o router e amplia os métodos CORS necessários
├── bootstrap_rbac.py                 # comando transacional para o primeiro Administrador
├── dependencies.py                   # identidade, origem confiável e permissão exigida
├── schemas.py                        # entradas e respostas de RBAC
├── core/
│   ├── authorization.py              # catálogo, consulta efetiva e guarda do Administrador
│   └── database/models.py             # cinco modelos RBAC com AuditMixin
└── routers/
    ├── auth.py                       # reutiliza as dependências extraídas sem mudar contratos
    └── rbac.py                       # operações administrativas e transações de RBAC

migrations/versions/
└── <revision>_user_authorization_rbac.py

tests/
├── conftest.py                       # somente fixtures RBAC reutilizadas em mais de um módulo
├── factories/
│   └── rbac_factory.py                # perfis e atribuições com FKs persistidas
├── unit/core/
│   └── test_authorization.py          # decisão de permissão e ramos críticos
├── unit/schemas/
│   └── test_rbac_schemas.py            # validações próprias dos schemas RBAC
├── integration/
│   ├── database/test_rbac_constraints.py
│   ├── migrations/test_rbac_migration.py
│   └── test_rbac_bootstrap.py
└── api/routers/
    ├── test_rbac_router.py            # jornadas e contratos administrativos
    ├── test_rbac_security.py          # 401, 403, origem, separação e não vazamento
    └── test_rbac_concurrency.py       # nomes, atribuições e último administrador

README.md                              # documenta operações RBAC e bootstrap
```

**Structure Decision**: A aplicação já concentra modelos, schemas e routers. `dependencies.py` recebe dependências HTTP compartilhadas para evitar importação entre routers. `core/authorization.py` concentra somente consultas e invariantes de acesso usadas por mais de uma operação. O plano não cria camadas de service ou repository.

## Complexity Tracking

Nenhuma violação constitucional exige justificativa.
