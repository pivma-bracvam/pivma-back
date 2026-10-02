# Implementation Plan: Token de Acesso no Corpo da Resposta de Login

**Branch**: `feat/auth-credentials-management` (decisão do usuário: sem branch própria) | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/038-login-token-body/spec.md` (issue #44)

## Summary

`POST /auth/login` passa a responder `{"access_token", "token_type": "bearer", "expires_in"}` com `Cache-Control: no-store`, mantendo o cookie `HttpOnly` atual. A extração do Bearer em `get_current_user` passa a usar o esquema `HTTPBearer` do FastAPI, o que documenta o Bearer no OpenAPI e habilita o "Authorize" de `/docs`. `require_trusted_origin` dispensa a checagem de `Origin` quando a requisição vem sem cookie `access_token` e com Bearer. Não há migração, tabela nem dependência nova.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141.1 (`fastapi.security.HTTPBearer`, já incluído), Pydantic v2, PyJWT

**Storage**: N/A (token sem estado; nada é persistido)

**Testing**: pytest com `TestClient` (`tests/api/routers/test_auth_router.py`), metodologia `fastapi-testing-methodology`

**Target Platform**: serviço web Linux (container)

**Project Type**: web-service (backend de API)

**Performance Goals**: sem impacto; a resposta do login ganha ~300 bytes

**Constraints**: preservar o contrato do cookie, as respostas de erro do login e a proteção CSRF de quem usa cookie

**Scale/Scope**: 3 arquivos de código (`schemas.py`, `routers/auth.py`, `dependencies.py`), 1 de teste, README

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Status |
|-----------|-----------|--------|
| I. Requisitos e evidência classificada | Fonte: issue #44 e decisão do usuário registrada em Clarifications. O Plano de Trabalho (RF001) não detalha o transporte do token; a spec marca os fatos do código como CONFIRMADO. | PASS |
| II. Rastreabilidade e auditoria | Login não gera evento auditável hoje e continua sem gerar. Nenhum dado de domínio muda. | PASS |
| III. Segurança e autorização | Autenticação e permissões continuam validadas no backend. A dispensa de `Origin` vale só sem cookie; o CORS impede um site terceiro de anexar `Authorization` (research.md, item 4). O token no corpo é exposição pedida pela issue; o frontend continua com o cookie `HttpOnly`. `Cache-Control: no-store` impede cache da credencial. | PASS |
| IV. IA | Não se aplica. | N/A |
| V. Mudanças pequenas e verificáveis | ~25 linhas de código, sem abstração nova. A troca da leitura manual do cabeçalho por `HTTPBearer` remove código em vez de acrescentar. Cada FR tem teste. | PASS |

**Re-check pós-design**: PASS. O design não acrescentou componentes além dos listados.

## Project Structure

### Documentation (this feature)

```text
specs/038-login-token-body/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── auth-login.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md             # gerado por $speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── schemas.py           # + LoginResponse
├── dependencies.py      # HTTPBearer em get_current_user; dispensa de Origin com Bearer sem cookie
└── routers/auth.py      # login devolve LoginResponse e Cache-Control: no-store

tests/api/routers/
└── test_auth_router.py  # contrato do login, Bearer, origem, OpenAPI

README.md                # integração: token no corpo, Bearer, SameSite=Strict
```

**Structure Decision**: projeto único existente (`src/pivma`, `tests/`). Nenhum módulo novo.

## Complexity Tracking

Sem violações a justificar.
