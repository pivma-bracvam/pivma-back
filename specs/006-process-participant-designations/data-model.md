# Data Model: Designações e Conflito de Interesse

## Visão geral

```text
ProcessInstance 1 ── * Assignment * ── 1 User
                             │
                             ├── 0..1 Laboratory
                             └── 1 ── * ConflictInterestDeclaration

Assignment / ConflictInterestDeclaration ── geram ── AuditEvent
User ── UserInstitutionalAffiliation ── Laboratory
```

`Assignment` continua sendo a fonte do papel local. O laboratório identifica o contexto dos dois papéis laboratoriais. A declaração referencia um ciclo de designação; o processo é alcançado por esse ciclo.

## Campos comuns de auditoria

`Assignment`, `ConflictInterestDeclaration` e `AuditEvent` usam o `AuditMixin` existente.

| Campo | Tipo | Nulável | Uso |
|---|---|---:|---|
| `created_at` | timestamp | não | Momento de criação |
| `updated_at` | timestamp | sim | Última alteração permitida do ciclo |
| `deleted_at` | timestamp | sim | Exclusão lógica legada; a API da feature não a expõe |
| `created_by` | UUID, FK para `users.id` | sim no banco | Responsável pela criação |
| `updated_by` | UUID, FK para `users.id` | sim | Responsável pela revogação quando aplicável |
| `deleted_by` | UUID, FK para `users.id` | sim | Responsável por exclusão lógica fora da API desta feature |

As operações autenticadas informam o responsável. A nulabilidade preserva o padrão de dados de sistema e migrações.

## Assignment

Tabela existente: `assignments`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK |
| `process_instance_id` | UUID | FK obrigatória para `process_instances.id` |
| `user_id` | UUID | FK obrigatória para `users.id` |
| `role_key` | varchar(64) | uma das oito chaves aprovadas para novas operações |
| `laboratory_id` | UUID | FK opcional para `laboratories.id`; nova coluna |
| `assigned_by` | UUID | FK obrigatória para `users.id` |
| `assigned_at` | timestamp com fuso | início do ciclo |
| `revoked_at` | timestamp com fuso | nulo enquanto o ciclo não foi revogado |
| auditoria | `AuditMixin` | autoria e datas técnicas |

Papéis locais:

| Papel | Laboratório |
|---|---|
| `lead_laboratory` | obrigatório |
| `participating_laboratory` | obrigatório |
| `group_manager` | proibido |
| `study_manager` | proibido |
| `statistician` | proibido |
| `adhoc_evaluator` | proibido |
| `peer_reviewer` | proibido |
| `proponent` | proibido |

Índices e constraints:

- Manter o índice único parcial `uq_assignments_active` em `(process_instance_id, user_id, role_key)` quando `revoked_at IS NULL AND deleted_at IS NULL`.
- Adicionar FK de `laboratory_id` para `laboratories.id`, sem exclusão em cascata.
- Reutilizar o prefixo do índice único para gestão local e listagem por processo e usuário.
- Não criar constraint estática para usuário ou vínculo ativos; a autorização consulta o estado atual.

Validações antes da inserção:

- processo e usuário existem e estão ativos; para `ProcessInstance`, ativo significa `deleted_at IS NULL`, sem regra adicional baseada em `status` ou `closed_at`;
- `role_key` pertence ao catálogo aprovado;
- papéis laboratoriais recebem laboratório ativo e vínculo institucional ativo entre usuário e laboratório;
- papéis não laboratoriais não recebem laboratório;
- não existe ciclo ativo para processo, usuário e papel.

### Estados derivados

| Estado | Condição | Efeito |
|---|---|---|
| `active` | `revoked_at` e `deleted_at` nulos | ciclo aparece na listagem atual |
| `revoked` | `revoked_at` preenchido | ciclo aparece somente no histórico |
| `effective` | ativo, usuário ativo e contexto laboratorial vigente quando exigido | pode conceder autorização |
| `ineffective` | ativo, mas usuário, laboratório ou vínculo exigido perdeu vigência | não concede autorização; permanece visível ao gestor |

Transições:

```text
inexistente ── designar ──> active/effective
active/effective ── perda de elegibilidade ──> active/ineffective
active/* ── revogar ──> revoked
revoked ── nova designação ──> novo ciclo active/effective
```

A API não reativa nem altera o papel de um ciclo. Mudanças exigem revogação e nova designação.

## ConflictInterestDeclaration

Nova tabela: `conflict_interest_declarations`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK |
| `assignment_id` | UUID | FK obrigatória para `assignments.id` |
| `has_conflict` | boolean | valor declarado |
| `justification` | text | obrigatório após remoção de espaços externos; não vazio |
| `declared_at` | timestamp com fuso | atribuído pela plataforma |
| auditoria | `AuditMixin` | `created_by` identifica o declarante |

Índices e constraints:

- FK de `assignment_id` sem exclusão em cascata.
- Índice `ix_conflict_declarations_assignment_time` em `(assignment_id, declared_at DESC, id DESC)`.
- A tabela não possui unicidade por designação porque cada nova declaração cria uma linha.

Validações antes da inserção:

- a designação existe, pertence ao processo da rota e mantém ciclo ativo;
- o usuário autenticado é o `user_id` da designação;
- a justificativa contém texto após normalização;
- o cliente não informa `declared_at` nem autoria.

### Estado e imutabilidade

```text
sem declaração ── declarar ──> declaração 1
declaração 1 ── declarar novamente ──> declaração 1 + declaração 2
```

Não há atualização, exclusão ou revogação de declaração. A consulta escolhe a última linha por `declared_at DESC, id DESC`.

## Estado de conflito do participante

O cálculo usa somente ciclos ativos, ainda que algum ciclo tenha perdido elegibilidade por laboratório ou vínculo:

1. selecionar os ciclos ativos do usuário no processo;
2. localizar a declaração mais recente de cada ciclo;
3. retornar conflito vigente se qualquer resultado tiver `has_conflict = true`.

Uma declaração `false` em um ciclo não elimina um `true` vigente em outro. A revogação retira o ciclo do cálculo, mas preserva suas declarações no histórico.

## AuditEvent

Tabela existente: `audit_events`

Não há mudança de schema. A feature acrescenta três tipos:

| `event_type` | Ator em `user_id` | Contexto obrigatório |
|---|---|---|
| `PARTICIPANT_ASSIGNED` | gestor ou criador do processo | `assignment_id`, `participant_user_id`, `role_key`, `laboratory_id`, `result`, `source` |
| `PARTICIPANT_REVOKED` | gestor | `assignment_id`, `participant_user_id`, `role_key`, `laboratory_id`, `result`, `source` |
| `CONFLICT_DECLARED` | titular | `assignment_id`, `participant_user_id`, `role_key`, `laboratory_id`, `has_conflict`, `justification`, `result`, `source` |

Todos os eventos recebem `process_instance_id` e `occurred_at`. `activity_run_id` permanece nulo porque as três operações não pertencem a uma execução de atividade. `source` usa `api` nas operações públicas e `process_creation` na designação automática do proponente.

Os eventos e a mudança pertencem à mesma transação. A aplicação não expõe alteração ou exclusão dos eventos.

## Permissão global

A migração amplia o catálogo existente.

| UUID | Código | Perfil inicial |
|---|---|---|
| `00000000-0000-0000-0000-000000000107` | `process.participants.manage` | Administrador |

A composição inicial usa `00000000-0000-0000-0000-000000000207`. Outros perfis não recebem a permissão. O papel local `group_manager` concede o mesmo conjunto de operações somente no processo de sua designação efetiva.

## Consultas e ordenação

### Participantes atuais

- Filtrar ciclos ativos por `process_instance_id`.
- Gestor recebe todos; participante recebe somente `user_id` próprio.
- Ordenar por `assigned_at DESC, id DESC`.
- Calcular `effective`, `has_conflict` e `latest_declared_at`.
- `has_conflict = null` representa ausência de declaração atual.

### Histórico

- Aplicar o mesmo escopo do usuário.
- Ordenar ciclos por `assigned_at DESC, id DESC`.
- Paginar ciclos com `offset` e `limit`, no máximo 200.
- Ordenar declarações de cada ciclo por `declared_at ASC, id ASC`.
- Gestores e o titular recebem a justificativa; outros usuários não recebem o ciclo.

### Timeline

- Manter a ordenação atual por `occurred_at ASC, id ASC`.
- Gestores recebem todos os três tipos novos.
- Participantes recebem somente eventos com seu `participant_user_id`.
- Pessoas externas ao processo não recebem os três tipos novos; os eventos anteriores seguem o contrato existente.

## Migração

Upgrade após `5e31a8c7d204`:

1. adicionar `assignments.laboratory_id` e sua FK;
2. converter `assignments.role_key = 'PROPONENT'` para `proponent`;
3. criar `conflict_interest_declarations` e o índice de última declaração;
4. inserir `process.participants.manage` e sua composição com Administrador;
5. não criar laboratórios, declarações ou eventos retroativos.

Downgrade:

1. remover composições que referenciem a nova permissão e remover a permissão;
2. remover índice e tabela de declarações;
3. converter `proponent` para `PROPONENT`;
4. remover FK e coluna laboratorial;
5. preservar usuários, processos, tarefas, designações e eventos anteriores.
