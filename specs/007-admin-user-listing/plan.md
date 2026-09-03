# Implementation Plan: Listagem Administrativa de Usuários

**Branch**: `007-admin-user-listing` (identificador do Spec Kit; branch Git ainda não criada) | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

**Input**: Especificação aprovada em `specs/007-admin-user-listing/spec.md` e ajustes de contrato registrados em 2026-09-02 e 2026-09-03.

## Summary

Adicionar `GET /users` ao router existente, com proteção de `require_permission('users.read')`, paginação `offset`/`limit`, busca literal case-insensitive em username e e-mail, filtros `active` e `profile_id` e ordem por `lower(username), id`. Cada item também inclui `full_name` e os perfis globais ativos com seus nomes. O cadastro exige `full_name` em novas contas e `GET /auth/me` expõe o mesmo campo, mantendo `null` para contas legadas. Uma migração incremental acrescenta a coluna anulável `full_name` sem alterar dados existentes. A atualização administrativa do nome pertence à feature 008. A implementação reutiliza os modelos, a sessão assíncrona, o RBAC e `FilterPage`; cria somente a projeção administrativa e a página específicas da resposta. O desenho dispensa nova camada, dependência, índice ou busca adicional.

## Evidence Classification

- **CONFIRMADO**: o head Alembic atual é `6f2c9a1d4e70`; `User.deleted_at` representa a exclusão lógica; `require_permission` calcula o acesso no banco e registra recusas 403; `FilterPage` contém `offset` e `limit`, mas não declara máximo 100.
- **DECISÃO EXPLÍCITA DA SPEC**: a rota exige `users.read`; o perfil Administrador recebe essa permissão; `ADMINISTRATIVE_PERMISSIONS` mantém somente as três capacidades do RBAC; a consulta usa os filtros, paginação, ordem e projeção definidos na spec. A projeção inclui os perfis globais ativos de cada conta.
- **PROPOSTA TÉCNICA DO PLANO**: a migração usa os UUIDs determinísticos `108`/`208`; a busca usa `icontains(autoescape=True)`; o filtro de perfil usa `EXISTS`; os novos schemas especializam `UserPublic` e `FilterPage`; `full_name` é uma coluna anulável `String(255)`, requerido em novos cadastros e aparado no schema.
- **INFERÊNCIA**: testes HTTP no PostgreSQL fornecem evidência suficiente da consulta contida no router; um teste de repository repetiria o mesmo caminho e exigiria uma camada sem uso no código atual.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg 3 e Alembic 1.19, todos existentes

**Storage**: PostgreSQL/pgvector existente; além dos dados RBAC já previstos, uma coluna anulável `users.full_name` adicionada por migração incremental

**Testing**: Pytest 9, TestClient, pytest-asyncio, Testcontainers com PostgreSQL/pgvector e Factory Boy existentes

**Target Platform**: Serviço web FastAPI para Linux e PostgreSQL 17

**Project Type**: API backend monolítica

**Performance Goals**: A spec não define benchmark; cada resposta terá no máximo 100 itens e a consulta não executará contagem total

**Constraints**: Resposta restrita a `offset`, `limit` e `items`; item restrito a `id`, `full_name`, `username`, `email`, `active` e `profiles`; perfil restrito a `id`, `name` e `active`; 401 sem autenticação; 403 sem `users.read`; busca literal case-insensitive; filtros aplicados antes da página; `full_name` requerido em novos cadastros, anulável no legado, aparado e limitado a 255 caracteres; sem evento persistente de RBAC; sem nova camada, dependência, índice ou ordenação configurável

**Scale/Scope**: Um endpoint GET, uma permissão semeada, uma coluna de usuário, schemas compartilhados e administrativos, uma consulta SQLAlchemy e testes focados; cadastro e `GET /auth/me` recebem `full_name`, com entrada requerida em novas contas e resposta anulável para legado; mutações RBAC e demais módulos permanecem inalterados

## Constitution Check

*GATE: verificado antes da pesquisa e novamente após o design.*

**Pré-pesquisa: APROVADO.**

- **Requisitos e evidência**: a spec classifica requisitos oficiais, decisões registradas e decisões da feature. O desenho cobre RF001, RF002, RF004 e o uso futuro previsto em RF005 sem antecipar vínculo ou designação.
- **Rastreabilidade e auditoria**: a consulta não altera conta nem RBAC. Ela preserva `AuditMixin`, não cria `RbacChange` e mantém o log operacional produzido por `require_permission` nas recusas 403, conforme a feature 003 e a delimitação de RF034.
- **Segurança**: o backend autentica e verifica `users.read` antes de executar busca, filtros ou paginação. A resposta 403 não contém itens, contagens ou indicação de correspondência.
- **Isolamento e cegamento**: a consulta não usa instituição, laboratório, processo, conflito de interesse ou regras contextuais.
- **Mudança mínima**: a implementação usa o router, os modelos, as dependências e os schemas compartilhados atuais. Não adiciona repository, service, cache, índice ou biblioteca.
- **Testes proporcionais**: testes HTTP contra PostgreSQL real cobrem consulta, paginação e segurança; um teste de migração cobre o seed e o downgrade; um teste isolado protege a invariável administrativa.

**Pós-design: APROVADO.** `research.md`, `data-model.md`, `contracts/users.openapi.yaml` e `quickstart.md` preservam os limites acima. O contrato estende as respostas de usuário e exige `full_name` na entrada de `POST /users` para novas contas, sem alterar autenticação ou operações RBAC.

## Project Structure

### Documentation (this feature)

```text
specs/007-admin-user-listing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── users.openapi.yaml
└── tasks.md                         # criado depois por $speckit-tasks
```

### Source Code (repository root)

```text
migrations/versions/
├── 7a3e1c9b4d82_admin_user_listing_permission.py
└── <nova_revisao>_user_full_name.py

src/pivma/
├── core/authorization.py            # constante USERS_READ; invariável RBAC intacta
├── routers/users.py                 # GET /users e consulta SQLAlchemy
├── routers/auth.py                  # identidade atual com full_name
├── core/database/models.py          # coluna User.full_name
├── seed_demo.py                     # dados de nome completo das contas de demonstração
└── schemas.py                       # UserSchema, UserPublic, item administrativo e página

tests/
├── unit/core/test_authorization.py  # users.read fora de ADMINISTRATIVE_PERMISSIONS
├── integration/migrations/
│   ├── test_admin_user_listing_migration.py
│   └── test_rbac_migration.py       # total do catálogo após head
└── api/routers/
    ├── test_user_listing.py         # contrato, consulta, filtros e paginação
    ├── test_user_listing_security.py # 401, 403, separação, log e não vazamento
    ├── test_user_router.py          # cadastro e exibição do full_name
    └── test_auth_router.py          # identidade atual com full_name

tests/integration/migrations/test_user_full_name_migration.py # coluna incremental

README.md                            # documenta a consulta e users.read
```

**Structure Decision**: O router `users.py` já possui a coleção `/users` e acesso direto à sessão. A nova leitura permanece nesse arquivo. `authorization.py` continua concentrando os códigos de permissão usados por dependências. O novo schema de página herda `FilterPage`; os parâmetros HTTP recebem validação própria para preservar o schema compartilhado. Os testes de API executam a consulta real no PostgreSQL e dispensam uma função de repository criada apenas para repetir a mesma evidência em outra camada.

## Implementation Sequence

1. **Catálogo e invariável**: criar a migração de dados após `6f2c9a1d4e70`, semear `users.read` e sua composição com `administrator`, adicionar a constante `USERS_READ` e manter `ADMINISTRATIVE_PERMISSIONS` inalterado.
2. **Persistência e schema compartilhado**: adicionar `User.full_name` como coluna anulável de até 255 caracteres, exigi-lo em `UserSchema` para novas contas e expô-lo em `UserPublic`, preservando registros legados sem o campo.
3. **Contrato de saída**: acrescentar um item administrativo que herda os campos de `UserPublic`, adiciona `active` e os perfis globais ativos, além de uma página `AdminUserPage` baseada em `FilterPage` que mantém `limit` entre 1 e 100 no schema de resposta sem alterar a classe base compartilhada, adicionando `items`.
4. **Consulta protegida**: implementar `GET /users` com a dependência existente de permissão, validação dos parâmetros pela FastAPI, predicados SQLAlchemy combináveis, `EXISTS` para `profile_id`, ordem determinística e projeção explícita da resposta.
5. **Evidência automatizada**: criar testes focados de migração, API e segurança, ajustar a expectativa agregada do catálogo RBAC e executar a regressão de cadastro, autenticação e RBAC.
6. **Contrato e documentação**: manter os contratos OpenAPI de usuários e autenticação alinhados à aplicação e registrar no README o campo requerido em novos cadastros e a nova operação administrativa da feature 008.

## Test Strategy

| Risco | Nível | Evidência planejada |
|---|---|---|
| Exposição administrativa sem autorização | API/segurança | 401 sem cookie; 403 sem `users.read`; separação parametrizada das permissões RBAC; corpo sem coleção; log operacional único; nenhum `RbacChange`. |
| Exposição de dados sensíveis | API | Resposta bem-sucedida com igualdade exata dos campos no topo e em cada item. |
| Persistência e propagação do nome completo | API/migração | Campo requerido e aparado em novos cadastros, coluna existente após upgrade, retorno no cadastro, `GET /auth/me` e `GET /users`, e `null` preservado no legado. |
| Busca textual incorreta | API com PostgreSQL real | Username, e-mail, variações de caixa, trim, vazio e `%`/`_` como literais. |
| Filtros e paginação inconsistentes | API com PostgreSQL real | Estado padrão/ativo/inativo, perfil e relações inativas, perfil desconhecido, combinação completa, limites, página vazia e ordem estável sem duplicatas. |
| Catálogo ou composição incorretos | Migração | Upgrade a partir do head anterior, seed exclusivo no Administrador, efeito em atribuição já existente e downgrade que remove a permissão e suas composições sem remover contas, perfis ou atribuições. |
| Ampliação da salvaguarda administrativa | Unidade/regressão | `USERS_READ` ausente de `ADMINISTRATIVE_PERMISSIONS` e suíte existente de preservação do administrador. |
| Regressão de contratos existentes | API/regressão | Suítes atuais de cadastro, autenticação e RBAC, seguidas da suíte completa. |

A consulta combinada permanece no router. Os testes HTTP já atravessam validação, autorização, SQLAlchemy e PostgreSQL; um segundo conjunto de testes de repository repetiria o mesmo comportamento e exigiria uma camada ausente. Não haverá teste unitário para schemas declarativos nem para construção SQL sem componente isolado.

### Behavioral test inventory

Cada caso abaixo observa um contrato. `pytest.mark.parametrize` agrupa somente entradas equivalentes do mesmo comportamento.

- **API de consulta**: página padrão ativa e campos exatos, incluindo `full_name`; busca por username; busca por e-mail; equivalência de caixa; trim e busca vazia; `%` e `_` literais; `active=false`; perfil ativo com atribuição ativa; perfil inativo; atribuição encerrada; perfil desconhecido; combinação de busca, estado, perfil e página; ordem e desempate; offset além do fim; nenhum resultado; limites válidos.
- **Nome completo**: cadastro com `full_name` e espaços externos; cadastro sem `full_name` rejeitado; valor vazio; valor acima de 255 caracteres; propagação para `GET /auth/me` e `GET /users`; legado com `null`.
- **Validação HTTP**: offset negativo; limit zero; limit acima de 100; booleano inválido; UUID de perfil malformado. Cada grupo parametrizado comprova um único tipo de validação 422.
- **Segurança**: ausência de sessão; ausência de `users.read`; cada permissão administrativa de RBAC isolada; concessão de `users.read`; log da recusa; ausência de `RbacChange` na recusa; ausência de `RbacChange` na leitura concluída.
- **Migração**: seed e composição oficial; efeito sobre Administrador já atribuído; ausência da composição em outros perfis; downgrade com composição adicional; preservação de contas, perfis e atribuições; total agregado do catálogo no head.
- **Invariável isolada**: `USERS_READ` não pertence a `ADMINISTRATIVE_PERMISSIONS`; os testes RBAC existentes continuam validando a salvaguarda das três capacidades.

Os testes criam entidades persistidas com as factories atuais e `session`. Casos com muitas contas informam um `password_hash` barato à `UserFactory`, pois a listagem não verifica senha. SQL direto fica restrito aos testes Alembic, onde o ORM não representa o estado intermediário da migration.

## Traceability

| Requisitos da spec | Decisão técnica | Evidência planejada |
|---|---|---|
| FR-001 a FR-008 | Rota na coleção existente e dependência `users.read` antes do handler | Testes de API e segurança 200/401/403, separação e log. |
| FR-009 a FR-013 | Query params validados, ordem `lower(username), id`, página baseada em `FilterPage` | Testes de limites, páginas sucessivas, desempate, vazio e não duplicação. |
| FR-014 e FR-015 | `icontains(autoescape=True)` após `strip()` | Testes de campos, caixa, vazio e curingas literais. |
| FR-016 a FR-021 | Predicado de `deleted_at` e `EXISTS` de perfil/atribuição ativos | Testes de estado, relações ativas/inativas, combinação e UUID desconhecido. |
| FR-022 a FR-025 | `UserPublic` especializado, perfis ativos em lote e construção explícita do item | Igualdade exata dos campos, nomes dos perfis e uso do UUID pelo RBAC existente. |
| FR-026 e FR-027 | Nenhum código institucional, laboratorial ou de processo | Diff restrito e regressão dos módulos existentes. |
| FR-028 | Nenhuma escrita na leitura; log existente no 403 | Testes distintos para leitura concluída, recusa e `RbacChange`. |
| FR-029 a FR-033 | `User.full_name`, validação requerida em novos cadastros e projeção compartilhada em `UserPublic` | Testes de cadastro, identidade, listagem, validação e migração incremental. |
| SC-001 a SC-013 | Matriz acima e quickstart | Grupos focados, regressão e suíte completa após a implementação. |

## Risks and Controls

- **Wildcard tratado pelo banco**: `LIKE` interpreta `%` e `_`. A consulta usará `icontains(valor, autoescape=True)`, e testes com ambos os caracteres impedirão regressão para padrões não literais.
- **Multiplicação por relações RBAC**: um `JOIN` externo pode repetir contas. Um `EXISTS` correlacionado verificará perfil e atribuição ativos sem ampliar as linhas de `users`.
- **Contrato compartilhado de paginação**: `FilterPage` não declara máximo 100. O schema de resposta `AdminUserPage` manterá `limit` entre 1 e 100 sem modificar o `FilterPage` compartilhado, garantindo alinhamento entre o OpenAPI da aplicação e `contracts/users.openapi.yaml`, enquanto a rota aplica a mesma restrição nos query params.
- **Downgrade com composições adicionais**: administradores podem associar `users.read` a outros perfis depois do upgrade. O downgrade removerá todas as linhas de `access_profile_permissions` ligadas à permissão antes de removê-la.
- **Páginas durante alterações concorrentes**: offset não oferece snapshot entre pedidos. A spec limita a garantia a conjuntos sem mudanças; o plano não cria cursor, lock ou transação entre requisições.
- **Busca por substring sem índice dedicado**: o padrão `%termo%` não aproveita os índices B-tree funcionais existentes em todos os casos. A spec retirou o benchmark de 10.000 contas; a equipe só acrescentará índice ou extensão depois que uma medição demonstrar necessidade.
- **Dados legados sem nome completo**: a migração adicionará a coluna como anulável, preservando os registros atuais sem inventar um nome. O schema e as respostas representam essa ausência como `null`.

## Complexity Tracking

Nenhuma violação constitucional exige justificativa.
