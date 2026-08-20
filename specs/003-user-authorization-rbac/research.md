# Pesquisa técnica: Autorização de Usuários e RBAC

## Limite funcional

**Decisão**: implementar somente RBAC global e proteger as operações administrativas desta feature. O catálogo inicial não concede permissões de submissão, IA, processo, laboratório ou avaliação.

**Justificativa**: RF002 exige perfis e permissões. A `spec.md` limita RF004 à dimensão de perfil e reserva instituição e participação para RF003 e RF005. O backlog de Gestão de Usuários adota a mesma ordem.

**Alternativas consideradas**:

- Incluir instituições, laboratórios ou processos: antecipa entidades e matrizes ainda não aprovadas.
- Criar uma linguagem genérica de policies: acrescenta hierarquia e expressões que a especificação exclui.

## Persistência relacional

**Decisão**: criar `access_profiles`, `permissions`, `access_profile_permissions` e `user_access_profiles`, todas com `AuditMixin`. Usar relações normalizadas e índices parciais para garantir um nome ativo por perfil, uma composição ativa por perfil/permissão e uma atribuição ativa por conta/perfil.

**Justificativa**: o modelo muitos-para-muitos atende à união cumulativa aprovada e preserva cada ciclo de concessão e retirada. Índices parciais seguem o padrão atual de contas ativas e resolvem corridas no banco.

**Alternativas consideradas**:

- Array ou JSON de permissões no perfil: perde integridade referencial e dificulta o histórico da composição.
- Permissões diretas na conta: ignora a gestão por perfis exigida pelo RF002.
- Unicidade histórica das relações: impediria nova concessão depois de uma retirada preservada.

## Catálogos iniciais

**Decisão**: a migração insere os nove perfis oficiais com chaves internas determinísticas e as permissões `rbac.read`, `rbac.profiles.manage` e `rbac.assignments.manage`. O perfil Administrador recebe as três. Os outros oito começam sem permissão. Perfis e permissões semeados pela migração usam autoria nula.

**Justificativa**: chaves internas protegem os nomes oficiais sem usá-los em decisões de autorização. Códigos de permissão estáveis permitem que dependências declarem a capacidade exigida. A migração oferece o mesmo catálogo em todos os ambientes sem endpoint para criar permissões livres.

**Alternativas consideradas**:

- Usar o nome exibido como chave: renomeação, caixa e tradução poderiam alterar regras de acesso.
- Criar permissões por API: viola FR-007.
- Importar modelos na migração: mudanças futuras no código poderiam quebrar uma revisão histórica.

## Rastreabilidade restrita

**Decisão**: criar `rbac_changes` para registrar somente `action`, tipo e identificador do alvo, responsável e momento. Cada mutação grava estado e mudança na mesma transação. Somente a recusa 403 emitida após a verificação de permissão vai ao logger operacional; ela não entra nessa tabela.

**Justificativa**: `AuditMixin` registra criação, última atualização e exclusão. Ele não preserva duas alterações sucessivas do mesmo perfil. A tabela estreita cumpre FR-018 e FR-025 sem armazenar valores anteriores, IP, retenção ou eventos de outros módulos.

**Alternativas consideradas**:

- Usar somente `AuditMixin`: perderia mudanças intermediárias.
- Criar auditoria genérica com payload anterior e posterior: amplia RF034 além da decisão aprovada.
- Persistir recusas: contraria a Session 2026-08-19.

## Avaliação de permissão

**Decisão**: uma dependência `require_permission(code)` consulta a existência de uma atribuição ativa, perfil ativo e composição ativa para a conta autenticada. A ordem será autenticação, origem confiável nas mutações, permissão e consulta do alvo. A recusa usa 403 uniforme antes de resolver o recurso.

**Justificativa**: a consulta por pedido cumpre a revogação imediata sem alterar o JWT. A verificação anterior ao alvo impede que identificadores existentes e inexistentes produzam respostas diferentes para uma conta proibida.

**Alternativas consideradas**:

- Colocar perfis ou permissões no JWT: conserva acesso removido até a expiração.
- Cachear permissões entre pedidos: viola FR-017 sem um mecanismo adicional de invalidação.
- Importar dependências entre routers: cria acoplamento circular; um módulo compartilhado é menor e explícito.

## Contrato administrativo

**Decisão**: expor seis caminhos sob `/rbac`: catálogo de permissões; lista e criação de perfis; alteração e inativação de um perfil; acesso efetivo de uma conta; concessão e retirada de perfil; e lista paginada de mudanças. A alteração de perfil substitui seu conjunto de permissões em uma transação.

**Justificativa**: nove operações cobrem as jornadas da especificação. Substituir a composição evita dois endpoints por permissão e aplica a mudança como uma unidade. A consulta de acesso agrega perfis e permissões efetivas sem criar administração de contas.

**Alternativas consideradas**:

- CRUD individual de cada vínculo perfil/permissão: aumenta a superfície sem novo requisito.
- Acrescentar perfis a `/auth/me`: altera o contrato da feature 002.
- Criar busca ou edição de contas: pertence à feature de administração de usuários.

## Origem confiável e CORS

**Decisão**: extrair a validação de `Origin` existente para uma dependência reutilizada pelo logout e por todas as mutações RBAC. Ampliar CORS somente para `GET`, `POST`, `PATCH` e `DELETE`, mantendo origens explícitas e credenciais.

**Justificativa**: a autenticação usa cookie. A feature 002 aprovou `SameSite=Strict` com validação exata de origem nas operações autenticadas que alteram estado. A extração evita repetir a mesma regra.

**Alternativas consideradas**:

- Confiar somente em CORS: CORS não autoriza a operação no backend.
- Adicionar token CSRF: muda uma decisão aprovada sem requisito novo.
- Permitir todos os métodos: amplia a superfície sem uso.

## Preservação do Administrador

**Decisão**: bloquear a linha do perfil `administrator` durante mudanças que possam retirar capacidade administrativa. A mesma transação aplica a mudança, confirma que ao menos uma conta ativa preserva as três permissões e desfaz a operação se o conjunto ficar vazio.

**Justificativa**: uma contagem sem bloqueio permite que duas transações concorrentes removam os últimos administradores. Um bloqueio comum serializa essas mudanças. A regra cobre o perfil oficial e perfis adicionais que recebam as três capacidades.

**Alternativas consideradas**:

- Proteger somente a última atribuição ao perfil Administrador: ignora perfis adicionais com as três permissões.
- Restrição declarativa no banco: a condição cruza contas, perfis e duas relações.
- Contagem sem `FOR UPDATE`: falha sob duas retiradas concorrentes.

## Bootstrap do primeiro Administrador

**Decisão**: criar um comando idempotente `python -m pivma.bootstrap_rbac --user-id <UUID>`, executado depois da migração e da criação da conta indicada. O comando usa uma transação, falha com saída diferente de zero para conta ausente ou inativa e não escolhe outra conta. Se outra conta já possuir o perfil Administrador, o comando falha; se a mesma conta já o possuir, encerra sem duplicar. A primeira atribuição usa autoria nula e registra `bootstrap.admin_assigned`.

**Justificativa**: uma base nova pode não possuir conta durante a migração. Um hook de inicialização executaria em cada processo e poderia refazer uma concessão removida. A autoria nula registra a única exceção necessária: nenhuma identidade autorizada existe antes da primeira atribuição.

**Alternativas consideradas**:

- Promover a primeira conta: FR-024 proíbe escolha automática.
- Ler a conta na migração: acopla revisão de schema ao estado operacional.
- Executar a atribuição em toda inicialização da aplicação: cria mutação implícita e corrida entre processos.
- Modelar uma identidade de implantação: acrescenta um novo tipo de ator fora da especificação.

## Estratégia de testes

**Decisão**: usar API como evidência principal das jornadas, PostgreSQL real para consultas, constraints, migração e três corridas, e unidade somente para ramos isoláveis de autorização. Reutilizar `engine`, savepoints, `client`, `UserFactory`, `auth_token` e a suíte de regressão existentes.

**Justificativa**: autorização tem risco crítico e exige 401, 403, não vazamento e revogação verificadas no contrato HTTP. Índices parciais e bloqueios precisam do PostgreSQL. CRUD simples não justifica repository ou testes duplicados por camada.

**Alternativas consideradas**:

- Mockar `AsyncSession` para constraints e concorrência: não prova comportamento do banco.
- Testar login real em cada caso: repete a feature 002 e adiciona custo de hash.
- Adicionar xdist ou nova infraestrutura de fixtures: não há ganho demonstrado no escopo atual.
