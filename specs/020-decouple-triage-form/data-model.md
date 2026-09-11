# Data Model: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Feature**: 020-decouple-triage-form  
**Date**: 2026-09-11  
**Status**: Concluded  

---

## 1. Visão Estrutural

O modelo de dados não introduz novas tabelas nem remove colunas existentes. A mudança consiste em eliminar a dependência relacional da atividade de triagem com a tabela `form_instances`.

### Diagrama de Relacionamentos na Fase 1 (Submissão e Triagem)

```text
ProcessInstance
  │
  ├── (1) ActivityInstance: "proposal_submission"
  │         └── (1..N) ActivityRun
  │                      └── (1) FormInstance (submission_*_v1)
  │                                └── (N) FormValue
  │
  └── (1) ActivityInstance: "triage_evaluation"
            └── (1..N) ActivityRun
                         ├── (1) Task ("Realizar Triagem da Proposta", role: "bracvam")
                         ├── (1..N) Decision ("TRIAGE_INITIAL_DECISION", outcome, justification)
                         └── (0..N) FieldReview (aponta para FormInstance e FormField da submissão)
                         ─── [SEM FormInstance de Triagem]
```

---

## 2. Entidades Impactadas

### 2.1 `ActivityInstance` & `ActivityRun` (`triage_evaluation`)
- **Papel:** Conduzir a atividade de governança de triagem pelo grupo BraCVAM.
- **Relacionamento com Formulários:** Não possui `FormInstance` associada ao seu `ActivityRun`.
- **Transição de Estados da Atividade:**
  - `BLOCKED` (durante a edição da submissão ou pré-avaliação por IA)
  - `READY` / `IN_PROGRESS` (disponível para a equipe BraCVAM deliberar)
  - `COMPLETED` (após emissão da `Decision`)

### 2.2 `FieldReview`
- Mantém a vinculação com a instância de formulário da **submissão** (`form_instance_id`) e o campo avaliado (`form_field_id`), associando a autoria ao triador e o escopo da rodada ao `activity_run_id` da triagem.

### 2.3 `Decision`
- Registra a deliberação soberana da triagem vinculada a `process_instance_id` e ao `activity_run_id` da triagem, sem qualquer dependência com campos de formulário.

### 2.4 `FormTemplate` (`triage_review_v1`)
- O registro no banco de dados recebe `deleted_at` durante o bootstrap, marcando-o como descontinuado. Instâncias históricas eventualmente já persistidas mantêm integridade referencial intacta.
