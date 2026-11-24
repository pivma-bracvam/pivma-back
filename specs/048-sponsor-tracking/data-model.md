# Data Model: Acompanhamento do Patrocinador

Sem tabela nova, migração ou mudança de permissão. As duas respostas derivam
de `ProcessInstance`, `Assignment`, `User`, `Laboratory`, `Phase`,
`ActivityInstance` e `ActivityRun` (`src/pivma/core/database/models.py`).

## Fontes

| Dado | Origem | Filtro |
|---|---|---|
| Processo patrocinado | `Assignment` com `role_key = 'sponsor'` | ativa, não excluída, usuário ativo; processo não excluído ([R2](research.md#r2-quem-entra-na-lista)) |
| `sponsored_since` | `min(Assignment.assigned_at)` do usuário no cargo | mesmos filtros |
| Pessoa no cargo | `Assignment` + `User` + `Laboratory` | ativa, não excluída, usuário ativo, `effective_assignment_clause` ([R5](research.md#r5-pessoas-por-cargo)) |
| Atividade em andamento | `ActivityRun` + `ActivityInstance` + `Phase` + `Laboratory` | `ActivityRun.status = 'IN_PROGRESS'`, processo `OPEN` ([R6](research.md#r6-fase-atual-e-atividades-em-andamento)) |
| Fase atual | a fase de maior `order_index` entre as atividades em andamento | nula sem atividade em andamento; mesma função na lista e no detalhe ([R6](research.md#r6-fase-atual-e-atividades-em-andamento)) |
| Quantidade de atividades em andamento | número de execuções `IN_PROGRESS` do processo | as mesmas linhas da fase atual |

## Schemas novos (`src/pivma/schemas.py`)

Todos com `model_config = ConfigDict(extra='forbid')`.

### `SponsoredProcessSummary`

Item da lista (FR-001).

| Campo | Tipo | Origem |
|---|---|---|
| `id` | UUID | `ProcessInstance.id` |
| `code` | str | `ProcessInstance.code` |
| `title` | str | `ProcessInstance.title` |
| `status` | `ProcessLifecycle` | `ProcessInstance.status` |
| `started_at` | datetime \| null | `ProcessInstance.started_at` |
| `closed_at` | datetime \| null | `ProcessInstance.closed_at` |
| `sponsored_since` | datetime | designação mais antiga ativa |
| `current_phase` | `TrackingPhase` \| null | FR-004; nula fora de `OPEN` (FR-006) e sem atividade em andamento |
| `open_activity_count` | int (≥ 0) | FR-001; número de execuções em andamento, uma por laboratório na Fase 3; zero fora de `OPEN` |

### `SponsoredProcessListResponse`

`ListPage[SponsoredProcessSummary, NoFilters]`, com `sort = {by: created_at,
order: desc}`.

### `TrackingPerson`

| Campo | Tipo | Origem |
|---|---|---|
| `user` | `UserRef` | `User` (sem e-mail) |
| `laboratory` | `LaboratoryRef` \| null | `Assignment.laboratory_id`; nulo fora de `lead_laboratory` e `participating_laboratory` |

### `TrackingRole`

| Campo | Tipo | Regra |
|---|---|---|
| `role_key` | `ParticipantRole` | uma entrada por cargo do catálogo, na ordem do `Literal` |
| `people` | list[`TrackingPerson`] | vazia quando ninguém ocupa o cargo; ordem `assigned_at`, `id` |

### `TrackingPhase`

| Campo | Tipo | Origem |
|---|---|---|
| `key` | str | `Phase.key` |
| `name` | str | `Phase.name` |
| `order` | int | `Phase.order_index` |

### `TrackingActivity`

| Campo | Tipo | Origem |
|---|---|---|
| `key` | str | `ActivityInstance.key` |
| `name` | str | `ActivityInstance.name` |
| `phase_key` | str | `Phase.key` |
| `started_at` | datetime | `ActivityRun.started_at` da execução aberta |
| `laboratory` | `LaboratoryRef` \| null | `ActivityRun.laboratory_id`; nulo em atividade do processo inteiro |

### `SponsorTrackingDetail`

| Campo | Tipo | Regra |
|---|---|---|
| `id`, `code`, `title`, `status`, `started_at`, `closed_at` | como em `SponsoredProcessSummary` | |
| `current_phase` | `TrackingPhase` \| null | como em `SponsoredProcessSummary` (FR-004, FR-006) |
| `sponsored_since` | datetime \| null | nulo para Admin e BraCVAM sem designação ([R4](research.md#r4-quem-consulta-o-detalhe)) |
| `roles` | list[`TrackingRole`] | FR-003 |
| `open_activities` | list[`TrackingActivity`] | FR-005; vazia fora de `OPEN` (FR-006) e sem atividade em andamento; `len` igual ao `open_activity_count` da lista |

## Campos que não entram

Nenhum dos schemas acima referencia substância, código cego, SDS, recebimento,
não conformidade, formulário, parecer, decisão, tarefa, artefato, prazo ou
responsável (FR-007, [R7](research.md#r7-o-que-fica-fora-da-resposta)).

## Estados

Nenhum estado novo. A resposta lê `ProcessInstance.status` (`OPEN`, `CLOSED`,
`CANCELLED`, `ARCHIVED`) e `ActivityRun.status` (`IN_PROGRESS` conta como em
andamento; `COMPLETED`, `CANCELLED`, `WAIVED` e `SUPERSEDED`, não).
