# Contrato HTTP: Homologação da estrutura

Erros no formato da Spec 034 (`{"detail": {"code", "message"}}`). Códigos e
casos em [data-model.md](../data-model.md#regras-de-validação-da-decisão).

## `GET /processes/{id}/structure-approval`

Painel da homologação. Sessão obrigatória. Exige ver a atividade
`structure_approval` (Admin e BraCVAM). Processo sem a atividade (criado
com versão anterior do template) ou invisível: 404.

Resposta `200`:

```json
{
  "status": "IN_PROGRESS",
  "run_number": 2,
  "blocked_reason": null,
  "points": [
    {
      "activity_key": "assign_participating_laboratory",
      "name": "Definir os Laboratórios Participantes",
      "activity_type": "role_assignment",
      "status": "COMPLETED",
      "run_number": 2,
      "designations": [
        {
          "assignment_id": "uuid",
          "user": {"id": "uuid", "username": "tecnico", "full_name": "Técnico"},
          "laboratory": {"id": "uuid", "name": "Lab A", "active": true,
                          "institution": {"id": "uuid", "name": "Inst", "active": true}},
          "is_effective": true
        }
      ],
      "samples": null,
      "pending": []
    },
    {
      "activity_key": "sample_definition",
      "name": "Definição e Preparação das Amostras",
      "activity_type": "sample_definition",
      "status": "COMPLETED",
      "run_number": 1,
      "designations": null,
      "samples": {"substance_count": 3, "laboratory_count": 2, "code_count": 6},
      "pending": [
        {
          "code": "laboratory_without_codes",
          "message": "Laboratório participante sem códigos cegos.",
          "laboratory": {"id": "uuid", "name": "Lab B", "active": true,
                          "institution": {"id": "uuid", "name": "Inst", "active": true}}
        }
      ]
    }
  ],
  "decisions": [
    {
      "id": "uuid",
      "run_number": 1,
      "outcome": "REJECTED",
      "justification": "Equipe incompleta.",
      "rejected_points": [
        {"activity_key": "assign_participating_laboratory", "reason": "Laboratório errado."}
      ],
      "decided_by": {"id": "uuid", "username": "bracvam", "full_name": "BraCVAM"},
      "decided_at": "2026-10-14T12:00:00Z"
    }
  ]
}
```

- `status`, `run_number` e `blocked_reason` são da homologação. `run_number`
  é `null` antes da primeira abertura.
- `points` segue a ordem `order_index` das atividades.
- `designations` vem só em pontos `role_assignment`; `samples`, só no ponto
  `sample_definition`. Os dois são `null` nos demais.
- `laboratory` em `designations` e em `pending` é `null` quando não se aplica.
- `samples` traz só contagens de substâncias e laboratórios com códigos
  ativos e de códigos ativos. A resposta não traz nome químico, CAS, SDS nem
  código cego.
- `decisions` vem da mais recente para a mais antiga.

## `POST /processes/{id}/structure-approval/decision`

Sessão e `Origin` confiável obrigatórios. Exige editar a atividade
`structure_approval` (cargo BraCVAM) sem conflito de interesse vigente.

Aprovar:

```json
{"outcome": "APPROVED", "justification": "Equipe e amostras conferidas."}
```

Reprovar:

```json
{
  "outcome": "REJECTED",
  "justification": "Equipe incompleta.",
  "rejected_points": [
    {"activity_key": "assign_participating_laboratory", "reason": "Laboratório errado."}
  ]
}
```

Corpo com campo extra: 422.

Resposta `200`:

```json
{
  "decision_id": "uuid",
  "outcome": "REJECTED",
  "status": "BLOCKED",
  "reopened": [{"activity_key": "assign_participating_laboratory", "run_number": 2}]
}
```

`status` é o estado da homologação depois da decisão: `COMPLETED` na
aprovação, `BLOCKED` na reprovação. `reopened` é vazio na aprovação.

## Rotas existentes com efeito novo

- `DELETE /processes/{id}/participants/{assignment_id}`: passa a concluir a
  atribuição de cargo em andamento quando o cargo fica com ao menos uma
  designação ativa e nenhum convite pendente.
- `POST /processes/{id}/participants/invites/{invite_id}/revoke`: já concluía
  a atribuição; deixa de concluir quando o cargo fica sem designação ativa.
- Contrato de entrada e saída das duas rotas inalterado.
- Template de coleta: `409 template_locked` passa a valer depois que a Etapa
  3 de um processo vinculado começa.
- `GET /processes/{id}` e `/tasks`: mostram a atividade e a tarefa novas pelo
  contrato atual.

## `POST /processes/{id}/participants/roles/{role_key}/complete`

Revisão do PR #76 (research R14). Sessão e `Origin` confiável
obrigatórios. Exige gerir o cargo `role_key`, a mesma autorização de
`POST /processes/{id}/participants`. Sem corpo.

Conclui a atribuição de cargo em andamento. É a única forma de concluir
uma atribuição reaberta pela homologação; na primeira execução a atribuição
continua concluindo na designação e na revogação.

Resposta `200`:

```json
{"activity_key": "assign_participating_laboratory", "run_number": 2, "status": "COMPLETED"}
```

| Situação | Resposta |
| --- | --- |
| Sem autorização para o cargo ou com conflito de interesse vigente | 403 `forbidden` |
| Processo inexistente ou excluído, ou cargo sem atribuição no template do processo | 404 `not_found` |
| Processo encerrado, cancelado ou arquivado | 409 `process_closed` |
| Atribuição sem execução em andamento | 409 `invalid_transition` |
| Convite pendente para o cargo | 409 `pending_invites` |
| Cargo sem designação ativa | 409 `role_without_designation` |

## Plano estatístico

O plano usa as rotas de formulário existentes, com
`activity_key = statistical_plan` (research R13):

- `POST /processes/{id}/activities/statistical_plan/form/fields/plan_file/attachment`
  anexa o plano;
- `POST /processes/{id}/activities/statistical_plan/form` envia. Sem o
  anexo: 422 `invalid_form_values` com o campo. A resposta traz
  `artifact_id: null` e `pre_evaluation: null`.
- Para consultar uma execução anterior após reprovação, use
  `GET /processes/{id}/activities/statistical_plan/form?run_number=1` e
  `GET /processes/{id}/activities/statistical_plan/form/fields/plan_file/attachment?run_number=1`.
  Sem `run_number`, as rotas GET continuam retornando a execução mais
  recente; as rotas de escrita só aceitam a execução atual.
