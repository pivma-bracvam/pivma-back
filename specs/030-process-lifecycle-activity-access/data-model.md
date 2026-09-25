# Data Model: Ciclo de vida do processo e acesso por atividade

**Feature**: [spec.md](spec.md) · **Decisões**: [research.md](research.md)

## `process_instances` (alterada)

| Campo | Antes | Depois |
|---|---|---|
| `status` | `String(32)`, default `SUBMISSION`, sem validação | `String(32)`, default `OPEN`, `CHECK (status IN ('OPEN','CLOSED','CANCELLED','ARCHIVED'))` |
| `closed_at`, `closure_reason` | sem mudança | preenchidos também na desistência (revisão do retorno) |

### Transições (FR-003)

```text
            triagem REJECTED / revisão do retorno WITHDRAW
   OPEN ─────────────────────────────────────────────────▶ CLOSED ──┐
    │                                                               │ arquivar
    │ excluir                                                       ▼
    └──────────────────────────────────▶ CANCELLED ───────────▶ ARCHIVED
                                                     arquivar
```

Qualquer outra transição é recusada. Nenhuma edição de atividade é aceita fora
de `OPEN` (FR-019).

**Constantes** (`core/process_engine.py`): `STATUS_OPEN` passa a existir;
`STATUS_SUBMISSION`, `STATUS_AI_PRE_EVALUATION` e `PROPONENT_SCOPED_STATUSES`
são removidas. `TERMINAL_PROCESS_STATUSES` e `IMMUTABLE_PROCESS_STATUSES` ficam
`{CLOSED, CANCELLED, ARCHIVED}`.

## `activity_instances` (alterada)

| Campo | Tipo | Regra |
|---|---|---|
| `view_roles` | `ARRAY(String(64))`, `NOT NULL` | `edit_roles ∪ declarados em view ∪ {admin, bracvam}` |
| `edit_roles` | `ARRAY(String(64))`, `NOT NULL` | declarados em `edit`; na ausência, `[assigned_role]`; nunca vazio |

**Validação** (na carga de templates e na instanciação, FR-013):
- todo cargo pertence a `ACTIVITY_CARGOS`;
- `edit_roles` não vazio;
- `admin` e `bracvam` são acrescentados a `view_roles` pelo sistema; a
  definição não tem como removê-los (R3).

**Estados de atividade** não mudam: `BLOCKED`, `IN_PROGRESS`, `COMPLETED`,
`CANCELLED`. Eles passam a ser a única fonte da posição no fluxo.

## Definição de atividade no template (YAML)

Chave nova e opcional `access`:

```yaml
- key: "triage_evaluation"
  assigned_role: "bracvam"
  access:
    edit: ["bracvam"]
    view: []            # admin e bracvam entram sempre
```

Sem `access`, vale `edit: [assigned_role]`. Os 5 YAMLs canônicos declaram
`access` em toda atividade para tornar a matriz explícita (FR-014), mesmo
quando coincide com o padrão.

### Matriz da fase 1 (todos os templates)

| Atividade | `edit_roles` | `view_roles` |
|---|---|---|
| `proposal_submission` | `proponent` | `proponent`, `admin`, `bracvam` |
| `triage_evaluation` | `bracvam` | `bracvam`, `admin` |
| `submission_return_review` (nova) | `proponent` | `proponent`, `admin`, `bracvam` |

As atividades das fases seguintes (template 4 e 5) usam o padrão:
`edit = [assigned_role]`.

## Revisão do retorno (atividade nova)

`ActivityInstance` com `key = 'submission_return_review'`,
`activity_type = 'return_review'`, na fase 1. Nasce `BLOCKED`, sem execução.

| Evento | Efeito |
|---|---|
| IA negativa ou com falha | nova `ActivityRun` `IN_PROGRESS` (`execution_reason` = `AI_PRE_EVALUATION`), `Task` `READY` para `proponent`, atividade `IN_PROGRESS`, `AuditEvent RETURN_REVIEW_OPENED` |
| Triagem `NEEDS_REVISION` | idem, com `execution_reason` = `TRIAGE` |
| Escolha `REVISE` | execução e tarefa `COMPLETED`, atividade `BLOCKED`; nova execução de `proposal_submission` com valores copiados |
| Escolha `CONTEST_AI` (só origem IA) | execução e tarefa `COMPLETED`, atividade `BLOCKED`; mesmo efeito da revisão direta atual (triagem liberada) |
| Escolha `WITHDRAW` | execução e tarefa `COMPLETED`; processo `CLOSED` com `closure_reason`; filhos pendentes cancelados |
| Retry administrativo da IA | execução e tarefa abertas `CANCELLED`, atividade `BLOCKED` |

Toda escolha gera `AuditEvent RETURN_REVIEW_DECIDED` com
`{choice, source, justification}` (FR-040).

## Cargos efetivos de um usuário num processo (derivado, não persistido)

```text
user_cargos(user, process) =
    { a.role_key | a ∈ Assignment, a.user = user, a.process = process,
                   a.revoked_at IS NULL, a.deleted_at IS NULL, user ativo }
  ∪ { 'admin'   | user tem perfil 'administrator' }
  ∪ { 'bracvam' | user tem perfil 'bracvam' }
```

- `pode_ver(user, act)   = user_cargos ∩ act.view_roles ≠ ∅`
- `pode_editar(user, act) = pode_ver ∧ user_cargos ∩ act.edit_roles ≠ ∅`
- Conflito de interesse vigente bloqueia antes de qualquer concessão (FR-022).

## `evaluation_runs` (sem mudança de schema)

Passa a ser a linha travada (`FOR UPDATE`) na disputa entre `_execute`, retry e
contestação (R8). "Aguardando IA" = existe `EvaluationRun` `in_progress` na
execução corrente da submissão.

## `audit_events` (sem mudança de schema)

- `PROCESS_DELETED` e `PROCESS_ARCHIVED` continuam com
  `previous_status`/`result_status`, agora com valores de ciclo de vida.
- Novos `event_type`: `RETURN_REVIEW_OPENED`, `RETURN_REVIEW_DECIDED`,
  `PROCESS_WITHDRAWN`.
- `REVISION_REQUESTED` continua sendo gravado na triagem e na IA.
