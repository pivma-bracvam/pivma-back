# PIVMA API

API Backend desenvolvida em Python 3.14 utilizando FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic, Argon2id e banco de dados PostgreSQL com extensão `pgvector`.

A documentação interativa das rotas, esquemas de entrada/saída e testes de requisição está disponível em:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Sumário

- [Pré-requisitos](#pré-requisitos)
- [Requisitos do `.env`](#requisitos-do-env)
- [Instalação e Configuração](#instalação-e-configuração)
- [Arquitetura de Permissões e Acesso](#arquitetura-de-permissões-e-acesso)
- [Diretrizes de Integração (Frontend)](#diretrizes-de-integração-frontend)
- [Módulos e Regras de Negócio](#módulos-e-regras-de-negócio)
  - [Usuários e Autenticação](#usuários-e-autenticação)
  - [Controle de Acesso (RBAC Global)](#controle-de-acesso-rbac-global)
  - [Catálogo Institucional](#catálogo-institucional)
  - [Processos, Formulários e Triagem](#processos-formulários-e-triagem)
  - [Participantes e Conflito de Interesses](#participantes-e-conflito-de-interesses)
  - [Avaliação Configurável por IA](#avaliação-configurável-por-ia)
  - [Observabilidade de Logs](#observabilidade-de-logs)
- [Comandos Úteis (`poetry` e `uv`)](#comandos-úteis-poetry-e-uv)
- [Práticas de Desenvolvimento e Testes](#práticas-de-desenvolvimento-e-testes)
- [Execução com Docker](#execução-com-docker)
- [Diretrizes de Contribuição](#diretrizes-de-contribuição)

---

## Pré-requisitos

- **Python 3.14+**
- **Poetry** ou **uv**
- **Docker** e **Docker Compose**

---

## Requisitos do `.env`

As configurações são validadas pela classe `Settings` em `src/pivma/core/settings.py` via `pydantic-settings`.

### Variáveis Principais

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `DATABASE_URL` | String de conexão assíncrona PostgreSQL via `psycopg` | `postgresql+psycopg://db_user:db_password@localhost:5432/db` |
| `APP_ENV` | Ambiente de execução (`development`, `staging`, `production`) | `development` |
| `SECRET_KEY` | Chave secreta para assinatura de tokens e sessões | `sua-chave-secreta` |
| `AI_PROVIDER` | Provedor de IA para pré-avaliação (`openai` ou `fake` em CI/testes) | `fake` |
| `OPENAI_API_KEY` | Chave de API da OpenAI (necessária se `AI_PROVIDER=openai`) | `sk-...` |

Gere o arquivo local:

```bash
cp .env.example .env

```

> [!NOTE]
> Dentro da rede do Docker Compose, utilize o host do serviço de banco (`@db:5432/db`). No host local, aponte para `@localhost:5432/db`.

---

## Instalação e Configuração

### Com Poetry

```bash
poetry install
docker compose up db -d
poetry run alembic upgrade head
poetry run python -m pivma.bootstrap_process_templates
poetry run poe serve

```

### Com uv

```bash
uv sync
docker compose up db -d
uv run alembic upgrade head
uv run python -m pivma.bootstrap_process_templates
uv run fastapi dev src/pivma/__init__.py

```

---

## Arquitetura de Permissões e Acesso

A aplicação divide autorização em dois níveis:

1. **Perfis Globais (RBAC):** Definem permissões transversais no sistema (ex.: `Administrador`, `BraCVAM`, `Grupo Gestor`).
2. **Papéis Locais de Processo:** Definem atribuições dentro de instâncias específicas de processo (`ProcessInstance`).

### Bootstrap do Administrador Inicial

O primeiro administrador deve ser promovido via script CLI:

```bash
# Poetry
poetry run python -m pivma.bootstrap_rbac --user-id <UUID_DO_USUARIO>

# uv
uv run python -m pivma.bootstrap_rbac --user-id <UUID_DO_USUARIO>

```

O comando atribui o perfil global `Administrador`, é idempotente para o mesmo identificador e rejeita a execução se outra conta ativa já for administradora.

---

## Diretrizes de Integração (Frontend)

* **Transporte de Sessão:** A autenticação opera via cookie seguro `access_token` (`HttpOnly`, `SameSite=Lax`). Requisições no cliente HTTP devem utilizar `credentials: 'include'` (ou `withCredentials: true`).
* **Validação de Origem (CSRF):** Mutações de estado (`POST`, `PUT`, `PATCH`, `DELETE`) validam a procedência contra a lista de origens confiáveis da aplicação. Certifique-se de configurar o endereço do frontend em desenvolvimento no arquivo `.env`.
* **Avaliação Dinâmica de Permissões:** Perfis e papéis são validados a cada requisição no banco de dados, sem persistência de permissões dentro do token.
* **Convenções de Erro:**
* `401 Unauthorized`: Sessão inexistente ou expirada.
* `403 Forbidden`: Falta de permissão global ou restrição por conflito de interesse ativo.
* `409 Conflict`: Violação de unicidade ou regra de negócio (ex.: cadastro duplicado, duplicidade de papel no processo).
* `422 Unprocessable Entity`: Erro de validação de payload/schema.



---

## Módulos e Regras de Negócio

### Usuários e Autenticação

* **Validações de Conta:**
* `username`: 3 a 64 caracteres (ASCII alfanumérico, `.`, `-`, `_`), único (case-insensitive).
* `email`: Formato RFC válido, único (case-insensitive).
* `full_name`: 1 a 255 caracteres, obrigatório para novas contas.
* `password`: 8 a 128 caracteres, sem espaços em branco. O hash é gerado com Argon2id.


* **Exclusão Lógica:** Contas inativadas liberam seus identificadores (`username` e `email`) para novos cadastros.
* **Desativação de contas:** `DELETE /users/{user_id}` exige sessão ativa, origem confiável e `users.manage`. A API preserva o registro, preenche `deleted_at` e `deleted_by` e responde `204`. Autodesativação e remoção da última conta administradora ativa respondem `409`. Contas inativas não iniciam sessões nem reutilizam tokens existentes. `GET /users` lista contas ativas; `GET /users?active=false` lista contas inativas.

### Controle de Acesso (RBAC Global)

* Catálogo de permissões gerenciado estritamente por migrações.
* Permissões divididas em escopos operacionais: leitura de auditoria e perfis (`rbac.read`), gerenciamento de perfis (`rbac.profiles.manage`), atribuição a usuários (`rbac.assignments.manage`) e gestão de contas (`users.manage`).
* Atribuições utilizam exclusão lógica (`deleted_at`) para manter histórico imutável.

### Catálogo Institucional

* Gerenciamento de instituições, laboratórios e vínculos institucionais de usuários.
* Acesso administrativo restrito a contas com permissões do catálogo institucional (`institutional.catalogs.manage` e `institutional.affiliations.manage`).
* Alterações estruturais são auditadas na entidade `InstitutionalChange`.

### Processos, Formulários e Triagem

* Ciclo de validação analítica orientado por instâncias de templates versionados.
* Suporte a formulários dinâmicos com ciclos de rascunho e submissão estrita (bloqueio de alterações após envio).
* Fase 1 (Triagem) inclui pareceres técnicos por campo e decisão final (aprovação, rejeição ou retorno para ajustes), restritos a usuários com permissão de triagem (`triage.review`).
* Exclusão lógica permitida apenas para processos em estados não-terminais.

### Participantes e Conflito de Interesses

* **Papéis Locais Suportados:**
* Técnicos: `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`.
* Proponente: `proponent` (atribuído ao criador do processo).
* Laboratoriais: `lead_laboratory`, `participating_laboratory` (exigem vínculo institucional ativo do usuário com o respectivo laboratório).


* **Regras de Conflito de Interesse:**
* Histórico *append-only* em `ConflictInterestDeclaration`.
* Se um usuário possuir declaração de conflito ativa em qualquer papel do processo, qualquer tentativa de registrar parecer de triagem ou decisão regulatória é bloqueada imediatamente com status `403 Forbidden`.
* O conteúdo da justificativa do conflito é visível apenas ao declarante e aos gestores do processo.



### Avaliação Configurável por IA

* O BraCVAM configura critérios em linguagem natural vinculados a campos de formulário.
* A pré-avaliação opera de forma assíncrona na submissão através de modelos via LangChain.
* **Regra de Consolidação:** A presença de 1 ou mais não-conformidades de severidade alta ou crítica consolida o resultado como negativo.
* Resultado positivo: segue para a fila de triagem.
* Resultado negativo/falha: retorna ao proponente para retificação ou solicitação de intervenção direta.


* A IA não emite decisões regulatórias finais; o processo decisório permanece sob responsabilidade de triadores humanos.

### Observabilidade de Logs

Administradores podem consultar os registros recentes pelos endpoints
`GET /admin/logs/operational` e `GET /admin/logs/ai`. O primeiro aceita filtros
por status e tipo de operação; o segundo aceita `correlation_id` para consultar
etapas de uma execução.

`demos/operational-index/` consulta o histórico sob demanda ou a cada cinco
segundos, quando a atualização automática está ativa. `demos/ai-pipeline/`
consulta o histórico quando o usuário solicita.

---

## Comandos Úteis (`poetry` e `uv`)

| Ação | Com Poetry | Com uv |
| --- | --- | --- |
| **Instalar dependências** | `poetry install` | `uv sync` |
| **Servidor de desenvolvimento** | `poetry run poe serve` | `uv run fastapi dev src/pivma/__init__.py` |
| **Verificar Linter** | `poetry run poe lint` | `uv run ruff check` |
| **Formatar código** | `poetry run poe format` | `uv run ruff format` |
| **Executar testes** | `poetry run poe test` | `uv run pytest` |
| **Aplicar migrações** | `poetry run alembic upgrade head` | `uv run alembic upgrade head` |
| **Carregar templates** | `poetry run python -m pivma.bootstrap_process_templates` | `uv run python -m pivma.bootstrap_process_templates` |
| **Bootstrap Administrador** | `poetry run python -m pivma.bootstrap_rbac --user-id <UUID>` | `uv run python -m pivma.bootstrap_rbac --user-id <UUID>` |

---

## Práticas de Desenvolvimento e Testes

### Estrutura da Suíte

* `tests/unit/`: Testes unitários de schemas, segurança e regras isoladas.
* `tests/api/routers/`: Testes de contrato HTTP, autorização e respostas via `TestClient`.
* `tests/integration/database/`: Testes de integridade de dados e constraints no PostgreSQL.
* `tests/integration/migrations/`: Testes de upgrade e downgrade do Alembic.
* `tests/integration/bootstrap/`: Testes do provisionamento de perfis, permissões e administrador inicial.
* `tests/integration/ai/`: Testes do pipeline de pré-avaliação com o provedor fake.
* `tests/integration/journeys/`: Jornadas de ponta a ponta pela API pública, a partir de um deploy novo (bootstrap real, cadastro, login por cookie e troca de usuário).

### Padrões Adotados

1. **Testcontainers:** Inicialização de contêiner descartável PostgreSQL com extensão `pgvector` gerenciado na fixture de sessão do pytest.
2. **Factories:** Utilização de `Factory Boy` (`tests/factories/`) para geração declarativa de entidades nos testes.
3. **Padrão AAA:** Estruturação explícita de testes em *Arrange*, *Act* e *Assert*.

```python
from http import HTTPStatus
import pytest
from tests.factories.user_factory import UserFactory
from tests.api.routers.test_rbac_router import authenticate


@pytest.mark.asyncio
async def test_example_participant_listing(client, session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    response = client.get('/processes')

    assert response.status_code == HTTPStatus.OK
    assert 'items' in response.json()
```

---

## Execução com Docker

Execução dos serviços orquestrados via `compose.yaml`:

```bash
docker compose up --build -d

```

O contêiner executa automaticamente as migrações pendentes do Alembic via `entrypoint.sh` antes de inicializar o servidor.

* Documentação Interativa: `http://localhost:8000/docs`
* Logs da API: `docker compose logs -f api`
* Encerrar serviços: `docker compose down`

---

## Diretrizes de Contribuição

1. **Validação Local:** Execute linting, checagem de tipos e testes antes de submeter alterações (`ruff check`, `ruff format`, `pytest`).
2. **Modelos e Migrações:** Toda alteração nos modelos em `src/pivma/core/database/models.py` exige uma revisão Alembic descritiva gerada via `--autogenerate`.
3. **Rastreabilidade:** Novos modelos de dados relacionais devem herdar de `AuditMixin`.
4. **Segurança em Mutações:** Rotas de escrita devem aplicar validação de identidade autenticada (`CurrentUser`) e checagem de procedência segura (`TrustedOrigin`).

```
