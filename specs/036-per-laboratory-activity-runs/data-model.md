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

**Status de atividade `per_laboratory`** (derivado, R5), sobre a execução
vigente de cada laboratório do conjunto congelado:

| Condição | Status |
|---|---|
| nenhuma execução vigente viva (`IN_PROGRESS`, `COMPLETED`, `WAIVED`) | `BLOCKED` |
| toda execução vigente em `COMPLETED` ou `WAIVED` | `COMPLETED` |
| outro caso | `IN_PROGRESS` |

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

**Estados da execução** (R5):

```text
IN_PROGRESS ──conclusão do laboratório──▶ COMPLETED
IN_PROGRESS ──dispensa na fase──────────▶ WAIVED      (tarefas → CANCELLED)
(abertura com laboratório já dispensado) ▶ WAIVED      (tarefa criada CANCELLED)
COMPLETED   ──reabertura do laboratório─▶ SUPERSEDED  (nova execução n+1 IN_PROGRESS)
COMPLETED   ──reabertura a montante─────▶ SUPERSEDED  (cascata, R10)
IN_PROGRESS ──reabertura a montante─────▶ CANCELLED   (cascata, R10)
IN_PROGRESS ──cancelamento do processo──▶ CANCELLED   (existente, Spec 022/030)
```

`WAIVED`, `SUPERSEDED` e `CANCELLED` são terminais. Valores, anexos,
decisões e artefatos ligados à execução nunca são alterados por essas
transições (FR-024).

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

## Entidades lidas, sem alteração

- **`BlindSampleCode`** (Spec 031): o `laboratory_id` distinto dos códigos
  ativos do processo é o conjunto congelado (R3).
- **`Assignment`**: `participating_laboratory` efetiva pelo `laboratory_id`
  da execução autoriza agir nela (R8).
- **`Task`**: sem coluna nova; o laboratório vem de `activity_run`.
- **`AuditEvent`**: tipos novos, todos com `laboratory_id` em
  `context_data`:

| `event_type` | `activity_run_id` | `context_data` |
|---|---|---|
| `LABORATORY_RUN_COMPLETED` | execução concluída | `activity_key`, `laboratory_id`, `run_number` |
| `LABORATORY_WAIVED` | nulo | `phase_key`, `laboratory_id`, `reason`, `waived_run_ids` |
| `LABORATORY_RUN_REOPENED` | execução nova | `activity_key`, `laboratory_id`, `previous_run_number`, `run_number`, `reason`, `reblocked_activity_keys` |

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
