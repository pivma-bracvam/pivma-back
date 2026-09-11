# Data Model: Roteiro Dinâmico e Extensibilidade de Atividades

**Feature**: 017-process-roadmap-extensibility
**Spec**: [spec.md](spec.md)

Esta feature não cria entidades novas — estende `ActivityInstance` (Spec 004) e adiciona
uma nova versão declarativa a um template já existente (Spec 011). Nenhuma tabela nova.

## 1. Alteração em `activity_instances`

Coluna nova:

- `activity_type` (`VARCHAR(32)`, `NOT NULL`, `default='form'`): classificação da
  interação que a atividade representa. Populada a partir do campo opcional
  `activity_type` da definição YAML da atividade (Spec 011/004); quando ausente no YAML,
  assume `form`.

Valores suportados nesta entrega (FR-004 da spec):

| Valor | Significado |
|---|---|
| `form` | coleta de dados estruturados (comportamento atual, inalterado) |
| `decision` | decisão/parecer |
| `external_task` | tarefa externa/coordenação |
| `placeholder` | marcador reservado para fase futura (usado pelo exemplo desta spec) |

Migração: `ALTER TABLE activity_instances ADD COLUMN activity_type VARCHAR(32) NOT NULL
DEFAULT 'form'`. Retrocompatível — nenhuma linha existente muda de significado.

## 2. Extensão do esquema declarativo (YAML)

Cada item de `phases[].activities[]` ganha um campo opcional:

```yaml
activities:
  - key: "example_activity"
    name: "Nome da Atividade"
    order_index: 2
    assigned_role: "BRACVAM_ADMIN"
    activity_type: "placeholder"   # novo, opcional, default "form"
    dependencies:
      - required_activity_key: "triage_evaluation"
        required_status: "COMPLETED"
        condition_type: "ACTIVITY_COMPLETED"
```

Quando `activity_type` for `form` (ou omitido), `form_template_key` continua obrigatório
na prática (o comportamento não muda). Quando for qualquer outro valor,
`form_template_key` é omitido e nenhum `FormInstance` é criado para a atividade.

## 3. Nova versão do template `validated_method_dossier`

`04_validated_method_dossier.yaml` recebe `version: 2` e uma segunda fase:

```text
phase_1_submission_triage (inalterada, idêntica à versão 1)
  └── proposal_submission (form) → triage_evaluation (form)

phase_2_planning_preview (nova)
  └── planning_preview (activity_type: placeholder)
        dependencies: [triage_evaluation COMPLETED]
```

A versão 1 permanece intacta no banco (nenhuma linha de `process_template_versions` é
sobrescrita); instâncias já vinculadas a ela continuam mostrando só a Fase 1. Instâncias
novas passam a usar a versão 2 (a mais recente publicada), por já ser o critério de
seleção existente em `POST /processes` — nenhuma mudança de código necessária para isso.

## 4. Avanço de dependência (comportamento, não schema)

Hoje o desbloqueio de `triage_evaluation` é hardcoded por chave
(`_unblock_triage_activity`). Esta spec adiciona uma resolução genérica mínima, disparada
depois que uma atividade é marcada `COMPLETED`: para cada `ActivityDependency` cujo
`required_activity_id` aponte para a atividade recém-concluída, se todas as dependências
da atividade dependente estiverem satisfeitas, ela é ativada (status `IN_PROGRESS`,
`ActivityRun #1` criado, `Task` criada, `FormInstance` criada apenas se
`form_template_key` estiver presente). Isso não introduz uma tabela ou motor de regras
novo — apenas lê de volta o que `ActivityDependency` (Spec 004) já registra na
instanciação.

## 5. Roteiro (conceito, não persistido)

O "roteiro" de uma instância continua sendo uma composição em tempo de leitura de
`Phase` + `ActivityInstance` (já existentes) — não uma nova tabela. Para esta entrega, a
demonstração monta essa composição no cliente a partir de três leituras já existentes
(ver `contracts/`); uma consulta agregada dedicada permanece como evolução futura (Spec
017, User Story 1), não incluída nesta primeira fatia.
