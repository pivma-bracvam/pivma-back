# Contratos removidos

## `GET /activities/kanban`

- **Tag OpenAPI**: `Activities` (deixa de existir; era a única rota).
- **Origem**: Spec 018.
- **Response model removido**: `KanbanPage` (e os schemas aninhados
  `KanbanCardItem`, `KanbanCardProcess`, o tipo `KanbanColumn` e o tipo
  `ActivityCargo`).
- **Comportamento após a remoção**: `404 Not Found` para qualquer requisição,
  autenticada ou não. Não há resposta de depreciação nem redirecionamento.

## Contratos que não mudam

`GET /tasks`, `GET /tasks/{id}`, `/processes/*`, `/triage/*`, formulários,
participantes e convites mantêm caminhos, parâmetros e schemas.
