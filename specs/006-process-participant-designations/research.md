# Research: Designações e Conflito de Interesse

## 1. Limite funcional

**Decisão:** implementar designação, revogação, consulta atual, histórico, declaração de conflito, bloqueio das mutações avaliativas existentes e auditoria correspondente.

**Motivo:** esse conjunto cobre RF005, RF006 e a parcela de RF034 aprovada na especificação. O backend atual já possui processo, designação, tarefa e evento; a feature deve evoluir esses conceitos.

**Alternativas consideradas:** criar matriz completa de tarefas, fluxo de aprovação da declaração ou alertas assíncronos. Essas opções foram rejeitadas porque pertencem a requisitos futuros ou estão fora do escopo.

## 2. Compatibilidade dos papéis locais

**Decisão:** usar as oito chaves minúsculas da spec nas designações. A migração converte `PROPONENT` para `proponent`; a criação de novos processos passa a gravar `proponent`. `Task.assigned_role` mantém os valores existentes, como `PROPONENT` e `TRIAGE_LEAD`.

**Motivo:** `Assignment` representa participação local e precisa seguir o catálogo aprovado. Alterar os papéis de `Task` quebraria contratos da feature 004 sem necessidade. A guarda de conflito atua pelo usuário e processo, sem depender da grafia do papel da tarefa.

**Alternativas consideradas:** converter também todas as tarefas para minúsculas ou aceitar duas grafias nas designações. A primeira altera um contrato existente; a segunda permite duplicidade lógica entre `PROPONENT` e `proponent`.

## 3. Evolução da persistência

**Decisão:** adicionar `laboratory_id` opcional a `assignments` e criar `conflict_interest_declarations`. A declaração referencia somente `assignment_id`; o processo é obtido pela relação obrigatória da designação.

**Motivo:** a designação continua sendo a fonte do participante, do papel e do processo. Repetir `process_instance_id` na declaração exigiria uma FK composta e permitiria inconsistência se a validação falhasse. Uma tabela própria preserva as declarações sucessivas sem alterar o ciclo.

**Alternativas consideradas:** armazenar o conflito atual em `assignments`, guardar declarações em JSON ou repetir o processo na declaração. As duas primeiras apagam ou enfraquecem o histórico; a terceira duplica estado.

## 4. Integridade e vínculo laboratorial

**Decisão:** a API exige laboratório para `lead_laboratory` e `participating_laboratory`, rejeita laboratório nos outros papéis e verifica processo, usuário, laboratório e vínculo institucional vigentes. Para esta feature, `ProcessInstance` está ativo quando `deleted_at` é nulo; `status` e `closed_at` não recebem outra regra. O banco mantém a FK para `laboratories.id` e a unicidade parcial existente em `(process_instance_id, user_id, role_key)`.

**Motivo:** a elegibilidade institucional depende do estado atual de três entidades e não cabe em uma constraint estática. A FK evita laboratório inexistente; o serviço de autorização recalcula a elegibilidade em cada pedido. A unicidade parcial resolve duplicidades concorrentes.

**Alternativas consideradas:** copiar `institution_id` para a designação, criar FK direta para o vínculo ou inativar a designação em cascata. Essas opções duplicam estado ou alteram o histórico quando o vínculo muda.

## 5. Capacidade global e gestão local

**Decisão:** adicionar `process.participants.manage` ao catálogo e concedê-la somente ao perfil protegido de Administrador na migração. Uma designação efetiva de `group_manager` autoriza gestão somente no próprio processo.

**Motivo:** a spec exige uma capacidade global para inicializar e recuperar a gestão e uma capacidade contextual. O RBAC existente já resolve a parte global; `Assignment` resolve o processo específico.

**Alternativas consideradas:** conceder a permissão global ao perfil `management_group`, reutilizar `rbac.assignments.manage` ou permitir que qualquer participante designe. A primeira concede alcance global a um papel que a spec trata como local; a segunda mistura perfil global com participação; a terceira viola a fronteira de autorização.

## 6. Estado efetivo da designação

**Decisão:** distinguir ciclo ativo de designação efetiva. O ciclo está ativo quando não possui revogação nem exclusão lógica. Ele é efetivo quando, além disso, o usuário está ativo e, para papel laboratorial, laboratório e vínculo correspondente estão ativos.

**Motivo:** a revogação preserva história, enquanto a perda de elegibilidade deve retirar acesso no pedido seguinte sem reescrever o ciclo. A listagem atual inclui ciclos ativos e informa `effective` para que o gestor identifique a perda de elegibilidade.

**Alternativas consideradas:** revogar automaticamente quando usuário, laboratório ou vínculo muda. A atualização em cascata registraria uma decisão que o gestor não tomou e dificultaria reconstruir o motivo original.

## 7. Estado atual do conflito

**Decisão:** a declaração mais recente de cada ciclo ativo, ordenada por `declared_at DESC, id DESC`, define o estado daquele ciclo. O usuário está em conflito no processo quando pelo menos um ciclo ativo possui declaração atual verdadeira. Um ciclo sem declaração não bloqueia.

**Motivo:** a regra segue FR-018 e FR-019 e impede que outro papel contorne um conflito existente. O identificador desempata declarações com o mesmo timestamp.

**Alternativas consideradas:** copiar um booleano para `Assignment`, considerar somente a designação usada pela tarefa ou exigir declaração antes de agir. Essas opções apagariam histórico, permitiriam desvio por outro papel ou ampliariam a spec.

## 8. Integração com tarefas avaliativas e decisórias

**Decisão:** criar uma consulta reutilizável de conflito por usuário e processo e chamá-la no início de `save_field_reviews` e `execute_triage_decision`. A guarda lança `AuthorizationError` antes de qualquer alteração. O router de triagem converte somente essa exceção em resposta 403; `ConflictError` mantém o uso e o status legados.

**Motivo:** esses são os dois fluxos avaliativos ou decisórios implementados. A função poderá ser usada pelos módulos futuros quando surgirem ações de `statistician`, `adhoc_evaluator`, `peer_reviewer` ou gestores.

**Alternativas consideradas:** criar endpoints genéricos para iniciar e concluir tarefas ou bloquear a leitura de tarefas. A spec não pede novos fluxos de tarefa nem proíbe consulta; ela bloqueia execução avaliativa ou decisória.

## 8.1 Proteção de origem das mutações

**Decisão:** aplicar a proteção de origem às três mutações públicas criadas nesta feature: designar, revogar e declarar conflito. As rotas legadas de triagem mantêm seu contrato de origem atual.

**Motivo:** a decisão atende à proteção de origem da autenticação por cookie sem estender esta feature a uma correção transversal de rotas legadas.

## 9. Contrato HTTP e visibilidade

**Decisão:** criar cinco operações sob `/processes/{process_id}/participants`: listar, designar, revogar, declarar e consultar histórico. Gestores veem todos os participantes; um participante vê somente os próprios registros. O histórico usa `offset` e `limit`, limitado a 200 ciclos.

**Motivo:** o conjunto corresponde às operações pedidas e reutiliza paginação por deslocamento já adotada no projeto. Um único caminho de listagem aplica o escopo calculado no backend.

**Alternativas consideradas:** criar rotas `/me`, separar histórico de designações e declarações ou expor consulta global fora do processo. Essas opções aumentam a superfície sem novo comportamento.

## 10. Privacidade dos eventos na timeline

**Decisão:** gravar `PARTICIPANT_ASSIGNED`, `PARTICIPANT_REVOKED` e `CONFLICT_DECLARED` em `audit_events`. A timeline mantém os eventos existentes, mas filtra esses três tipos: gestores veem todos; participantes veem somente eventos cujo `participant_user_id` corresponde à própria conta; pessoas externas ao processo não recebem esses eventos.

**Motivo:** FR-025 exige contexto e justificativa no evento; FR-023 e FR-014 restringem sua exposição. Filtrar somente os novos tipos preserva o contrato anterior da timeline.

**Alternativas consideradas:** omitir justificativa do evento, restringir toda a timeline ou criar outra tabela de auditoria. A primeira viola a spec, a segunda altera eventos existentes e a terceira duplica a trilha do processo.

## 11. Atomicidade e imutabilidade

**Decisão:** designação, inclusive a automática do proponente na criação do processo, revogação e declaração adicionam o `AuditEvent` na mesma transação. A designação automática usa `PARTICIPANT_ASSIGNED` e `source=process_creation`. O contrato não oferece atualização ou exclusão de declarações e eventos. Violações esperadas de unicidade são convertidas em `409 Conflict`.

**Motivo:** a transação impede mudança concluída sem rastro. A ausência de operações mutáveis mantém o histórico append-only no acesso normal da aplicação.

**Alternativas consideradas:** emitir evento após o commit, permitir correção da declaração ou usar mensageria. Essas opções admitem perda de auditoria ou ampliam o ciclo aprovado.

## 12. Migração e seed

**Decisão:** criar uma revisão após `5e31a8c7d204`. Ela adiciona a coluna e FK laboratorial, cria a tabela e o índice de declarações, normaliza `PROPONENT`, insere `process.participants.manage` com UUID estável terminado em `107` e associa a permissão ao Administrador com UUID terminado em `207`.

**Motivo:** a feature 005 é o head confirmado pela cadeia de migrações inspecionada. Os UUIDs continuam a sequência do catálogo. O downgrade remove a permissão e a tabela, remove a coluna e converte `proponent` para `PROPONENT` para restaurar o contrato anterior.

**Alternativas consideradas:** seed no startup, script separado ou backfill de declarações e laboratórios. A migração oferece instalação determinística; os backfills criariam dados sem fonte.

## 13. Estratégia e granularidade dos testes

**Decisão:** usar unidade para schemas; PostgreSQL real para predicates de autorização e conflito, constraints, consulta atual, migração e concorrência; TestClient para contratos e segurança. Cada teste prova um comportamento observável. Casos parametrizados compartilham a mesma regra e variam somente a entrada.

**Motivo:** autorização e conflito têm risco crítico. Índice parcial, FK, consulta de última declaração e concorrência dependem do banco real. A metodologia do projeto exige separar caminho de sucesso, código de erro, fronteira de autorização, auditoria, paginação e concorrência.

**Alternativas consideradas:** testes de mega-cenário, mocks para constraints ou um teste de rota que também valide evento, segurança e ordenação. Esses formatos escondem a causa da falha e não oferecem evidência isolada para cada requisito.

## 14. Organização da implementação

**Decisão:** manter transações no router de participantes, predicates em `authorization.py` e a guarda de conflito em `process_engine.py`. Não criar camada repository/service.

**Motivo:** o projeto usa esse padrão nos módulos de RBAC e vínculo institucional. As consultas reutilizadas por router, timeline e engine pertencem ao módulo de autorização; as mutações permanecem em um único router.

**Alternativas consideradas:** um repository por entidade, policy engine genérico ou serviço de eventos. A feature não apresenta consumidores nem variações suficientes para justificar essas abstrações.
