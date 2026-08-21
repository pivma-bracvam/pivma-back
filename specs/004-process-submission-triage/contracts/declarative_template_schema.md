# Declarative Template Schema (YAML)

Este documento especifica o formato dos arquivos YAML utilizados para definir templates de processo, fases, atividades, pré-condições de dependência e esquemas de formulários.

---

## 1. Exemplo de Definição Declarativa: `full_validation_v1.yaml`

```yaml
process_template:
  key: "full_validation"
  name: "Validação Completa"
  description: "Pipeline padrão para validação completa de novos métodos alternativos ao uso de animais."
  version: 1

phases:
  - key: "phase_1_submission_triage"
    name: "Fase 1: Submissão e Triagem"
    order_index: 1
    activities:
      - key: "proposal_submission"
        name: "Submissão da Proposta"
        order_index: 1
        assigned_role: "PROPONENT"
        form_template_key: "submission_full_validation_v1"
        dependencies: [] # Ponto de entrada, pronto para execução imediata

      - key: "triage_evaluation"
        name: "Triagem e Decisão Inicial"
        order_index: 2
        assigned_role: "TRIAGE_LEAD"
        form_template_key: "triage_review_v1"
        dependencies:
          - required_activity_key: "proposal_submission"
            required_status: "COMPLETED"
            condition_type: "ACTIVITY_COMPLETED"

  - key: "phase_2_planning_governance"
    name: "Fase 2: Planejamento e Governança"
    order_index: 2
    activities:
      - key: "sample_selection"
        name: "Seleção de Amostras"
        order_index: 1
        assigned_role: "SAMPLE_COMMITTEE"
        dependencies:
          - required_activity_key: "triage_evaluation"
            required_status: "COMPLETED"
            condition_type: "DECISION_APPROVED"

forms:
  - key: "submission_full_validation_v1"
    name: "Formulário de Submissão de Método Alternativo"
    version: 1
    description: "Preencha as informações técnicas e regulatórias do método proposto."
    fields:
      - field_key: "method_title"
        label: "Título do Método"
        field_type: "text"
        is_required: true
        order_index: 1

      - field_key: "endpoint_target"
        label: "Desfecho / Toxicidade Avaliada"
        field_type: "select"
        is_required: true
        order_index: 2
        options:
          - value: "ocular_irritation"
            label: "Irritação / Corrosão Ocular"
          - value: "skin_sensitization"
            label: "Sensibilização Cutânea"
          - value: "phototoxicity"
            label: "Fototoxicidade"
          - value: "acute_toxicity"
            label: "Toxicidade Aguda"

      - field_key: "scientific_justification"
        label: "Justificativa Científica e Mecanística"
        field_type: "textarea"
        is_required: true
        order_index: 3

      - field_key: "expected_laboratories_count"
        label: "Estimativa de Laboratórios Participantes"
        field_type: "integer"
        is_required: false
        order_index: 4
        validation_rules:
          min: 1
          max: 50

      - field_key: "study_protocol_file"
        label: "Protocolo Detalhado do Estudo (PDF)"
        field_type: "file_upload"
        is_required: true
        order_index: 5
        validation_rules:
          allowed_extensions: ["pdf"]
          max_size_mb: 25

  - key: "triage_review_v1"
    name: "Formulário de Parecer de Triagem"
    version: 1
    description: "Avaliação técnica preliminar dos requisitos de elegibilidade da proposta."
    fields:
      - field_key: "regulatory_adherence_score"
        label: "Nível de Aderência Regulatória"
        field_type: "select"
        is_required: true
        order_index: 1
        options:
          - value: "high"
            label: "Alto - Atende a todas as diretrizes da OCDE"
          - value: "medium"
            label: "Médio - Pendências documentais sanáveis"
          - value: "low"
            label: "Baixo - Não atende critérios mínimos"

      - field_key: "triage_summary_notes"
        label: "Notas de Síntese da Triagem"
        field_type: "textarea"
        is_required: true
        order_index: 2
```
