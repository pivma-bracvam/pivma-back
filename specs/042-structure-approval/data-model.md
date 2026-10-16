# Data Model: Homologação da estrutura do estudo

## Mudança de esquema

Uma migração Alembic, reversível:

| Tabela | Coluna | Tipo | Regra |
| --- | --- | --- | --- |
| `decisions` | `rejected_points` | JSONB, anulável | `NULL` em toda decisão que não seja reprovação da homologação |

Formato de `rejected_points` (research R5):

```json
[{"activity_key": "assign_participating_laboratory", "reason": "Laboratório errado."}]
```

Nenhuma tabela nova. Nenhuma permissão nova (research R7).

## Template de processo (os cinco YAML, versão seguinte: 01, 02, 03 e 05 vão para 5; 04 vai para 7)

Atividade nova, última de `phase_2_role_assignment`:

| Campo | Valor |
| --- | --- |
| `key` | `structure_approval` |
| `name` | `Homologação da Estrutura do Estudo` |
| `order_index` | 11 |
| `assigned_role` | `bracvam` |
| `access` | `edit: ["bracvam"]`, `view: []` |
| `activity_type` | `structure_approval` |
| `dependencies` | as dez atividades da fase 2, `ACTIVITY_COMPLETED` |

`sample_receipt` (fase 3) troca a dependência `sample_definition` por
`structure_approval`.

Atividade nova antes da homologação (revisão do PR #76, research R13):

| Campo | Valor |
| --- | --- |
| `key` | `statistical_plan` |
| `name` | `Plano Estatístico` |
| `order_index` | 10 |
| `assigned_role` | `statistician` |
| `access` | `edit: ["statistician"]`, `view: []` |
| `form_template_key` | `statistical_plan_v1` |
| `dependencies` | `assign_statistician`, `ACTIVITY_COMPLETED` |

Formulário `statistical_plan_v1`: `plan_file` (`file_upload`, obrigatório,
`pdf` ou `docx`) e `summary` (`textarea`, opcional).

## Entidades usadas

### Homologação (`ActivityInstance` com `key = 'structure_approval'`)

Estados:

```text
BLOCKED ──(dez pontos COMPLETED)──▶ IN_PROGRESS
IN_PROGRESS ──(aprovar)──▶ COMPLETED            (fase 2 COMPLETED, Etapa 3 abre)
IN_PROGRESS ──(reprovar)──▶ BLOCKED             (blocked_reason preenchido)
BLOCKED ──(último ponto reprovado conclui)──▶ IN_PROGRESS   (execução nova)
```

Cada passagem para `IN_PROGRESS` cria uma `ActivityRun` com tarefa
`READY` do cargo `bracvam`. A decisão conclui a execução e a tarefa.

### Ponto auditado (`ActivityInstance` dependência da homologação)

```text
COMPLETED ──(reprovado)──▶ IN_PROGRESS (execução n+1, execution_reason = motivo)
IN_PROGRESS ──(regra atual da atividade)──▶ COMPLETED
```

- `role_assignment`: na primeira execução, conclui na designação, na
  revogação de designação ou na revogação de convite, com ao menos uma
  designação ativa do cargo e nenhum convite pendente (research R8). Na
  execução reaberta, conclui só por
  `POST /processes/{id}/participants/roles/{role_key}/complete`, com as
  mesmas condições (research R14).
- `statistical_plan`: conclui no envio do formulário com o anexo
  (research R13). A execução nova traz formulário novo.
- `sample_definition`: conclui por `POST /processes/{id}/samples/complete`.

A execução n continua `COMPLETED`.

### Decisão (`Decision`)

| Campo | Valor |
| --- | --- |
| `decision_type` | `STRUCTURE_APPROVAL` |
| `outcome` | `APPROVED` ou `REJECTED` |
| `justification` | texto, 3 caracteres ou mais |
| `rejected_points` | lista não vazia em `REJECTED`; `NULL` em `APPROVED` |
| `activity_run_id` | execução da homologação decidida |
| `decided_by`, `decided_at` | autor e data |

Sem rota de alteração ou exclusão.

## Regras de validação da decisão

| Regra | Resposta |
| --- | --- |
| `outcome` fora de `APPROVED`/`REJECTED` | 422 `validation_error` |
| `justification` com menos de 3 caracteres | 422 `validation_error` |
| `APPROVED` com `rejected_points`, inclusive lista vazia | 422 `validation_error` |
| `REJECTED` sem `rejected_points` | 422 `validation_error` |
| `activity_key` repetida | 422 `validation_error` |
| `reason` com menos de 3 caracteres | 422 `validation_error` |
| `activity_key` que não é ponto da homologação | 422 `invalid_point` |
| Homologação sem execução em andamento | 409 `invalid_transition` |
| Processo encerrado, cancelado, excluído ou arquivado | 409 `invalid_transition` (`ensure_process_mutable`) |
| Aprovação com pendência | 409 `structure_pending` |
| Sem ver a homologação ou o processo | 404 `not_found` |
| Vê sem editar, ou conflito de interesse vigente | 403 `forbidden` |

## Pendências (research R3)

| `code` | Ponto | Quando |
| --- | --- | --- |
| `activity_not_completed` | qualquer | o ponto não está `COMPLETED` |
| `role_without_designation` | `role_assignment` | o cargo-alvo não tem designação ativa |
| `laboratory_without_codes` | `sample_definition` | laboratório participante ativo sem código cego ativo |
| `codes_without_laboratory` | `sample_definition` | código cego ativo de laboratório que não é participante ativo |

Laboratório participante ativo: designação ativa de `participating_laboratory`
e laboratório não excluído (`active_laboratories`, research R3).

Convite adicional criado após a conclusão de uma atribuição de cargo não
reabre a atividade nem constitui pendência da homologação. A aprovação
considera as designações ativas e a consistência das amostras no momento
da decisão. Em atividade aberta ou reaberta, os convites pendentes
continuam impedindo a conclusão.

## Eventos na linha do tempo

| `event_type` | `activity_run_id` | `context_data` |
| --- | --- | --- |
| `STRUCTURE_APPROVED` | execução da homologação | `decision_id`, `justification` |
| `STRUCTURE_REJECTED` | execução da homologação | `decision_id`, `justification`, `rejected_points` |
| `ACTIVITY_REOPENED` | execução nova do ponto | `activity_key`, `previous_run_number`, `run_number`, `reason` |
| `ACTIVITY_UNBLOCKED` | execução nova da homologação | já existente, gravado pelo motor |
| `FORM_SUBMITTED` | execução do plano estatístico | `activity_key`, `run_number` |
| `ROLE_ASSIGNMENT_COMPLETED` | execução reaberta da atribuição | `activity_key`, `role_key`, `run_number` |

## Template de coleta (research R9)

Trava quando algum processo vinculado tem uma execução de atividade da fase
`phase_3_validation_execution`. Processos excluídos depois do início da
Etapa 3 continuam contando; excluídos antes não travam.
