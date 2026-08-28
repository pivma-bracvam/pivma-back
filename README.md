# PIVMA API

API Backend desenvolvida em **Python 3.14** utilizando o framework **FastAPI**, **SQLAlchemy 2.0** (Async), **Pydantic v2**, **Alembic**, **Argon2id** e banco de dados **PostgreSQL** (com extensão `pgvector`).

---

## 📌 Sumário
- [Pré-requisitos](#-pré-requisitos)
- [Requisitos Mínimos do `.env`](#-requisitos-mínimos-do-env)
- [Instalação e Configuração](#-instalação-e-configuração)
- [Executando Comandos com Poe-the-poet (`poe`)](#-executando-comandos-com-poe-the-poet-poe)
- [Cadastro de Usuários](#-cadastro-de-usuários)
- [Autorização RBAC](#-autorização-rbac)
- [Vinculação institucional](#-vinculação-institucional)
- [Práticas de Desenvolvimento e Testes](#-práticas-de-desenvolvimento-e-testes)
  - [Como os Testes Estão Estruturados](#como-os-testes-estão-estruturados)
  - [Como Criar um Novo Teste](#como-criar-um-novo-teste)
- [Execução com Docker & Docker Compose](#-execução-com-docker--docker-compose)
- [Boas Práticas de Desenvolvimento](#-boas-práticas-de-desenvolvimento)

---

## 🚀 Pré-requisitos

Para rodar e desenvolver este projeto localmente, certifique-se de possuir instalado:

- **Python 3.14** ou superior
- **Poetry** (Gerenciador de pacotes e ambientes virtuais)
- **Docker** e **Docker Compose** (opcional para rodar localmente, recomendado para a suíte de testes e banco PostgreSQL)

---

## 🔑 Requisitos Mínimos do `.env`

As configurações da aplicação são gerenciadas centralidamente pela classe `Settings` em [`src/pivma/core/settings.py`](file:///home/JASPION/BraCVAM/pivma-back/src/pivma/core/settings.py) via `pydantic-settings`.

### Variáveis Obrigatórias:

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `DATABASE_URL` | String de conexão assíncrona PostgreSQL via `psycopg3` | `postgresql+psycopg://db_user:db_password@localhost:5432/db` |

Você pode criar o seu arquivo `.env` a partir do template pré-definido:

```bash
cp .env.example .env
```

> [!NOTE]
> Quando estiver executando a aplicação dentro da rede de containers via **Docker Compose**, o host do banco de dados deve ser o nome do serviço (ex: `@db:5432/db`). Em desenvolvimento local fora do container, utilize `@localhost:5432/db`.

---

## ⚙️ Instalação e Configuração

1. **Clone o repositório:**
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd pivma-back
   ```

2. **Instale as dependências com o Poetry:**
   ```bash
   poetry install
   ```

3. **Crie o arquivo de ambiente `.env`:**
   ```bash
   cp .env.example .env
   ```

4. **Suba o banco de dados via Docker Compose (se rodar a API localmente):**
   ```bash
   docker compose up db -d
   ```

5. **Execute as migrações do banco de dados:**
   ```bash
   poetry run alembic upgrade head
   ```

---

## 👤 Cadastro de Usuários

**CONFIRMADO:** `POST /users/` cria uma conta e retorna HTTP 201 com `id`, `username` e `email`. A resposta não inclui a senha nem seu hash.

| Campo | Regra |
| :--- | :--- |
| `username` | De 3 a 64 caracteres; aceita letras ASCII, números, ponto, hífen e sublinhado. Espaços externos são removidos e a caixa é preservada. |
| `email` | Deve ter formato de e-mail válido. Espaços externos são removidos e a caixa é preservada. |
| `password` | De 8 a 128 caracteres Unicode, sem caracteres de espaço em branco. A API armazena somente um hash Argon2id. |

Username e e-mail são únicos entre usuários ativos sem distinguir maiúsculas de minúsculas. Um usuário com exclusão lógica libera ambos os identificadores para novo cadastro.

```bash
curl -X POST http://localhost:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"UmaSenhaSegura2026"}'
```

Conflitos retornam HTTP 409 com `Username already exists` ou `Email already exists`. Senhas inválidas retornam HTTP 422 com `{"detail":"Invalid password"}`. Falhas inesperadas retornam HTTP 500 sem detalhes internos.

Autenticação, login, JWT e recuperação de senha não fazem parte deste endpoint.

## 🔐 Autorização RBAC

Após aplicar as migrações, o backend disponibiliza autorização global por
perfis. O catálogo inicial é fechado e contém `rbac.read`,
`rbac.profiles.manage` e `rbac.assignments.manage`; somente a migração cria
essas permissões.

| Rota | Permissão necessária |
| --- | --- |
| `GET /rbac/permissions`, `GET /rbac/profiles`, `GET /rbac/users/{user_id}/access`, `GET /rbac/changes` | `rbac.read` |
| `POST /rbac/profiles`, `PATCH/DELETE /rbac/profiles/{profile_id}` | `rbac.profiles.manage` |
| `POST/DELETE /rbac/users/{user_id}/profiles/{profile_id}` | `rbac.assignments.manage` |

As mutações exigem cookie de sessão e o cabeçalho `Origin` configurado. O
backend consulta o estado atual das atribuições a cada pedido; não há cache de
permissões no token. Perfis e atribuições são encerrados por exclusão lógica,
preservando o histórico de concessões.

Em uma instalação nova, crie a conta inicial, aplique as migrações e execute
uma única vez o bootstrap para atribuir o perfil `Administrador`:

```bash
poetry run python -m pivma.bootstrap_rbac --user-id <UUID_DA_CONTA_ATIVA>
```

O comando é idempotente para a mesma conta e falha se outra conta já recebeu o
perfil. Ele não cria contas nem deve ser executado no startup da aplicação.

## 🏛 Vinculação institucional

A API mantém instituições, laboratórios e vínculos de usuários. A migração
inclui `institutional.read`, `institutional.catalogs.manage` e
`institutional.affiliations.manage` no perfil `Administrador`.

| Operações | Permissão necessária |
| --- | --- |
| `GET /institutional/institutions`, `GET /institutional/laboratories`, `GET /institutional/users/{user_id}/affiliations`, `GET /institutional/changes` | `institutional.read` |
| `POST`, `PATCH` e `DELETE` de instituições e laboratórios | `institutional.catalogs.manage` |
| `POST` e `DELETE /institutional/users/{user_id}/affiliations` | `institutional.affiliations.manage` |
| `GET /institutional/me/affiliations` | Conta autenticada |

As mutações exigem `Origin` confiável. Instituições, laboratórios e vínculos
usam inativação lógica e mantêm o histórico em `GET /institutional/changes`.
Uma conta sem leitura global consulta apenas os próprios vínculos efetivamente
ativos em `GET /institutional/me/affiliations`.

## 👥 Participantes de processo e conflito de interesse

A API designa, revoga e consulta participantes de um `ProcessInstance` e
registra declarações imutáveis de conflito de interesse. A migração inclui
`process.participants.manage` no perfil `Administrador`; uma designação
efetiva do papel local `group_manager` concede a mesma capacidade somente no
processo em que está ativa.

Papéis locais aprovados: `group_manager`, `study_manager`, `statistician`,
`adhoc_evaluator`, `peer_reviewer`, `proponent` e os dois papéis
laboratoriais `lead_laboratory` e `participating_laboratory`, que exigem
`laboratory_id` e vínculo institucional vigente entre o usuário e o
laboratório.

| Operação | Rota | Autorização |
| --- | --- | --- |
| Listar participantes atuais | `GET /processes/{process_id}/participants` | gestor (global ou local) vê todos; participante vê os próprios ciclos |
| Designar participante | `POST /processes/{process_id}/participants` | `process.participants.manage` ou `group_manager` efetivo do processo |
| Revogar designação | `DELETE /processes/{process_id}/participants/{assignment_id}` | `process.participants.manage` ou `group_manager` efetivo do processo |
| Declarar conflito de interesse | `POST /processes/{process_id}/participants/{assignment_id}/conflicts` | titular ativo da designação |
| Consultar histórico paginado | `GET /processes/{process_id}/participants/history` | mesmo escopo da listagem atual |

As três mutações exigem `Origin` confiável. Declarações são *append-only*:
cada nova declaração cria uma linha e a mais recente (por `declared_at` e,
em empate, pelo maior `id`) define o estado do ciclo. Qualquer ciclo ativo
do usuário com conflito vigente bloqueia a gravação de revisões de campo
(`POST /processes/{id}/triage/reviews`) e decisões de triagem
(`POST /processes/{id}/triage/decision`) com `403`, mesmo quando outro papel
ativo do mesmo usuário autorizaria a ação. A timeline do processo
(`GET /processes/{id}/timeline`) filtra os eventos `PARTICIPANT_ASSIGNED`,
`PARTICIPANT_REVOKED` e `CONFLICT_DECLARED` pelo mesmo critério: gestores
veem todos, participantes veem somente os próprios eventos e pessoas
externas ao processo não os recebem.

---

## 🛠 Executando Comandos com Poe-the-poet (`poe`)

O projeto utiliza o **Poe-the-poet** como *task runner* declarativo, configurado no arquivo [`pyproject.toml`](file:///home/JASPION/BraCVAM/pivma-back/pyproject.toml).

Os comandos disponíveis são:

### 1. Iniciar o servidor de desenvolvimento
```bash
poetry serve
```
Executa a API com hot-reload ativado apontando para o arquivo de entrada `src/pivma/__init__.py`.

### 2. Verificar qualidade e padrões de código (*Linter*)
```bash
poetry lint
```
Roda a verificação de código com o **Ruff** sem alterar arquivos.

### 3. Formatação automática e correção de *Lints*
```bash
poetry format
```
Executa uma sequência automatizada:
- Analisa lints com `ruff check`
- Aplica correções automáticas seguras com `ruff check --fix`
- Formata o código fonte com `ruff format`

### 4. Executar os testes automatizados
```bash
poetry test
```
Executa a suíte de testes com `pytest` (interrompe no primeiro erro `-x`, formato verboso `-vv`) e gera um relatório completo de cobertura de código em HTML na pasta `htmlcov/`.

Você também pode passar argumentos extras para o Pytest através de `$POE_EXTRA_ARGS`:
```bash
# Executar apenas um teste específico
poetry test -k test_create_user
```

---

## 🧪 Práticas de Desenvolvimento e Testes

### Como os Testes Estão Estruturados

A suíte de testes utiliza **Pytest**, **Testcontainers**, **Factory Boy** e o **TestClient** do FastAPI.

1. **Containers de Banco de Dados Isolados em Tempo de Teste**:
   - A fixture `engine` em [`tests/conftest.py`](file:///home/JASPION/BraCVAM/pivma-back/tests/conftest.py#L31-L45) utiliza a biblioteca `testcontainers-postgres` (`PostgresContainer`).
   - Ao rodar os testes em ambientes Linux/macOS, um container descartável PostgreSQL com a imagem `pgvector/pgvector:pg17` é levantado automaticamente e destruído ao final da sessão, garantindo isolamento total contra a base de produção/dev.

2. **Injeção de Sessão e Dependency Override**:
   - A fixture `client` substitui a dependência `get_session` da aplicação para forçar as rotas a utilizarem a sessão de teste assíncrona (`AsyncSession`).

3. **Geração de Dados Fictícios com Factory Boy**:
   - Para evitar cadastros manuais repetitivos, utilizamos `UserFactory` em [`tests/conftest.py`](file:///home/JASPION/BraCVAM/pivma-back/tests/conftest.py#L100-L107) com atributos dinâmicos (`factory.Sequence` e `factory.LazyAttribute`).

4. **Mock Temporal para Banco de Dados**:
   - A fixture `mock_db_time` permite congelar a data/hora dos eventos de inserção (`before_insert`) do SQLAlchemy (`created_at`, `updated_at`), tornando assertions temporais determinísticas.

---

### Como Criar um Novo Teste

Para adicionar novos testes de rotas ou regras de negócio:

1. **Localização**: Crie o arquivo dentro da subpasta correspondente em `tests/` (ex: `tests/routers/test_exemplo.py`).
2. **Padrão AAA (Arrange, Act, Assert)**:
   - **Arrange**: Prepare os dados de entrada ou utilize fixtures (`client`, `user`, `session`).
   - **Act**: Faça a requisição via `client` ou invoque a função da regra de negócio.
   - **Assert**: Valide o código de status HTTP (`HTTPStatus`) e o corpo do JSON retornado.

#### Exemplo de Teste de Rota (`tests/routers/test_user.py`):

```python
from http import HTTPStatus


def test_create_user(client):
    # Act
    response = client.post(
        '/users/',
        json={
            'username': 'alice',
            'email': 'alice@example.com',
            'password': 'UmaSenhaSegura2026',
        },
    )
    # Assert
    assert response.status_code == HTTPStatus.CREATED
    assert 'id' in response.json()
    assert response.json()['username'] == 'alice'
    assert response.json()['email'] == 'alice@example.com'
```

#### Exemplo de Teste com Fixtures Existentes (`user`):

```python
from http import HTTPStatus


def test_create_user_already_exists_username(client, user):
    response = client.post(
        '/users/',
        json={
            'username': user.username,  # Tenta usar username que já existe no banco
            'email': 'different@example.com',
            'password': 'UmaSenhaSegura2026',
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}
```

---

## 🐳 Execução com Docker & Docker Compose

### 1. Subindo toda a aplicação com Docker Compose (Recomendado)

O arquivo [`compose.yaml`](file:///home/JASPION/BraCVAM/pivma-back/compose.yaml) orquestra a API e o banco de dados PostgreSQL `pgvector`:

```bash
# Subir containers em background e forçar o build da imagem
docker compose up --build -d
```

O `compose.yaml` executa automaticamente o script [`entrypoint.sh`](file:///home/JASPION/BraCVAM/pivma-back/entrypoint.sh), aplicando as migrações do Alembic (`alembic upgrade head`) antes de iniciar o servidor Uvicorn.

- **Acessar a documentação Swagger**: `http://localhost:8000/docs`
- **Acompanhar os logs**: `docker compose logs -f api`
- **Parar a execução**: `docker compose down`

### 2. Construindo e Executando apenas a imagem da API isoladamente

Caso queira fazer o build manual apenas da imagem Docker da API:

```bash
# Build da imagem
docker build -t pivma_api .

# Execução do container passando o .env
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name pivma_app \
  pivma_api
```

---

## 💡 Boas Práticas de Desenvolvimento

1. **Format/Lint antes de enviar Código**:
   Execute sempre `poetry format` e `poetry test` antes de abrir *Pull Requests* ou efetuar commits.

2. **Criação de Migrações do Banco de Dados (Alembic)**:
   Ao alterar modelos em [`src/pivma/core/database/models.py`](file:///home/JASPION/BraCVAM/pivma-back/src/pivma/core/database/models.py), gere uma nova migração autogerada:
   ```bash
   poetry run alembic revision --autogenerate -m "add nova coluna x"
   poetry run alembic upgrade head
   ```

3. **Modelos ORM com AuditMixin**:
   Todos os novos modelos de tabela devem estender `AuditMixin` presente em `models.py` para registrar automaticamente `created_at`, `updated_at`, `deleted_at` e os IDs dos usuários criadores/editores (`created_by`, `updated_by`).

4. **Separação de Camadas e Padrões FastAPI**:
   - **Schemas (`src/pivma/schemas.py`)**: Utilizados para validação de entrada/saída (DTOs) com `Pydantic`. Nunca exponha hashes de senha ou colunas internas em `response_model`.
   - **Routers (`src/pivma/routers/`)**: Mantenha os endpoints focados, delegando injeção de dependências via `Annotated[AsyncSession, Depends(get_session)]`.
