# Research: Vinculação Institucional

## 1. Limite funcional

**Decisão:** implementar somente catálogos de instituições e laboratórios, vínculos de usuários, autorização, inativação, histórico e consulta do escopo institucional.

**Motivo:** esse é o limite de RF003 aprovado na especificação. RF005, RF006, refresh token, 2FA e mensageria estão explicitamente fora do escopo.

**Alternativas consideradas:** antecipar regras de estudos, submissões ou notificações. Foram rejeitadas porque dependeriam de requisitos ainda não aprovados.

## 2. Persistência relacional

**Decisão:** criar as tabelas `institutions`, `laboratories`, `user_institutional_affiliations` e `institutional_changes`, todas com `AuditMixin`.

**Motivo:** instituições, laboratórios e vínculos têm ciclos de vida próprios. O histórico de alterações precisa permanecer consultável mesmo após inativação. Quatro tabelas atendem ao requisito sem introduzir herança, tipos genéricos ou armazenamento documental.

**Alternativas consideradas:** armazenar laboratório como texto no vínculo ou usar uma tabela genérica de unidades organizacionais. A primeira não garante catálogo e integridade; a segunda acrescenta hierarquia e abstração não exigidas.

## 3. Cardinalidade e unicidade ativa

**Decisão:** cada laboratório pertence a exatamente uma instituição. Um usuário pode possuir vários vínculos ativos; cada vínculo contém uma instituição e, opcionalmente, um laboratório dessa instituição. Dois índices únicos parciais impedem duplicidade ativa para vínculos com e sem laboratório.

**Motivo:** a decisão resolve a cardinalidade esclarecida e preserva histórico por exclusão lógica. A restrição composta entre laboratório e instituição garante integridade também em gravações concorrentes ou fora da API.

**Alternativas consideradas:** um único vínculo por usuário, laboratório obrigatório ou uma instituição primária. Foram rejeitadas por conflito com a especificação esclarecida. Uma constraint única com coluna nula também foi rejeitada porque o tratamento padrão de `NULL` permitiria duplicidades de vínculo somente institucional.

## 4. Estado efetivo e inativação

**Decisão:** inativar uma entidade preenche `deleted_at` e `deleted_by`, sem exclusão física e sem reativação. A inativação de instituição ou laboratório não altera em massa os descendentes. Um vínculo é efetivamente ativo somente quando vínculo, usuário, instituição e laboratório opcional estão ativos.

**Motivo:** a regra preserva o histórico original e evita atualizações em cascata difíceis de auditar. A consulta própria e a consulta reutilizável de escopo filtram o estado efetivo no momento da requisição.

**Alternativas consideradas:** apagar vínculos em cascata ou copiar um estado derivado para cada vínculo. Ambas duplicariam estado e exigiriam sincronização adicional. Reativação foi rejeitada porque não foi especificada.

## 5. Permissões e consulta própria

**Decisão:** adicionar `institutional.read`, `institutional.catalogs.manage` e `institutional.affiliations.manage`. O perfil Administrador recebe as três na migração. Um usuário autenticado consulta somente os próprios vínculos efetivamente ativos sem permissão adicional.

**Motivo:** essa separação foi escolhida na etapa de esclarecimento. Ela permite delegar leitura, manutenção de catálogo e gestão de vínculos de forma independente. A rota própria deriva o usuário do token e não aceita `user_id` do cliente.

**Alternativas consideradas:** uma permissão institucional única ou duas permissões combinando leitura e gestão. Foram substituídas pela decisão explícita de três permissões.

## 6. Contrato HTTP

**Decisão:** expor oito caminhos sob `/institutional`, com quinze operações: listagem, consulta individual e mutação de instituições e laboratórios, consulta própria, consulta e criação de vínculos por usuário, inativação de vínculo e histórico paginado.

**Motivo:** o conjunto cobre a listagem e a consulta exigidas por FR-027 sem criar uma listagem irrestrita de vínculos de todos os usuários. As listas de catálogo, as consultas individuais e a consulta administrativa por usuário incluem ativos e inativos; a consulta própria retorna apenas vínculos efetivamente ativos.

**Alternativas consideradas:** endpoints de reativação, exclusão física, alteração de instituição do laboratório, atualização de vínculo e consulta global de todos os vínculos. Foram rejeitados por ausência de requisito ou por aumentarem o risco de alterar histórico.

## 7. Transações, conflitos e histórico

**Decisão:** cada mutação e seu registro em `institutional_changes` são persistidos na mesma transação. O histórico registra ação, tipo e identificador do alvo, além do `AuditMixin`, sem snapshots completos. Violações esperadas de unicidade e integridade são convertidas em `409 Conflict`.

**Motivo:** a transação impede alteração sem rastro correspondente. O estado atual permanece auditável nos modelos e o registro estreito de eventos atende à rastreabilidade com o padrão já adotado pelo RBAC.

**Alternativas consideradas:** emitir eventos depois do commit, armazenar documentos completos antes e depois ou introduzir mensageria. A primeira admite perda de histórico; as demais aumentam escopo e complexidade sem requisito aprovado.

## 8. Migração e catálogo RBAC

**Decisão:** criar uma migração Alembic após `1bd1b3d5ddad`, sem backfill. A migração cria tabelas, constraints e índices, usa os UUIDs estáveis terminados em `104`, `105` e `106` para as três permissões e associa todas ao perfil Administrador protegido com composições terminadas em `204`, `205` e `206`. O downgrade remove todas as composições que referenciem essas permissões, depois as permissões e as tabelas da feature.

**Motivo:** não existem dados institucionais anteriores para migrar. Identificadores estáveis tornam o seed e os testes determinísticos. A ordem do downgrade respeita referências sem remover usuários ou RBAC preexistente.

**Alternativas consideradas:** seed em inicialização da aplicação ou script separado. Foram rejeitadas porque fragmentariam a instalação e poderiam produzir ambientes inconsistentes.

## 9. Estratégia de testes

**Decisão:** usar testes unitários somente para validação isolada de schemas; testes de integração com PostgreSQL real para constraints, escopo e migração; testes HTTP para jornadas e segurança; e testes concorrentes para criação duplicada de instituição e vínculo.

**Motivo:** a maior parte do risco está em constraints PostgreSQL, autorização e atomicidade, não em funções puras. A estrutura existente já oferece TestClient, savepoints, Testcontainers, Factory Boy e sessões independentes para concorrência.

**Alternativas consideradas:** mocks de banco para regras relacionais ou SQL manual para preparar cenários comuns. Foram rejeitadas porque não validariam índices parciais e FKs compostas ou duplicariam a infraestrutura ORM existente.
