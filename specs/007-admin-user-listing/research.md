# Pesquisa técnica: Listagem Administrativa de Usuários

## Fontes e estado confirmado

**Decisão**: basear o desenho na spec aprovada, no Plano de Trabalho, no backlog de Gestão de Usuários e no comportamento atual de usuários e RBAC.

**Justificativa**: `docs/plano-de-trabalho-fase-ii.md` define RF001, RF002, RF004, RF005 e RF034. `docs/planejamento/gestao-de-usuarios.md` registra consulta administrativa e autorização no backend. `src/pivma/routers/users.py`, `src/pivma/dependencies.py`, `src/pivma/core/authorization.py`, modelos, migrations e testes confirmam os contratos disponíveis.

**Alternativas consideradas**:

- Usar telas do protótipo para definir filtros: o protótipo não comprova contrato de backend.
- Acrescentar filtros institucionais ou de processo: RF003 e RF005 já possuem modelos próprios, mas a spec 007 os exclui desta consulta.

## Migração e seed de `users.read`

**Decisão**: criar uma revisão Alembic após o head atual `6f2c9a1d4e70`. O upgrade insere `users.read` em `permissions` com UUID `00000000-0000-0000-0000-000000000108` e insere a composição do perfil `administrator` com UUID `00000000-0000-0000-0000-000000000208`. O downgrade remove todas as composições ligadas à permissão e depois remove a permissão.

**Justificativa**: as migrations 003, 005 e 006 ampliam o catálogo com UUIDs determinísticos e compõem novas permissões com o perfil oficial Administrador. O próximo par `108`/`208` evita colisão com `process.participants.manage`, que usa `107`/`207`. A migração apenas de dados atualiza instalações novas e existentes; uma atribuição ativa ao Administrador passa a conceder a nova capacidade pelo cálculo atual.

**Alternativas consideradas**:

- Alterar a migration histórica da feature 003: instalações que já a aplicaram não receberiam a permissão.
- Criar a permissão no startup ou no bootstrap: produziria mutação implícita e diferenças entre ambientes.
- Criar endpoint de catálogo: a feature 003 reserva a ampliação do catálogo a features aprovadas.

## Salvaguarda administrativa do RBAC

**Decisão**: adicionar `USERS_READ = 'users.read'` em `core/authorization.py` e não incluí-la em `ADMINISTRATIVE_PERMISSIONS`.

**Justificativa**: `ensure_administrator_remains` usa somente `ADMINISTRATIVE_PERMISSIONS` para garantir uma conta ativa com `rbac.read`, `rbac.profiles.manage` e `rbac.assignments.manage`. A spec separa consulta de usuários da capacidade de manter o próprio RBAC. A composição do perfil Administrador pode conter permissões adicionais sem ampliar essa invariável.

**Alternativas consideradas**:

- Incluir `users.read` na frozenset: uma remoção da permissão de consulta bloquearia mudanças de RBAC sem relação com a salvaguarda aprovada.
- Autorizar a rota por nome `Administrador`: quebraria o cálculo cumulativo de permissões e impediria perfis adicionais de receber a capacidade.

## Proteção do endpoint

**Decisão**: declarar uma dependência tipada em `routers/users.py` com `Depends(require_permission(USERS_READ))` e executá-la antes da função da rota.

**Justificativa**: `require_permission` já autentica por `CurrentUser`, consulta permissões efetivas no banco, registra a recusa 403 no logger `pivma.dependencies` e devolve a mesma resposta proibida. O endpoint GET não precisa de `TrustedOrigin`, reservado a mutações autenticadas por cookie.

**Alternativas consideradas**:

- Repetir a consulta de autorização no router: duplicaria a regra existente.
- Exigir `rbac.read` ou `rbac.assignments.manage`: uniria capacidades que a spec mantém separadas.
- Validar autorização no frontend: não protege a coleção no backend.

## Paginação e `FilterPage`
 
**Decisão**: herdar `FilterPage` no schema de resposta `AdminUserPage`, mantendo `limit` entre 1 e 100 no schema específico sem modificar a classe base compartilhada, e declarar `offset >= 0` e `1 <= limit <= 100` nos parâmetros de consulta da rota.
 
**Justificativa**: a classe existente fornece os campos e defaults `offset=0` e `limit=100`, e `RbacChangePage` e `InstitutionalChangePage` já a usam como base de resposta. Como `FilterPage` possui apenas `ge=1`, alterá-la diretamente impactaria outros contratos compartilhados. Especializar o campo `limit` em `AdminUserPage` com `ge=1, le=100` garante alinhamento exato entre o OpenAPI gerado da aplicação e `contracts/users.openapi.yaml`, enquanto a validação de query params pela FastAPI produz 422 antes da consulta para valores fora da faixa.

**Alternativas consideradas**:

- Usar `FilterPage` como modelo completo dos query params: não imporia o máximo de 100 sem modificar a classe compartilhada.
- Acrescentar total de registros: a spec limita a resposta a `offset`, `limit` e `items`.
- Criar cursor: amplia o contrato além da paginação aprovada.

## Busca textual literal e case-insensitive

**Decisão**: remover espaços externos em Python e, quando restar texto, combinar `User.username.icontains(search, autoescape=True)` e `User.email.icontains(search, autoescape=True)` com `or_`.

**Justificativa**: SQLAlchemy 2.0 documenta `icontains` como comparação case-insensitive de substring. `autoescape=True` escapa `%`, `_` e o próprio caractere de escape no parâmetro literal. O driver mantém o termo como bind parameter. Um valor vazio após `strip()` não adiciona predicado.

**Alternativas consideradas**:

- `ilike(f'%{search}%')`: `%` e `_` enviados pelo cliente continuariam funcionando como curingas sem escape manual.
- Comparação com `lower(...) == lower(...)`: implementaria igualdade, não substring.
- Normalização Unicode, busca por similaridade ou texto completo: não consta da spec e exigiria decisões e infraestrutura adicionais.

## Filtro de estado

**Decisão**: usar `User.deleted_at.is_(None)` para `active=true`, inclusive quando o parâmetro for omitido, e `User.deleted_at.is_not(None)` para `active=false`.

**Justificativa**: `User` herda `AuditMixin` e não possui outro campo de estado. A criação e a autenticação atuais tratam `deleted_at IS NULL` como conta ativa. A resposta derivará `active` da mesma condição.

**Alternativas consideradas**:

- Adicionar coluna booleana: duplicaria o estado e exigiria sincronização.
- Misturar contas ativas e inativas por padrão: contraria a decisão aprovada.

## Filtro por perfil sem duplicatas

**Decisão**: quando `profile_id` estiver presente, adicionar ao `select(User)` um `EXISTS` correlacionado sobre `user_access_profiles` com `user_id = users.id`, `profile_id` solicitado, atribuição ativa e `access_profiles.deleted_at IS NULL`.

**Justificativa**: o `EXISTS` verifica a relação sem adicionar linhas ao conjunto externo. Ele combina com busca, estado, ordem e paginação no mesmo statement. Um UUID desconhecido ou ligado somente a perfil inativo não encontra relação e produz página vazia.

**Alternativas consideradas**:

- `JOIN` com `DISTINCT`: funciona, mas amplia o conjunto intermediário e exige deduplicação antes de ordenar e paginar.
- Consultar o perfil antes e devolver 404: contraria o resultado vazio definido na spec.
- Carregar perfis em Python: aplicaria filtro depois da paginação e criaria consultas adicionais.

## Ordenação e seleção da página

**Decisão**: ordenar o conjunto filtrado por `func.lower(User.username).asc()` e `User.id.asc()`, depois aplicar `offset` e `limit` no banco.

**Justificativa**: a ordem reproduz FR-012, desempata usernames reutilizados após exclusão lógica e mantém páginas estáveis enquanto o conjunto não mudar. A API não executará query de total.

**Alternativas consideradas**:

- Ordenar somente por username: valores equivalentes por caixa ou reutilizados ficariam sem desempate.
- Ordenar em Python: exigiria carregar todos os resultados antes da paginação.
- Permitir campo e direção configuráveis: a spec exclui ordenação configurável.

## Schemas e exposição de dados

**Decisão**: criar um item administrativo `AdminUser` que herda `id`, `username` e `email` de `UserPublic` e adiciona `active: bool`. Criar uma página `AdminUserPage` que herda de `FilterPage`, especializa `limit` para a faixa de 1 a 100 sem modificar a classe base compartilhada e declara `items` com a lista de itens administrativos. A rota construirá os itens de forma explícita.

**Justificativa**: `UserPublic` já preserva o formato UUID e e-mail sem expor `password_hash` ou auditoria. A especialização acrescenta somente o estado aprovado. O response model restringe os campos de topo e dos itens.

**Alternativas consideradas**:

- Alterar `UserPublic`: mudaria `POST /users/` e `GET /auth/me`.
- Retornar o modelo ORM: poderia expor campos internos e não possui atributo público `active`.
- Incluir perfis nos itens: duplica o contrato de acesso RBAC e excede a spec.

## Auditoria da leitura

**Decisão**: a rota não cria `RbacChange` nem outro evento persistente. A recusa 403 continuará no log operacional existente.

**Justificativa**: `RbacChange` registra mutações concluídas de perfil e atribuição. FR-028 exclui a listagem dessa trilha e mantém a política geral de leitura pendente para RF034.

**Alternativas consideradas**:

- Persistir toda consulta: a equipe ainda não definiu retenção, acesso e conteúdo desses eventos.
- Não verificar o log de recusa: perderia uma garantia aprovada e já fornecida pela feature 003.

## Estratégia de testes orientada a risco

**Decisão**: usar testes de API como evidência principal da consulta e da segurança, uma suíte de migração para o seed e downgrade e um teste isolado para a fronteira de `ADMINISTRATIVE_PERMISSIONS`. Reutilizar `client`, `session`, cookies JWT, factories e PostgreSQL do projeto.

**Justificativa**: a listagem tem risco médio de consulta e alto de exposição. Os testes HTTP percorrem validação FastAPI, dependência RBAC, SQLAlchemy e banco real. A migração precisa de Alembic e PostgreSQL. Não há regra pura, service ou repository que justifique mocks ou outra camada de unidade.

**Alternativas consideradas**:

- Criar repository apenas para testá-lo: adicionaria uma camada sem consumidor adicional.
- Duplicar cada filtro em teste direto de SQL e teste HTTP: produziria a mesma evidência por dois caminhos.
- Testar via login real em cada caso: repetiria autenticação e custo de senha; os cookies assinados das fixtures já isolam a autorização em análise.
- Adicionar concorrência, benchmark ou xdist: a spec aceita mudanças entre páginas, removeu o benchmark e não exige infraestrutura nova.

## Índices e desempenho

**Decisão**: não criar índice nesta feature.

**Justificativa**: a busca por substring `%termo%` não recebe benefício geral dos índices B-tree funcionais atuais. A spec não define volume nem meta temporal. Um índice trigram ou outra otimização exigiria extensão, migração e evidência de carga que o projeto ainda não possui.

**Alternativas consideradas**:

- Índice por `lower(username)`: já existe para unicidade ativa e não resolve todos os padrões de substring nem contas inativas.
- `pg_trgm` e índices GIN: acrescentariam dependência de banco e custo de escrita sem benchmark.
