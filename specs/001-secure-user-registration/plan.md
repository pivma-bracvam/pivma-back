# Implementation Plan: Cadastro Seguro de Usuários

**Branch**: `feature/secure-user-registration` (a criar a partir de `main`; integração em `main`
por PR) | **Date**: 2026-08-11 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`/specs/001-secure-user-registration/spec.md`

## Summary

Endurecer o cadastro existente sem criar novos endpoints: validar e preservar username e e-mail,
proteger senhas com Argon2id, registrar a auditoria de criação já prevista e garantir unicidade
case-insensitive entre usuários ativos sob concorrência por índices únicos parciais do PostgreSQL.
O endpoint mantém HTTP 201 e o corpo público atual; conflitos continuam em HTTP 409, com precedência
de username.

> **Redução de escopo em 2026-08-12** (ver `spec.md`, Clarifications, Session 2026-08-12): esta é a
> primeira feature da requisitante com Spec Kit, e a spec original aprovada em 2026-08-12 acabou
> pedindo garantias de nível produção crítica desproporcionais a um projeto novo sem usuários reais.
> A própria requisitante, única aprovadora, decidiu remover: bloqueio de senha por blocklist local
> (e sua prontidão fail-closed), inspeção de formato de credencial na migração, reserva de
> identificador após exclusão lógica, e o gate formal de benchmark. Este plano já reflete o escopo
> reduzido; os pontos originais permanecem descritos no histórico do `spec.md` para rastreabilidade.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg 3,
Alembic; adicionar `argon2-cffi >=25.1,<26` como única dependência de produção nova; a pessoa
solicitante da feature revisa cada atualização

**Storage**: PostgreSQL 17 com pgvector

**Testing**: Pytest, TestClient, pytest-asyncio, Testcontainers PostgreSQL/pgvector e Factory Boy

**Target Platform**: Serviço web em Linux/container; desenvolvimento e testes também em macOS e
Windows conforme a configuração existente

**Project Type**: API web em projeto Python único

**Performance Goals**: Nenhum limite numérico foi aprovado nem exigido como gate de aceite nesta
versão (ver redução de escopo de 2026-08-12); pode ser revisitado se houver indício de latência
excessiva do Argon2id em uso real

**Constraints**: Sem login, JWT, cookies, perfis, permissões ou novos endpoints; senha de 8 a 128
caracteres Unicode sem whitespace e sem normalização; respostas, logs e erros não podem ecoar senha
ou suas representações; username e e-mail preservam caixa; unicidade ignora caixa e vale entre
usuários ativos; rate limiting permanece fora desta feature

**Scale/Scope**: Um endpoint, um modelo persistente, uma migração incremental e testes focados no
cadastro; volume de usuários não foi especificado

## Constitution Check

*GATE: aprovado em 2026-08-12 pela pessoa solicitante da feature.*

| Princípio | Evidência no plano | Estado |
|---|---|---|
| Requisitos oficiais e evidência classificada | As escolhas técnicas foram classificadas e aprovadas para esta feature | PASS |
| Rastreabilidade, auditoria e versionamento | Mantém `AuditMixin`; somente `created_at` recebe valor no cadastro público e os demais campos permanecem nulos; versiona blocklist e cria migração nova | PASS |
| Segurança e autorização no backend | Todas as validações ocorrem no backend; senha não aparece na resposta nem permanece em texto simples | PASS |
| Autoridade científica e IA | Não se aplica; a feature não usa IA nem decisão científica | PASS |
| Mudanças pequenas e verificáveis | Reusa rota, schemas, modelo e testes existentes; adiciona somente segurança, recurso e migração necessários | PASS |
| Limites de decisão de domínio | Login, JWT, cookies, papéis e vínculos permanecem fora do escopo | PASS |
| Desenvolvimento com Spec Kit | Spec, pesquisa, design e tarefas existem e receberam aprovação explícita | PASS |

### Divergências registradas

- **CONFIRMADO na spec**: a senha mínima tem 8 caracteres e rejeita whitespace.
- **CONFIRMADO na spec**: caracteres Unicode são preservados sem NFC/NFKC.
- **INFERÊNCIA baseada em fonte externa**: essas decisões divergem da orientação atual do NIST
  para senha usada como fator único, que exige 15 caracteres, recomenda normalização NFC quando
  Unicode é aceito e permite espaços. O plano preserva as decisões aprovadas e não as altera.

### Reavaliação pós-design

PASS. A pessoa solicitante aprovou a spec e o plano em 2026-08-12 e, na mesma data, reduziu o
escopo (ver Clarifications, Session 2026-08-12 em `spec.md`) após perceber que o conjunto de
decisões da sessão anterior gerava complexidade desproporcional para uma primeira feature. O
desenho final mantém a unicidade concorrente no banco (agora restrita a usuários ativos) e evita
conversão silenciosa de credenciais legadas por meio da checagem de colisão na migração.

## Project Structure

### Documentation (this feature)

```text
specs/001-secure-user-registration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── benchmark-results.md    # registro histórico; deixou de ser gate de aceite em 2026-08-12
├── contracts/
│   └── users.openapi.yaml
├── checklists/
│   ├── readiness.md
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── security.py          # hash e verificação Argon2id
│   └── database/
│       └── models.py        # User, AuditMixin e índices únicos parciais case-insensitive
├── routers/
│   └── users.py             # fluxo e tradução de conflitos
└── schemas.py               # normalização e validação da entrada

migrations/versions/
└── <revision>_secure_user_registration.py

tests/
├── core/
│   ├── database/
│   │   └── test_user_constraints.py
│   └── test_security.py
├── migrations/
│   └── test_secure_user_registration.py
├── routers/
│   ├── test_user.py
│   ├── test_user_audit.py
│   ├── test_user_concurrency.py
│   └── test_user_failures.py
└── conftest.py
```

**Structure Decision**: Manter o projeto único e as camadas existentes. `security.py` concentra
somente o hashing de senha; o schema valida e normaliza entrada; a rota coordena a persistência e
mapeia conflitos; o PostgreSQL é a autoridade final de unicidade entre usuários ativos.

## Implementation Strategy

1. **PROPOSTA aprovada nesta feature**: adicionar e travar `argon2-cffi >=25.1,<26`; a pessoa
   solicitante da feature revisa cada atualização.
2. *(removido em 2026-08-12)* Blocklist local de senhas comuns/comprometidas. Ver redução de escopo
   no topo deste documento e Session 2026-08-12 em `spec.md`.
3. **PROPOSTA**: implementar em `security.py` as funções de hash e verificação Argon2id, com o
   hashing executado fora do event loop.
4. **PROPOSTA**: aplicar trim e validações no schema antes do banco e sanitizar respostas de senha
   inválida para HTTP 422 com `{"detail": "Invalid password"}`, sem ecoar o valor recebido.
5. **PROPOSTA**: criar migração incremental com preflight antes de qualquer mutação: verificar
   colisões case-insensitive entre usuários ativos. Abortar sem mudar schema ou dados se o preflight
   falhar; caso passe, renomear `password` para `password_hash` e substituir os índices por versões
   case-insensitive parciais (usuários ativos).
6. **PROPOSTA**: atualizar o modelo e a rota. Manter verificação prévia para mensagens determinísticas,
   restrita a usuários ativos, e tratar `IntegrityError` após rollback como garantia contra corrida.
7. **PROPOSTA**: atualizar factories e ampliar testes de unidade, rota, banco real, concorrência e
   migração.
8. Tratar separadamente falhas inesperadas de hashing, `flush` e `commit`: executar rollback,
   retornar HTTP 500 genérico e provar que resposta e persistência não contêm detalhes ou segredos.
9. Preservar o estado inicial do `AuditMixin`: `created_at` preenchido; `created_by`, `updated_at`,
   `updated_by`, `deleted_at` e `deleted_by` nulos.

## Rastreabilidade dos critérios de sucesso

| Critério | Decisão técnica relacionada | Evidência verificável |
|---|---|---|
| SC-001 | Estratégia 4, 6 e 10 | testes de cadastro e auditoria |
| SC-002 | Constraints; estratégias 4 e 9 | testes de rota, senha inválida e falhas internas |
| SC-003 | Estratégias 1, 3 e 6 | testes reais de Argon2id e persistência |
| SC-004 | Estratégias 5 e 6 | testes concorrentes e índices únicos no PostgreSQL |
| SC-005 | Estratégia 10 | `tests/routers/test_user_audit.py` |
| SC-006 | Estratégia 7 | suíte completa registrada em `quickstart.md` |
| SC-007 | Constraints; estratégia 4 | testes de schema e senha Unicode |
| SC-008 | Constraints; estratégias 4 e 6 | testes de trim, caixa e conflitos |
| SC-009 | Constraints; estratégia 4 | testes de limites e caracteres do username |
| SC-010 | *(removido, ver Session 2026-08-12)* | — |
| SC-011 | *(removido, ver Session 2026-08-12)* | — |
| SC-012 | *(removido, ver Session 2026-08-12)* | — |
| SC-013 | Estratégia 8 | testes separados de hashing, `flush` e `commit` |

## Migration Safety

- Antes de qualquer DDL ou DML, a migração deve detectar colisões de `lower(username)` e
  `lower(email)` entre usuários ativos (`deleted_at IS NULL`), já que essa colisão violaria o novo
  índice único parcial.
- Diagnósticos podem informar etapa, contagem e identificadores conflitantes, mas nunca senha ou
  fragmentos dela; a migração não escolhe vencedores.
- Se o preflight passar, a migração renomeia `password` para `password_hash`, remove o índice
  anterior e cria índices únicos parciais case-insensitive sobre `lower(username)` e `lower(email)`,
  restritos a `deleted_at IS NULL`.
- A inspeção do formato da credencial armazenada foi removida em 2026-08-12: como o projeto é novo
  e não há credenciais reais em produção, a migração não tenta validar se a senha existente já é um
  hash Argon2id.

## Complexity Tracking

Nenhuma violação constitucional ou abstração adicional foi identificada.
