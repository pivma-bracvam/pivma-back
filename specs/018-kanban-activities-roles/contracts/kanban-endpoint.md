# Contrato HTTP: `GET /activities/kanban` (User Stories 1 e 3)

Endpoint novo (justificativa de por que não é um facilitador de demo: `research.md` D7).
Aplica a mesma regra de visibilidade de `visibility-fixes.md`. Base: `ActivityInstance`
(não `Task`), para cobrir também atividades ainda não iniciadas (sem `ActivityRun`).

## Requisição

```
GET /activities/kanban?column=EM_ANDAMENTO&page=1&size=50
```

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `column` | não | filtra por `NAO_INICIADO` \| `EM_ANDAMENTO` \| `EM_ATRASO` \| `CONCLUIDO` |
| `process_id` | não | restringe a um único processo (útil para navegação a partir do detalhe do método) |
| `page`, `size` | não (default `1`/`50`, `size` máx. `200`) | paginação — necessária para o volume de até ~300 métodos × N atividades de um usuário Admin/BraCVAM (FR-012) |

## Resposta — `200 OK`

```json
{
  "items": [
    {
      "activity_id": "uuid",
      "activity_key": "triage_evaluation",
      "activity_name": "Triagem e Decisão BraCVAM",
      "column": "EM_ANDAMENTO",
      "cargo": "bracvam",
      "process": {
        "id": "uuid",
        "code": "VAL-2026-ab12cd34",
        "title": "Método X — Laboratório Y",
        "template_key": "pre_validated_method"
      },
      "blocked_reason": null,
      "blocking_activity_key": null,
      "run_started_at": "2026-09-10T14:00:00Z",
      "sla_hours": 120,
      "completed_at": null
    },
    {
      "activity_id": "uuid",
      "activity_key": "planning_preview",
      "activity_name": "Prévia do Planejamento",
      "column": "NAO_INICIADO",
      "cargo": "admin",
      "process": {
        "id": "uuid",
        "code": "VAL-2026-ef56gh78",
        "title": "Método Z — Laboratório W",
        "template_key": "validated_method_dossier"
      },
      "blocked_reason": "Aguardando atividades predecessoras.",
      "blocking_activity_key": "triage_evaluation",
      "run_started_at": null,
      "sla_hours": null,
      "completed_at": null
    }
  ],
  "total": 842,
  "page": 1,
  "size": 50,
  "counts_by_column": {
    "NAO_INICIADO": 210,
    "EM_ANDAMENTO": 305,
    "EM_ATRASO": 12,
    "CONCLUIDO": 315
  }
}
```

`counts_by_column` é calculado sobre o total visível ao usuário (antes da paginação),
não só sobre a página atual — é o que permite ao Kanban renderizar os totais de cada
coluna sem uma segunda requisição por coluna (contribui para FR-001/FR-012).

## Regras de conteúdo

- Toda atividade declarada em uma instância visível ao usuário aparece — inclusive as
  `BLOCKED` sem nenhuma `Task`/`ActivityRun` (FR-002, FR-009).
- `cargo` nunca é um identificador de pessoa (FR-016) — é sempre um valor de
  `ActivityCargo` (`data-model.md` §1).
- `blocking_activity_key`/`blocking_activity_status`/`blocking_activity_cargo` só são
  preenchidos quando `column = NAO_INICIADO` por dependência não satisfeita (não para
  espera assíncrona, ex.: pré-avaliação por IA, onde `blocked_reason` já descreve
  textualmente a espera sem uma atividade predecessora no roteiro).
- `actionable_now` e `cargo_unassigned` só podem ser `true` quando
  `column IN (EM_ANDAMENTO, EM_ATRASO)` — uma atividade `CONCLUIDO` não é "a vez" de
  ninguém, e uma `NAO_INICIADO` ainda não tem pendência de cargo para sinalizar.
- Lista vazia (nunca erro) quando o usuário não tem nenhuma atividade visível (FR-015).

## Casos de erro

| Situação | Resposta |
|---|---|
| Usuário não autenticado | `401` (padrão já existente, `CurrentUser`) |
| `column` fora do enum | `422` (validação Pydantic) |
| `process_id` de um processo sem acesso | `200` com `items: []`, `total: 0` (mesmo padrão de "lista vazia filtrada", não `404` — o `404` de existência já é responsabilidade de `GET /processes/{id}`) |
