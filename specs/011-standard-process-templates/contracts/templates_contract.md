# Process Templates Contract: 5 Processos Oficiais do BraCVAM

**Feature**: `011-standard-process-templates`
**Date**: 2026-09-09

---

## 1. Estrutura Canônica de um Arquivo Declarativo YAML

Cada um dos 5 arquivos em `src/pivma/templates_data/*.yaml` respeita estritamente o seguinte schema declarativo:

```yaml
process_template:
  key: "<semantic_process_key>"
  name: "<official_display_name>"
  description: "<detailed_regulatory_description>"
  version: 1
  is_active: true

phases:
  - key: "phase_1_submission_triage"
    name: "Fase 1: Submissão e Triagem"
    order_index: 1
    activities:
      - key: "proposal_submission"
        name: "Submissão da Proposta"
        order_index: 1
        assigned_role: "PROPONENT"
        form_template_key: "<specific_submission_form_key>"
        dependencies: []

      - key: "triage_evaluation"
        name: "Triagem e Decisão BraCVAM"
        order_index: 2
        assigned_role: "TRIAGE_LEAD"
        form_template_key: "triage_review_v1"
        dependencies:
          - required_activity_key: "proposal_submission"
            required_status: "COMPLETED"
            condition_type: "ACTIVITY_COMPLETED"

forms:
  - key: "<specific_submission_form_key>"
    name: "<form_name>"
    version: 1
    description: "<form_description>"
    fields:
      - field_key: "<key>"
        label: "<label>"
        field_type: "text|textarea|select|integer|file_upload"
        is_required: true|false
        order_index: 1
        ai_evaluation_enabled: true|false
        ai_context_instructions: "<instructions_for_ai>"
        ai_validation_rules:
          min_length: 50
        validation_rules: {}
        options: []

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

---

## 2. Mapa dos 5 Arquivos de Template

### 2.1 `01_pre_validated_method.yaml`
- **Key**: `pre_validated_method`
- **Name**: "Método Pré-Validado"
- **Description**: "Método 100% novo já desenvolvido, protocolo estabelecido e validação interlaboratorial ainda por ser executada (Candidato à Validação Interlaboratorial / Validation-Ready Method)."
- **Formulário de Submissão**: `submission_pre_validated_v1`
  - `method_title` (text, required)
  - `endpoint_target` (select, required)
  - `scientific_justification` (textarea, required, `ai_evaluation_enabled: true`)
  - `pre_validation_evidence` (textarea, required, `ai_evaluation_enabled: true`)
  - `study_protocol_file` (file_upload, required)
  - `expected_laboratories_count` (integer, optional)

### 2.2 `02_scope_extension.yaml`
- **Key**: `scope_extension`
- **Name**: "Extensão de Escopo de Aplicação"
- **Description**: "Método já validado sendo proposta uma nova aplicação regulatória ou nova finalidade de uso (Fitness-for-Purpose Validation)."
- **Formulário de Submissão**: `submission_scope_extension_v1`
  - `method_title` (text, required)
  - `base_validated_method` (text, required)
  - `new_application_endpoint` (select, required)
  - `scope_extension_justification` (textarea, required, `ai_evaluation_enabled: true`)
  - `applicability_domain_data` (textarea, required, `ai_evaluation_enabled: true`)
  - `adapted_protocol_file` (file_upload, required)

### 2.3 `03_me_too_validation.yaml`
- **Key**: `me_too_validation`
- **Name**: "Validação Me-Too"
- **Description**: "Método já validado sendo proposto um novo sistema teste ou método mecanisticamente e funcionalmente semelhante (Transferência / Adaptação de Sistema-Teste)."
- **Formulário de Submissão**: `submission_me_too_v1`
  - `method_title` (text, required)
  - `reference_validated_method` (text, required)
  - `test_system_description` (text, required)
  - `mechanistic_similarity_rationale` (textarea, required, `ai_evaluation_enabled: true`)
  - `functional_equivalence_data` (textarea, required, `ai_evaluation_enabled: true`)
  - `comparative_protocol_file` (file_upload, required)

### 2.4 `04_validated_method_dossier.yaml`
- **Key**: `validated_method_dossier`
- **Name**: "Método Validado – Dossiê Submetido"
- **Description**: "Método 100% novo já desenvolvido, protocolo estabelecido e toda validação já concluída – dossiê pronto para revisão por pares e adoção regulatória (Peer-Review Ready)."
- **Formulário de Submissão**: `submission_validated_dossier_v1`
  - `method_title` (text, required)
  - `validated_endpoint` (select, required)
  - `executive_validation_summary` (textarea, required, `ai_evaluation_enabled: true`)
  - `complete_dossier_file` (file_upload, required)
  - `international_guidelines_adherence` (textarea, required, `ai_evaluation_enabled: true`)
  - `peer_reviewed_publications` (textarea, optional)

### 2.5 `05_proof_of_concept.yaml`
- **Key**: `proof_of_concept`
- **Name**: "Prova de Conceito (PoC)"
- **Description**: "Ideia de método ainda a ser desenvolvido ou em estágio inicial de desenvolvimento e otimização (Método Conceitual / Early-Stage Pipeline)."
- **Formulário de Submissão**: `submission_proof_of_concept_v1`
  - `method_title` (text, required)
  - `targeted_endpoint` (select, required)
  - `biological_rationale_and_3rs` (textarea, required, `ai_evaluation_enabled: true`)
  - `development_roadmap` (textarea, required, `ai_evaluation_enabled: true`)
  - `estimated_timeline_months` (integer, optional)
  - `concept_note_file` (file_upload, optional)
