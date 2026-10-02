# Implementation Plan: Autogestão de Nome e Senha da Própria Conta

**Branch**: `feat/037-self-profile-update` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

Adicionar `PATCH /auth/me` ao router `auth` para que qualquer conta autenticada altere o próprio `full_name` e/ou troque a senha confirmando a atual. A rota reaproveita `CurrentUser`, `TrustedOrigin`, `verify_password`, `hash_password`, `set_update_audit`, `api_error` e a projeção `UserPublic`. Entra um schema novo, `SelfUserUpdate`, e um ajuste de uma linha no formatador de erros da Spec 034 para que os novos campos de senha também tenham a regra mascarada. Não há migração, dependência nem camada nova.

## Evidence Classification

- **CONFIRMADO** (`origin/develop`, `8560237`): a única mutação de conta é `PATCH /users/{user_id}`, que exige `users.manage`. Já existem `CurrentUser`, `TrustedOrigin`, `verify_password`/`hash_password` (Argon2id) e `AuditMixin.set_update_audit`.
- **CONFIRMADO**: `src/pivma/core/errors.py` mascara a regra de senha apenas quando o campo se chama exatamente `password`, o que deixaria `current_password` e `new_password` expostos (ver [research.md](research.md), item 7).
- **CONFIRMADO**: há um handler global para exceções não tratadas (`src/pivma/errors.py`) que responde 500 `internal_error`.
- **DECISÃO DA SPEC**: HTTP 400 `invalid_current_password` para senha atual incorreta; resposta `UserPublic`.
- **INFERÊNCIA**: a autogestão de dados de acesso faz parte do RF001 (cadastro e autenticação).
- **FORA DE ESCOPO**: revogação de sessões, limite de tentativas, alteração de `username`/`email`, recuperação de senha.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, argon2-cffi (via `pivma.core.security`); nenhuma dependência nova

**Storage**: PostgreSQL com pgvector; tabela existente `users`, sem mudança de schema

**Testing**: Pytest com `TestClient`, fixtures assíncronas de sessão, Testcontainers e Factory Boy

**Target Platform**: API web (Linux/Docker)

**Project Type**: backend monolítico (web-service)

**Performance Goals**: uma leitura de sessão e um commit por requisição; Argon2 em threadpool, no máximo uma verificação e um hash por chamada

**Constraints**: cookie JWT `access_token`; origem confiável em mutações; formato único de erros (Spec 034) sem expor regra ou valor de senha; atomicidade sem estado parcial; contratos existentes inalterados

**Scale/Scope**: uma rota, um schema, uma linha no formatador de erros, testes focados e README

## Constitution Check

*GATE: avaliado antes da pesquisa e reavaliado após o desenho.*

- **I. Requisitos e evidência**: PASS. As afirmações estão classificadas; a única inferência (RF001) está marcada; as decisões abertas pela issue estão registradas na spec.
- **II. Rastreabilidade e auditoria**: PASS. Usa `set_update_audit(current_user.id)`, o padrão vigente; não cria trilha paralela.
- **III. Segurança e autorização**: PASS. Sessão validada no backend; a conta alvo vem só da sessão; `TrustedOrigin` contra CSRF; senha atual conferida antes de trocar; hash Argon2id; nenhum segredo na resposta; regra de senha mascarada no 422.
- **IV. IA**: PASS. Não se aplica.
- **V. Mudanças pequenas e verificáveis**: PASS. Sem refatoração de código vizinho, sem abstração nova. O ajuste em `errors.py` é necessário para que os campos novos cumpram a Spec 034 e tem teste próprio.

**Reavaliação pós-desenho**: PASS em todos os princípios. O desenho (research, data-model, contrato) não introduziu tabela, dependência, serviço ou exceção à auditoria.

## Project Structure

### Documentation (this feature)

```text
specs/037-self-profile-update/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/auth-me.openapi.yaml
├── checklists/requirements.md
└── tasks.md              # gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/errors.py          # máscara de senha cobre *password
├── routers/auth.py         # PATCH /auth/me
└── schemas.py              # SelfUserUpdate
tests/
├── api/routers/test_auth_router.py   # comportamento HTTP da rota
├── unit/schemas/test_user_schemas.py # regras do SelfUserUpdate
└── unit/core/test_errors.py          # máscara de current_password/new_password
README.md                   # seção "Usuários e Autenticação"
```

**Structure Decision**: segue a organização atual: schemas em `schemas.py`, rotas de sessão em `routers/auth.py` e testes de API no arquivo indicado pela issue.

## Implementation Sequence

1. **Máscara de senha** (teste primeiro): teste unitário em `test_errors.py` para `current_password` e `new_password`; depois, a condição em `_field_error` passa a ser `any(str(part).endswith('password') for part in path)`.
2. **Testes de API** (antes da rota), agrupados por história:
   - US1: nome atualizado e aparado; `GET /auth/me` reflete; `updated_by`/`updated_at` preenchidos.
   - US2: troca de senha válida (login novo aceita, antigo recusa); senha atual errada → 400 sem alteração; sem `current_password` → 422; política violada → 422; nome + senha atual errada → 400 sem alterar o nome.
   - US3: 401 sem sessão; 403 sem origem e com origem não confiável; 422 para campos extras (`username`, `email`, `password_hash`), `{}`, `null`, nome vazio, `current_password` sozinha; outra conta intacta; conta desativada → 401; resposta sem senha ou hash.
3. **Schema `SelfUserUpdate`** em `schemas.py`, logo após `UserUpdate`, conforme [data-model.md](data-model.md), com testes unitários em `tests/unit/schemas/test_user_schemas.py` escritos antes. O `model_validator` confere as combinações na ordem de [research.md](research.md), item 3.
4. **Rota `PATCH /auth/me`** em `auth.py`: `operation_id='updateCurrentUser'`, `response_model=UserPublic`, `responses` com 400/401/403; dependências `CurrentUser`, `Session`, `TrustedOrigin`; verificação da senha atual antes de qualquer atribuição; hash em threadpool; `set_update_audit`; `commit`; `refresh`. Sem `try/except` (ver research, item 5).
5. **README**: acrescentar em "Usuários e Autenticação" a regra de autogestão (rota, campos, 400/401/403/422, sessão não revogada).
6. **Verificação**: testes focados, suíte completa, `poetry run ruff check src tests` e `poetry run ruff format --check src tests`, conferindo a saída real.

## Test Strategy

As tarefas de teste serão detalhadas em `/speckit-tasks` com a skill `fastapi-testing-methodology`, um teste por comportamento.

- **Schema**: cada regra do `SelfUserUpdate` tem teste unitário próprio em `tests/unit/schemas/test_user_schemas.py`, enviando os demais campos válidos e conferindo o `loc` do erro, para que a falha venha da regra testada.
- **Verificação de estado**: após cada erro, recarregar a conta do banco e comparar `full_name`, `password_hash`, `updated_at` e `updated_by` com os valores anteriores (SC-003).
- **Senha**: confirmar a troca pelo comportamento observável (`POST /auth/login` com a senha nova e a antiga) e por `verify_password` sobre o hash persistido, como em `test_user_update.py`.
- **Erros**: conferir `detail.code` (`invalid_current_password`, `not_authenticated`, `invalid_origin`, `validation_error`) e, nos 422 de senha, a ausência da regra e do valor enviado.
- **Regressão**: `test_auth_router.py`, `test_user_update.py`, `test_error_contract.py` e a suíte completa continuam verdes sem mudar asserções existentes (SC-007).

## Traceability

| Requirement | Design / Implementation | Evidence |
|---|---|---|
| FR-001, FR-002 | Rota em `auth.py` usando apenas `CurrentUser` | Teste 200 com conta sem `users.manage`; outra conta intacta |
| FR-003 | `CurrentUser` + `TrustedOrigin` | Testes 401, 403 (sem origem, origem não confiável), conta desativada |
| FR-004 | `SelfUserUpdate` com `extra='forbid'` | Testes 422 para `username`, `email`, `password_hash` |
| FR-005, FR-008 (presença) | `model_validator` de `SelfUserUpdate` | Testes 422 de `{}`, `null`, `current_password` só, `new_password` sem atual |
| FR-006, FR-007 | `FullNameValue`; restrições e validador de `new_password` | Testes de nome aparado/vazio e senha curta/com espaço |
| FR-008 (conferência), FR-009 | `verify_password` em threadpool + `api_error(400, 'invalid_current_password', ...)` | Testes 400 com e sem `full_name` |
| FR-010 | `hash_password` em threadpool; `UserPublic` | `verify_password` sobre o hash; resposta sem segredo |
| FR-011 | Verificação antes de qualquer atribuição | Comparação do estado persistido após cada erro |
| FR-012 | `set_update_audit(current_user.id)` | Teste de `updated_by`/`updated_at` |
| FR-013 | `response_model=UserPublic` | Teste do corpo 200 |
| FR-014 | Mesmo registro, commit e refresh | Teste `GET /auth/me` após PATCH |
| FR-015, FR-016 | Rota altera só `full_name`/`password_hash`; nada mais muda | Asserções de campos inalterados; suíte existente verde |
| Spec 034, FR-010 | Condição `endswith('password')` em `_field_error` | Teste unitário em `test_errors.py` e teste de API do 422 |

## Risks and Controls

| Risk | Control |
|---|---|
| Alterar o nome antes de rejeitar a senha atual | Verificar a senha antes de atribuir; teste do caso combinado |
| CSRF via cookie | `TrustedOrigin` e testes de 403 |
| Expor regra ou valor de senha no 422 | Ajuste em `errors.py` e teste unitário/API |
| Front-end deslogar por 401 na senha errada | Status 400 com código próprio |
| Bloquear o loop de eventos com Argon2 | `run_in_threadpool` para verificar e para gerar o hash |
| Senha atual curta voltar 422 em vez de 400 | `current_password` com mínimo 1, não 8 |

## Complexity Tracking

Não há violação a justificar. A entrega adiciona uma rota, um schema e uma condição no formatador de erros, sem tabela, serviço, dependência ou migração.
