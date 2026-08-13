# Quickstart: Validar Cadastro Seguro de Usuários

Este guia será executado após a implementação. Ele valida os contratos de
[spec.md](spec.md), o desenho de [data-model.md](data-model.md) e a interface
[users.openapi.yaml](contracts/users.openapi.yaml).

> **Nota (2026-08-12)**: as seções 1, 2, 5 e 6, e as evidências da seção 7, descrevem o guia
> original da Session 2026-08-11, anterior à redução de escopo (ver `spec.md`, Clarifications,
> Session 2026-08-12). Ficam preservadas como registro histórico. A seção 8 registra a validação
> executada após o corte de escopo e reflete o comportamento atual.

## Pré-requisitos

- Python 3.14 e Poetry.
- Docker em execução para o PostgreSQL/pgvector descartável.
- Dependências instaladas e migrações disponíveis.
- `DATABASE_URL` definido durante a coleta do Pytest, mesmo que os testes em macOS/Linux substituam
  a conexão por um PostgreSQL descartável do Testcontainers.

## 1. Conferir migrações

```bash
poetry run alembic upgrade head
```

Resultado esperado: a migração conclui somente quando não há colisões case-insensitive entre
quaisquer usuários e todas as credenciais existentes já são Argon2id válidas. Em bases preparadas
separadamente com colisão ou credencial não Argon2id, ela aborta antes de alterar schema ou dados.
O diagnóstico não contém senha, SHA-1, Argon2id nem fragmentos. A migração cria dois índices únicos
globais e usuários excluídos continuam reservando seus identificadores.

## 2. Executar testes focados

```bash
DATABASE_URL=postgresql+psycopg://test:test@localhost/test \
  poetry run pytest tests/core/test_security.py tests/routers/test_user.py -vv
```

Resultados esperados:

- cadastro válido retorna HTTP 201 com id, username e e-mail;
- resposta não contém senha nem hash;
- banco contém Argon2id, e a senha original é verificável somente pela função de segurança;
- validações cobrem limites, ASCII do username, Unicode e whitespace da senha;
- blocklist retorna HTTP 422 genérico para valores conhecidos sem ecoar senha, digest ou causa;
- o corpo da senha inválida é exatamente `{"detail": "Invalid password"}`;
- recurso da blocklist ausente ou inválido provoca falha operacional fechada, nunca HTTP 422;
- username e e-mail rejeitam duplicatas com variação de caixa;
- identificadores de usuários excluídos permanecem reservados;
- em cada caso, dois pedidos concorrentes equivalentes produzem um HTTP 201, um HTTP 409 e uma
  conta;
- `created_at` é preenchido e `created_by` permanece nulo.
- `updated_at`, `updated_by`, `deleted_at` e `deleted_by` permanecem nulos após a criação;
- falhas separadas de hashing, `flush` e `commit` retornam HTTP 500 genérico, executam rollback e
  não criam usuário nem expõem detalhes ou segredos.

## 3. Executar a suíte completa

```bash
DATABASE_URL=postgresql+psycopg://test:test@localhost/test poetry run pytest -vv
```

Confirmar a saída do Pytest. Não usar apenas o status agregado de `poetry test`, pois essa tarefa
ignora falhas na etapa do Pytest.

## 4. Verificar qualidade

```bash
poetry run ruff check
```

Resultado esperado: nenhuma violação.

## 5. Verificar distribuição da blocklist

```bash
poetry build
```

Inspecionar wheel e sdist e confirmar a presença de:

- `pivma/resources/password_blocklist/hashes.sha1`;
- `pivma/resources/password_blocklist/metadata.json`.

Validar checksums, versão local, fonte, data de aquisição, seleção, ferramenta de derivação e
referência aos termos vigentes. Instalar o wheel em ambiente limpo e executar o teste de
carregamento. Remover ou corromper o recurso deve impedir a prontidão; restaurar o pacote íntegro e
reiniciar deve permitir novo cadastro, sem fallback externo.

## 6. Medir Argon2id

Executar dentro do container da API o benchmark com o perfil `RFC_9106_LOW_MEMORY` e exatamente
dois pedidos válidos, com identificadores distintos, em concorrência. Registrar em
`benchmark-results.md`:

- data e imagem/configuração do ambiente;
- parâmetros Argon2id e latência de cada pedido;
- duração total e resultados HTTP/persistência;
- pico de memória;
- responsável, data e decisão de aprovação.

Não existe limite numérico pré-fixado. Sem aprovação explícita do responsável técnico, a feature
não está aceita. Resultado desfavorável exige revisão do plano; o sistema não reduz custos nem
seleciona outro perfil automaticamente.

## 7. Evidências da execução de 2026-08-12

### Histórias independentes

| Escopo | Comando | Resultado |
|---|---|---|
| US1 | `pytest tests/test_schemas.py tests/core/test_security.py tests/routers/test_user.py tests/routers/test_user_failures.py tests/test_blocklist_readiness.py tests/test_package_resources.py -q` | 40 passaram em 2,87 s |
| US2 | `pytest tests/routers/test_user.py tests/routers/test_user_concurrency.py tests/core/database/test_user_constraints.py -q` | 15 passaram em 3,00 s |
| US3 | `pytest tests/routers/test_user_audit.py -q` | 1 passou em 1,95 s |

Todos os comandos Pytest da tabela foram executados por `poetry run` com a `DATABASE_URL` de teste
descrita nos pré-requisitos. US2 confirmou os dois casos concorrentes, de username e de e-mail,
com um HTTP 201, um HTTP 409 e somente um usuário por caso.

### Migração e distribuição

- `pytest tests/migrations/test_secure_user_registration.py -q`: 9 testes passaram em 2,57 s,
  incluindo upgrade vazio, preservação de Argon2id válido, abortos antes de mutação para texto
  legado e seis combinações de colisão, além de downgrade;
- `docker compose up --build -d`: a imagem foi construída, as duas revisões Alembic foram aplicadas
  em base limpa e a aplicação concluiu a prontidão;
- `poetry build`: wheel e sdist foram gerados;
- a inspeção de ambos os arquivos confirmou `hashes.sha1` e `metadata.json`; o hash ocupa
  4.100.000 bytes no wheel;
- o wheel foi instalado no ambiente limpo `/tmp/pivma-wheel-validation.ZmvKSq/.venv` e o
  carregamento íntegro retornou 100.000 entradas.

Durante a primeira validação da imagem, o container não iniciou porque `entrypoint.sh` não possuía
permissão de execução após o `COPY`. O `Dockerfile` passou a aplicar `chmod +x entrypoint.sh`; a
reconstrução posterior iniciou a API e aplicou as migrações normalmente.

### Regressão e qualidade

- tentativa inicial de `poetry run pytest -vv`: interrompida durante a coleta porque
  `DATABASE_URL` não estava definida;
- repetição definitiva com a variável de teste: 59 testes passaram em 4,02 s, com cobertura total
  de 92%;
- `poetry run ruff check`: `All checks passed!`.

O benchmark foi executado e está registrado em [benchmark-results.md](benchmark-results.md). Seus
resultados ainda aguardam a aprovação explícita exigida pelo SC-011.

## 8. Evidências da execução de 2026-08-12 (após redução de escopo)

Após remover blocklist, inspeção de formato de credencial na migração, reserva de identificador
pós-exclusão lógica e o gate de benchmark (ver `spec.md`, Clarifications, Session 2026-08-12), a
suíte foi reexecutada com `DATABASE_URL` de teste e Testcontainers reais:

```bash
DATABASE_URL=postgresql+psycopg://db_user:db_password@localhost:5432/db \
  poetry run pytest -x -vv
poetry run ruff check .
```

- 46 testes passaram em 3,35 s; cobertura total de 94% (`src/pivma`);
- `ruff check`: `All checks passed!`;
- migração testada com upgrade limpo, aborto por colisão entre usuários ativos, colisão ignorada
  quando envolve usuário excluído, e downgrade — sem inspeção de formato de credencial;
- novos testes provam que a exclusão lógica libera username e e-mail para reuso
  (`tests/core/database/test_user_constraints.py::test_deleted_user_identifiers_do_not_block_reuse`,
  `tests/routers/test_user.py::test_create_user_frees_identifiers_after_deletion`).

A suíte caiu de 59 para 46 testes (remoção de `test_blocklist_readiness.py`,
`test_derive_password_blocklist.py`, `test_package_resources.py` e dos casos de blocklist em
`test_security.py`/`test_user.py`), mantendo cobertura de hashing, unicidade, concorrência,
auditoria e falhas internas.
