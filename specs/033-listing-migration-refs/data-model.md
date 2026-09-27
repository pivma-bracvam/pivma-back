# Data Model: Migração das listagens e referências resumidas

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Sem tabela nova e sem migração. Mudam só os modelos de resposta.

## Envelope

### ListPage[Item, Filters] (novo; base de `ListEnvelope`)

| Campo | Tipo | Regra |
|---|---|---|
| `data` | lista de `Item` | itens da página |
| `pagination` | `Pagination` (Spec 032) | página a partir de 1, `per_page` de 1 a 100 (padrão 20) |
| `filters_applied` | `Filters` | filtros usados, com os padrões |
| `sort` | `SortApplied` (Spec 032) | ordem padrão da listagem (research R4) |

`ListEnvelope` (Spec 032) passa a estender `ListPage` e acrescenta `facets` e `summary`. O JSON de `GET /tasks` não muda.

### NoFilters

Modelo sem campos; serializa `{}`.

### Filtros por listagem

| Modelo | Campos (padrão) |
|---|---|
| `UserListFilters` | `search: str \| null` (null), `active: bool` (true), `profile_id: UUID \| null` (null) |
| `ProcessListFilters` | `status: OPEN\|CLOSED\|CANCELLED\|ARCHIVED \| null` (null = todos, menos arquivados) |
| `EvaluationListFilters` | `search: str \| null` (null) |

## Referências

Todo campo com descrição na documentação. Nenhuma referência contém listas.

| Referência | Campos | Substitui |
|---|---|---|
| `UserRef` | `id`, `username`, `full_name` (nunca `email`) | `user_id` soltos |
| `ProfileRef` | `id`, `name`, `active` | `ProfileSummary` (mesmo JSON) |
| `InstitutionRef` | `id`, `name`, `active` | `InstitutionSummary` (mesmo JSON), `institution_id` |
| `LaboratoryRef` | `id`, `name`, `active`, `institution: InstitutionRef` | `LaboratorySummary`, `laboratory_id`, `laboratory_name` |
| `TemplateRef` | `key`, `name`, `version` | `template_key`, `version_number` |
| `ProcessRef` (Spec 032) | `id`, `code`, `title` | `process_id` soltos |

`active` de pessoa não existe na referência; a pessoa desativada continua aparecendo com o nome (edge case da spec).

## Schemas alterados

| Schema | Remove | Acrescenta |
|---|---|---|
| `ParticipantAssignmentPublic` | `process_id`, `user_id`, `laboratory_id` | `process`, `user`, `laboratory` (nulo sem laboratório) |
| `InvitePublic`, `InviteCreatedResponse` | `process_id`, `laboratory_id` | `process`, `laboratory` (nulo) |
| `LaboratoryPublic` | `institution_id` | `institution` |
| `AffiliationPublic` | `user_id`; `institution`/`laboratory` como resumo | `user`; `institution`/`laboratory` como referência |
| `SelfAffiliationPublic` | resumos | referências |
| `ProcessInstanceDetail` | `template_key`, `version_number` | `template` |
| `SampleLabel` | `laboratory_id`, `laboratory_name` | `laboratory` |
| `AdminUser` | — | `profiles` passa a `ProfileRef` (mesmo JSON) |

## Respostas de listagem

| Listagem | Antes | Depois |
|---|---|---|
| `GET /users` | `AdminUserPage` (`offset`, `limit`, `items`) | `ListPage[AdminUser, UserListFilters]` |
| `GET /rbac/permissions` | lista | `ListPage[PermissionPublic, NoFilters]` |
| `GET /rbac/profiles` | lista | `ListPage[ProfilePublic, NoFilters]` |
| `GET /rbac/changes` | `RbacChangePage` | `ListPage[RbacChangePublic, NoFilters]` |
| `GET /institutional/institutions` | lista | `ListPage[InstitutionPublic, NoFilters]` |
| `GET /institutional/laboratories` | lista | `ListPage[LaboratoryPublic, NoFilters]` |
| `GET /institutional/users/{user_id}/affiliations` | lista | `ListPage[AffiliationPublic, NoFilters]` |
| `GET /institutional/me/affiliations` | lista | `ListPage[SelfAffiliationPublic, NoFilters]` |
| `GET /institutional/changes` | `InstitutionalChangePage` | `ListPage[InstitutionalChangePublic, NoFilters]` |
| `GET /processes/templates` | lista | `ListPage[ProcessTemplateSummary, NoFilters]` |
| `GET /processes` | `ProcessInstanceListResponse` (`items`, `total`, `page`, `size`) | `ListPage[ProcessInstanceDetail, ProcessListFilters]` |
| `GET /processes/{id}/submission-versions` | lista | `ListPage[SubmissionVersionSummary, NoFilters]` |
| `GET /processes/{id}/timeline` | `ProcessTimelineResponse` | `ListPage[TimelineEvent, NoFilters]` |
| `GET /processes/{process_id}/participants` | lista | `ListPage[ParticipantAssignmentPublic, NoFilters]` |
| `GET /processes/{process_id}/participants/history` | `ParticipantHistoryPage` | `ListPage[ParticipantHistoryItem, NoFilters]` |
| `GET /processes/{process_id}/participants/invites` | lista | `ListPage[InvitePublic, NoFilters]` |
| `GET /ai-evaluations` | `EvaluationDefinitionPage` | `ListPage[EvaluationDefinitionSummary, EvaluationListFilters]` |
| `GET /ai-evaluations/references` | lista | `ListPage[ReferencePublic, NoFilters]` |
| `GET /processes/{id}/samples/labels` | lista | `ListPage[SampleLabel, NoFilters]` |

Cada especialização é declarada como classe nomeada (ex.: `class UserListResponse(ListPage[AdminUser, UserListFilters])`), para o OpenAPI ter um nome legível por listagem.

Schemas que deixam de ser usados e saem: `FilterPage`, `AdminUserPage`, `RbacChangePage`, `InstitutionalChangePage`, `ProcessInstanceListResponse`, `ProcessTimelineResponse`, `ParticipantHistoryPage`, `EvaluationDefinitionPage`, `ProfileSummary`, `InstitutionSummary`, `LaboratorySummary`.
