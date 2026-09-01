# PIVMA API

API Backend desenvolvida em Python 3.14 utilizando FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic, Argon2id e banco de dados PostgreSQL com extensão `pgvector`.

---

## Sumário

- [Pré-requisitos](#pré-requisitos)
- [Requisitos Mínimos do `.env`](#requisitos-mínimos-do-env)
- [Instalação e Configuração](#instalação-e-configuração)
- [Semeadura Completa do Banco (Seed Demo)](#semeadura-completa-do-banco-seed-demo)
- [Protótipos Interativos Isolados](#protótipos-interativos-isolados)
- [Promoção de Usuários e Gestão de Cargos](#promoção-de-usuários-e-gestão-de-cargos)
- [Guia de Integração para o Frontend](#guia-de-integração-para-o-frontend)
- [Cadastro de Usuários](#cadastro-de-usuários)
- [Autorização RBAC](#autorização-rbac)
- [Vinculação Institucional](#vinculação-institucional)
- [Processos, Submissão e Triagem](#processos-submissão-e-triagem)
- [Participantes de Processo e Conflito de Interesse](#participantes-de-processo-e-conflito-de-interesse)
- [Comandos Úteis (`poetry` e `uv`)](#comandos-úteis-poetry-e-uv)
- [Práticas de Desenvolvimento e Testes](#práticas-de-desenvolvimento-e-testes)
  - [Estrutura da Suíte de Testes](#estrutura-da-suíte-de-testes)
  - [Padrão para Criação de Testes](#padrão-para-criação-de-testes)
- [Execução com Docker e Docker Compose](#execução-com-docker-e-docker-compose)
- [Diretrizes de Desenvolvimento](#diretrizes-de-desenvolvimento)

---

## Pré-requisitos

Para executar e desenvolver o projeto localmente, são necessários:

- **Python 3.14** ou superior
- **Poetry** ou **uv** (gerenciador de dependências e ambientes virtuais)
- **Docker** e **Docker Compose** (para PostgreSQL local com `pgvector` e execução de testes isolados)

---

## Requisitos Mínimos do `.env`

As configurações da aplicação são gerenciadas centralmente pela classe `Settings` em [`src/pivma/core/settings.py`](src/pivma/core/settings.py) via `pydantic-settings`.

### Variáveis Obrigatórias

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `DATABASE_URL` | String de conexão assíncrona PostgreSQL via `psycopg` | `postgresql+psycopg://db_user:db_password@localhost:5432/db` |
| `APP_ENV` | Ambiente de execução (`development`, `staging`, `production`) | `development` |
| `SECRET_KEY` | Chave secreta para assinatura de tokens e integridade de sessão | `sua-chave-secreta-de-producao` |

Crie o arquivo `.env` a partir do modelo:

```bash
cp .env.example .env
```

> [!NOTE]
> Ao executar a aplicação dentro da rede de contêineres via Docker Compose, o host do banco de dados deve ser o nome do serviço (ex.: `@db:5432/db`). Em desenvolvimento local direto no host, utilize `@localhost:5432/db`.

---

## Instalação e Configuração

Você pode utilizar tanto **Poetry** quanto **uv** para gerenciar o ambiente:

### Com Poetry:

```bash
# 1. Instalar dependências
poetry install

# 2. Iniciar o banco de dados local
docker compose up db -d

# 3. Aplicar migrações do banco de dados
poetry run alembic upgrade head

# 4. Carregar templates declarativos de processos
poetry run python -m pivma.bootstrap_process_templates

# 5. Iniciar o servidor de desenvolvimento
poetry run poe serve
```

### Com uv:

```bash
# 1. Sincronizar dependências
uv sync

# 2. Iniciar o banco de dados local
docker compose up db -d

# 3. Aplicar migrações do banco de dados
uv run alembic upgrade head

# 4. Carregar templates declarativos de processos
uv run python -m pivma.bootstrap_process_templates

# 5. Iniciar o servidor de desenvolvimento
uv run fastapi dev src/pivma/__init__.py
```

---

## Semeadura Completa do Banco (Seed Demo)

Para inicializar rapidamente um ambiente local completo de desenvolvimento, testes e protótipos, utilize o script unificado `pivma.seed_demo`.

Esse script executa automaticamente:
1. Sincronização dos templates declarativos de processos e formulários YAML (`full_validation_v1.yaml`).
2. Criação das contas de demonstração para todos os papéis canônicos.
3. Promoção automática do Administrador do sistema (`bootstrap_administrator`).
4. Atribuição dos perfis de acesso globais RBAC (`proponent`, `management_group`, `ad_hoc_evaluator`).
5. Criação de instituição de demonstração (*Fiocruz*) e laboratório com filiação dos usuários.

### Executar a Semeadura:

```bash
# Com Poetry:
poetry run python -m pivma.seed_demo

# Com uv:
uv run python -m pivma.seed_demo
```

### Contas de Demonstração Criadas:

| Papel / Perfil | Nome | E-mail | Usuário | Senha Padrão |
| :--- | :--- | :--- | :--- | :--- |
| **Administrador** | Administrador Geral | `admin@bracvam.gov.br` | `admin` | `Password123!` |
| **Proponente** | Dra. Helena Souza | `helena.proponente@fiocruz.br` | `helena.souza` | `Password123!` |
| **Grupo Gestor / Triador** | Dr. Carlos Mendes | `carlos.gestor@bracvam.gov.br` | `carlos.mendes` | `Password123!` |
| **Avaliador Ad Hoc** | Dr. Roberto Silva | `avaliador.adhoc@fiocruz.br` | `roberto.silva` | `Password123!` |

---

## Protótipos Interativos Isolados

O repositório disponibiliza protótipos interativos acessíveis diretamente no navegador através da rota `/prototypes/` quando o backend está em execução (`poetry run poe serve` ou `uv run fastapi dev src/pivma/__init__.py`).

### Catálogo de Protótipos:

- **Hub Central de Protótipos:**
  - URL: `http://localhost:8000/prototypes/`
  - Descrição: Catálogo unificado com visão geral de todos os fluxos do sistema e status do ambiente.
- **Modelagem, Preenchimento e Triagem de Formulários (Fase 1):**
  - URL: `http://localhost:8000/prototypes/forms-and-triage/`
  - Descrição: Ambiente interativo dividido em 3 sessões integradas:
    - **Sessão 1:** Construtor e editor dinâmico de campos (*Form Builder*);
    - **Sessão 2:** Preenchimento da proposta pelo Proponente com validações em tempo real e submissão formal ("Dar OK");
    - **Sessão 3:** Avaliação técnica pelo Triador BraCVAM com apontamento de parecer campo a campo e deliberação (Aprovação, Rejeição ou Solicitação de Diligência).

---

## Promoção de Usuários e Gestão de Cargos

A aplicação divide permissões e papéis em dois níveis distintos: **Perfis Globais (RBAC)** e **Papéis Locais de Processo (Designações)**.

### 1. Criar e Promover o Primeiro Administrador (Bootstrap CLI)

Para o primeiro acesso administrativo ao sistema:

1. Registre uma conta comum via `POST /users` (ou use uma conta criada previamente) e copie o `id` (UUID) retornado.
2. Execute o script de bootstrap no terminal:

```bash
# Com Poetry:
poetry run python -m pivma.bootstrap_rbac --user-id <UUID_DO_USUARIO>

# Com uv:
uv run python -m pivma.bootstrap_rbac --user-id <UUID_DO_USUARIO>
```

> [!IMPORTANT]
> Esse comando atribui o perfil global `Administrador` (que contém permissões para gerenciar outros perfis, catálogos institucionais e participantes). O comando é idempotente para o mesmo usuário e falha caso outra conta já possua o perfil `Administrador`.

### 2. Atribuir Outros Cargos/Perfis Globais (via API)

Com uma conta de Administrador autenticada:

1. **Listar perfis disponíveis:**
   ```http
   GET /rbac/profiles
   ```
   *Perfis pré-semeados na migração:* `Administrador`, `Grupo Gestor`, `Gerente do Estudo`, `Laboratório Participante`, `Avaliador Ad Hoc`, `Revisor`, `Especialista`, `Analista Estatístico`.

2. **Atribuir perfil a um usuário:**
   ```http
   POST /rbac/users/{user_id}/profiles/{profile_id}
   ```

3. **Revogar perfil de um usuário:**
   ```http
   DELETE /rbac/users/{user_id}/profiles/{profile_id}
   ```

### 3. Consultar Contas para Administração

Uma conta com a permissão `users.read` pode consultar a listagem administrativa:

```http
GET /users?search=joao&active=true&profile_id=<UUID>&offset=0&limit=20
```

Os parâmetros são opcionais. A consulta usa contas ativas por padrão, remove
espaços externos de `search`, procura por substring literal sem distinção de
caixa em username ou e-mail e aceita `active=false` para contas inativas.
`profile_id` considera somente atribuições ativas a perfis ativos. `offset`
começa em zero e `limit` aceita valores entre 1 e 100, com padrão 100.

A resposta ordena por username sem distinção de caixa e usa o UUID como
desempate. Cada item contém somente `id`, `username`, `email` e `active`:

```json
{
  "offset": 0,
  "limit": 20,
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "username": "joao",
      "email": "joao@example.com",
      "active": true
    }
  ]
}
```

### 4. Designar Papéis Locais em um Processo Específico

A designação local vincula um usuário a uma instância de processo (`ProcessInstance`):

```http
POST /processes/{process_id}/participants
Content-Type: application/json

{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "role_key": "ad_hoc_evaluator",
  "laboratory_id": null
}
```

- **Papéis gerais:** `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`, `proponent`.
- **Papéis laboratoriais:** `lead_laboratory`, `participating_laboratory` (campo `laboratory_id` é obrigatório e o usuário deve ter vínculo institucional ativo com aquele laboratório).

---

## Guia de Integração para o Frontend

Esta seção sintetiza os pontos fundamentais para o desenvolvimento e integração da interface com a API.

### 1. Autenticação e Transporte de Sessão por Cookies

- **Login (`POST /auth/token`):** A autenticação bem-sucedida envia um cookie `access_token` seguro (`HttpOnly`, `SameSite=Lax`).
- **Requisições autenticadas:** O navegador envia o cookie automaticamente. No cliente HTTP do frontend (como `axios` ou `fetch`), configure `credentials: 'include'` (ou `withCredentials: true`).
- **Logout (`POST /auth/logout`):** Invalida a sessão e limpa o cookie.

Após o login, `GET /auth/me` retorna a identidade autenticada e o estado de
acesso necessário para inicializar a interface. O campo `access` contém as
permissões globais efetivas e os escopos ativos por processo:

```json
{
  "id": "...",
  "username": "maria",
  "email": "maria@exemplo.org",
  "user": {
    "id": "...",
    "username": "maria",
    "email": "maria@exemplo.org"
  },
  "access": {
    "global_permissions": ["rbac.read"],
    "scopes": [
      {
        "process_id": "...",
        "institution_id": null,
        "laboratory_id": null,
        "roles": ["proponent"]
      }
    ]
  }
}
```

Esses dados apoiam a renderização da interface. As rotas protegidas continuam
reavaliando a autorização no banco a cada requisição.

### 2. Proteção CSRF e Cabeçalho `Origin`

Todas as requisições de mutação protegidas (`POST`, `PUT`, `PATCH`, `DELETE`) validam a procedência da requisição:
- O navegador inclui o cabeçalho `Origin` automaticamente em chamadas CORS/Fetch.
- Em desenvolvimento, certifique-se de que a URL do frontend (ex.: `http://localhost:3000` ou `http://localhost:5173`) esteja na lista de origens confiáveis da configuração.

### 3. Consultas Úteis para o Estado da Interface

| Finalidade | Endpoint | Como a UI deve usar |
| :--- | :--- | :--- |
| **Vínculos e Laboratórios do Usuário** | `GET /institutional/me/affiliations` | Carrega os laboratórios ativos aos quais o usuário logado pertence para seleção em formulários |
| **Permissões Globais Efetivas** | `GET /rbac/users/{id}/access` | Define permissões administrativas e menus visíveis |
| **Participantes e Conflitos no Processo** | `GET /processes/{process_id}/participants` | Mostra quem está atuando no processo e se há bandeira de conflito ativo (`has_conflict: true`) |
| **Formulários Dinâmicos da Fase** | `GET /processes/{id}/forms/{form_key}` | Renderiza os campos de entrada, validações e rascunhos da proposta/triagem |
| **Minhas Tarefas Pendentes** | `GET /tasks` | Lista as ações que exigem atuação do usuário logado |

### 4. Tratamento de Erros e Códigos de Status

- `HTTP 200 / 201 / 204`: Sucesso na consulta / criação / exclusão.
- `HTTP 401 Unauthorized`: Sessão expirada ou ausente. Redirecionar para tela de login.
- `HTTP 403 Forbidden`: Usuário sem permissão **OU usuário com conflito de interesse vigente** tentando avaliar/decidir no processo. Exibir mensagem explicativa.
- `HTTP 404 Not Found`: Entidade (processo, formulário, usuário, laboratório) inexistente.
- `HTTP 409 Conflict`: Conflito de regra de negócio (ex.: e-mail já cadastrado, usuário já designado com aquele papel, processo ou usuário inativo).
- `HTTP 422 Unprocessable Entity`: Validação de schema do payload (campos obrigatórios ausentes, tipos incorretos).

---

## Cadastro de Usuários

O endpoint `POST /users` registra uma nova conta e retorna HTTP 201 com `id`, `username` e `email`. A resposta não expõe a senha nem seu hash.

| Campo | Regra de Validação |
| :--- | :--- |
| `username` | 3 a 64 caracteres; aceita letras ASCII, números, ponto, hífen e sublinhado. Espaços externos são removidos e a caixa original é preservada. |
| `email` | Formato de e-mail RFC válido. Espaços externos são removidos e a caixa original é preservada. |
| `password` | 8 a 128 caracteres Unicode, sem espaços em branco. O hash é gerado com Argon2id. |

Identificadores `username` e `email` são únicos entre contas ativas com comparação case-insensitive. Contas com exclusão lógica liberam os identificadores para novos cadastros.

```bash
curl -X POST http://localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"UmaSenhaSegura2026"}'
```

- Conflito de unicidade retorna HTTP 409 (`Username already exists` ou `Email already exists`).
- Senhas fora da política retornam HTTP 422 (`{"detail":"Invalid password"}`).
- Falhas de infraestrutura retornam HTTP 500 sem vazamento de detalhes internos.

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

---

## Autorização RBAC

Após as migrações, a aplicação disponibiliza controle de acesso baseado em papéis (RBAC). O catálogo de permissões é estrito e inclui:

| Rota | Permissão Necessária |
| :--- | :--- |
| `GET /rbac/permissions`, `GET /rbac/profiles`, `GET /rbac/users/{user_id}/access`, `GET /rbac/changes` | `rbac.read` |
| `POST /rbac/profiles`, `PATCH/DELETE /rbac/profiles/{profile_id}` | `rbac.profiles.manage` |
| `POST/DELETE /rbac/users/{user_id}/profiles/{profile_id}` | `rbac.assignments.manage` |

Operações de mutação exigem cookie de autenticação e validação do cabeçalho `Origin`. O backend verifica as atribuições diretamente no banco a cada requisição, sem cache em token. Perfis e atribuições utilizam exclusão lógica (`deleted_at`), mantendo histórico completo de concessões.

---

## Vinculação Institucional

A API gerencia o catálogo de instituições, laboratórios e vínculos institucionais de usuários. A migração inicial concede permissões institucionais exclusivamente ao perfil `Administrador`.

| Operação | Rota | Permissão Necessária |
| :--- | :--- | :--- |
| Listar instituições e laboratórios | `GET /institutional/institutions`, `GET /institutional/laboratories` | `institutional.read` |
| Consultar vínculos de terceiros | `GET /institutional/users/{user_id}/affiliations` | `institutional.read` |
| Trilha de alterações institucionais | `GET /institutional/changes` | `institutional.read` |
| Gerenciar instituições e laboratórios | `POST`, `PATCH`, `DELETE /institutional/institutions/{id}`, `/institutional/laboratories/{id}` | `institutional.catalogs.manage` |
| Gerenciar vínculos de usuários | `POST`, `DELETE /institutional/users/{user_id}/affiliations` | `institutional.affiliations.manage` |
| Consultar próprios vínculos ativos | `GET /institutional/me/affiliations` | Conta autenticada |

Mutações exigem cabeçalho `Origin` confiável. Instituições, laboratórios e vínculos inativos utilizam exclusão lógica e são auditados em `InstitutionalChange`.

---

## Processos, Submissão e Triagem

O módulo de processos gerencia instâncias de validação analítica, formulários dinâmicos e o ciclo de triagem da Fase 1.

| Operação | Rota | Descrição |
| :--- | :--- | :--- |
| Criar processo | `POST /processes` | Inicia uma nova instância a partir de um template versionado |
| Listar processos | `GET /processes` | Lista instâncias ativas com filtros por status e código |
| Timeline do processo | `GET /processes/{id}/timeline` | Consulta trilha cronológica determinística de auditoria |
| Obter formulário | `GET /processes/{id}/forms/{form_key}` | Retorna esquema e valores do formulário dinâmico |
| Preencher rascunho | `PUT /processes/{id}/forms/{form_key}` | Salva valores preliminares sem avançar o fluxo |
| Submeter formulário | `POST /processes/{id}/forms/{form_key}/submit` | Valida campos obrigatórios, bloqueia edição e avança etapa |
| Avaliar campos na triagem | `POST /processes/{id}/triage/reviews` | Registra pareceres técnicos por campo da proposta |
| Decisão de triagem | `POST /processes/{id}/triage/decision` | Registra aprovação, rejeição ou pedido de ajuste |
| Listar tarefas | `GET /tasks` | Lista e filtra tarefas pendentes por processo, papel ou executor |

---

## Participantes de Processo e Conflito de Interesse

A API permite designar, revogar e consultar participantes de um `ProcessInstance` e registrar declarações imutáveis de conflito de interesse.

### Papéis Locais Suportados

- **Gestão e avaliação técnica:** `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`
- **Proponente:** `proponent` (atribuído ao criador do processo)
- **Papéis laboratoriais:** `lead_laboratory`, `participating_laboratory` (exigem `laboratory_id` e vínculo institucional ativo entre usuário e laboratório)

### Matriz de Endpoints

| Operação | Rota | Autorização |
| :--- | :--- | :--- |
| Listar participantes atuais | `GET /processes/{process_id}/participants` | Gestor (global ou local) vê todos; participante vê apenas seus ciclos |
| Designar participante | `POST /processes/{process_id}/participants` | `process.participants.manage` ou `group_manager` ativo do processo |
| Revogar designação | `DELETE /processes/{process_id}/participants/{assignment_id}` | `process.participants.manage` ou `group_manager` ativo do processo |
| Declarar conflito de interesse | `POST /processes/{process_id}/participants/{assignment_id}/conflicts` | Titular ativo da designação |
| Consultar histórico paginado | `GET /processes/{process_id}/participants/history` | Mesmo escopo de leitura da listagem |

### Regras de Conflito de Interesse

- **Append-only:** cada submissão cria um novo registro imutável em `ConflictInterestDeclaration`. A declaração mais recente define o estado vigente do ciclo.
- **Bloqueio abrangente:** se o usuário possuir conflito vigente em qualquer ciclo ativo no processo, o backend bloqueia a submissão de revisões de campo (`POST /processes/{id}/triage/reviews`) e decisões de triagem (`POST /processes/{id}/triage/decision`) com HTTP 403 Forbidden, mesmo que possua outro papel sem conflito.
- **Isolamento de justificativa:** o texto da justificativa de conflito é restrito ao declarante e aos gestores do processo, não sendo exposto na listagem geral.
- **Filtragem de auditoria:** eventos `PARTICIPANT_ASSIGNED`, `PARTICIPANT_REVOKED` e `CONFLICT_DECLARED` na timeline respeitam o escopo de leitura do usuário solicitante.

---

## Comandos Úteis (`poetry` e `uv`)

Tabela comparativa de comandos rápidos para o dia a dia de desenvolvimento:

| Ação | Com Poetry | Com uv |
| :--- | :--- | :--- |
| **Instalar dependências** | `poetry install` | `uv sync` |
| **Servidor com hot-reload** | `poetry run poe serve` | `uv run fastapi dev src/pivma/__init__.py` |
| **Verificar Lints** | `poetry run poe lint` | `uv run ruff check` |
| **Formatar Código** | `poetry run poe format` | `uv run ruff format` |
| **Executar Testes** | `poetry run poe test` | `uv run pytest` |
| **Aplicar Migrações** | `poetry run alembic upgrade head` | `uv run alembic upgrade head` |
| **Bootstrap Templates** | `poetry run python -m pivma.bootstrap_process_templates` | `uv run python -m pivma.bootstrap_process_templates` |
| **Bootstrap Admin** | `poetry run python -m pivma.bootstrap_rbac --user-id <UUID>` | `uv run python -m pivma.bootstrap_rbac --user-id <UUID>` |

---

## Práticas de Desenvolvimento e Testes

### Estrutura da Suíte de Testes

A suíte de testes é organizada em níveis de granularidade:

- `tests/unit/`: testes unitários isolados de schemas, segurança e regras de validação.
- `tests/api/routers/`: testes de contrato HTTP, autorização e códigos de status via `TestClient`.
- `tests/integration/database/`: testes de integridade relacional, concorrência e constraints no PostgreSQL.
- `tests/integration/migrations/`: testes de aplicação e downgrade de migrações Alembic.

### Padrão para Criação de Testes

1. **Isolamento com Testcontainers:**
   A fixture `engine` em [`tests/conftest.py`](tests/conftest.py) inicializa um contêiner PostgreSQL descartável com imagem `pgvector/pgvector:pg17` fora do Windows, destruído ao final da execução.

2. **Geração de Entidades com Factory Boy:**
   Utilize as factories disponíveis em [`tests/factories/`](tests/factories/) (`UserFactory`, `InstitutionFactory`, `LaboratoryFactory`, `AssignmentFactory`, `ConflictInterestDeclarationFactory`) em vez de inserções SQL manuais.

3. **Padrão AAA (Arrange, Act, Assert):**

```python
from http import HTTPStatus
import pytest
from tests.factories.user_factory import UserFactory
from tests.api.routers.test_rbac_router import authenticate


@pytest.mark.asyncio
async def test_example_participant_listing(client, session):
    # Arrange
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # Act
    response = client.get('/processes')

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert 'items' in response.json()
```

---

## Execução com Docker e Docker Compose

### Executar Ambiente Completo

O arquivo [`compose.yaml`](compose.yaml) orquestra a API e o banco de dados PostgreSQL:

```bash
docker compose up --build -d
```

O contêiner executa automaticamente [`entrypoint.sh`](entrypoint.sh), aplicando as migrações do Alembic antes de iniciar o Uvicorn.

- Documentação Swagger Interativa: `http://localhost:8000/docs`
- Logs da API: `docker compose logs -f api`
- Encerrar serviços: `docker compose down`

---

## Diretrizes de Desenvolvimento

1. **Verificação Prévia:** execute `poetry run poe format`, `poetry run poe lint` e `poetry run pytest` (ou os equivalentes `uv`) antes de submeter alterações.
2. **Migrações de Banco de Dados:** ao alterar modelos em [`src/pivma/core/database/models.py`](src/pivma/core/database/models.py), gere uma revisão com nome descritivo:
   ```bash
   poetry run alembic revision --autogenerate -m "descricao_da_migracao"
   poetry run alembic upgrade head
   ```
3. **AuditMixin:** novos modelos relacionais devem herdar de `AuditMixin` para rastreamento de criação, atualização e exclusão lógica.
4. **Proteção de Origem e Cookies:** rotas de mutação protegidas devem validar `CurrentUser` e `TrustedOrigin`.
