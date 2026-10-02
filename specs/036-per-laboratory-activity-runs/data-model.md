# Data Model: Execução de atividades por laboratório participante

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Uma migração Alembic, encadeada em `cc6c65843305_blind_sample_coding`. Ela
altera duas tabelas e cria uma. Processos existentes não mudam de
comportamento: as colunas novas têm padrão de execução única.

## `activity_instances` (alterada)

| Coluna | Tipo | Regra |
|---|---|---|
| `execution_scope` | `VARCHAR(32) NOT NULL DEFAULT 'process'` | `'process'` ou `'per_laboratory'`; copiada do template na instanciação (R1) |
| `is_custody` | `BOOLEAN NOT NULL DEFAULT false` | `true` só com `execution_scope = 'per_laboratory'` (R2, regra 4) |

**Status de atividade `per_laboratory`** (derivado, R5):

> Uma atividade por laboratório atinge `COMPLETED` se, e somente se, para
> **todo** laboratório do conjunto congelado existir uma execução vigente com
> status `COMPLETED` ou `WAIVED`.

| Condição | Status |
|---|---|
| ainda não ativada (FR-004a) | `BLOCKED` |
| ativada, e todo laboratório congelado tem execução vigente `COMPLETED` ou `WAIVED` | `COMPLETED` |
| ativada, outro caso | `IN_PROGRESS` |

A ativação cria uma execução para cada laboratório congelado, e toda
execução encerrada por cascata é substituída por uma nova `BLOCKED` (R10).
Por isso, depois da ativação, todo laboratório congelado tem execução
vigente. A regra confere contra a lista congelada, não contra as execuções
existentes.

Atividades `process` mantêm as transições atuais.

## `activity_runs` (alterada)

| Coluna | Tipo | Regra |
|---|---|---|
| `laboratory_id` | `UUID NULL REFERENCES laboratories(id)` | preenchida só em atividade `per_laboratory` (FR-004) |

**Índice**: `uq_activity_runs_number_active` passa a ser
`UNIQUE (activity_instance_id, laboratory_id, run_number) NULLS NOT DISTINCT
WHERE deleted_at IS NULL` (R4).

**Execução vigente do laboratório**: maior `run_number` não excluído para o
par `(activity_instance_id, laboratory_id)`.

**Estados da execução** (R5, R14). Terminais: `COMPLETED`, `CANCELLED`,
`WAIVED`, `SUPERSEDED` (`IMMUTABLE_RUN_STATUSES`). Abertos: `IN_PROGRESS`,
`BLOCKED`.

```text
(ativação, dependências do lab resolvidas)   ▶ IN_PROGRESS  (Task READY, FormInstance se houver formulário)
(ativação, dependência do lab pendente)      ▶ BLOCKED      (sem Task)
(ativação, lab dispensado, sem custódia)     ▶ WAIVED       (Task criada CANCELLED)
BLOCKED     ──dependências do lab resolvidas─▶ IN_PROGRESS  (Task READY criada)
BLOCKED     ──lab dispensado, sem custódia───▶ WAIVED       (Task criada CANCELLED)
IN_PROGRESS ──conclusão do laboratório──────▶ COMPLETED    (Task COMPLETED)
IN_PROGRESS ──dispensa na fase──────────────▶ WAIVED       (Task CANCELLED)
COMPLETED   ──reabertura do laboratório─────▶ SUPERSEDED   (+ execução n+1 IN_PROGRESS)
COMPLETED   ──reabertura a montante─────────▶ SUPERSEDED   (+ execução n+1 BLOCKED, R10)
IN_PROGRESS ──reabertura a montante─────────▶ CANCELLED    (Task CANCELLED; + execução n+1 BLOCKED)
IN_PROGRESS | BLOCKED ──cancelamento do processo──▶ CANCELLED (FR-039)
```

Estados terminais nunca mudam, nem no cancelamento do processo (FR-039).
Valores, anexos, decisões e artefatos ligados à execução nunca são alterados
por essas transições (FR-024).

## `laboratory_waivers` (nova)

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | `UUID PK` | |
| `process_instance_id` | `UUID NOT NULL REFERENCES process_instances(id)` | |
| `phase_id` | `UUID NOT NULL REFERENCES phases(id)` | fase do processo dispensada |
| `laboratory_id` | `UUID NOT NULL REFERENCES laboratories(id)` | deve estar no conjunto congelado |
| `reason` | `TEXT NOT NULL` | não vazio após `strip` |
| colunas de `AuditMixin` | | `created_by` é o autor da dispensa |

**Índice**: `UNIQUE (phase_id, laboratory_id) WHERE deleted_at IS NULL`
(FR-020). Não há atualização nem exclusão pela aplicação (FR-020a).
**Pré-condição**: só gravada com a atividade `sample_definition` do processo
em `COMPLETED` (FR-017a).

## Entidades lidas, sem alteração

- **`BlindSampleCode`** (Spec 031): o `laboratory_id` distinto dos códigos
  ativos do processo é o conjunto congelado (R3). Nunca alterado (FR-033).
- **`Assignment`**: `participating_laboratory` efetiva pelo `laboratory_id`
  da execução autoriza agir nela (R8) e ver as tarefas e eventos dela (R13);
  `group_manager` efetivo dá visão de gestor (FR-035).
- **`Task`**: sem coluna nova; o laboratório vem de `activity_run`.
- **`AuditEvent`**: tipos novos, todos com `laboratory_id` em
  `context_data`:

| `event_type` | `activity_run_id` | `context_data` | Quem vê (R13) |
|---|---|---|---|
| `LABORATORY_RUN_COMPLETED` | execução concluída | `activity_key`, `laboratory_id`, `run_number` | gestor do processo e o próprio laboratório |
| `LABORATORY_WAIVED` | execução marcada (um evento por execução); nulo se nenhuma mudou | `phase_key`, `activity_key` (com execução), `laboratory_id`, `reason` | só gestor do processo |
| `LABORATORY_RUN_REOPENED` | execução nova | `activity_key`, `laboratory_id`, `previous_run_number`, `run_number`, `reason`, `reblocked_activity_keys` | gestor do processo e o próprio laboratório |

Qualquer outro evento com `activity_run_id` de execução com laboratório segue
a mesma regra dos eventos de conclusão. Eventos de designação seguem as
Specs 006 e 035.

## Template (YAML)

```yaml
- key: "sample_receipt"
  name: "Recebimento das Amostras"
  execution_scope: "per_laboratory"   # opcional; padrão "process"
  custody: false                       # opcional; só em per_laboratory
  access:
    edit: ["participating_laboratory"]
  dependencies:
    - required_activity_key: "sample_definition"
```
