# Contrato: Acompanhamento do Patrocinador

Duas rotas de leitura no router `sponsor_tracking`, tag `Sponsor Tracking`.
Exigem sessão (`CurrentUser`). Não gravam evento. Schemas em
[data-model.md](../data-model.md).

## `GET /sponsor-tracking/processes`

Processos em que o usuário logado tem designação ativa de Patrocinador
(FR-001, FR-002).

**Query**: `page` (≥ 1, padrão 1), `per_page` (1 a 100, padrão 20).

**200** `SponsoredProcessListResponse`:

```json
{
  "data": [
    {
      "id": "0b9c…",
      "code": "VAL-2026-0067",
      "title": "[TESTE] Formulário Curto",
      "status": "OPEN",
      "started_at": "2026-11-20T13:02:11Z",
      "closed_at": null,
      "sponsored_since": "2026-11-21T10:15:00Z",
      "current_phase": {"key": "phase_2_role_assignment", "name": "Fase 2: Composição da Governança", "order": 2},
      "open_activity_count": 3
    }
  ],
  "pagination": {"page": 1, "per_page": 20, "total_items": 1, "total_pages": 1, "has_next": false, "has_prev": false},
  "filters_applied": {},
  "sort": {"by": "created_at", "order": "desc"}
}
```

| Situação | Resposta |
|---|---|
| Sem designação de Patrocinador | `200` com `data: []` |
| Só outros cargos, designação revogada, convite pendente, processo excluído | o processo não aparece |
| Patrocinador e outro cargo no mesmo processo | o processo aparece uma vez |
| Processo `OPEN` com atividades em andamento | `current_phase` e `open_activity_count` pela mesma regra do detalhe |
| Processo `OPEN` sem atividade em andamento | `current_phase: null`, `open_activity_count: 0` |
| Processo `CLOSED` ou `ARCHIVED` | aparece, com `closed_at`, `current_phase: null` e `open_activity_count: 0` |
| Sem sessão | `401`, como as outras rotas |
| `page` ou `per_page` fora do intervalo | `422` no formato de validação |

## `GET /sponsor-tracking/processes/{process_id}`

Andamento de um processo patrocinado (FR-003 a FR-009).

**200** `SponsorTrackingDetail`:

```json
{
  "id": "0b9c…",
  "code": "VAL-2026-0067",
  "title": "[TESTE] Formulário Curto",
  "status": "OPEN",
  "started_at": "2026-11-20T13:02:11Z",
  "closed_at": null,
  "sponsored_since": "2026-11-21T10:15:00Z",
  "roles": [
    {"role_key": "group_manager", "people": [
      {"user": {"id": "…", "username": "demo.gestor", "full_name": "Gestor Demo"}, "laboratory": null}
    ]},
    {"role_key": "statistician", "people": []},
    {"role_key": "participating_laboratory", "people": [
      {"user": {"id": "…", "username": "demo.lab.a", "full_name": "Lab A"},
       "laboratory": {"id": "…", "name": "Laboratório Demo A", "active": true,
                      "institution": {"id": "…", "name": "Instituição Demo", "active": true}}}
    ]},
    {"role_key": "proponent", "people": [
      {"user": {"id": "…", "username": "demo.proponente", "full_name": "Proponente Demo"}, "laboratory": null}
    ]},
    {"role_key": "sponsor", "people": [
      {"user": {"id": "…", "username": "demo.patrocinador", "full_name": "Patrocinador Demo"}, "laboratory": null}
    ]}
  ],
  "current_phase": {"key": "phase_3_validation_execution", "name": "Execução da Validação", "order": 3},
  "open_activities": [
    {"key": "sample_receipt", "name": "Confirmação de Recebimento de Amostras", "phase_key": "phase_3_validation_execution",
     "started_at": "2026-11-22T09:00:00Z",
     "laboratory": {"id": "…", "name": "Laboratório Demo A", "active": true,
                    "institution": {"id": "…", "name": "Instituição Demo", "active": true}}}
  ]
}
```

O exemplo abrevia `roles`: a resposta traz uma entrada por cargo de
`ParticipantRole`, inclusive os vazios.

| Situação | Resposta |
|---|---|
| Patrocinador com designação ativa | `200` |
| Admin ou BraCVAM | `200`, `sponsored_since` nulo se não for Patrocinador |
| Processo `CLOSED` ou `ARCHIVED` | `200`, `current_phase: null`, `open_activities: []`, `closed_at` preenchido |
| Processo `OPEN` sem atividade em andamento | `200`, `current_phase: null`, `open_activities: []` |
| Usuário com outro cargo no processo, sem ser Patrocinador | `404` `{"detail": {"code": "not_found", "message": "Processo não encontrado."}}` |
| Designação revogada, processo inexistente ou excluído | `404`, mesma resposta. Hoje só a exclusão leva o processo a `CANCELLED` (`delete_process`), então `CANCELLED` sempre cai aqui |
| Sem sessão | `401` |
| `process_id` que não é UUID | `422` no formato de validação |

## Fora do contrato

A resposta não traz e-mail, data de designação dos outros, prazos,
responsável, tarefas, formulários, pareceres, decisões, substâncias, códigos
cegos, SDS, recebimentos ou contagens de amostras (FR-007). A única contagem é
`open_activity_count`, de execuções em andamento. As rotas de formulário de
atividade, amostras, recebimento, homologação, retorno e plano estatístico, e
as ações sobre execuções de laboratório, continuam recusando o Patrocinador
com `403` ou `404`, como hoje (FR-008). O acompanhamento é só informativo e
não muda nenhuma regra de acesso.
`GET /processes`, `GET /processes/{id}` e `GET /processes/{id}/participants`
não mudam.
