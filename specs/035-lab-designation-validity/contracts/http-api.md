# Contrato HTTP: Validade da designação laboratorial

Nenhum endpoint novo. Nenhum schema de request ou response muda. O que muda é
o comportamento de endpoints existentes para quem tem designação laboratorial
não efetiva, e dois valores novos de `event_type` na linha do tempo.

## Comportamento alterado

Para uma pessoa cuja única concessão vinha de designação laboratorial não
efetiva (FR-001):

| Endpoint | Antes | Depois |
|---|---|---|
| `GET /processes`, `GET /processes/{id}` | processo aparece | processo não aparece / `404 not_found` |
| `GET /processes/{id}/timeline` | eventos visíveis | `404 not_found` |
| Rotas de atividade, formulário e anexo do cargo | acesso liberado | `404 not_found` (sem ver) |
| `GET /tasks` | tarefas do cargo listadas; `actionable=true` inclui | tarefas do cargo não listadas |
| `/processes/{id}/samples/...` (edição pelo cargo) | conforme concessão | negado como a quem não tem o cargo |

Quando a pessoa tem outro cargo efetivo no processo, só o acesso do cargo
laboratorial muda (FR-007). As respostas de negação são as mesmas de quem
nunca teve o cargo (FR-005), no formato da Spec 034.

| Endpoint | Mudança |
|---|---|
| `GET /auth/me` | `access.scopes` omite a designação não efetiva por instituição inativa (antes só omitia por laboratório ou vínculo) |
| `GET /processes/{id}/participants` | `effective` passa a ser `false` também quando a instituição do laboratório está inativa |
| `POST /processes/{id}/participants`, `POST /invites/{token}/accept` | inalterados: já recusam laboratório inativo e vínculo ausente; a checagem passa a usar a mesma regra do FR-001 |

## Endpoints que passam a gravar eventos

Sem mudança de request, response ou status:

| Endpoint | Evento gravado (FR-008, FR-012a) |
|---|---|
| `DELETE /institutional/users/{user_id}/affiliations/{affiliation_id}` | `PARTICIPANT_EFFECTIVENESS_LOST`, `reason = affiliation_ended` |
| `POST /institutional/users/{user_id}/affiliations` | `PARTICIPANT_EFFECTIVENESS_RESTORED`, `reason = affiliation_created` |
| `DELETE /institutional/laboratories/{laboratory_id}` | `PARTICIPANT_EFFECTIVENESS_LOST`, `reason = laboratory_deactivated` |
| `DELETE /institutional/institutions/{institution_id}` | `PARTICIPANT_EFFECTIVENESS_LOST`, `reason = institution_deactivated` |

Um evento por designação que mudou de estado, só em processos em andamento
(FR-008a).

## Linha do tempo (`GET /processes/{id}/timeline`)

Item novo possível em `data`:

```json
{
  "event_type": "PARTICIPANT_EFFECTIVENESS_LOST",
  "user_id": "<responsável pela ação institucional>",
  "activity_run_id": null,
  "context_data": {
    "assignment_id": "<uuid>",
    "participant_user_id": "<uuid>",
    "role_key": "participating_laboratory",
    "laboratory_id": "<uuid>",
    "result": "success",
    "source": "institutional",
    "reason": "affiliation_ended"
  }
}
```

Visibilidade: a mesma dos eventos `PARTICIPANT_ASSIGNED` e
`PARTICIPANT_REVOKED`. Quem gere participantes vê todos; os demais veem só os
eventos em que `participant_user_id` é o próprio id.
