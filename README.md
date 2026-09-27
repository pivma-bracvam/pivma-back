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
  - [Amostras Cegas](#amostras-cegas)
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
| `SAMPLE_QR_BASE_URL` | Base da URL do frontend gravada no QR code dos frascos. Sem valor, usa a primeira origem de `AUTH_ALLOWED_ORIGINS` | `https://pivma.exemplo` |

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

A aplicação divide autorização em três níveis:

1. **Perfis Globais (RBAC):** Definem permissões transversais no sistema (ex.: `Administrador`, `BraCVAM`, `Grupo Gestor`).
2. **Papéis Locais de Processo:** Definem atribuições dentro de instâncias específicas de processo (`ProcessInstance`).
3. **Concessões por Atividade:** Cada atividade de processo lista os cargos que podem vê-la (`view_roles`) e editá-la (`edit_roles`). As concessões valem para cargos, nunca para usuários. Um usuário tem um cargo no processo por atribuição ativa ou, no caso de `admin` e `bracvam`, pelo perfil global. `admin` e `bracvam` veem todas as atividades; editar exige que o cargo esteja em `edit_roles`. As concessões vêm da chave `access` dos templates (ver `src/pivma/templates_data/README.md`).

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
* **Padrão de Listagem:** Todas as listagens respondem com `data`, `pagination` (`page`, `per_page`, `total_items`, `total_pages`, `has_next`, `has_prev`), `filters_applied` (com os padrões aplicados) e `sort` (`by`, `order`). `facets` e `summary` só aparecem quando pedidos em `include` (hoje só em `GET /tasks`). A paginação é por página: `page` começa em 1, `per_page` vai de 1 a 100 (padrão 20), e uma página além da última devolve `data` vazio com os totais. Não há `offset`, `limit` nem `size`. Cada listagem tem uma ordem padrão estável, informada em `sort`, e ecoa seus filtros em `filters_applied` (vazio quando não tem filtros).
* **Referências Resumidas:** Entidades relacionadas vêm como objetos pequenos de formato fixo, em um nível só:
  * pessoa (`user`): `id`, `username`, `full_name` (nunca e-mail);
  * perfil: `id`, `name`, `active`;
  * instituição (`institution`): `id`, `name`, `active`;
  * laboratório (`laboratory`): `id`, `name`, `active` e `institution`;
  * template (`template`): `key`, `name`, `version`;
  * processo (`process`): `id`, `code`, `title`; etapa (`phase`): `key`, `order`.

  Aparecem em designações de participante, convites, laboratórios, afiliações, processos, etiquetas e tarefas. Campos de auditoria (`created_by`, `assigned_by`, `accepted_by` e similares) continuam como identificadores.
* **Convenções de Erro:**
* `401 Unauthorized`: Sessão inexistente ou expirada.
* `403 Forbidden`: Falta de permissão global, concessão de ver sem concessão de editar na atividade, ou conflito de interesse ativo.
* `404 Not Found`: Recurso inexistente ou sem concessão de ver. Um processo sem atribuição ativa (para quem não é Admin/BraCVAM) e uma atividade sem concessão de ver respondem 404, sem revelar que existem.
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
* **Ciclo de vida:** o campo `status` do processo aceita só `OPEN`, `CLOSED`, `CANCELLED` e `ARCHIVED`, validado por `CHECK` no banco. Todo processo nasce `OPEN`; a triagem rejeitada leva a `CLOSED`, a exclusão a `CANCELLED` e o arquivamento (a partir de `CLOSED` ou `CANCELLED`) a `ARCHIVED`. `GET /processes?status=` aceita só esses valores.
* **Posição no fluxo:** vem dos estados de fases e atividades (`BLOCKED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`), não do processo. Etapas como submissão, pré-avaliação e triagem são atividades, e várias podem estar em andamento ao mesmo tempo.
* **Visibilidade:** Admin e BraCVAM veem todos os processos. Os demais veem o cabeçalho dos processos em que têm atribuição ativa, em qualquer cargo; formulários, versões, anexos, pré-avaliação, tarefas e eventos da linha do tempo seguem a concessão de ver de cada atividade.
* **Tarefas:** `GET /tasks` responde no padrão de listagem (ver "Diretrizes de Integração"). Cada tarefa traz o processo (`process`: `id`, `code`, `title`), a atividade (`activity_key`), a execução (`activity_run_number`), a fase (`phase`: `key`, `order`), o cargo, o status, o prazo e `can_act`. `can_act` é verdadeiro quando o usuário tem cargo com concessão de editar a atividade e nenhum conflito de interesse vigente no processo, a mesma regra que as ações aplicam.
  * **Filtros:** `status` (repetível: `READY`, `COMPLETED`, `CANCELLED`), `activity_key` (repetível), `phase_order`, `process_id`, `role`, `actionable` (só onde o usuário pode agir), `current_run` (padrão `true`: só a execução vigente de cada atividade; `false` inclui o histórico) e `overdue` (abertas com prazo vencido). Valor inválido responde `422`.
  * **Ordenação:** `sort_by` (`due_date`, padrão, ou `created_at`) e `sort_order` (`asc`, padrão, ou `desc`). Tarefas sem prazo ficam sempre por último.
  * **Contagens e resumo:** `include=facets` devolve as contagens por `activity_key` e por `status` sobre todo o conjunto filtrado. `include=summary` devolve `ai_pre_evaluation_in_progress`, os processos visíveis com pré-avaliação por IA em andamento, que não têm tarefa aberta nesse intervalo. Com os dois, o quadro de uma etapa sai numa chamada (ex.: `phase_order=1&status=READY&include=facets&include=summary`).
* Suporte a formulários dinâmicos com ciclos de rascunho e submissão estrita (bloqueio de alterações após envio). Só o cargo `proponent` edita a submissão; BraCVAM e Admin a leem.
* Fase 1 (Triagem) inclui pareceres técnicos por campo e decisão final (aprovação, rejeição ou pedido de revisão). Exige a permissão `triage.review` e a concessão de edição da atividade, que pertence só ao cargo `bracvam`: o Admin lê a triagem, mas não decide. A decisão só é aceita com a triagem em andamento; fora disso, `409`.
* **Revisão do retorno:** quando a pré-avaliação por IA termina negativa ou com falha, ou quando a triagem pede revisão, abre a atividade `submission_return_review` para o cargo `proponent`. `GET /processes/{id}/return-review` mostra o retorno (resultado da IA ou decisão e justificativa da triagem) e as escolhas disponíveis. `POST /processes/{id}/return-review` registra a escolha: `REVISE` reabre a submissão como rascunho com os valores anteriores; `CONTEST_AI` (só em retorno da IA) encaminha à triagem humana; `WITHDRAW` encerra o processo como `CLOSED`. Enquanto a revisão está aberta, a submissão fica travada. A escolha vale uma vez por retorno (`409` na segunda). A antiga `POST /processes/{id}/submission/direct-review` foi removida. A resposta da decisão de triagem traz `return_review_run` quando abre uma revisão.
* **Fase 2 (Composição da Governança):** presente nos cinco templates (versões 3 dos templates 01, 02, 03 e 05; versão 5 do template 04). Abre quando a triagem é aprovada, com as oito atividades de atribuição de cargo e a atividade de amostras (`sample_definition`). Processos criados em versões anteriores mantêm a estrutura da versão em que nasceram.
* Exclusão lógica permitida apenas para processos `OPEN`.

### Participantes e Conflito de Interesses

* **Designações e convites:** cada designação traz `process`, `user` e `laboratory` (nulo fora dos cargos de laboratório) como referências resumidas; cada convite traz `process` e `laboratory`. As listagens de participantes, histórico e convites seguem o padrão de listagem.
* **Papéis Locais Suportados:**
* Técnicos: `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`.
* Proponente: `proponent` (atribuído ao criador do processo).
* Laboratoriais: `lead_laboratory`, `participating_laboratory` (exigem vínculo institucional ativo do usuário com o respectivo laboratório).
* Fase 2: `sponsor`, `sample_selection_group`, `regulatory_observer`, `collaborator`.


* **Regras de Conflito de Interesse:**
* Histórico *append-only* em `ConflictInterestDeclaration`.
* Se um usuário possuir declaração de conflito ativa em qualquer papel do processo, qualquer tentativa de registrar parecer de triagem ou decisão regulatória é bloqueada imediatamente com status `403 Forbidden`.
* O conteúdo da justificativa do conflito é visível apenas ao declarante e aos gestores do processo.



### Amostras Cegas

Atividade `sample_definition` da Fase 2 (Spec 031, RF038 e RF050). Abre quando as atribuições do Grupo de Seleção de Amostras e dos Laboratórios Participantes estão concluídas.

* **Acesso:** só o cargo `sample_selection_group` do processo vê e altera substâncias, códigos, SDS e etiquetas. Todas as rotas exigem a concessão de **edição** da atividade, também nas leituras. Laboratórios e Grupo Gestor recebem `404`; Admin e BraCVAM veem a atividade e seu status em `GET /tasks`, mas recebem `403` no conteúdo. Conflito de interesse vigente também bloqueia a leitura.
* **Substâncias:** `GET/POST /processes/{id}/samples`, `PATCH/DELETE /processes/{id}/samples/{substance_id}`. Nome químico, CAS, lote e instruções de manuseio seguro são obrigatórios. O CAS passa por formato e dígito verificador (`422 invalid_cas`) e é único entre as substâncias ativas do processo (`409 duplicate_cas`); pode se repetir em outro processo.
* **Códigos cegos:** cada cadastro gera um código de 8 caracteres (`23456789ABCDEFGHJKMNPQRSTUVWXYZ`, sem `0/O/1/I/L`) por laboratório com designação ativa de `participating_laboratory`. O código é aleatório, único no processo e não carrega informação da substância ou do laboratório. O laboratório líder não recebe código por ser líder.
* **SDS:** `PUT/GET /processes/{id}/samples/{substance_id}/sds`, só PDF, com o limite de `ATTACHMENT_MAX_SIZE_MB`. Substituir a SDS descarta a anterior.
* **Conclusão:** `POST /processes/{id}/samples/complete` exige ao menos uma substância, SDS em todas e ao menos um laboratório (`422 no_substances`, `missing_sds`, `no_laboratories`). Gera os códigos que faltam, descarta os de laboratórios que saíram e conclui a atividade. Depois disso, toda alteração responde `409 invalid_transition`.
* **Etiquetas:** `GET /processes/{id}/samples/labels` devolve, no padrão de listagem, por frasco, estudo, laboratório (`laboratory`, referência resumida), código, lote, `qr_url` e `qr_svg` (data URI SVG gerado com `segno`). O QR só é gerado para a página pedida. O frontend monta o layout e imprime.
* **QR code:** contém só `{SAMPLE_QR_BASE_URL}/amostras/{process_id}/frascos/{code}`, rota do frontend que chama `GET /processes/{id}/samples/vials/{code}`. Essa rota exige login e devolve só código, lote e instruções de manuseio, nunca nome químico, CAS ou SDS.
* **Auditoria:** eventos `SAMPLE_*` na linha do tempo guardam só identificadores e contagens.
* O acesso dos laboratórios participantes aos próprios códigos fica para o recebimento de amostras (issue #28).

### Avaliação Configurável por IA

* O BraCVAM configura critérios em linguagem natural vinculados a campos de formulário.
* A pré-avaliação opera de forma assíncrona na submissão através de modelos via LangChain.
* **Regra de Consolidação:** A presença de 1 ou mais não-conformidades de severidade alta ou crítica consolida o resultado como negativo.
* Resultado positivo: segue para a fila de triagem.
* Resultado negativo/falha: abre a revisão do retorno para o proponente, que pode revisar a submissão, contestar a IA ou desistir. O reprocessamento administrativo de uma execução com falha cancela a revisão do retorno em aberto.


* A IA não emite decisões regulatórias finais; o processo decisório permanece sob responsabilidade de triadores humanos.

### Observabilidade de Logs

As consultas `GET /admin/logs/operational` e `GET /admin/logs/ai` ainda
respondem a administradores, mas estão fora da documentação da API e serão
removidas.

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
* `tests/integration/journeys/`: Jornadas de ponta a ponta pela API pública, agrupadas por etapa do processo (`etapa_1_submissao_triagem/`, `etapa_2_planejamento_preparacao/`). Os helpers comuns (bootstrap de deploy novo, cadastro, login por cookie e troca de usuário) ficam em `journeys/conftest.py`.

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
