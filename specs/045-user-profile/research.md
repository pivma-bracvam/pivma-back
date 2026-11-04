# Research: Perfil do Usuário

O Technical Context não tem itens em aberto. Cada seção abaixo registra uma
decisão de desenho, com o que foi descartado.

## R1. Perfil e cargos locais em rotas separadas

- **Decisão**: `GET /users/{user_id}` traz o perfil, e
  `GET /users/{user_id}/process-roles` traz os cargos locais, paginados por
  processo.
- **Motivo**: o perfil tem tamanho fixo, mas os cargos locais crescem a cada
  processo, e os revogados nunca saem do histórico. Numa rota própria, eles
  usam o envelope paginado do projeto (Specs 032 e 033) e o filtro `active`
  de `GET /users`.
- **Alternativas descartadas**:
  - Cargos locais embutidos no perfil: a resposta cresceria sem limite, ou o
    perfil precisaria de uma paginação interna fora do padrão do projeto.
  - Embutir só os ativos: a pessoa ainda pode ter muitos, e o histórico
    continuaria precisando de outra rota.

## R2. A própria pessoa usa as mesmas rotas

- **Decisão**: o frontend chama as duas rotas com o `id` que recebe em
  `GET /auth/me`. `GET /auth/me` não muda.
- **Motivo**: um único código serve à própria pessoa e à administração. O
  `GET /auth/me` carrega a sessão a cada página e precisa continuar leve.
- **Alternativas descartadas**:
  - Ampliar `GET /auth/me`: o histórico pesaria em toda página, e o contrato
    dele mudaria (FR-016).
  - Criar `GET /users/me`: seria uma segunda rota com a mesma resposta, e
    `me` disputaria o caminho com `{user_id}`.

## R3. Um ponto único de acesso

- **Decisão**: a função `authorize_profile_read`, no router, decide o acesso
  das duas rotas: a própria pessoa ou `users.read`; caso contrário, 403.
- **Motivo**: FR-015 pede que a visão futura dos membros comuns seja um caso a
  mais num ponto só. Quando ela existir, a função passa a devolver a visão, e o
  perfil omite o e-mail nessa visão. Hoje as duas visões mostram os mesmos
  campos, então a função não devolve nada.
- **Alternativas descartadas**:
  - `require_permission(USERS_READ)`: recusaria a própria pessoa.
  - Enum de visões ou schema público já agora: criaria código sem uso, já que
    nenhuma rota precisa disso hoje.

## R4. 403 antes da busca, 404 só com `users.read`

- **Decisão**: sem `users.read`, a consulta a outra conta recebe 403 antes de
  qualquer leitura. Com a permissão, um id inexistente recebe 404, e uma conta
  desativada recebe o perfil com `active: false`.
- **Motivo**: o 403 igual nos dois casos não revela se a conta existe. Quem
  tem `users.read` já lista contas inativas com `GET /users?active=false`.
- **Alternativa descartada**: 404 para tudo sem permissão. O projeto usa 404
  quando o próprio recurso é segredo; aqui, o que falta é a permissão, como em
  `GET /users`.

## R5. Data da atribuição global

- **Decisão**: o perfil usa `UserAccessProfile.created_at` como `assigned_at`.
  O perfil mostra só as atribuições vigentes.
- **Motivo**: o índice único `uq_user_access_profiles_active` garante uma
  atribuição vigente por perfil e conta. Depois de revogar e atribuir de novo,
  a data é a da atribuição nova. O histórico de concessões e revogações já
  existe em `GET /rbac/changes`.
- **Alternativa descartada**: mudar `active_profiles_for_users` para devolver
  a data. Essa função serve à listagem, a `/auth/me` e à autorização, e o
  retorno novo mexeria nos três.

## R6. Paginação por processo

- **Decisão**: `paginate_query` sobre os `process_instance_id` agrupados, em
  ordem de `max(assigned_at)` decrescente e depois de `process_instance_id`
  crescente. Em seguida, uma consulta traz as designações dos processos da
  página.
- **Motivo**: a contagem de `paginate_query` usa uma subconsulta, que conta os
  grupos e não as designações. O número de consultas por página é fixo: não
  há uma consulta por processo.
- **Alternativas descartadas**:
  - Paginar designações: um processo ficaria partido entre duas páginas.
  - `paginate_items` em Python: carregaria todas as designações da pessoa a
    cada página.

## R7. O que cada cargo local traz

- **Decisão**: `id` da designação, `role_key`, `laboratory` (`LaboratoryRef`
  ou `null`), `assigned_at` e `revoked_at`. O processo usa `ProcessRef` com o
  campo `status`.
- **Motivo**: são os campos que o frontend pediu. O `id` serve de chave na
  lista e liga o cargo às rotas de participantes. `ProcessRef` não tem
  `status`, e acrescentá-lo mudaria todas as respostas que o usam; uma
  subclasse resolve sem tocar nelas.
- **Alternativas descartadas**:
  - `effective`, conflito de interesse e `assigned_by`: já estão na listagem de
    participantes, e o frontend não os pediu.
  - Convites pendentes: ainda não são cargos.

## R8. Filtro de exclusão lógica

- **Decisão**: só a leitura da conta usa `skip_soft_delete_filter=True`. As
  consultas de cargos globais e locais ficam com o filtro global, sem repetir
  `deleted_at` nos predicados. Os laboratórios vêm de `laboratory_refs`, que
  já ignora o filtro.
- **Motivo**: o filtro global (`with_loader_criteria`) já tira as
  atribuições, os perfis, as designações e os processos excluídos (FR-004,
  FR-010), e repetir o predicado seria código a mais. Os testes de exclusão
  lógica provam a regra de qualquer forma. Um laboratório desativado aparece
  com `active: false`, como nas outras referências.
