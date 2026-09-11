# Phase 1 Data Model: Kanban de Pendências e Revisão de Cargos

Nenhuma tabela nova é criada por esta feature (ver `research.md`, decisões D1-D7). Este
documento descreve as entidades **conceituais** da spec e como cada uma mapeia para o
modelo relacional já existente (`src/pivma/core/database/models.py`), mais o único campo
declarativo novo e a única migração (de dados) necessária.

## 1. Entidades conceituais → modelo existente

### Cargo Global (`Padrão` / `Admin` / `BraCVAM`)

Não é uma tabela nova. Computado a partir de `AccessProfile.system_key` via
`UserAccessProfile`:

| Cargo Global | Condição |
|---|---|
| `Admin` | usuário tem `UserAccessProfile` ativa apontando para `AccessProfile.system_key = 'administrator'` |
| `BraCVAM` | usuário tem `UserAccessProfile` ativa apontando para `AccessProfile.system_key = 'bracvam'` |
| `Padrão` | nenhuma das duas acima |

Um usuário pode, em teoria, ter as duas atribuições simultaneamente — tratado como
"acesso de plataforma", sem hierarquia entre elas (`has_platform_wide_access` retorna
`true` se qualquer uma estiver presente).

### Atribuição por Processo / Cargo Contextual

Já modelada por `Assignment` (`process_instance_id`, `user_id`, `role_key`,
`revoked_at`). Nenhuma mudança de schema. O vocabulário de `role_key` continua sendo o
`Literal` `ParticipantRole` já existente em `schemas.py` (`proponent`, `group_manager`,
`study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`, `lead_laboratory`,
`participating_laboratory`).

**Mudança de comportamento (não de schema)**: a unicidade já garantida por
`uq_assignments_active` (`process_instance_id + user_id + role_key`, only where
active) já permite múltiplas pessoas no mesmo cargo no mesmo processo — pré-condição
para FR-016 (cargo, não pessoa), confirmada, não alterada.

### Cargo de uma Atividade/Tarefa

Já modelado por `Task.assigned_role` (string). **Mudança**: o vocabulário aceito passa a
ser o mesmo de `Assignment.role_key` **mais** dois valores reservados para cargo global:
`admin`, `bracvam`. Formalizado como um novo `Literal` Python (validação em código, não
`CHECK` de banco — mesmo padrão já usado para `ParticipantRole`):

```python
ActivityCargo = Literal[
    'proponent',
    'group_manager',
    'study_manager',
    'statistician',
    'adhoc_evaluator',
    'peer_reviewer',
    'lead_laboratory',
    'participating_laboratory',  # contextual — resolvido via Assignment
    'admin',
    'bracvam',  # global — resolvido via AccessProfile
]
```

Validado (a) quando `bootstrap_process_templates.py` sincroniza um YAML de template, e
(b) sempre que o motor de processos cria uma `Task` a partir da definição de uma
atividade.

**Mudança de comportamento**: `_init_first_activity` deixa de gravar
`Task.assigned_user_id`. A coluna permanece no schema (nullable, sem uso pelo motor de
processos daqui em diante) — ver `research.md` D4 para a justificativa de não removê-la.

### Critério de Atraso (SLA de Etapa)

Não é uma coluna nova. Uma chave opcional nova dentro de cada objeto de atividade em
`ProcessTemplateVersion.definition_payload` (JSONB, já existente):

```yaml
activities:
  - key: "triage_evaluation"
    assigned_role: "bracvam"      # normalizado (era "TRIAGE_LEAD")
    sla_hours: 120                 # novo, opcional — ausente/null = sem prazo
    ...
```

Resolvido em tempo de leitura: `em_atraso = sla_hours is not None and (utc_now() -
activity_run.started_at) > timedelta(hours=sla_hours)`, usando a `ActivityRun` mais
recente (`run_number` máximo não soft-deletado) e o `sla_hours` da definição da
atividade dentro do payload ao qual a `ProcessTemplateVersion` da instância aponta —
nunca o payload "mais atual" do template, preservando a imutabilidade por instância
(Spec 004 FR-001/SC-002).

### Atividade do Processo (Pendência) — unidade do cartão do Kanban

Mapeia para `ActivityInstance`, decorada em tempo de leitura (não persistida) com:

| Campo do cartão | Origem |
|---|---|
| `activity_id`, `key`, `name` | `ActivityInstance` |
| `process_id`, `process_code`, `process_title`, `process_template_key` | `ProcessInstance` (join) |
| `cargo` | `Task.assigned_role` da run mais recente, ou a definição da atividade no payload se ainda não houver `Task` (atividade `BLOCKED` sem run) |
| `column` | ver tabela de classificação abaixo |
| `blocked_reason` | `ActivityInstance.blocked_reason` |
| `blocking_activity_key` | resolvido via `ActivityDependency.required_activity_id` → `ActivityInstance.key`, quando `status = BLOCKED` |
| `run_started_at` / `completed_at` | `ActivityRun` mais recente |

**Classificação de coluna** (determinística, sem estado próprio):

| `ActivityInstance.status` | `sla_hours` | Coluna |
|---|---|---|
| `BLOCKED` (sem run, ou bloqueada por dependência/espera assíncrona) | — | `NAO_INICIADO` |
| `READY` / `IN_PROGRESS` | ausente, ou dentro do prazo | `EM_ANDAMENTO` |
| `READY` / `IN_PROGRESS` | presente e excedido | `EM_ATRASO` |
| `COMPLETED` | — | `CONCLUIDO` |

### Processo (Método)

Já modelado por `ProcessInstance`. Nenhuma mudança de schema; passa a ser filtrado, em
toda listagem/consulta, pela regra de visibilidade unificada (ver `research.md` D2).

## 2. Novas funções de domínio (sem novo estado persistido)

Todas em `src/pivma/core/authorization.py`, seguindo o padrão já estabelecido pelas
funções existentes (`is_active_effective_proponent`, `active_proponent_process_scope`,
`can_manage_process_templates`):

- `has_platform_wide_access(session, user_id) -> bool`
- `active_participant_process_scope(user_id) -> Select` (subquery de `process_instance_id`)
- `resolve_activity_holders(session, process_id, cargo) -> list[User]`

## 3. Migração necessária

Uma única migração Alembic, **de dados** (sem `ALTER TABLE`):

```text
migrations/versions/<hash>_normalize_task_assigned_role.py
  upgrade():
    UPDATE tasks SET assigned_role = 'proponent' WHERE assigned_role = 'PROPONENT';
    UPDATE tasks SET assigned_role = 'bracvam'    WHERE assigned_role = 'TRIAGE_LEAD';
    UPDATE tasks SET assigned_role = 'bracvam'    WHERE assigned_role = 'BRACVAM_ADMIN';
  downgrade(): inverso exato (três UPDATE simétricos).
```

Acompanhada, na mesma entrega, da atualização dos 5 YAML em `src/pivma/templates_data/`
para declarar `assigned_role` já no vocabulário novo. **Nota de implementação**:
`_sync_process_template_and_version` (`bootstrap_process_templates.py`) mantém o mesmo
`version_number` sem criar linha nova quando a chave `version` do YAML não muda — ou
seja, editar o payload de uma versão já publicada sem incrementar `version` mutaria
`definition_payload` em vigor para instâncias já criadas, quebrando a imutabilidade da
Spec 004. Por isso esta entrega incrementa `version` em todos os 5 templates
(`01`-`03`/`05`: 1→2; `04`, já em 2 pela Spec 017: 2→3) junto com a normalização de
`assigned_role` — o mesmo padrão já usado pela Spec 017 ao tocar `04`. Instâncias já
criadas mantêm o payload antigo congelado; só a migração de dados acima corrige as
`Task` já gravadas dessas instâncias existentes.

Teste de migração (upgrade + downgrade) obrigatório em
`tests/integration/migrations/`, conforme Constituição Princípio IV.

## 4. Sem transições de estado novas

Esta feature não introduz nenhuma máquina de estado nova — reutiliza integralmente os
estados já existentes de `Phase.status`, `ActivityInstance.status`, `ActivityRun.status`
e `Task.status` definidos pela Spec 004/017. A única "transição" nova é puramente
derivada (entrar/sair de `EM_ATRASO` é uma função do tempo, não um evento gravado).
