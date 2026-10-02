# Contrato HTTP: Execução de atividades por laboratório

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **compatível**: duas rotas novas e campos novos em respostas
existentes. Legenda: 🟢 novo, 🟡 muda. Erros seguem o formato único da Spec
034.

## Regra de acesso das rotas novas

| Quem | Resposta |
|---|---|
| `group_manager` com designação efetiva no processo | acesso |
| Admin, BraCVAM | acesso |
| Demais participantes do processo (proponente, laboratórios, estatístico, avaliadores) | **403** |
| Quem não vê o processo | **404** |
| Sem login | **401** |

Mutações exigem origem confiável (`TrustedOrigin`), como as demais.

## 🟢 `POST /processes/{id}/phases/{phase_key}/laboratory-waivers`

Dispensa um laboratório na fase (FR-017 a FR-021).

```json
// Request
{ "laboratory_id": "uuid", "reason": "Quebra irreversível da leitora de placas." }

// 201 Response: LaboratoryWaiver
{
  "id": "uuid",
  "process_id": "uuid",
  "phase": { "key": "phase_3_execution", "order": 3 },
  "laboratory": { "id": "uuid", "name": "Lab C", "active": true, "institution": { "...": "InstitutionRef" } },
  "reason": "Quebra irreversível da leitora de placas.",
  "waived_by": { "...": "UserRef" },
  "created_at": "2026-10-02T12:00:00Z",
  "waived_activity_keys": ["sample_receipt", "results_upload"]
}
```

`waived_activity_keys`: atividades cujas execuções do laboratório foram
marcadas como dispensadas nesta chamada; vazio se nenhuma mudou.

Ordem das validações: processo mutável → fase existe →
`sample_definition` concluída → laboratório congelado → motivo → duplicada.
O código `sample_definition_not_frozen` segue a convenção minúscula da Spec
034.

| Situação | Status | `code` |
|---|---|---|
| Sucesso | 201 | |
| `reason` ausente, vazio ou só espaços | 422 | `validation_error` |
| `sample_definition` do processo ainda não concluída | 409 | `sample_definition_not_frozen` (mensagem: "Não é permitido registrar dispensa de ensaio antes do congelamento e expedição das amostras.") |
| Laboratório fora do conjunto congelado | 422 | `laboratory_not_frozen` |
| Fase inexistente no processo | 404 | `not_found` |
| Laboratório já dispensado na fase | 409 | `already_waived` |
| Processo encerrado, cancelado ou arquivado | 409 | `invalid_transition` |
| Sem autorização (tabela acima) | 403/404/401 | |

## 🟢 `POST /processes/{id}/activities/{activity_key}/laboratories/{laboratory_id}/reopen`

Reabertura administrativa da execução de um laboratório (FR-022 a FR-027).

```json
// Request
{ "reason": "Controle positivo fora da faixa na placa 2." }

// 201 Response: LaboratoryRunReopened
{
  "activity_key": "results_upload",
  "laboratory": { "...": "LaboratoryRef" },
  "previous_run_number": 1,
  "run_number": 2,
  "activity_status": "IN_PROGRESS",
  "reblocked_activity_keys": ["statistical_evaluation"]
}
```

| Situação | Status | `code` |
|---|---|---|
| Sucesso | 201 | |
| `reason` ausente, vazio ou só espaços | 422 | `validation_error` |
| Atividade inexistente no processo | 404 | `not_found` |
| Atividade de execução única | 409 | `invalid_transition` |
| Laboratório sem execução vigente concluída (sem execução, em andamento, bloqueada, cancelada ou substituída) | 409 | `invalid_transition` |
| Laboratório dispensado na fase, atividade sem custódia | 409 | `laboratory_waived` |
| Processo encerrado, cancelado ou arquivado | 409 | `invalid_transition` |
| Sem autorização (tabela acima) | 403/404/401 | |

## 🟡 `GET /tasks` e `GET /tasks/{id}`

Campos novos em `TaskSummary` e `TaskDetail` (FR-028):

```json
{
  "...": "campos atuais",
  "laboratory": { "id": "uuid", "name": "Lab A", "active": true, "institution": { "...": "InstitutionRef" } },
  "activity_run_status": "COMPLETED"
}
```

- `laboratory`: `null` em atividade de execução única.
- `activity_run_status`: `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `WAIVED` ou
  `SUPERSEDED` (`Literal`). Execução `BLOCKED` não tem tarefa, então não
  aparece.
- `current_run=true` (padrão) passa a devolver a execução mais recente de
  **cada laboratório** em atividade por laboratório (FR-029).
- `can_act` passa a exigir, em tarefa com laboratório, designação efetiva de
  `participating_laboratory` pelo mesmo laboratório ou cargo global em
  `edit_roles` (FR-009).

**Visibilidade das tarefas de execução de laboratório** (FR-035, FR-036):

| Quem | Tarefas de execução de laboratório |
|---|---|
| `group_manager` efetivo no processo, Admin, BraCVAM | de todos os laboratórios |
| `participating_laboratory` efetivo pelo Lab A | só as do Lab A |
| Demais cargos com visão da atividade (estatístico, colaborador, `lead_laboratory`, outro laboratório) | nenhuma |

- Na lista, as tarefas não visíveis não aparecem; `pagination.total`,
  `facets` e `summary` seguem o mesmo filtro.
- No detalhe, tarefa não visível responde **404** "Tarefa não encontrada.".
- Tarefas de atividades de execução única não mudam.

## 🟡 Rotas de formulário

`/processes/{id}/activities/{activity_key}/form` (GET, PUT, POST, anexos)
respondem **409 `invalid_transition`** quando a atividade é `per_laboratory`
(research R7, FR-034). A pré-avaliação usa a chave fixa
`proposal_submission` e não muda.
Hoje nenhuma atividade de template é por laboratório; as issues #28 a #31
estendem essas rotas quando precisarem.

## 🟡 `GET /processes/{id}/timeline`

Tipos novos de evento, formato inalterado: `LABORATORY_RUN_COMPLETED`,
`LABORATORY_WAIVED`, `LABORATORY_RUN_REOPENED` (ver data-model).

**Visibilidade** (FR-037, FR-038), somada à regra atual:

| Evento | Quem vê |
|---|---|
| `LABORATORY_WAIVED` | só gestor do processo (`group_manager` efetivo, Admin, BraCVAM) |
| ligado a execução de laboratório, `LABORATORY_RUN_COMPLETED`, `LABORATORY_RUN_REOPENED` | gestor do processo e `participating_laboratory` efetivo pelo mesmo laboratório |
| eventos de designação (`PARTICIPANT_*`) | regra atual (Specs 006 e 035) |

`pagination.total` conta só os eventos visíveis, como hoje (Spec 033).

## Funções do motor (contrato interno para #28 a #31)

| Função | Autorização | Commit |
|---|---|---|
| `complete_laboratory_run(session, process_id, activity_key, laboratory_id, user_id)` | interna (R8) | não |
| `reopen_laboratory_run(session, process_id, activity_key, laboratory_id, reason, user_id)` | do chamador | não |
| `require_laboratory_run_access(session, user_id, act, run)` | é a própria regra | não |
