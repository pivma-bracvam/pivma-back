# Research: Migração das listagens e referências resumidas

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Não havia `NEEDS CLARIFICATION` aberto; as duas dúvidas de escopo foram resolvidas na spec. As decisões abaixo tratam de como migrar 19 listagens sem mudar quem vê o quê.

## R1. Envelope sem contagens para as listagens comuns

**Decision**: Separar o envelope da Spec 032 em dois níveis, sem mudar o JSON de `GET /tasks`:

- `ListPage[ItemT, FiltersT]`: `data`, `pagination`, `filters_applied`, `sort`.
- `ListEnvelope[ItemT, FiltersT, FacetsT, SummaryT]`: estende `ListPage` com `facets` e `summary` opcionais e o serializer que os omite.

As 19 listagens usam `ListPage`. Listagens sem filtros usam `NoFilters` (modelo vazio, serializa `{}`).

**Rationale**: nenhuma das 19 tem contagens ou resumo. Usar `ListEnvelope[..., None, None]` poria `facets: null` e `summary: null` em 19 schemas da documentação, o que confunde quem lê o Swagger.

**Alternatives considered**: um segundo envelope independente, que duplicaria os campos e poderia divergir; e `ListEnvelope` com parâmetros `None`, que polui a documentação.

## R2. Paginação no banco ou em memória

**Decision**: Dois helpers em `core/listing.py`:

- `paginate_query(session, stmt, *, order_by, page, per_page) -> (items, total)`: `count(*)` sobre a subconsulta e `offset`/`limit` com a ordem dada. Vale para as listagens montadas numa consulta só.
- `paginate_items(items, page, per_page) -> (page_items, total)`: fatia uma lista já filtrada. Vale para as listagens cujo filtro de acesso roda em Python depois da consulta.

| Listagem | Onde pagina | Por quê |
|---|---|---|
| usuários, alterações do RBAC, alterações do catálogo, processos, histórico de participantes, avaliações de IA, instituições, laboratórios, afiliações de um usuário, permissões, templates, participantes, referências de IA, etiquetas | banco | consulta única, filtros em SQL |
| convites | memória | cada convite passa por `can_manage_role_assignment` em Python |
| linha do tempo | memória | `_visible_events` filtra por concessão de atividade em Python |
| versões de submissão | memória | o serviço já devolve a lista filtrada |
| afiliações próprias | memória | `active_institutional_affiliations` já devolve a lista filtrada |
| perfis | banco (lista), `profile_public` só na página | ver R6 |

**Rationale**: paginar antes de um filtro de acesso feito em Python daria totais e páginas errados e poderia esconder itens (FR-006, SC-004). Levar esses filtros para SQL está fora do escopo e mexe em autorização.

**Alternatives considered**: reescrever os filtros de convites e da linha do tempo em SQL. O ganho só aparece com volumes que ainda não existem, e o risco de mudar a autorização é alto.

**Nota**: a linha do tempo continua carregando todos os eventos do processo a cada chamada, como hoje. Só a resposta passa a ser paginada.

## R3. Parâmetros de paginação

**Decision**: Em `core/listing.py`, `PageQuery = Annotated[int, Query(ge=1)]` e `PerPageQuery = Annotated[int, Query(ge=1, le=100)]`, com os padrões `page=1` e `per_page=20` na assinatura de cada rota. Saem `offset`, `limit` e `size`, e os limites próprios `MAX_CHANGE_LIMIT`, `MAX_HISTORY_LIMIT` e `MAX_LIMIT` (os que ficarem sem uso).

**Rationale**: FR-002 e FR-003. O `422` fica a cargo da validação do FastAPI, igual a `GET /tasks`. Hoje as alterações do RBAC e do catálogo validam à mão e respondem `detail='Invalid pagination'`; passam a responder como as demais.

**Nota**: parâmetros antigos enviados por clientes desatualizados são ignorados pelo FastAPI (edge case da spec).

## R4. Ordem padrão por listagem

**Decision**: A ordem atual vira a padrão, com desempate por `id` onde faltava:

| Listagem | `sort.by` / `order` | Ordem aplicada |
|---|---|---|
| usuários | `username` / `asc` | `lower(username), id` (já total) |
| permissões | `code` / `asc` | `code` (único) |
| perfis | `name` / `asc` | `name, id` (+ `id`) |
| alterações do RBAC | `occurred_at` / `desc` | `created_at desc, id desc` |
| instituições | `name` / `asc` | `lower(name), id` |
| laboratórios | `institution` / `asc` | `institution_id, lower(name), id` |
| afiliações de um usuário | `created_at` / `desc` | `created_at desc, id desc` |
| afiliações próprias | `created_at` / `desc` | a do serviço, com desempate por `id` |
| alterações do catálogo | `occurred_at` / `desc` | `created_at desc, id desc` |
| templates | `name` / `asc` | `name, key` (**hoje sem ordem**) |
| processos | `created_at` / `desc` | `created_at desc, id desc` (+ `id`) |
| versões de submissão | `returned_at` / `desc` | a do serviço (`occurred_at desc, id desc`) |
| linha do tempo | `occurred_at` / `asc` | `occurred_at, id` |
| participantes | `assigned_at` / `desc` | `assigned_at desc, id desc` |
| histórico de participantes | `assigned_at` / `desc` | `assigned_at desc, id desc` |
| convites | `created_at` / `desc` | `created_at desc, id desc` (+ `id`) |
| avaliações de IA | `name` / `asc` | `lower(name), id` (+ `id`) |
| referências de IA | `identifier` / `asc` | `identifier, id` (+ `id`) |
| etiquetas | `laboratory` / `asc` | `Laboratory.name, code` (código é único no processo) |

**Rationale**: FR-005 e SC-006. Manter a ordem atual evita surpresa para o frontend. O desempate por `id` torna a paginação estável.

## R5. Filtros aplicados

**Decision**: Cada listagem com filtro ganha um modelo `XFilters` com seus filtros atuais, que são ecoados com os padrões:

- usuários: `search`, `active` (padrão `true`), `profile_id`;
- processos: `status` (`null` = todos, menos os arquivados, como hoje);
- avaliações de IA: `search`.

As demais usam `NoFilters`.

**Rationale**: FR-004. A regra de `status` nulo em processos já existe e fica documentada na descrição do campo.

## R6. Referências e carregamento em lote

**Decision**: Schemas em `schemas.py`, na seção "Referências" da Spec 032:

- `UserRef` (`id`, `username`, `full_name`);
- `ProfileRef` (`id`, `name`, `active`), que substitui `ProfileSummary`, com o mesmo JSON;
- `InstitutionRef` (`id`, `name`, `active`), que substitui `InstitutionSummary`, com o mesmo JSON;
- `LaboratoryRef` (`id`, `name`, `active`, `institution: InstitutionRef`), que substitui `LaboratorySummary` e passa a trazer a instituição;
- `TemplateRef` (`key`, `name`, `version`).

Todos os campos com `Field(description=...)`.

Novo módulo `core/references.py` com funções de carregamento em lote:

- `user_refs(session, ids) -> dict[UUID, UserRef]`;
- `laboratory_refs(session, ids) -> dict[UUID, LaboratoryRef]`, com a instituição num `join`.

As duas ignoram o filtro global de exclusão lógica (`skip_soft_delete_filter`), para que pessoas, laboratórios e instituições desativados continuem aparecendo. `ProcessRef` e `TemplateRef` são montados a partir das relações já carregadas.

**Rationale**:
- Participantes, histórico, convites e afiliações exibem várias pessoas e laboratórios por página. Carregar em lote evita N+1.
- Trocar `ProfileSummary` e `InstitutionSummary` por referências de mesmo formato padroniza os nomes sem mudar o JSON de `/auth/me` nem o de `/rbac`.
- `LaboratoryRef` com a instituição atende a tela de participantes e vínculos (US2).

**Alternatives considered**: `selectinload` em cada consulta. Funciona para as relações ORM, mas `Assignment` e `RoleAssignmentInvite` não têm relação mapeada para `User` e `Laboratory` em todos os casos, e o helper dá o mesmo resultado nas quatro rotas.

## R7. Onde cada referência entra

| Schema | Antes | Depois |
|---|---|---|
| `ParticipantAssignmentPublic` | `process_id`, `user_id`, `laboratory_id` | `process: ProcessRef`, `user: UserRef`, `laboratory: LaboratoryRef \| null` |
| `InvitePublic` / `InviteCreatedResponse` | `process_id`, `laboratory_id` | `process: ProcessRef`, `laboratory: LaboratoryRef \| null` |
| `LaboratoryPublic` | `institution_id` (+ `id`, `name`, `active`) | `institution: InstitutionRef` |
| `AffiliationPublic` | `user_id`, `institution: InstitutionSummary`, `laboratory: LaboratorySummary` | `user: UserRef`, `institution: InstitutionRef`, `laboratory: LaboratoryRef \| null` |
| `SelfAffiliationPublic` | `institution`, `laboratory` (resumos) | `institution: InstitutionRef`, `laboratory: LaboratoryRef \| null` |
| `ProcessInstanceDetail` | `template_key`, `version_number` | `template: TemplateRef` |
| `SampleLabel` | `laboratory_id`, `laboratory_name` | `laboratory: LaboratoryRef` |
| `AdminUser` | `profiles: list[ProfileSummary]` | `profiles: list[ProfileRef]` (mesmo JSON) |

Os campos de auditoria e os alvos polimórficos continuam como estão (FR-015). `ConflictDeclarationPublic.assignment_id` é a chave do item pai no histórico e continua como identificador.

**Nota**: `InviteAcceptResponse` e `/invites/{token}` usam `InvitePublic` ou campos soltos próprios. `InviteAcceptResponse` embute `InvitePublic` e ganha as referências por consequência (FR-016). A pré-visualização pública (`InvitePreview`) não expõe laboratório nem pessoa e não muda.

## R8. Logs administrativos fora da documentação

**Decision**: `include_in_schema=False` nas duas rotas de `routers/admin_logs.py`. Rota, acesso e resposta não mudam.

**Rationale**: FR-018. A remoção de verdade fica para uma spec própria.

## R9. Linha do tempo

**Decision**: `ProcessTimelineResponse` (`process_id`, `code`, `events`) é substituído por `ListPage[TimelineEvent, NoFilters]`. `TimelineEvent` não muda. O 404 para processo inexistente ou invisível continua antes da paginação.

## R10. Testes existentes afetados

**Decision**: Cerca de 40 arquivos de teste leem essas listagens ou os campos que viram referência. Cada um passa a ler `['data']` e as referências, sem mudar o que verifica. Os testes de paginação por `offset`/`limit` (usuários, alterações, histórico, avaliações) são reescritos para `page`/`per_page`, com o mesmo comportamento verificado.
