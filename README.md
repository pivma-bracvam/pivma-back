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
  - [Execução por Laboratório](#execução-por-laboratório)
  - [Avaliação Configurável por IA](#avaliação-configurável-por-ia)
  - [Notificações](#notificações)
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
| `NOTIFICATION_EMAIL_BACKEND` | Canal de e-mail: `smtp`, `fake` (testes) ou vazio (envio por e-mail desativado) | `smtp` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Servidor SMTP de qualquer provedor. `SMTP_SECURITY`: `starttls` (padrão, 587), `ssl` (465) ou `none` | `mailpit`, `1025`, `none` |
| `NOTIFICATION_FROM_ADDRESS`, `NOTIFICATION_FROM_NAME` | Remetente das mensagens | `nao-responda@pivma.exemplo` |
| `NOTIFICATION_ENCRYPTION_KEY` | Chave Fernet que cifra o conteúdo dos envios pendentes | ver [Notificações](#notificações) |
| `INVITE_URL_TEMPLATE` | Endereço da página de aceite do convite no frontend, com `{token}` | `https://pivma.exemplo/convites/{token}` |

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

A aplicação divide autorização em quatro níveis:

1. **Perfis Globais (RBAC):** Definem permissões transversais no sistema (ex.: `Administrador`, `BraCVAM`, `Grupo Gestor`).
2. **Papéis Locais de Processo:** Definem atribuições dentro de instâncias específicas de processo (`ProcessInstance`).
3. **Concessões por Atividade:** Cada atividade de processo lista os cargos que podem vê-la (`view_roles`) e editá-la (`edit_roles`). As concessões valem para cargos, nunca para usuários. Um usuário tem um cargo no processo por atribuição ativa ou, no caso de `admin` e `bracvam`, pelo perfil global. `admin` e `bracvam` veem todas as atividades; editar exige que o cargo esteja em `edit_roles`. As concessões vêm da chave `access` dos templates (ver `src/pivma/templates_data/README.md`).
4. **Isolamento por Laboratório:** Nas atividades executadas por laboratório (ver [Execução por Laboratório](#execução-por-laboratório)), a concessão da atividade não basta. Cada laboratório lê e age só na própria execução.

| Perfil | Lê a execução de um laboratório | Age na execução |
|---|---|---|
| `participating_laboratory` efetivo pelo laboratório da execução | Sim | Sim, com concessão de edição |
| `participating_laboratory` de outro laboratório | Não (`404`) | Não (`404`) |
| `lead_laboratory`, `sample_selection_group`, `statistician` e demais cargos | Não (`404`) | Não |
| `group_manager` efetivo | Sim | Não (`403`) |
| Admin, BraCVAM | Sim | Só se o template der edição a `admin`/`bracvam` |

A designação de `lead_laboratory` não dá acesso a execução nenhuma, nem à do laboratório da própria designação. Quem é líder por um laboratório e participante por outro vê só as execuções do segundo. A execução de outro laboratório responde com o mesmo `404` e a mesma mensagem da execução inexistente, então a resposta não revela que o laboratório existe no processo. O motor aplica a regra em `require_laboratory_run_access(..., level='view' | 'edit')`, que as rotas de conteúdo e anexo da Etapa 3 chamam; `GET /tasks`, `GET /tasks/{id}` e a linha do tempo aplicam a mesma regra. Um usuário tem no máximo uma designação ativa de `participating_laboratory` por processo: a segunda, por qualquer laboratório, responde `409 duplicate`.

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
* **Convenções de Erro:** todo erro responde `{"detail": {"code": ..., "message": ...}}`. O `code` é estável, em inglês, e é por ele que o cliente decide o comportamento; a `message` está em português e serve para exibir. Nenhuma resposta repete valores enviados nem detalhes internos. Os erros de validação (`422`) trazem também `fields`, uma entrada por campo com `location` (`body`, `query`, `path`, `header`, `cookie`), `field` (caminho separado por ponto), `code` e `message`. Na senha, o item vem com `code: invalid` e sem a regra.
  * `400 bad_request` (anexo vazio: `empty_file`).
  * `401 not_authenticated`: sessão inexistente ou expirada; `invalid_credentials` no login.
  * `403 forbidden`: falta de permissão global, concessão de ver sem concessão de editar na atividade, ou conflito de interesse ativo. Também `invalid_origin` (mutação de origem não confiável), `admin_only` e `invite_email_mismatch`.
  * `404 not_found`: recurso inexistente ou sem concessão de ver. Um processo sem atribuição ativa (para quem não é Admin/BraCVAM) e uma atividade sem concessão de ver respondem 404, sem revelar que existem.
  * `405 method_not_allowed`.
  * `409 conflict`: regra de negócio. Códigos específicos: `duplicate`, `inactive_entity`, `process_closed`, `invalid_transition`, `form_submitted`, `invite_expired`, `invite_not_pending`, `self_deactivation`, `last_administrator`, `duplicate_cas`, `channel_unavailable`.
  * `413 payload_too_large` (anexo acima do limite: `file_too_large`).
  * `422 validation_error`: validação de entrada, com `fields`. Formulário dinâmico: `invalid_form_values` e `invalid_submission_values`, também com `fields` (`field: values.<chave>`). Outros específicos: `extension_not_allowed`, `not_a_file_field`, `invalid_cas`, `no_substances`, `missing_sds` (com `substance_ids`), `no_laboratories`.
  * `500 internal_error` e `503 service_unavailable` (`ai_unavailable` quando o provedor de IA falha).



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
* **Autogestão da conta:** `PATCH /auth/me` exige sessão ativa e origem confiável, sem permissão administrativa. Aceita `full_name`, `current_password` e `new_password`; qualquer outro campo responde `422`. A nova senha exige a senha atual e segue as regras de `password`. Senha atual incorreta responde `400` (`invalid_current_password`) sem alterar nada. Sem sessão, a resposta é `401`; com origem não confiável, `403`. A sessão atual continua válida após a troca de senha.

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
* **Tarefas:** `GET /tasks` responde no padrão de listagem (ver "Diretrizes de Integração"). Cada tarefa traz o processo (`process`: `id`, `code`, `title`), a atividade (`activity_key`), a execução (`activity_run_number`), a fase (`phase`: `key`, `order`), o cargo, o status, o prazo, `can_act`, o status da execução (`activity_run_status`: `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `WAIVED` ou `SUPERSEDED`) e o laboratório da execução (`laboratory`, referência resumida, `null` em atividade de execução única). `can_act` é verdadeiro quando o usuário tem cargo com concessão de editar a atividade e nenhum conflito de interesse vigente no processo, a mesma regra que as ações aplicam; na execução de um laboratório, a designação tem de ser por esse laboratório.
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
* **Convite por e-mail (Spec 036):** `channel` aceita `link` (padrão, link compartilhado manualmente) ou `email`. Com `email`, a criação e o reenvio registram o envio do link para o e-mail do convite; a resposta continua trazendo o `token`. Revogar ou aceitar cancela o envio pendente. Cada convite traz `delivery` (`status`, `attempts`, `last_attempt_at`, `sent_at`, `error_code`), nulo no canal `link`. Sem o canal de e-mail ou sem `INVITE_URL_TEMPLATE` configurados, `channel: "email"` responde `409 channel_unavailable`.
* **Papéis Locais Suportados:**
* Técnicos: `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`.
* Proponente: `proponent` (atribuído ao criador do processo).
* Laboratoriais: `lead_laboratory`, `participating_laboratory` (exigem vínculo institucional ativo do usuário com o respectivo laboratório).
* Fase 2: `sponsor`, `sample_selection_group`, `regulatory_observer`, `collaborator`.

* **Designação efetiva (Spec 035):**
* Uma designação ativa (não revogada) só concede acesso quando é efetiva: usuário ativo e, nos cargos laboratoriais, vínculo ativo do usuário com o laboratório da designação, com laboratório e instituição ativos.
* Encerrar o vínculo ou inativar o laboratório ou a instituição retira no pedido seguinte o acesso que dependia do cargo (atividades, tarefas, amostras, linha do tempo e visibilidade do processo), sem revogar a designação nem mexer em tarefas ou dados. Um novo vínculo com o mesmo laboratório devolve o acesso.
* A mesma regra (`effective_assignment_clause` em `core/authorization.py`) decide a autorização, o `effective` da listagem de participantes, os escopos de `GET /auth/me` e a validação de nova designação.
* Nos processos em andamento, cada mudança de efetividade causada por ação institucional grava `PARTICIPANT_EFFECTIVENESS_LOST` ou `PARTICIPANT_EFFECTIVENESS_RESTORED` na linha do tempo, com `reason` (`affiliation_ended`, `laboratory_deactivated`, `institution_deactivated` ou `affiliation_created`). Processos encerrados, cancelados, arquivados ou excluídos não recebem esses eventos.


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
* **Etiquetas:** `GET /processes/{id}/samples/labels` devolve, no padrão de listagem, por frasco, estudo, laboratório (`laboratory`, referência resumida), código, lote e `qr_url`. A imagem do QR vem de `GET /processes/{id}/samples/vials/{code}/qr.svg` (`image/svg+xml`, gerada com `segno`, mesmo acesso das etiquetas), para usar direto em `<img>`. O frontend monta o layout e imprime.
* **QR code:** contém só `{SAMPLE_QR_BASE_URL}/amostras/{process_id}/frascos/{code}`, rota do frontend que chama `GET /processes/{id}/samples/vials/{code}`. Essa rota exige login e devolve só código, lote e instruções de manuseio, nunca nome químico, CAS ou SDS.
* **Auditoria:** eventos `SAMPLE_*` na linha do tempo guardam só identificadores e contagens.
* O acesso dos laboratórios participantes aos próprios códigos fica para o recebimento de amostras (issue #28).

### Execução por Laboratório

Motor de atividades executadas por laboratório participante (Spec 036, issue #58). Nenhum template padrão declara essas atividades ainda; as da Etapa 3 chegam com as issues #28 a #31.

* **Declaração no template:** `execution_scope: "per_laboratory"` (padrão `"process"`) e, para devolução ou descarte, `custody: true`. A carga recusa modo desconhecido, atividade por laboratório sem dependência (direta ou transitiva) de uma atividade `sample_definition`, atividade por laboratório que `participating_laboratory` não edita e `custody` fora de atividade por laboratório.
* **Ativação:** a atividade cria uma execução para cada laboratório congelado na conclusão de `sample_definition` (os laboratórios com código cego). Quem designa um laboratório depois do congelamento não ganha execução; quem perde a designação mantém a dele. A execução do laboratório com as dependências resolvidas nasce `IN_PROGRESS`, com tarefa; as demais nascem `BLOCKED`, sem tarefa.
* **Cadeia por laboratório:** entre duas atividades por laboratório, a execução do Lab X passa a `IN_PROGRESS` quando a anterior do Lab X conclui ou é dispensada, sem esperar os outros. O prazo da tarefa conta desse momento.
* **Conclusão:** a atividade conclui quando todo laboratório congelado tem execução vigente `COMPLETED` ou `WAIVED`. Só então abre a atividade de execução única que depende dela. As issues da Etapa 3 concluem a execução do laboratório chamando `complete_laboratory_run` no motor; esta entrega não tem rota HTTP para isso.
* **Quem age e quem vê:** só quem tem designação efetiva de `participating_laboratory` pelo laboratório da execução age nela (além de Admin e BraCVAM quando o template dá edição a eles). Em `GET /tasks` e `GET /tasks/{id}`, a tarefa de uma execução de laboratório aparece só para o próprio laboratório e para o gestor do processo (`group_manager` efetivo, Admin, BraCVAM); os demais recebem `404` no detalhe. Na linha do tempo vale a mesma regra para os eventos de execução de laboratório, e os eventos de dispensa aparecem só para o gestor do processo.
* **Dispensa:** `POST /processes/{id}/phases/{phase_key}/laboratory-waivers` com `laboratory_id` e `reason`, só para o gestor do processo. Exige `sample_definition` concluída (`409 sample_definition_not_frozen`) e laboratório congelado (`422 laboratory_not_frozen`); a segunda dispensa do mesmo laboratório na fase responde `409 already_waived`. Marca `WAIVED` as execuções abertas ou bloqueadas do laboratório nas atividades por laboratório da fase, fora da custódia, e cancela as tarefas delas. A devolução ou descarte continua obrigatória para o dispensado e abre para ele. Não há como desfazer a dispensa.
* **Reabertura:** `POST /processes/{id}/activities/{activity_key}/laboratories/{laboratory_id}/reopen` com `reason`, só para o gestor do processo. A execução concluída do laboratório vira `SUPERSEDED`, com valores, anexos e eventos intactos, e uma nova abre com o número seguinte e formulário vazio. As atividades de execução única que dependiam dela voltam a `BLOCKED`; nas atividades por laboratório seguintes, só a cadeia desse laboratório volta a bloquear. Execução aberta, bloqueada ou de laboratório dispensado (fora da custódia) responde `409`. As issues que recusam dados usam a mesma função do motor, `reopen_laboratory_run`.
* **Formulários:** as rotas `/processes/{id}/activities/{activity_key}/form` respondem `409 invalid_transition` em atividade por laboratório até as issues da Etapa 3 as estenderem.
* **Cancelamento:** excluir o processo cancela só execuções `IN_PROGRESS` e `BLOCKED`; `COMPLETED`, `CANCELLED`, `WAIVED` e `SUPERSEDED` não mudam.
* **Auditoria:** `LABORATORY_RUN_COMPLETED`, `LABORATORY_WAIVED` e `LABORATORY_RUN_REOPENED`, todos com `laboratory_id` no contexto.

### Avaliação Configurável por IA

* O BraCVAM configura critérios em linguagem natural vinculados a campos de formulário.
* A pré-avaliação opera de forma assíncrona na submissão através de modelos via LangChain.
* **Regra de Consolidação:** A presença de 1 ou mais não-conformidades de severidade alta ou crítica consolida o resultado como negativo.
* Resultado positivo: segue para a fila de triagem.
* Resultado negativo/falha: abre a revisão do retorno para o proponente, que pode revisar a submissão, contestar a IA ou desistir. O reprocessamento administrativo de uma execução com falha cancela a revisão do retorno em aberto.


* A IA não emite decisões regulatórias finais; o processo decisório permanece sob responsabilidade de triadores humanos.

### Notificações

Base de envio de mensagens (Spec 036). O primeiro uso é o convite por e-mail.

* **Pedir um envio:** `enqueue_notification` (`pivma.notifications`) grava o pedido na mesma transação da operação de negócio, sem comitar. Se a operação for desfeita, nada é enviado. Cada tipo de aviso (`kind`) tem um renderizador em `notifications/renderers.py` que devolve assunto, texto e HTML.
* **Processo de envio:** `python -m pivma.notifications.worker` (serviço `worker` do compose). Pega um envio pendente por vez com `FOR UPDATE SKIP LOCKED`, envia e grava o resultado. Erro temporário (4xx, conexão, timeout) tenta de novo em 30 s, 60 s, 120 s… até 900 s, no máximo `NOTIFICATION_MAX_ATTEMPTS` (5) vezes. Erro permanente (5xx, destinatário recusado) falha na hora. Envio com prazo vencido (o do convite) falha como `expired` sem enviar.
* **Situação:** `pending`, `sent`, `failed` ou `cancelled`, com `error_code` (`smtp_permanent`, `smtp_temporary`, `connection`, `max_attempts`, `expired`, `decrypt`, `cancelled_*`). A trilha recebe `NOTIFICATION_SENT`, `NOTIFICATION_FAILED` e `NOTIFICATION_CANCELLED`, sem destinatário nem conteúdo.
* **Conteúdo protegido:** o conteúdo fica cifrado com `NOTIFICATION_ENCRYPTION_KEY` e é apagado quando o envio termina. Logs e auditoria não registram o conteúdo. Gere a chave com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Trocar a chave com envios pendentes faz esses envios falharem como `decrypt`.
* **Provedor:** o envio usa SMTP; trocar de provedor (SES, Brevo, Postmark, Mailgun e outros) é trocar as variáveis `SMTP_*`. O sistema só envia: não precisa de caixa de entrada, mas o domínio do remetente precisa de SPF, DKIM e DMARC no DNS para as mensagens não caírem no spam.
* **Desenvolvimento:** o serviço `mailpit` do compose recebe tudo em `http://localhost:8025` (`SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_SECURITY=none`). Nos testes, `NOTIFICATION_EMAIL_BACKEND=fake` guarda as mensagens em memória.
* **Limite conhecido:** se o processo de envio cair depois que o servidor SMTP aceitou a mensagem e antes de gravar o resultado, a mensagem pode sair de novo.

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

Serviços: `db`, `api`, `worker` (processo de envio de notificações, mesma imagem da API) e `mailpit` (SMTP falso para desenvolvimento). Em produção, rode o `worker` junto da API e troque o Mailpit por um provedor SMTP real.

* Documentação Interativa: `http://localhost:8000/docs`
* Caixa do Mailpit: `http://localhost:8025`
* Logs da API: `docker compose logs -f api`
* Logs do envio de notificações: `docker compose logs -f worker`
* Encerrar serviços: `docker compose down`

---

## Diretrizes de Contribuição

1. **Validação Local:** Execute linting, checagem de tipos e testes antes de submeter alterações (`ruff check`, `ruff format`, `pytest`).
2. **Modelos e Migrações:** Toda alteração nos modelos em `src/pivma/core/database/models.py` exige uma revisão Alembic descritiva gerada via `--autogenerate`.
3. **Rastreabilidade:** Novos modelos de dados relacionais devem herdar de `AuditMixin`.
4. **Segurança em Mutações:** Rotas de escrita devem aplicar validação de identidade autenticada (`CurrentUser`) e checagem de procedência segura (`TrustedOrigin`).

```
