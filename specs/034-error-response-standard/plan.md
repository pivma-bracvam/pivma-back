# Implementation Plan: Formato único das respostas de erro

**Branch**: `feat/034-error-response-standard` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/034-error-response-standard/spec.md`

## Summary

Toda resposta de erro passa a ser `{"detail": {"code", "message", "fields"?}}`, com mensagens em português. Três handlers globais garantem o formato: `HTTPException` (inclui 404 de rota e 405), `RequestValidationError` e exceções não tratadas (R1). Um texto livre esquecido sai com o código genérico do status.

Os pontos de erro conhecidos passam a usar `api_error(status, code, message)`, com códigos explícitos (R2). As exceções de domínio ganham um `code` opcional, e as mensagens em inglês são traduzidas (R4).

A validação vira `fields` com `location`, `field`, `code` (o `type` do Pydantic) e uma mensagem traduzida, sem nunca repetir o valor enviado. A senha continua sem expor a regra (R3). O OpenAPI troca `HTTPValidationError` por `ErrorResponse` (R5).

Nenhum status HTTP muda.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI (handlers de exceção, `openapi()`), Starlette, Pydantic v2

**Storage**: N/A (sem mudança de esquema)

**Testing**: Pytest + pytest-asyncio, `TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: sem impacto; os handlers só atuam em respostas de erro

**Constraints**:
- Status HTTP inalterados (FR-008).
- `404` que esconde a existência de um recurso continua escondendo (FR-009).
- Nenhum valor enviado nas respostas (FR-004).
- A senha não expõe a regra (FR-010).

**Scale/Scope**:
- 2 módulos novos: `core/errors.py` (`api_error`, códigos, tradução, montagem de campos) e `errors.py` (handlers e `custom_openapi`).
- `schemas.py`: `ErrorResponse`, `ErrorDetail`, `FieldError`.
- Cerca de 100 pontos de erro em 16 roteadores, `dependencies.py` e mensagens de domínio em `core/*`.
- 17 arquivos de teste que comparam `detail`, mais os testes novos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template sem preencher. Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Alinhamento de 2026-09-27 (Specs 032–034); Q1 e Q2 da spec respondidas |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ Nenhum marcador aberto |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Status e regras de acesso inalterados. `404` de ocultação mantido. Nenhum valor enviado ou detalhe interno exposto. Amostras cegas mantêm os códigos |
| Mudança cirúrgica, sem abstração preventiva | ✅ Um helper (`api_error`) e três handlers; os helpers locais dos roteadores passam a delegar a ele, sem nova hierarquia de exceções |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final (seção "Convenções de Erro") |

**Re-check pós-design**: sem violações. Pontos de atenção:

- **Handler de `Exception`:** o `500` deixa de ser texto. O teste precisa usar `TestClient(app, raise_server_exceptions=False)`.
- **OpenAPI:** o pós-processamento de `openapi()` precisa manter o cache do FastAPI (`app.openapi_schema`) e rodar uma vez só.
- **Roteadores com `str(e)`:** a mensagem passa a depender de o domínio escrever para o usuário. As mensagens em inglês são traduzidas na origem (R4).
- **Códigos genéricos de `not_found`/`forbidden`:** hoje já aparecem como específicos em alguns pontos; continuam com o mesmo nome.

## Project Structure

### Documentation (this feature)

```text
specs/034-error-response-standard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py              # registra handlers e custom_openapi; sai o handler atual de senha
├── errors.py                # novo: handlers de HTTPException, RequestValidationError e Exception; custom_openapi
├── core/
│   ├── errors.py            # novo: api_error, GENERIC_CODES, VALIDATION_MESSAGES, field_errors()
│   ├── process_engine.py    # ProcessEngineError.code opcional; mensagens em português
│   ├── attachment_service.py, invite_service.py, sample_service.py, ... # códigos/mensagens
├── dependencies.py          # not_authenticated, invalid_origin, forbidden, admin_only
├── schemas.py               # ErrorResponse, ErrorDetail, FieldError
└── routers/*.py             # pontos de erro com api_error e mensagens em português

tests/
├── unit/core/test_errors.py     # tradução por tipo, montagem de campos, senha
├── api/test_error_contract.py   # formato por status, 404 de rota, 405, 500, cabeçalhos
└── (17 arquivos existentes ajustados)
```

**Structure Decision**: backend único. `core/errors.py` não depende do FastAPI app, e os handlers e o `openapi` ficam em `pivma/errors.py`, junto do app.

## Complexity Tracking

Sem violações a justificar.
