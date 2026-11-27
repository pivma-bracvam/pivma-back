# Data Model: Andamento do processo

Sem tabela nova, migração ou mudança de permissão. As respostas derivam de
`ProcessInstance`, `Assignment`, `User`, `Laboratory`, `Phase`,
`ActivityInstance` e `ActivityRun` (`src/pivma/core/database/models.py`).

## Fontes

| Dado | Origem | Filtro |
|---|---|---|
| Filtro `role` | `Assignment` do usuário no cargo | `process_cargos_scope`: ativa, efetiva, usuário ativo ([R2](research.md#r2-filtro-role-na-lista)) |
| `my_roles` | `Assignment` do usuário no processo | mesmos filtros, por `assigned_at` |
| Pessoa no cargo | `Assignment` + `User` + `Laboratory` | ativa, não excluída, usuário ativo, `effective_assignment_clause`, recorte ([R5](research.md#r5-pessoas-por-cargo), [R9](research.md#r9-recorte-por-cargo)) |
| Fases | `Phase` do processo | por `order_index` |
| Atividade em andamento | `ActivityRun` + `ActivityInstance` + `Phase` + `Laboratory` | `ActivityRun.status = 'IN_PROGRESS'`, processo `OPEN`, recorte ([R6](research.md#r6-fase-atual-e-atividades-em-andamento)) |
| Fase atual | a fase de maior `order_index` entre todas as execuções em andamento | nula sem execução aberta; igual para todos |
| `open_activity_count` | execuções em andamento que o usuário vê | as mesmas linhas do andamento |

## Schemas (`src/pivma/schemas.py`)

Os schemas do andamento têm `model_config = ConfigDict(extra='forbid')`.

| Schema | Campos |
|---|---|
| `ProgressPhase` | `key`, `name`, `order` |
| `ProgressPhaseStatus` | `ProgressPhase` + `status` (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`) + `activities` |
| `ViewerRole` | `role_key` (`ParticipantRole`), `laboratory` (`LaboratoryRef` ou nulo), `assigned_at` |
| `ProcessListItem` | `ProcessInstanceDetail` + `current_phase`, `open_activity_count` (≥ 0), `my_roles` |
| `ProgressPerson` | `user` (`UserRef`, sem e-mail), `laboratory` |
| `ProgressRole` | `role_key`, `occupied`, `people` |
| `ProgressActivity` | `key`, `name`, `status` (`BLOCKED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`), `conditional`, `open_runs` |
| `ProgressRun` | `started_at`, `laboratory` |
| `ProcessProgress` | `process_id`, `my_roles`, `current_phase`, `phases`, `roles` |

`ProcessListFilters` ganha `role` (`ParticipantRole` ou nulo), e
`ProcessListResponse` passa a listar `ProcessListItem`.

## Regra de recorte

`ProgressView` (`src/pivma/core/process_progress.py`) guarda `user_id`, `full`
(perfil de plataforma ou cargo de coordenação), `roles` e `laboratories`
(laboratórios das designações `participating_laboratory`). Três métodos
decidem o recorte: `sees_role`, `sees_person` e `sees_run`. A tabela está em
[R9](research.md#r9-recorte-por-cargo).
