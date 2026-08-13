# Implementation Plan: Autenticação de Usuários

**Branch**: `feature/user-authentication` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification and instruction to keep the implementation limited to a single JWT session without refresh, rotation, blacklist, persistent revocation, advanced session management, or MFA.

## Summary

Implementar login por username ou e-mail, emitir um JWT de 8 horas em cookie e disponibilizar a identidade atual no backend. O plano adiciona somente PyJWT, configura segredos e origens pelo ambiente, cria três rotas de autenticação e testa os contratos de sessão e proteção de origem. Não haverá migração nem tabelas de sessão.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, SQLAlchemy 2 assíncrono, Argon2id, PyJWT 2.13

**Storage**: PostgreSQL existente para contas; nenhum armazenamento novo para sessão ou revogação

**Testing**: Pytest, TestClient, Testcontainers e testes assíncronos existentes

**Target Platform**: Serviço HTTP Python em servidor Linux, com HTTPS no ambiente que entrega cookies `Secure`

**Project Type**: Serviço web de API

**Performance Goals**: Todos os casos automatizados definidos em SC-001 a SC-006 devem ser aprovados.

**Constraints**: JWT HS256 com validade máxima de 8 horas; cookie `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`; sem refresh, rotação, blacklist, revogação persistente, MFA ou tabelas de sessão; origem permitida configurada explicitamente.

**Scale/Scope**: Uma rota de login, uma rota de identidade atual e uma rota de logout; contas já existentes e ativas; uma dependência nova; sem alteração de esquema.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pré-pesquisa: APROVADO.**

- **Requisitos e evidência**: o plano atende ao RF001 e às decisões registradas em `spec.md`. Perfis, permissões e vínculos dos RF002 a RF006 ficam fora do escopo.
- **Auditoria e versionamento**: não há evento de domínio ou alteração de entidade que exija nova auditoria. O plano preserva `AuditMixin` e não altera a tabela `users`.
- **Segurança**: o backend valida assinatura, claims, expiração e atividade da conta em cada requisição autenticada. O logout valida `Origin` antes de alterar o cookie.
- **Mudança mínima e verificável**: o plano reutiliza o hash Argon2id, a sessão do banco e a estrutura de routers e testes existentes. Cada comportamento novo terá teste de rota ou unidade.

**Pós-design: APROVADO.** Os artefatos definem três rotas, uma dependência pequena e nenhuma persistência de sessão. O único aumento de dependência é PyJWT, necessário para a decisão explícita de JWT.

## Project Structure

### Documentation (this feature)

```text
specs/002-user-authentication/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)
```text
src/pivma/
├── __init__.py                 # registra o router de autenticação
├── core/
│   ├── security.py              # hash existente e funções JWT mínimas
│   └── settings.py              # segredo e origens confiáveis
├── routers/
│   └── auth.py                  # login, identidade atual e logout
└── schemas.py                   # credenciais e resposta pública da identidade

tests/
├── core/test_security.py        # emissão e validação de JWT
└── routers/test_auth.py         # contratos HTTP, cookies, identidade e origem

.env.example                     # documenta variáveis obrigatórias sem segredos
pyproject.toml                   # registra PyJWT
```

**Structure Decision**: O serviço já usa routers, schemas, `core/security.py` e testes por router. A feature acrescenta somente `routers/auth.py` e `tests/routers/test_auth.py`; os demais arquivos recebem extensões pontuais.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Nenhuma violação que exija justificativa.
