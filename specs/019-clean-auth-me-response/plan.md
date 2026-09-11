# Implementation Plan: Limpeza e Padronização do Contrato de Sessão Atual

**Branch**: `019-clean-auth-me-response` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-clean-auth-me-response/spec.md`

## Summary

Refatorar o endpoint `GET /auth/me` para eliminar campos de usuário redundantes no nível raiz da resposta JSON, adotando formalmente uma quebra de retrocompatibilidade. A classe `CurrentUserResponse` deixará de herdar de `UserIdentity`, passando a encapsular de forma estrita e isolada os blocos `user` (identidade do usuário) e `access` (perfis, permissões e escopos). Todos os testes que validavam os campos na raiz serão atualizados ou removidos, e as páginas de demonstração em `demos/` serão atualizadas para consumir `user.user.*`.

## Technical Context

**Language/Version**: Python >= 3.14  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0  
**Storage**: PostgreSQL com migrações Alembic (inalterado nesta feature, sem novas tabelas ou colunas)  
**Testing**: pytest, pytest-asyncio, Testcontainers (PostgreSQL 17), factories factory_boy  
**Target Platform**: Linux server / Web REST API  
**Project Type**: Web service  
**Performance Goals**: Desempenho idêntico ou superior na serialização Pydantic da resposta de sessão (< 5ms)  
**Constraints**: Resposta estrita de `CurrentUserResponse` sem campos extras (`extra='forbid'`); eliminação completa de campos planos legados na raiz  
**Scale/Scope**: Refatoração de 1 schema (`src/pivma/schemas.py`), 1 endpoint (`src/pivma/routers/auth.py`), 1 contrato OpenAPI, ~2 arquivos de teste e ~8 arquivos de demonstração  

## Constitution Check

*GATE: Avaliado antes da implementação e confirmado após o design.*

- [x] **Princípio I (Spec Kit)**: Especificação formal (`spec.md`), pesquisa (`research.md`), modelo de dados (`data-model.md`), contrato OpenAPI (`contracts/auth.openapi.yaml`), quickstart (`quickstart.md`) e plano gerados em ordem.
- [x] **Princípio II (Domínio Puro na API, Demos Descartáveis)**: O contrato da API reflete o domínio puro e limpo da entidade de sessão. As demos consomem a API real e permanecem desacopladas em `demos/`.
- [x] **Princípio III (Demonstração como Critério de Conclusão)**: As páginas em `demos/` são atualizadas para operar perfeitamente contra o novo contrato.
- [x] **Princípio IV (Qualidade Verificável Antes da Entrega)**: `poe format`, `poe lint` e `poe test` serão executados. Testes de contrato ajustados para refletir a nova estrutura.
- [x] **Princípio V (Auditabilidade e Rastreabilidade)**: Não há alterações de banco de dados ou histórico de auditoria.
- [x] **Princípio VI (Segurança por Padrão)**: Autenticação baseada em cookie `access_token` seguro e inalterado; validação de sessão preservada.

## Project Structure

### Documentation (this feature)

```text
specs/019-clean-auth-me-response/
├── checklists/
│   └── requirements.md      # Validação de qualidade da especificação
├── contracts/
│   └── auth.openapi.yaml    # Contrato OpenAPI atualizado sem herança de UserIdentity
├── data-model.md            # Modelos DTOs e payload JSON
├── plan.md                  # Este arquivo (plano de arquitetura e implementação)
├── quickstart.md            # Roteiro de validação manual e automatizada
├── research.md              # Decisões arquiteturais e justificativas
└── spec.md                  # Especificação funcional de negócio
```

### Source Code (repository root)

```text
src/pivma/
├── schemas.py               # CurrentUserResponse herda de BaseModel com user e access
└── routers/
    └── auth.py              # GET /auth/me instancia CurrentUserResponse(user=..., access=...)

tests/
└── api/
    └── routers/
        └── test_auth_router.py   # Testes atualizados sem asserções em campos legados na raiz

demos/
├── ai-pipeline/app.js       # Atualizado para ler user.user.*
├── attachments/index.html   # Atualizado para ler user.user.*
├── forms/ai-config.html     # Atualizado para ler user.user.*
├── forms/index.html         # Atualizado para ler user.user.*
├── operational-index/app.js # Atualizado para ler user.user.*
├── roadmap/index.html       # Atualizado para ler user.user.*
├── submission/index.html    # Atualizado para ler user.user.*
├── triage/index.html        # Atualizado para ler user.user.*
└── users/index.html         # Atualizado para ler user.user.*
```

**Structure Decision**: A alteração é cirúrgica e restrita à borda de entrada (schemas, router de autenticação, contrato OpenAPI, testes de contrato e scripts de demonstração clientes). Não requer migração de banco nem afeta o core de segurança ou repositórios.

## Complexity Tracking

> **Sem violações constitucionais**. A simplificação reduz a complexidade do modelo (remoção de herança múltipla conceitual e descompactação de dicionários).
