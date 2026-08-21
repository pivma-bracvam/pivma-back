# Data Model: Estrutura Base de Processos e Fase 1: Submissão e Triagem

**Feature**: 004-process-submission-triage  
**Date**: 2026-08-21  
**Spec**: [spec.md](spec.md)

Este documento define o modelo de dados relacional e entidades ORM para o motor de processos do PIVMA, suportando a execução da Fase 1 (Submissão e Triagem) e estabelecendo as fundações estruturais para as fases subsequentes.

---

## 1. Diagrama de Relacionamentos (ERD Conceitual)

```text
ProcessTemplate (1) ─── (N) ProcessTemplateVersion
                                   │ (1)
                                   │
                                   ▼ (N)
                             ProcessInstance ─── (N) Assignment
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼ (N)             ▼ (N)             ▼ (N)
               Phase           AuditEvent         Decision
                 │
                 ▼ (N)
          ActivityInstance ─── (N) ActivityDependency
                 │
                 ▼ (1..N)
            ActivityRun
                 │
      ┌──────────┼──────────┐
      ▼ (N)      ▼ (1..N)   ▼ (N)
    Task    FormInstance  Artifact
                 │
           ┌─────┴─────┐
           ▼ (N)       ▼ (N)
       FormValue   FieldReview
```

---

## 2. Entidades e Definições de Tabelas

Todas as entidades herdam de `AuditMixin` (`created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by`, `deleted_by`) garantindo soft-delete e rastreabilidade total.

### 2.1 Templates de Processo

#### `process_templates`
Representa a definição de um tipo de pipeline de validação (ex.: Validação Completa).
- `id` (UUID, PK): Identificador único.
- `key` (VARCHAR(64), UNIQUE): Código estável (ex.: `full_validation`).
- `name` (VARCHAR(255)): Nome amigável do processo.
- `description` (TEXT): Descrição detalhada do pipeline.
- `is_active` (BOOLEAN, default=True): Se o template está ativo para criação de novas instâncias.

#### `process_template_versions`
Representa uma versão imutável da definição de um template.
- `id` (UUID, PK): Identificador único.
- `template_id` (UUID, FK -> `process_templates.id`): Template pai.
- `version_number` (INTEGER): Número sequencial da versão (1, 2, ...).
- `definition_payload` (JSONB): Definição estrutural completa declarativa (fases, atividades, dependências, formulários associados).
- `is_published` (BOOLEAN, default=True): Se a versão está publicada.
- *Constraints*: `UNIQUE(template_id, version_number) WHERE deleted_at IS NULL`.

---

### 2.2 Formulários Dinâmicos

#### `form_templates`
Definição de um modelo de formulário.
- `id` (UUID, PK): Identificador único.
- `key` (VARCHAR(64), UNIQUE): Código único do formulário (ex.: `submission_full_validation_v1`, `triage_review_v1`).
- `name` (VARCHAR(255)): Nome do formulário.
- `version` (INTEGER): Versão do esquema do formulário.
- `description` (TEXT): Instruções de preenchimento.

#### `form_fields`
Campos pertencentes a um `FormTemplate`.
- `id` (UUID, PK): Identificador único.
- `form_template_id` (UUID, FK -> `form_templates.id`): Formulário ao qual o campo pertence.
- `field_key` (VARCHAR(64)): Chave programática do campo (ex.: `method_name`, `target_endpoint`, `study_protocol_file`).
- `label` (VARCHAR(255)): Rótulo exibido ao usuário.
- `help_text` (TEXT, nullable=True): Texto de ajuda/orientação.
- `field_type` (VARCHAR(32)): Tipo do campo (`text`, `integer`, `float`, `boolean`, `select`, `date`, `file_upload`, `textarea`).
- `is_required` (BOOLEAN, default=False): Se o preenchimento é obrigatório.
- `order_index` (INTEGER): Ordem de exibição na interface.
- `options` (JSONB, nullable=True): Lista de opções para campos `select` (ex.: `[{"value": "opt1", "label": "Opção 1"}]`).
- `validation_rules` (JSONB, nullable=True): Regras extras (min, max, regex, tamanho máximo de arquivo, extensões aceitas).
- *Constraints*: `UNIQUE(form_template_id, field_key) WHERE deleted_at IS NULL`.

---

### 2.3 Execução de Processos

#### `process_instances`
Execução concreta de uma submissão de validação.
- `id` (UUID, PK): Identificador único do processo.
- `template_version_id` (UUID, FK -> `process_template_versions.id`): Versão imutável do template utilizada.
- `code` (VARCHAR(32), UNIQUE): Código identificador do processo (ex.: `VAL-2026-0001`).
- `title` (VARCHAR(255)): Título da submissão/proposta.
- `status` (VARCHAR(32)): Estado macro (`DRAFT`, `SUBMISSION`, `TRIAGE`, `PLANNING`, `EXECUTION`, `REVIEW`, `FINAL_DECISION`, `CLOSED`).
- `started_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data de submissão formal.
- `closed_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data de encerramento do processo.
- `closure_reason` (TEXT, nullable=True): Motivo do encerramento (conclusão, rejeição, cancelamento).

#### `phases`
Grandes etapas organizacionais dentro de uma instância.
- `id` (UUID, PK): Identificador único.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo ao qual a fase pertence.
- `key` (VARCHAR(64)): Chave da fase (ex.: `phase_1_submission_triage`, `phase_2_planning`).
- `name` (VARCHAR(255)): Nome da fase (ex.: `Fase 1: Submissão e Triagem`).
- `order_index` (INTEGER): Ordem da fase no ciclo de vida.
- `status` (VARCHAR(32)): Estado da fase (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`).

#### `activity_instances`
Unidades de trabalho vinculadas à instância de processo.
- `id` (UUID, PK): Identificador único.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo pai.
- `phase_id` (UUID, FK -> `phases.id`): Fase à qual a atividade pertence.
- `key` (VARCHAR(64)): Chave da atividade (ex.: `proposal_submission`, `triage_evaluation`).
- `name` (VARCHAR(255)): Nome da atividade.
- `order_index` (INTEGER): Ordem de execução sugerida.
- `status` (VARCHAR(32)): Estado atual da atividade (`BLOCKED`, `READY`, `IN_PROGRESS`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`).
- `blocked_reason` (TEXT, nullable=True): Explicação da dependência que impede o início.

#### `activity_runs`
Execuções concretas e versionadas de uma atividade (suporta reexecução sem perda de histórico).
- `id` (UUID, PK): Identificador único da execução.
- `activity_instance_id` (UUID, FK -> `activity_instances.id`): Atividade executada.
- `run_number` (INTEGER, default=1): Número da execução (1 para a primeira tentativa, 2 para diligência, etc.).
- `status` (VARCHAR(32)): Estado da execução (`IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`).
- `started_at` (TIMESTAMP WITH TIME ZONE): Data/hora de início da execução.
- `completed_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data/hora de conclusão.
- `execution_reason` (TEXT, nullable=True): Justificativa da execução (ex.: "Submissão inicial" ou "Correção após solicitação de diligência").
- *Constraints*: `UNIQUE(activity_instance_id, run_number) WHERE deleted_at IS NULL`.

#### `tasks`
Ações operacionais atribuídas a participantes dentro de uma execução.
- `id` (UUID, PK): Identificador único da tarefa.
- `activity_run_id` (UUID, FK -> `activity_runs.id`): Execução à qual a tarefa pertence.
- `title` (VARCHAR(255)): Título da tarefa (ex.: "Preencher Formulário de Submissão", "Realizar Triagem da Proposta").
- `assigned_role` (VARCHAR(64), nullable=True): Papel responsável (ex.: `PROPONENT`, `TRIAGE_LEAD`).
- `assigned_user_id` (UUID, FK -> `users.id`, nullable=True): Usuário específico responsável.
- `status` (VARCHAR(32)): Estado da tarefa (`UNASSIGNED`, `ASSIGNED`, `IN_PROGRESS`, `SUBMITTED`, `COMPLETED`, `CANCELLED`).
- `due_date` (TIMESTAMP WITH TIME ZONE, nullable=True): Prazo limite opcional.
- `completed_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data de conclusão.

---

### 2.4 Preenchimento de Formulários e Revisão Campo a Campo

#### `form_instances`
Preenchimento concreto de um formulário vinculado a um `ActivityRun`.
- `id` (UUID, PK): Identificador único.
- `form_template_id` (UUID, FK -> `form_templates.id`): Template utilizado.
- `activity_run_id` (UUID, FK -> `activity_runs.id`): Execução que originou o preenchimento.
- `is_submitted` (BOOLEAN, default=False): Se a submissão foi finalizada ou está em rascunho.
- `submitted_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data do envio formal.

#### `form_values`
Valores persistidos para cada campo do formulário.
- `id` (UUID, PK): Identificador único.
- `form_instance_id` (UUID, FK -> `form_instances.id`): Instância do formulário.
- `form_field_id` (UUID, FK -> `form_fields.id`): Campo preenchido.
- `text_value` (TEXT, nullable=True): Valor textual.
- `numeric_value` (NUMERIC, nullable=True): Valor numérico/inteiro/decimal.
- `boolean_value` (BOOLEAN, nullable=True): Valor booleano.
- `date_value` (DATE, nullable=True): Data informada.
- `json_value` (JSONB, nullable=True): Estruturas complexas / opções múltiplas.
- `file_attachment_id` (UUID, FK -> `artifacts.id`, nullable=True): Arquivo anexado.
- *Constraints*: `UNIQUE(form_instance_id, form_field_id) WHERE deleted_at IS NULL`.

#### `field_reviews`
Avaliações e pareceres individuais emitidos pelo triador sobre cada campo preenchido.
- `id` (UUID, PK): Identificador único da avaliação de campo.
- `form_instance_id` (UUID, FK -> `form_instances.id`): Instância do formulário avaliado.
- `form_field_id` (UUID, FK -> `form_fields.id`): Campo avaliado.
- `activity_run_id` (UUID, FK -> `activity_runs.id`): Execução da atividade de triagem que emitiu a avaliação.
- `status` (VARCHAR(32)): Resultado da avaliação do campo (`CONFORME`, `NAO_CONFORME`, `OBSERVACAO`, `NAO_APLICAVEL`).
- `comments` (TEXT, nullable=True): Apontamento técnico do triador.
- `reviewed_by` (UUID, FK -> `users.id`): Triador que realizou a revisão.
- `reviewed_at` (TIMESTAMP WITH TIME ZONE): Data/hora da avaliação.
- *Constraints*: `UNIQUE(form_instance_id, form_field_id, activity_run_id) WHERE deleted_at IS NULL`.

---

### 2.5 Artefatos, Decisões, Dependências e Auditoria

#### `artifacts`
Evidências, documentos gerados, anexos ou consolidações produzidos por uma execução.
- `id` (UUID, PK): Identificador único.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo ao qual pertence.
- `activity_run_id` (UUID, FK -> `activity_runs.id`): Execução que gerou o artefato.
- `key` (VARCHAR(64)): Tipo/chave do artefato (ex.: `proposal_dossier`, `triage_report`, `supporting_document`).
- `name` (VARCHAR(255)): Nome do arquivo ou documento.
- `file_path` (VARCHAR(500), nullable=True): Caminho de armazenamento do arquivo.
- `file_size` (BIGINT, nullable=True): Tamanho em bytes.
- `mime_type` (VARCHAR(128), nullable=True): Tipo MIME.
- `checksum_sha256` (VARCHAR(64), nullable=True): Checksum de integridade.
- `metadata_payload` (JSONB, nullable=True): Metadados estruturados associados.
- `status` (VARCHAR(32)): Estado do artefato (`DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `SUPERSEDED`).

#### `decisions`
Decisões e deliberações formais tomadas durante o processo (ex.: Decisão de Triagem).
- `id` (UUID, PK): Identificador único.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo pai.
- `activity_run_id` (UUID, FK -> `activity_runs.id`): Execução da atividade que emitiu a decisão.
- `decision_type` (VARCHAR(64)): Tipo da decisão (ex.: `TRIAGE_INITIAL_DECISION`).
- `outcome` (VARCHAR(32)): Resultado (`APPROVED`, `REJECTED`, `NEEDS_REVISION`).
- `justification` (TEXT): Justificativa técnica e formal fundamentando a decisão.
- `decided_by` (UUID, FK -> `users.id`): Usuário que assinou a decisão.
- `decided_at` (TIMESTAMP WITH TIME ZONE): Data/hora da decisão.

#### `activity_dependencies`
Declaração de dependências e pré-condições entre atividades na instância.
- `id` (UUID, PK): Identificador único.
- `dependent_activity_id` (UUID, FK -> `activity_instances.id`): Atividade que aguarda a pré-condição.
- `required_activity_id` (UUID, FK -> `activity_instances.id`, nullable=True): Atividade que precisa ser concluída.
- `required_status` (VARCHAR(32), default='COMPLETED'): Status exigido na atividade requerida.
- `condition_type` (VARCHAR(32), default='ACTIVITY_COMPLETED'): Tipo de pré-condição (`ACTIVITY_COMPLETED`, `DECISION_APPROVED`, `ARTIFACT_AVAILABLE`).

#### `assignments`
Atribuições de papéis locais do processo a usuários em uma instância.
- `id` (UUID, PK): Identificador único.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo.
- `user_id` (UUID, FK -> `users.id`): Usuário atribuído.
- `role_key` (VARCHAR(64)): Papel local (`PROPONENT`, `TRIAGE_LEAD`, `GROUP_MANAGER`).
- `assigned_by` (UUID, FK -> `users.id`): Quem realizou a atribuição.
- `assigned_at` (TIMESTAMP WITH TIME ZONE): Data de início da atribuição.
- `revoked_at` (TIMESTAMP WITH TIME ZONE, nullable=True): Data de revogação/encerramento da responsabilidade.
- *Constraints*: `UNIQUE(process_instance_id, user_id, role_key) WHERE revoked_at IS NULL AND deleted_at IS NULL`.

#### `audit_events`
Trilha imutável de eventos da instância do processo.
- `id` (UUID, PK): Identificador único do evento.
- `process_instance_id` (UUID, FK -> `process_instances.id`): Processo.
- `activity_run_id` (UUID, FK -> `activity_runs.id`, nullable=True): Execução relacionada.
- `user_id` (UUID, FK -> `users.id`, nullable=True): Autor do evento.
- `event_type` (VARCHAR(64)): Tipo de ação (`PROCESS_CREATED`, `SUBMISSION_SUBMITTED`, `FIELD_REVIEWED`, `TRIAGE_DECIDED`, `REVISION_REQUESTED`, `TASK_ASSIGNED`).
- `context_data` (JSONB, nullable=True): Dados de contexto e snapshot do evento.
- `occurred_at` (TIMESTAMP WITH TIME ZONE, default=func.now()): Data/hora do evento.
- *Indexes*: `ix_audit_events_process_time (process_instance_id, occurred_at DESC)`.

