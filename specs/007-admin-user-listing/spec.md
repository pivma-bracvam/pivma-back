# Feature Specification: Listagem Administrativa de Usuários

**Feature Branch**: `not-created`

**Created**: 2026-08-31

**Status**: Ready for Planning

**Input**: User description: "Criar a especificação da próxima feature do Módulo de Gestão de
Usuários, voltada à consulta administrativa e à listagem paginada de contas, com busca textual,
filtros compatíveis com o domínio atual e proteção pelo RBAC existente."

## Clarifications

### Session 2026-08-31

- Q: Como a permissão de listagem administrativa de usuários deve ser definida e atribuída? → A: É criada a permissão específica e estável `users.read`, que passa a integrar a composição de permissões do perfil oficial Administrador. Qualquer conta que possua esse perfil ativo obtém `users.read` automaticamente através do cálculo normal de permissões efetivas do RBAC. Ela permanece separada de `rbac.read`, `rbac.profiles.manage` e `rbac.assignments.manage`.
- Q: Qual a justificativa arquitetural para a criação de `users.read` separada das permissões de RBAC? → A: A consulta de contas e a gestão de atribuições RBAC são capacidades distintas. A listagem administrativa não deve exigir nem conceder implicitamente capacidade de alterar perfis. A autorização reutiliza o catálogo e o mecanismo RBAC existentes sem criar mecanismos paralelos de autorização.
- Q: A permissão `users.read` afeta a invariante de segurança do RBAC (garantia de administrador)? → A: Não. `users.read` integra a composição de permissões do perfil oficial Administrador, mas NÃO é incluída no conjunto/invariante das permissões necessárias para garantir que exista ao menos um administrador capaz de administrar o próprio RBAC. Essa invariante continua relacionada exclusivamente às capacidades administrativas de RBAC já existentes.
- Q: Qual é o comportamento padrão para contas ativas e inativas e como funciona o filtro `active`? → A: A consulta lista somente contas ativas por padrão (`deleted_at` ausente, equivalente a `active=true`). Contas inativas (`deleted_at` preenchido) podem ser consultadas explicitamente através de `active=false`.
- Q: Como funciona o filtro opcional `profile_id`? → A: O filtro por `profile_id` considera somente perfil ativo e atribuição ativa à conta.
- Q: Como a busca textual e a paginação devem operar? → A: Busca textual case-insensitive por substring literal em username ou e-mail. Paginação determinística por `offset` e `limit`, ordenada por username ascendente (case-insensitive) com `id` da conta como critério de desempate.
- Q: Há requisito de benchmark de performance com 10.000 contas nesta feature? → A: Não. O critério de benchmark com 10.000 contas em até 2 segundos foi removido da especificação sem substituição por outro requisito de performance.

### Session 2026-09-02

- Q: Como a resposta deve apresentar o cargo global da conta? → A: Cada resposta deve incluir os perfis globais ativos em `profiles`, com `id`, `name` e `active`. Uma conta pode ter mais de um perfil.
- Q: Qual é o caminho canônico da coleção de usuários? → A: `GET /users`, sem barra final. O cadastro público também usa `POST /users`.

### Session 2026-09-03

- Q: Como o nome completo deve ser armazenado e exposto? → A: O campo `full_name` é obrigatório em
  novos cadastros e o sistema remove espaços externos, aceitando de 1 a 255 caracteres. Contas
  antigas ou mockadas podem permanecer com `null` e podem ser completadas pela feature
  `008-admin-user-update`. O campo aparece no cadastro público, na identidade de `GET /auth/me` e
  nos itens de `GET /users`; ele não participa da busca, ordenação, filtros ou autorização.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Localizar uma conta ativa (Priority: P1)

Uma pessoa autorizada consulta a coleção de usuários e localiza uma conta ativa por username ou
e-mail. Cada resultado fornece o identificador necessário para operações administrativas
posteriores, como a atribuição de um perfil pelo RBAC.

**Why this priority**: A localização da conta, do nome completo e de seu identificador atende ao caso de uso que
motivou a feature e permite reutilizar as operações administrativas existentes.

**Independent Test**: Cadastrar contas ativas, consultar `GET /users` com e sem busca e confirmar
que a pessoa autorizada recebe páginas limitadas com os identificadores e dados administrativos
permitidos.

**Acceptance Scenarios**:

1. **Given** contas ativas cadastradas e uma pessoa autenticada com a permissão `users.read`,
   **When** ela consulta `GET /users` sem parâmetros, **Then** o sistema retorna HTTP 200 com a
   primeira página de contas ativas, limitada a 100 itens.
2. **Given** uma conta ativa conhecida, **When** a pessoa autorizada busca parte de seu username,
   **Then** o resultado contém a conta e seu identificador.
3. **Given** uma conta ativa conhecida, **When** a pessoa autorizada busca parte de seu e-mail,
   **Then** o resultado contém a conta, seu nome completo e seu identificador.
4. **Given** as buscas `joao`, `Joao` e `JOAO` sobre o mesmo conjunto de contas, **When** a pessoa
   autorizada executa cada busca, **Then** as três consultas retornam os mesmos itens na mesma
   ordem.
5. **Given** nenhum resultado compatível, **When** a pessoa autorizada consulta a coleção,
   **Then** o sistema retorna HTTP 200 com `items` vazio e preserva `offset` e `limit` na resposta.

---

### User Story 2 - Refinar e paginar a listagem (Priority: P2)

Uma pessoa autorizada combina busca, estado da conta e perfil de acesso para reduzir o conjunto de
resultados. Ela percorre esse conjunto por páginas sem receber todos os usuários em uma resposta.

**Why this priority**: Os filtros reduzem o trabalho de localização e atendem à necessidade do
frontend sem antecipar dados institucionais ou contextuais.

**Independent Test**: Preparar contas ativas e inativas com diferentes atribuições de perfil,
combinar os filtros definidos com `offset` e `limit` e comparar cada página com o conjunto
esperado.

**Acceptance Scenarios**:

1. **Given** mais contas compatíveis que o `limit` solicitado, **When** a pessoa consulta páginas
   sucessivas sem mudanças no conjunto, **Then** cada resposta contém no máximo `limit` itens e a
   ordenação mantém a sequência esperada entre as páginas.
2. **Given** contas ativas e inativas, **When** a pessoa omite `active` ou usa `active=true`,
   **Then** o sistema retorna somente contas ativas.
3. **Given** contas ativas e inativas, **When** a pessoa usa `active=false`, **Then** o sistema
   retorna somente contas inativas.
4. **Given** um perfil ativo com atribuições ativas, **When** a pessoa usa seu identificador em
   `profile_id`, **Then** o sistema retorna uma única vez cada conta que possui essa atribuição e
   também atende aos demais filtros.
5. **Given** busca, `active`, `profile_id`, `offset` e `limit` válidos, **When** a pessoa combina os
   parâmetros, **Then** o sistema aplica todos os critérios ao mesmo conjunto antes de selecionar a
   página.
6. **Given** um `offset` válido além do último resultado, **When** a pessoa consulta a página,
   **Then** o sistema retorna HTTP 200 com `items` vazio.

---

### User Story 3 - Proteger dados administrativos (Priority: P3)

O backend entrega a listagem somente a pessoas autenticadas que possuem a permissão específica de
consulta de usuários. A resposta limita cada item aos dados necessários para localizar e distinguir
contas.

**Why this priority**: A listagem reúne identificadores de contas e dados pessoais. O RF004 e a
constituição exigem autorização no backend antes da exposição.

**Independent Test**: Repetir a mesma consulta sem sessão, com sessão sem `users.read` e com sessão
autorizada, conferindo os códigos de resposta e os campos devolvidos.

**Acceptance Scenarios**:

1. **Given** uma requisição sem identidade autenticada, **When** ela consulta `GET /users`,
   **Then** o sistema retorna HTTP 401 e não devolve itens nem metadados da coleção.
2. **Given** uma conta autenticada sem `users.read`, **When** ela consulta `GET /users`, **Then** o
   sistema retorna HTTP 403 e não revela contas, contagens ou correspondências de busca.
3. **Given** uma conta que possui somente `rbac.read`, `rbac.profiles.manage` ou
   `rbac.assignments.manage`, **When** ela consulta `GET /users`, **Then** o sistema retorna HTTP
   403 enquanto essa conta não receber também `users.read`.
4. **Given** uma pessoa autorizada, **When** ela examina os itens retornados, **Then** cada item
   contém somente `id`, `username`, `email`, `active` e os perfis globais ativos em `profiles`.
5. **Given** qualquer consulta autorizada, **When** a pessoa examina a resposta, **Then** ela não
   encontra hash de senha, senha, token, credencial, dado interno de sessão nem campo interno de
   autenticação.
6. **Given** o perfil oficial Administrador com sua composição de permissões atualizada, **When** uma
   conta possui esse perfil ativo, **Then** suas permissões efetivas calculadas pelo RBAC incluem
   `users.read` sem remover as permissões administrativas existentes.
7. **Given** uma conta autenticada sem `users.read`, **When** o backend nega a consulta com HTTP
   403, **Then** o acompanhamento operacional registra a recusa e a trilha persistente de mudanças
   de RBAC não recebe um novo evento.

### Edge Cases

- `search` ausente, vazio ou composto apenas por espaços não restringe o conjunto; o sistema remove
  somente os espaços externos antes de decidir se aplica a busca.
- A busca interpreta o texto como substring literal em username ou e-mail. Caracteres com função
  de curinga em mecanismos internos não ampliam a busca por conta própria.
- A busca não distingue caixa e preserva a ordenação padrão dos resultados.
- `offset` menor que zero, `limit` menor que 1 ou `limit` maior que 100 retorna HTTP 422 sem itens.
- Valores que não representam booleano em `active` retornam HTTP 422.
- Um `profile_id` malformado retorna HTTP 422. Um identificador bem formado que não corresponde a
  um perfil ativo retorna HTTP 200 com `items` vazio.
- Uma atribuição encerrada ou um perfil inativo não produz correspondência para `profile_id`.
- Uma conta inativa pode aparecer somente em consultas com `active=false`. Seu item expõe
  `active=false`, sem dados sobre a causa, autoria ou momento da inativação.
- A reutilização de username ou e-mail após inativação pode produzir contas ativa e inativa com o
  mesmo identificador textual. A ordenação pelo identificador da conta desfaz o empate.
- `full_name` ausente retorna `null`; valor composto somente por espaços ou com mais de 255 caracteres
  retorna HTTP 422.
- Inserções, inativações ou mudanças de perfil entre duas requisições podem alterar a composição
  das páginas. A garantia de sequência entre páginas considera um conjunto sem mudanças durante a
  navegação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE disponibilizar a consulta administrativa na coleção `GET /users`;
  `POST /users` DEVE preservar os campos e comportamentos existentes e aceitar também `full_name`
  conforme FR-029.
- **FR-002**: O sistema DEVE exigir uma identidade autenticada antes de processar busca, filtros ou
  paginação da listagem administrativa.
- **FR-003**: O backend DEVE exigir a permissão estável `users.read` para devolver qualquer dado ou
  metadado da listagem.
- **FR-004**: A feature DEVE acrescentar `users.read` ao catálogo do RBAC existente e integrá-la à
  composição de permissões do perfil oficial Administrador, assegurando que qualquer conta com esse
  perfil ativo receba `users.read` pelo cálculo padrão de permissões efetivas, sem incluir
  `users.read` no conjunto invariante de permissões necessárias para a salvaguarda da administração
  do próprio RBAC.
- **FR-005**: A permissão `users.read` DEVE permanecer separada de `rbac.read`,
  `rbac.profiles.manage` e `rbac.assignments.manage`; possuir uma dessas permissões não concede as
  demais.
- **FR-006**: O backend DEVE usar o cálculo existente de permissões efetivas por perfis ativos e
  não DEVE autorizar pela presença de um nome de perfil nem por informação enviada pelo cliente.
- **FR-007**: Uma requisição sem identidade autenticada DEVE retornar HTTP 401 sem conteúdo da
  coleção.
- **FR-008**: Uma conta autenticada sem `users.read` DEVE receber HTTP 403 sem conteúdo protegido,
  contagem ou indicação de correspondência.
- **FR-009**: O sistema DEVE aceitar `offset` e `limit`, com `offset` padrão 0, `limit` padrão 100,
  `offset` mínimo 0 e `limit` entre 1 e 100, inclusive.
- **FR-010**: A resposta bem-sucedida DEVE conter somente `offset`, `limit` e `items`; `items` DEVE
  conter no máximo o número solicitado em `limit`.
- **FR-011**: O sistema NÃO DEVE devolver todos os usuários em uma única resposta quando a
  quantidade compatível exceder o `limit`.
- **FR-012**: A listagem DEVE ordenar contas por username em ordem crescente sem distinção de caixa
  e usar o identificador da conta em ordem crescente como desempate estável.
- **FR-013**: Em um conjunto sem mudanças, busca, filtros e paginação DEVEM preservar a ordenação de
  FR-012 e não DEVEM repetir uma conta por causa de múltiplas relações compatíveis.
- **FR-014**: O sistema DEVE aceitar `search` como busca de substring literal em username ou e-mail,
  sem distinção de caixa.
- **FR-015**: O sistema DEVE remover espaços externos de `search`; valor ausente, vazio ou composto
  somente por espaços DEVE produzir o mesmo conjunto que a ausência de busca textual.
- **FR-016**: O sistema DEVE aceitar o filtro booleano `active`. A ausência do filtro DEVE
  equivaler a `active=true`; `active=true` seleciona contas com `deleted_at` ausente e
  `active=false` seleciona contas com `deleted_at` preenchido.
- **FR-017**: O sistema DEVE aceitar `profile_id` como filtro opcional e selecionar somente contas
  com atribuição ativa ao perfil ativo indicado.
- **FR-018**: O sistema DEVE combinar `search`, `active`, `profile_id`, `offset` e `limit` sobre o
  mesmo conjunto, aplicando busca e filtros antes da seleção da página.
- **FR-019**: Um `offset` válido sem resultados ou qualquer combinação válida sem correspondência
  DEVE retornar HTTP 200 com `items` vazio.
- **FR-020**: Paginação ou filtro com formato ou faixa inválida DEVE retornar HTTP 422 sem resultado
  parcial.
- **FR-021**: Um `profile_id` bem formado sem perfil ativo correspondente DEVE produzir uma página
  vazia e não um erro de recurso inexistente.
- **FR-022**: Cada item da listagem DEVE conter somente `id`, `full_name`, `username`, `email`,
  `active` e `profiles`. `profiles` DEVE listar os perfis globais ativos da conta e cada perfil DEVE
  conter somente `id`, `name` e `active`.
- **FR-023**: O campo `id` DEVE identificar a mesma conta aceita pelas operações administrativas de
  RBAC existentes.
- **FR-024**: O campo `active` DEVE ser verdadeiro quando a conta não possui exclusão lógica e falso
  quando possui exclusão lógica.
- **FR-025**: A resposta NÃO DEVE conter `password_hash`, senha, tokens, credenciais, dados de
  sessão, permissões efetivas, dados internos de autenticação ou campos de auditoria. A lista de
  perfis não deve incluir permissões nem atribuições históricas.
- **FR-026**: A feature NÃO DEVE alterar cadastro, autenticação, ciclo de sessão, operações de RBAC,
  vínculos institucionais, vínculos laboratoriais nem designações de processo.
- **FR-027**: A feature NÃO DEVE criar filtros por instituição, laboratório, participação em
  processo, conflito de interesse ou outro conceito que dependa dos RF003, RF005 ou RF006.
- **FR-028**: A consulta, por não alterar conta ou RBAC, NÃO DEVE criar evento na trilha persistente
  de mudanças de RBAC. Recusas por ausência de `users.read` DEVEM manter o registro operacional de
  negação já definido pela feature 003.
- **FR-029**: O cadastro `POST /users` DEVE exigir `full_name` para novas contas. O valor DEVE ser
  uma string de 1 a 255 caracteres após a remoção de espaços externos.
- **FR-030**: O sistema DEVE rejeitar `full_name` vazio, composto somente por espaços ou com mais de
  255 caracteres, retornando HTTP 422 sem criar a conta.
- **FR-031**: O sistema DEVE preservar `full_name` como nulo somente para contas antigas ou mockadas
  que já não possuam o campo e DEVE persistir o valor aparado em novos cadastros e atualizações.
- **FR-032**: As respostas de `POST /users`, `GET /auth/me` e `GET /users` DEVEM expor `full_name`;
  seu valor DEVE corresponder ao valor persistido ou ser `null`.
- **FR-033**: `full_name` NÃO DEVE alterar busca, ordenação, filtros, autenticação, autorização ou
  os campos sensíveis expostos pelas respostas de usuário.

### Key Entities

- **Conta de usuário**: Registro identificado por id, username e e-mail, com `full_name` opcional.
  A presença de exclusão lógica determina se a conta está ativa para esta listagem.
- **Perfil de acesso**: Perfil global do RBAC existente. O filtro considera somente perfil ativo e
  sua atribuição ativa à conta.
- **Permissão de consulta de usuários**: Capacidade `users.read` do catálogo existente que autoriza
  a leitura da coleção administrativa sem conceder gestão de perfis ou atribuições.
- **Página de usuários**: Resultado limitado que informa `offset`, `limit` e uma coleção de itens
  administrativos.
- **Item administrativo de usuário**: Projeção com id, nome completo, username, e-mail, estado ativo
  e perfis globais ativos, sem credenciais, dados de sessão, permissões ou auditoria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários automatizados, uma conta com `users.read` localiza pelo username
  ou e-mail uma conta conhecida e obtém o identificador aceito pelas operações existentes de RBAC.
- **SC-002**: Em 100% dos cenários automatizados, consultas sem autenticação ou sem `users.read`
  não devolvem itens, contagens nem indicação de correspondência.
- **SC-003**: Em 100% das respostas bem-sucedidas, a quantidade de itens não excede o `limit`
  solicitado nem o máximo de 100.
- **SC-004**: Em um conjunto sem mudanças, a concatenação de todas as páginas cobre cada conta
  compatível uma vez e preserva a ordenação definida, sem omissões ou repetições.
- **SC-005**: As variações de caixa de cada termo usado no conjunto de aceitação retornam os mesmos
  identificadores na mesma ordem para buscas por username e por e-mail.
- **SC-006**: Todos os cenários de `search`, `active` e `profile_id`, isolados e combinados com
  paginação, retornam somente contas que atendem a todos os critérios informados.
- **SC-007**: Em 100% das respostas de listagem, cada item contém os seis campos permitidos e cada
  perfil contém somente `id`, `name` e `active`; nenhuma resposta contém senha, token, credencial,
  sessão, permissão ou auditoria.
- **SC-008**: Durante a validação manual, uma pessoa autorizada localiza uma conta conhecida e copia
  seu identificador em até 2 minutos, sem consultar outra fonte de dados.
- **SC-009**: Todos os cenários existentes de cadastro, autenticação e RBAC preservam seus resultados
  após a introdução da listagem administrativa.
- **SC-010**: 100% das contas com atribuição ativa ao perfil oficial Administrador obtêm `users.read`
  em suas permissões efetivas através do cálculo padrão do RBAC; nenhuma conta recebe essa permissão
  sem possuir um perfil ativo que a contenha.
- **SC-011**: Em 100% das recusas por ausência de `users.read`, o acompanhamento operacional recebe
  o registro da negação e a trilha persistente de mudanças de RBAC permanece inalterada.
- **SC-012**: Em 100% dos cadastros automatizados que informam `full_name`, o mesmo valor aparado
  aparece no cadastro, na identidade autenticada e na listagem administrativa.
- **SC-013**: Em 100% das contas antigas ou mockadas sem `full_name`, as três respostas de usuário
  continuam válidas e devolvem o campo com valor `null` até uma atualização posterior.

## Assumptions

- **CONFIRMADO, fonte oficial**: RF001 define cadastro e autenticação; RF002 define gestão de perfis;
  RF004 exige controle de acesso conforme perfil, instituição e participação. RF005 usa usuários
  em designações por processo, conforme `docs/plano-de-trabalho-fase-ii.md`, seção 3.1.
- **CONFIRMADO, fonte oficial**: RF034 exige registro de usuários, datas, alterações, decisões e
  eventos. A política geral de auditoria e a persistência de consultas de leitura ainda não foram
  definidas pela equipe.
- **DECISÃO TÉCNICA REGISTRADA**: A administração de usuários inclui consulta, atualização e
  inativação, mas cada feature define seus contratos e campos expostos, conforme
  `docs/planejamento/gestao-de-usuarios.md`. Esta feature cobre somente consulta e listagem.
- **CONFIRMADO, features 001 e 002**: Username e e-mail identificam contas sem distinção de caixa
  nas comparações de identidade, preservam a caixa armazenada e podem ser reutilizados após
  exclusão lógica. Uma conta excluída não autentica.
- **CONFIRMADO, feature 003 e implementação atual**: O RBAC calcula permissões pela união dos
  perfis ativos e permite que features aprovadas acrescentem permissões estáveis ao catálogo. O
  backend registra a recusa 403 por permissão no acompanhamento operacional.
- **CONFIRMADO, implementação atual**: A conta possui id, username, e-mail, hash de senha e campos
  do padrão de auditoria. `deleted_at` ausente representa conta ativa; o modelo não possui outro
  estado de conta.
- **CONFIRMADO, contratos atuais**: Páginas administrativas existentes usam `offset`, `limit` e
  `items`, com limite máximo de 100. O schema público de usuário expõe id, username e e-mail.
- **DECISÃO EXPLÍCITA DESTA ALTERAÇÃO, atualizada pela feature 008**: `full_name` é obrigatório em
  novos cadastros e anulável no armazenamento para preservar contas antigas ou mockadas. O valor
  informado é aparado e validado entre 1 e 255 caracteres.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: A listagem usa a permissão específica e estável `users.read`,
  que passa a integrar a composição de permissões do perfil oficial Administrador, assegurando que
  contas com esse perfil ativo a obtenham pelo cálculo padrão de permissões efetivas, para separar
  consulta de contas das três capacidades administrativas da feature 003. A capacidade de consulta
  de contas e a gestão de atribuições RBAC são capacidades distintas; a listagem administrativa não
  exige capacidade de alterar perfis e reutiliza o catálogo e mecanismo RBAC existentes sem criar
  mecanismos paralelos. A permissão `users.read` não integra o conjunto invariante de salvaguarda
  administrativa do RBAC.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: A consulta omite contas inativas por padrão (`active=true`,
  `deleted_at` ausente) e permite consultá-las com `active=false` (`deleted_at` preenchido). O item
  acrescenta somente o estado derivado da exclusão lógica.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: O filtro por perfil usa `profile_id` e considera somente
  atribuições ativas e perfis ativos. A resposta não replica a composição do RBAC; a consulta de
  acesso de uma conta permanece no contrato da feature 003.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: Cada item também expõe `profiles`, com os perfis globais
  ativos da conta e seus nomes de exibição. A lista pode conter mais de um perfil e não expõe
  permissões ou atribuições históricas.



## Scope and Traceability

| Fonte | Natureza | Cobertura nesta feature |
|---|---|---|
| RF001 | Requisito oficial | Reutiliza as contas cadastradas e preserva cadastro e autenticação. |
| RF002 | Requisito oficial | Permite localizar o identificador usado na atribuição de perfis e filtrar por atribuição ativa, sem alterar o RBAC. |
| RF004 | Requisito oficial | Protege a coleção com permissão do RBAC validada no backend. Não cria autorização contextual. |
| RF005 | Requisito oficial futuro | Entrega o identificador que pode apoiar designações futuras, sem implementar seleção ou designação por processo. |
| RF034 | Requisito oficial transversal | Preserva o registro operacional de recusas do RBAC; a política de auditoria de leituras continua pendente. |
| Backlog de Gestão de Usuários | Decisão técnica registrada | Entrega a operação de consulta e delimita atualização e inativação como features próprias. |
| Feature 001 | Especificação existente | Preserva os campos e comportamentos existentes do cadastro, ampliando o schema de forma compatível, além da regra de reutilização após exclusão lógica. |
| Feature 002 | Especificação existente | Reutiliza identidade autenticada e rejeita sessão ligada a conta inativa. |
| Feature 003 | Especificação existente | Reutiliza catálogo, perfis, permissões efetivas e registro operacional de recusas. |
| Código, testes e contratos atuais | Estado confirmado | Usa os campos existentes de conta, o padrão de página e os identificadores aceitos pelo RBAC. |

## Out of Scope

- Consulta individual, atualização administrativa, reativação e inativação de contas.
- Vínculo institucional ou laboratorial e filtros derivados do RF003.
- Seleção, elegibilidade ou designação de participantes do RF005.
- Conflito de interesse, regras contextuais de processo, isolamento entre laboratórios ou cegamento.
- Recuperação ou troca de senha, confirmação de e-mail e autenticação em dois fatores.
- Refresh token, revogação antecipada ou outra evolução do gerenciamento de sessão.
- Notificações, mensageria e mudanças no fluxo de cadastro ou autenticação.
- Ordenação configurável, busca avançada, exportação em lote ou CRUD completo de usuários.
- Busca, ordenação ou filtros baseados em `full_name`; o campo serve apenas para identificação e
  exibição nesta alteração.
- Exposição de permissões efetivas, vínculos, participações ou dados de auditoria nos itens. Os
  perfis globais ativos e seus nomes de exibição fazem parte do contrato desta feature.
- Registro persistente de cada consulta bem-sucedida. A equipe deve decidir essa política na feature
  geral de auditoria do RF034 antes de exigir retenção, consulta ou imutabilidade desses eventos.
