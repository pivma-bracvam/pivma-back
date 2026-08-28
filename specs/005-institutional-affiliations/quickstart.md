# Validação rápida: Vinculação Institucional

## Pré-requisitos

1. Configure as variáveis existentes de banco, JWT e origens confiáveis.
2. Inicie PostgreSQL/pgvector com `docker compose up -d db`.
3. Aplique `poetry run alembic upgrade head`.
4. Use HTTPS no fluxo real do navegador, pois a autenticação usa cookie `Secure`.

## Sequência mínima de implementação

1. Criar a migração após `1bd1b3d5ddad`, incluindo tabelas, constraints, índices, permissões e composições do Administrador.
2. Adicionar os quatro modelos e os schemas de entrada e saída.
3. Acrescentar as constantes de permissão e a consulta reutilizável de vínculos efetivamente ativos.
4. Implementar e registrar o router `/institutional`, mantendo cada mutação e sua mudança institucional na mesma transação.
5. Adicionar factories e testes por camada, sem criar infraestrutura paralela à existente.
6. Atualizar o README com endpoints, permissões e comandos de validação.

## Validação automatizada

Execute primeiro os grupos focados:

```bash
poetry run pytest tests/unit/schemas/test_institutional_schemas.py -q
poetry run pytest tests/integration/database/test_institutional_constraints.py tests/integration/database/test_institutional_scope.py -q
poetry run pytest tests/integration/migrations/test_institutional_migration.py -q
poetry run pytest tests/api/routers/test_institutional_router.py tests/api/routers/test_institutional_security.py tests/api/routers/test_institutional_concurrency.py -q
```

Depois execute regressão, lint e verificação da migração:

```bash
poetry run pytest
poetry run ruff check
poetry run alembic heads
poetry run alembic check
```

Confirme a saída direta de `poetry run pytest`. O task `poetry test` usa `ignore_fail = true` e não comprova sucesso sozinho.

## Evidência mínima por risco

| Risco | Evidência esperada |
|---|---|
| Integridade | FK composta impede laboratório de outra instituição; índices parciais impedem nomes e vínculos ativos duplicados. |
| Autorização | 401 sem identidade; 403 uniforme antes da consulta do alvo; cada permissão institucional concede somente sua capacidade. |
| Autoconsulta | A rota `/institutional/me/affiliations` usa o usuário autenticado e retorna somente vínculos efetivamente ativos. |
| Isolamento | Uma conta sem `institutional.read` não consulta vínculos, catálogos nem histórico globais. |
| Inativação | Instituição, laboratório ou vínculo inativo deixa de compor o escopo no pedido seguinte, sem apagar o ciclo. |
| Concorrência | Criações simultâneas de nome institucional ou vínculo equivalente mantêm somente um registro ativo. |
| Rastreabilidade | Toda mudança concluída possui alvo, ator e momento; operação negada ou revertida não deixa evento concluído. |
| Migração | Upgrade preserva usuários e RBAC existentes, não cria vínculos implícitos e associa as três permissões apenas ao Administrador; downgrade remove somente a feature 005. |

## Validação manual do fluxo principal

1. Prepare uma conta administradora autenticada e uma segunda conta ativa.
2. Consulte `GET /institutional/institutions` e confirme que o acesso exige `institutional.read`.
3. Inicie o cronômetro.
4. Com `institutional.catalogs.manage` e um `Origin` confiável, crie uma instituição e um laboratório.
5. Com `institutional.affiliations.manage`, vincule a segunda conta ao laboratório.
6. Pare o cronômetro e confirme que as três mutações foram concluídas em até 3 minutos.
7. Autentique a segunda conta e consulte `GET /institutional/me/affiliations`; confirme somente o vínculo criado.
8. Inative o laboratório e repita a autoconsulta com o mesmo cookie; confirme que o vínculo não compõe mais o escopo.
9. Com `institutional.read`, consulte o vínculo histórico e `GET /institutional/changes`; confirme identificadores, estados, ator, ação e momento.

As respostas esperadas estão no [contrato HTTP](contracts/institutional.openapi.yaml). As constraints e os estados estão no [modelo de dados](data-model.md).

## Registro de validação

- 2026-08-24: testes focados executados com PostgreSQL descartável em Docker,
  resultado `22 passed`.
- 2026-08-24: regressão completa executada com PostgreSQL descartável em
  Docker, resultado `155 passed`.
- 2026-08-24: `poetry run ruff check src tests migrations/versions/5e31a8c7d204_institutional_affiliations.py` passou.
- 2026-08-24: `poetry run alembic heads` confirmou `5e31a8c7d204 (head)`.
- 2026-08-24: `PYTHONPATH=src poetry run alembic check` não concluiu porque o
  PostgreSQL local em `localhost:5432` não estava disponível. Os testes de
  migração passaram contra PostgreSQL descartável.
- 2026-08-24: com PostgreSQL local iniciado pelo Compose e migrações aplicadas,
  `PYTHONPATH=src poetry run alembic check` detectou divergências em RBAC e
  processo, tipos de data e FKs de auditoria também nas tabelas institucionais.
  A correção exige uma decisão separada para alinhar a estratégia de auditoria
  do schema ao metadata atual.
- 2026-08-24: testes focados de migração, contratos e segurança executados com
  PostgreSQL descartável em Docker, resultado `16 passed`.
- 2026-08-24: regressão completa executada com PostgreSQL descartável em
  Docker, resultado `160 passed`; `poetry run ruff check` passou e
  `poetry run alembic heads` confirmou `5e31a8c7d204 (head)`.
- 2026-08-24: revisão de granularidade dos testes institucionais. Testes
  "mega-cenário" de `test_institutional_router.py` foram divididos em casos
  menores por comportamento observável; foram acrescentados testes para
  `GET /institutional/laboratories`, 409 de nome de laboratório duplicado,
  listagem administrativa de vínculos com sucesso, correção de vínculo por
  novo ciclo (FR-012), autoconsulta com múltiplos vínculos ativos (US3) e
  separação `institutional.catalogs.manage` não concede
  `institutional.affiliations.manage`. Testes institucionais focados:
  `44 passed`. Regressão completa: `177 passed`. `ruff check` passou.
  `alembic heads` confirmou `5e31a8c7d204 (head)`.
- Fluxo manual de até três minutos: pendente de execução por uma pessoa com
  sessão de navegador e contas do ambiente alvo.

## Backlog registrado (não são lacunas de implementação desta feature)

- **Validação manual cronometrada (SC-006, T030/T035)**: exige uma pessoa com
  sessão de navegador autenticada contra o ambiente alvo. Essa sessão só
  existe após o deploy e a integração do front-end desta feature; não há
  como executá-la antes disso. A implementação e os testes automatizados já
  cobrem os mesmos passos do fluxo (criação de instituição e laboratório,
  vinculação, autoconsulta, inativação e histórico). Retomar esta tarefa
  quando o ambiente alvo e o front-end estiverem disponíveis; até lá, não
  tratar como pendência da implementação.
- **Divergência do `alembic check` (T031/T035)**: com PostgreSQL local
  disponível, `PYTHONPATH=src poetry run alembic check` reporta FKs de
  auditoria "adicionadas" e mudanças de tipo de timestamp em praticamente
  todas as tabelas com `AuditMixin` do sistema — RBAC e processo (features
  001 a 004) e as quatro tabelas desta feature igualmente. A divergência é
  pré-existente e transversal ao projeto, não algo introduzido pelas tabelas
  institucionais: a migração 5e31a8c7d204 segue o mesmo padrão de auditoria
  já usado pelas migrações anteriores. Corrigi-la exige uma decisão separada
  sobre a estratégia de auditoria do schema (nomes de FK e representação de
  timestamp) aplicada a todas as migrações existentes, fora do escopo desta
  feature. Registrar e acompanhar essa decisão em uma tarefa própria, sem
  bloquear a feature 005 por ela.
