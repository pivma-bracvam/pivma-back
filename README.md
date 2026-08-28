# PIVMA API

API Backend desenvolvida em Python 3.14 utilizando FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic, Argon2id e banco de dados PostgreSQL com extensão `pgvector`.

---

## Sumário

- [Pré-requisitos](#pré-requisitos)
- [Requisitos Mínimos do `.env`](#requisitos-mínimos-do-env)
- [Instalação e Configuração](#instalação-e-configuração)
- [Cadastro de Usuários](#cadastro-de-usuários)
- [Autorização RBAC](#autorização-rbac)
- [Vinculação Institucional](#vinculação-institucional)
- [Processos, Submissão e Triagem](#processos-submissão-e-triagem)
- [Participantes de Processo e Conflito de Interesse](#participantes-de-processo-e-conflito-de-interesse)
- [Executando Comandos com Poe-the-poet (`poe`)](#executando-comandos-com-poe-the-poet-poe)
- [Práticas de Desenvolvimento e Testes](#práticas-de-desenvolvimento-e-testes)
  - [Estrutura da Suíte de Testes](#estrutura-da-suíte-de-testes)
  - [Padrão para Criação de Testes](#padrão-para-criação-de-testes)
- [Execução com Docker e Docker Compose](#execução-com-docker-e-docker-compose)
- [Diretrizes de Desenvolvimento](#diretrizes-de-desenvolvimento)

---

## Pré-requisitos

Para executar e desenvolver o projeto localmente, são necessários:

- **Python 3.14** ou superior
- **Poetry** (gerenciador de dependências e ambientes virtuais)
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

1. **Clonar o repositório:**
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd pivma-back
   ```

2. **Instalar dependências com Poetry:**
   ```bash
   poetry install
   ```

3. **Configurar variáveis de ambiente:**
   ```bash
   cp .env.example .env
   ```

4. **Iniciar o banco de dados via Docker Compose:**
   ```bash
   docker compose up db -d
   ```

5. **Executar migrações do banco de dados:**
   ```bash
   poetry run alembic upgrade head
   ```

6. **Carregar templates declarativos de processos:**
   ```bash
   poetry run python -m pivma.bootstrap_process_templates
   ```

7. **Configurar o usuário administrador inicial (bootstrap RBAC):**
   Após cadastrar a primeira conta, vincule o perfil `Administrador`:
   ```bash
   poetry run python -m pivma.bootstrap_rbac --user-id <UUID_DA_CONTA_ATIVA>
   ```

---

## Cadastro de Usuários

O endpoint `POST /users/` registra uma nova conta e retorna HTTP 201 com `id`, `username` e `email`. A resposta não expõe a senha nem seu hash.

| Campo | Regra de Validação |
| :--- | :--- |
| `username` | 3 a 64 caracteres; aceita letras ASCII, números, ponto, hífen e sublinhado. Espaços externos são removidos e a caixa original é preservada. |
| `email` | Formato de e-mail RFC válido. Espaços externos são removidos e a caixa original é preservada. |
| `password` | 8 a 128 caracteres Unicode, sem espaços em branco. O hash é gerado com Argon2id. |

Identificadores `username` e `email` são únicos entre contas ativas com comparação case-insensitive. Contas com exclusão lógica liberam os identificadores para novos cadastros.

```bash
curl -X POST http://localhost:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"UmaSenhaSegura2026"}'
```

- Conflito de unicidade retorna HTTP 409 (`Username already exists` ou `Email already exists`).
- Senhas fora da política retornam HTTP 422 (`{"detail":"Invalid password"}`).
- Falhas de infraestrutura retornam HTTP 500 sem vazamento de detalhes internos.

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

## Executando Comandos com Poe-the-poet (`poe`)

O projeto utiliza o **Poe-the-poet** como executor de tarefas declarado em [`pyproject.toml`](pyproject.toml).

```bash
# Iniciar servidor de desenvolvimento com hot-reload
poetry run poe serve

# Executar verificação estática de código com Ruff
poetry run poe lint

# Formatar código e aplicar correções automáticas seguras
poetry run poe format

# Executar a suíte de testes com relatório de cobertura HTML
poetry run poe test
```

Para executar o Pytest diretamente com parâmetros adicionais:

```bash
# Executar apenas testes de uma rota específica
poetry run pytest tests/api/routers/test_participant_router.py -v

# Executar filtrando por nome de teste
poetry run pytest -k "test_current_conflict"
```

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

1. **Verificação Prévia:** execute `poetry run poe format`, `poetry run poe lint` e `poetry run pytest` antes de submeter alterações.
2. **Migrações de Banco de Dados:** ao alterar modelos em [`src/pivma/core/database/models.py`](src/pivma/core/database/models.py), gere uma revisão com nome descritivo:
   ```bash
   poetry run alembic revision --autogenerate -m "descricao_da_migracao"
   poetry run alembic upgrade head
   ```
3. **AuditMixin:** novos modelos relacionais devem herdar de `AuditMixin` para rastreamento de criação, atualização e exclusão lógica.
4. **Proteção de Origem e Cookies:** rotas de mutação protegidas devem validar `CurrentUser` e `TrustedOrigin`.
