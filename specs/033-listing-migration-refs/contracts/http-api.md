# Contrato HTTP: Migração das listagens e referências resumidas

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **incompatível** em 19 listagens e nos schemas com referências novas. Legenda: 🔴 quebra, 🟡 muda comportamento, ⚪ sem mudança de JSON.

## Regras comuns (todas as listagens abaixo)

- Resposta no envelope da Spec 032, sem `facets` nem `summary`:

  ```json
  {
    "data": [ ... ],
    "pagination": { "page": 1, "per_page": 20, "total_items": 3, "total_pages": 1, "has_next": false, "has_prev": false },
    "filters_applied": { },
    "sort": { "by": "name", "order": "asc" }
  }
  ```
- Parâmetros `page` (≥ 1, padrão 1) e `per_page` (1–100, padrão 20). Fora do limite: `422`.
- `offset`, `limit` e `size` deixam de existir (são ignorados se enviados).
- Página além da última: `200` com `data: []` e os totais corretos.
- Autorização, escopos e códigos de erro de cada rota não mudam.

## Listagens

| Rota | Antes | Filtros | `sort` padrão |
|---|---|---|---|
| 🔴 `GET /users` | `{offset, limit, items}` | `search`, `active` (true), `profile_id` | `username asc` |
| 🔴 `GET /rbac/permissions` | lista | — | `code asc` |
| 🔴 `GET /rbac/profiles` | lista | — | `name asc` |
| 🔴 `GET /rbac/changes` | `{offset, limit, items}`; paginação inválida `422 "Invalid pagination"` | — | `occurred_at desc` |
| 🔴 `GET /institutional/institutions` | lista | — | `name asc` |
| 🔴 `GET /institutional/laboratories` | lista | — | `institution asc` |
| 🔴 `GET /institutional/users/{user_id}/affiliations` | lista | — | `created_at desc` |
| 🔴 `GET /institutional/me/affiliations` | lista | — | `created_at desc` |
| 🔴 `GET /institutional/changes` | `{offset, limit, items}` | — | `occurred_at desc` |
| 🔴 `GET /processes/templates` | lista (sem ordem) | — | `name asc` |
| 🔴 `GET /processes` | `{items, total, page, size}` | `status` (null = todos, menos arquivados) | `created_at desc` |
| 🔴 `GET /processes/{id}/submission-versions` | lista | — | `returned_at desc` |
| 🔴 `GET /processes/{id}/timeline` | `{process_id, code, events}` | — | `occurred_at asc` |
| 🔴 `GET /processes/{process_id}/participants` | lista | — | `assigned_at desc` |
| 🔴 `GET /processes/{process_id}/participants/history` | `{offset, limit, items}` | — | `assigned_at desc` |
| 🔴 `GET /processes/{process_id}/participants/invites` | lista | — | `created_at desc` |
| 🔴 `GET /ai-evaluations` | `{offset, limit, items}` | `search` | `name asc` |
| 🔴 `GET /ai-evaluations/references` | lista | — | `identifier asc` |
| 🔴 `GET /processes/{id}/samples/labels` | lista | — | `laboratory asc` |

## Referências (valem em listas, detalhes, criações e alterações)

```json
"user":        { "id": "…", "username": "maria", "full_name": "Maria Silva" },
"institution": { "id": "…", "name": "Fiocruz", "active": true },
"laboratory":  { "id": "…", "name": "Lab A", "active": true,
                 "institution": { "id": "…", "name": "Fiocruz", "active": true } },
"template":    { "key": "pre_validated_method", "name": "Método Pré-Validado", "version": 3 },
"process":     { "id": "…", "code": "PIVMA-2026-0001", "title": "Método X" }
```

| Onde | Antes | Depois |
|---|---|---|
| 🔴 Designações de participante (lista, histórico, criação) | `process_id`, `user_id`, `laboratory_id` | `process`, `user`, `laboratory` (ou `null`) |
| 🔴 Convites (lista, criação, reenvio, revogação, aceite) | `process_id`, `laboratory_id` | `process`, `laboratory` (ou `null`) |
| 🔴 Laboratórios (lista, detalhe, criação, alteração) | `institution_id` | `institution` |
| 🔴 Afiliações (lista de um usuário, criação) | `user_id`; `institution`/`laboratory` sem instituição no laboratório | `user`; `laboratory.institution` |
| 🔴 Afiliações próprias | `laboratory` sem instituição | `laboratory.institution` |
| 🔴 Processos (lista, detalhe, criação, ciclo de vida) | `template_key`, `version_number` | `template` |
| 🔴 Etiquetas de amostra | `laboratory_id`, `laboratory_name` | `laboratory` |
| ⚪ Perfis de usuário (`/users`, `/auth/me`, `/rbac`) | `{id, name, active}` | igual (agora `ProfileRef`) |

`created_by`, `updated_by`, `deleted_by`, `assigned_by`, `accepted_by`, `revoked_by`, `actor_user_id`, o `user_id` dos eventos da linha do tempo, `target_type`/`target_id` e `assignment_id` das declarações continuam como identificadores.

## Fora da documentação

- `GET /admin/logs/operational` e `GET /admin/logs/ai` saem do OpenAPI (Swagger e ReDoc). O comportamento não muda. **Não entram no changelog do frontend.**

## Sem mudança

- `GET /processes/{id}/samples` (lista de substâncias com `activity_status`).
- Coleções dentro de recursos (campos de formulário, versões e critérios de avaliação, anexos).
- `GET /invites/{token}` (pré-visualização pública).
