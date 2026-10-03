# Listagens e referências

## Envelope

Toda listagem responde no mesmo formato:

```json
{
  "data": [],
  "pagination": {"page": 1, "per_page": 20, "total_items": 0,
                 "total_pages": 0, "has_next": false, "has_prev": false},
  "filters_applied": {},
  "sort": {"by": "name", "order": "asc"}
}
```

| Regra | Valor |
|---|---|
| `page` | Começa em 1 |
| `per_page` | 1 a 100, padrão 20 |
| Página além da última | `data` vazio, com os totais |
| `offset`, `limit`, `size` | Não existem |
| `filters_applied` | Ecoa os filtros, inclusive os padrões aplicados; `{}` quando a listagem não tem filtros |
| `sort` | Ordem aplicada. Cada listagem tem uma ordem padrão estável |
| `facets`, `summary` | Só quando pedidos com `include=` (hoje só em `GET /tasks`) |

## Tarefas

`GET /tasks` lista as tarefas das atividades que o usuário pode ver.

| Filtro | Valores | Padrão |
|---|---|---|
| `status` | `READY`, `COMPLETED`, `CANCELLED` (repetível) | todos |
| `activity_key` | chave da atividade (repetível) | todas |
| `phase_order` | inteiro ≥ 1 | todas |
| `process_id` | UUID | todos |
| `role` | cargo | todos |
| `actionable` | `true`: só onde `can_act` é verdadeiro | `false` |
| `current_run` | `true`: só a execução vigente de cada atividade | `true` |
| `overdue` | `true`: abertas com prazo vencido | `false` |
| `sort_by` | `due_date`, `created_at` | `due_date` |
| `sort_order` | `asc`, `desc` | `asc` |
| `include` | `facets`, `summary` (repetível) | nenhum |

Tarefas sem prazo ficam sempre por último. Valor inválido responde `422`.

| Campo | Conteúdo |
|---|---|
| `id`, `title`, `status`, `due_date` | A tarefa |
| `process`, `phase` | Referências resumidas |
| `activity_key`, `assigned_role` | Atividade e cargo |
| `activity_run_number`, `activity_run_status` | Execução (`IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `WAIVED`, `SUPERSEDED`) |
| `laboratory` | Laboratório da execução; `null` fora de atividade por laboratório |
| `can_act` | Cargo com edição na atividade, sem conflito de interesse vigente e, em execução de laboratório, designado por esse laboratório |

`include=facets` devolve contagens por `activity_key` e por `status` sobre
todo o conjunto filtrado. `include=summary` devolve
`ai_pre_evaluation_in_progress`: processos visíveis com pré-avaliação por IA
em andamento, que não têm tarefa aberta nesse intervalo.

## Referências resumidas

Entidades relacionadas vêm como objetos pequenos, de formato fixo e um nível
só. Campos de auditoria (`created_by`, `assigned_by`, `accepted_by` e
similares) continuam como identificadores.

| Referência | Campos |
|---|---|
| pessoa (`user`) | `id`, `username`, `full_name`. Nunca o e-mail |
| perfil | `id`, `name`, `active` |
| instituição (`institution`) | `id`, `name`, `active` |
| laboratório (`laboratory`) | `id`, `name`, `active`, `institution` |
| template (`template`) | `key`, `name`, `version` |
| processo (`process`) | `id`, `code`, `title` |
| etapa (`phase`) | `key`, `order` |

Aparecem em designações, convites, laboratórios, vínculos, processos,
etiquetas de amostras e tarefas.
