# Implementation Plan: Atualização Administrativa de Usuários

**Branch**: `008-admin-user-update` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Adicionar `PATCH /users/{user_id}` ao router existente para que uma pessoa com `users.manage` atualize somente `full_name`. O endpoint reutiliza a sessão, a autenticação por cookie, a dependência de origem confiável, o cálculo de permissões e o padrão `AuditMixin` já adotados. Uma migração posterior a `7b4f5d6e8a90` semeia `users.manage` no perfil oficial Administrador. O cadastro passa a exigir `full_name` para novas contas; a coluna continua anulável para registros antigos e mockados.

## Evidence Classification

- **CONFIRMADO**: o backlog técnico de Gestão de Usuários registra consulta, atualização e inativação administrativas como operações do módulo, deixando rota, campos, atores e auditoria para a spec da feature.
- **DECISÃO EXPLÍCITA DA EQUIPE**: a rota desta entrega é `PATCH /users/{user_id}` e contas antigas/mockadas não precisam ser preenchidas em massa.
- **DECISÃO TÉCNICA REGISTRADA**: `users.manage` é uma permissão distinta de `users.read` e é concedida ao perfil Administrador.
- **INFERÊNCIA CONTROLADA**: `updated_by` e `updated_at` do `AuditMixin` atendem à rastreabilidade desta alteração enquanto não existe uma trilha genérica de mudanças de conta.
- **FORA DE ESCOPO**: display name, edição pelo próprio usuário e atualização em lote.

## Technical Context

**Language/Version**: Python 3.14  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg, Alembic, Pytest, Testcontainers, Factory Boy  
**Storage**: PostgreSQL com pgvector; tabela existente `users`; catálogo RBAC em `permissions` e `access_profile_permissions`  
**Testing**: Pytest com TestClient para contratos HTTP, fixtures SQLAlchemy e testes de migração  
**Target Platform**: API web  
**Project Type**: backend monolítico  
**Performance Goals**: uma atualização por requisição, sem consulta adicional de relações; manter o padrão de uma operação administrativa simples  
**Constraints**: autenticação por cookie JWT; origem confiável em mutações; autorização no backend; `full_name` aparado e limitado a 255 caracteres; coluna anulável para legado; sem alteração de senha ou RBAC; manter o `AuditMixin`  
**Scale/Scope**: uma rota, um schema de entrada, uma permissão, uma revisão de dados e testes focados nos comportamentos observáveis  

## Constitution Check

*GATE: Must pass before implementation. Re-check after design.*

- **I. Requisitos e evidência**: PASS. A rota, o campo, a permissão e a compatibilidade legada estão classificados e rastreados na spec.
- **II. Rastreabilidade e auditoria**: PASS. A atualização chama o padrão de auditoria de `User` e não cria uma trilha paralela sem requisito aprovado.
- **III. Segurança e autorização**: PASS. O endpoint exige sessão, `users.manage` e origem confiável; a listagem continua exigindo apenas `users.read`.
- **IV. Autoridade científica e IA**: PASS. A feature não envolve IA nem decisão científica.
- **V. Mudanças pequenas e verificáveis**: PASS. O escopo contém somente `full_name`, permissão, rota, migração, contratos, documentação e testes correspondentes.

## Project Structure

### Documentation (this feature)

```text
specs/008-admin-user-update/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/users.openapi.yaml
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/pivma/
├── core/authorization.py
├── core/database/models.py
├── routers/users.py
└── schemas.py
migrations/versions/
└── 8c5e7a1b9d02_user_management_permission.py
tests/api/routers/
└── test_user_update.py
tests/integration/migrations/
└── test_user_management_permission_migration.py
```

## Implementation Sequence

1. Testar o contrato de `UserSchema` obrigatório para novos cadastros e criar `UserUpdate`.
2. Testar o PATCH nos caminhos de sucesso, validação, autenticação, permissão, origem e UUID desconhecido.
3. Implementar a constante `USERS_MANAGE`, o schema de atualização e a rota protegida.
4. Criar a migração de `users.manage` e sua composição no Administrador; manter a permissão fora de `ADMINISTRATIVE_PERMISSIONS`.
5. Alinhar contratos OpenAPI, README, quickstart e tarefas.
6. Executar testes focados, suíte completa, lint direcionado e verificações de migração.

## Test Strategy

- **Schema unitário**: `full_name` obrigatório em `UserSchema`; valores inválidos e campos extras retornam erro; `UserUpdate` remove espaços externos.
- **API success**: PATCH de conta legada preenche o nome; PATCH de conta preenchida substitui o nome; resposta pública não expõe credenciais.
- **API security**: ausência de sessão retorna 401; ausência de `users.manage` retorna 403; origem inválida retorna 403; UUID desconhecido retorna 404.
- **API validation**: corpo vazio, `null`, vazio, espaços, acima do limite e campos extras retornam 422 sem alteração.
- **Persistence/audit**: `full_name`, `updated_at` e `updated_by` mudam; username, e-mail, hash e estado permanecem iguais.
- **Migration**: upgrade semeia a permissão e a composição no Administrador; downgrade remove somente as composições e a permissão da feature.
- **Regression**: todos os testes existentes de cadastro, autenticação, listagem, RBAC e demais módulos permanecem verdes.

## Traceability

| Requirement | Design / Implementation | Evidence |
|---|---|---|
| FR-001 | `PATCH /users/{user_id}` em `src/pivma/routers/users.py` | Teste HTTP 200 |
| FR-002 | `CurrentUser`, `TrustedOrigin` e `USERS_MANAGE` | Testes 401/403/origem |
| FR-003 | Migração, constante e composição do Administrador | Testes de migração e autorização |
| FR-004 a FR-007 | `UserUpdate` e `extra='forbid'` | Testes de payload e 422 |
| FR-008 | Busca do alvo pelo UUID | Teste 404 |
| FR-009 a FR-010 | Atribuição, `set_update_audit` e `UserPublic` | Teste de persistência e não alteração |
| FR-011 | `UserSchema.full_name` requerido e banco anulável | Testes POST/legado |
| FR-012 | `UserPublic` compartilhado | Testes de POST, auth/me e listagem |
| SC-001 a SC-006 | Matriz de testes focados e suíte completa | Quickstart e saída real dos comandos |

## Risks and Controls

| Risk | Control |
|---|---|
| Usar `users.read` para mutação | Permissão separada `users.manage` e teste de ausência de autorização |
| Bloquear conta legada | Banco continua anulável; PATCH permite preencher valor válido |
| Alterar credenciais por payload extra | Schema com `extra='forbid'` e teste dedicado |
| Atualizar conta sem origem confiável | Dependência `TrustedOrigin` e teste de 403 |
| Perder rastreabilidade | `set_update_audit(actor.id)` e teste de `updated_by`/`updated_at` |

## Complexity Tracking

Não há violação dos guardrails. A mudança adiciona uma rota, um schema, uma permissão e uma revisão de dados, sem nova camada, dependência ou tabela de eventos.
