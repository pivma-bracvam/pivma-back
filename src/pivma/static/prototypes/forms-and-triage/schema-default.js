/**
 * Esquema de campos inicial baseado na especificação declarativa do pi*VMA:
 * specs/004-process-submission-triage/contracts/declarative_template_schema.md
 */

const DEFAULT_FORM_TEMPLATE = {
  key: "submission_full_validation_v1",
  name: "Formulário de Submissão de Método Alternativo",
  version: 1,
  description: "Preencha as informações técnicas, mecanísticas e regulatórias do método proposto para validação.",
  fields: [
    {
      id: "fld_1",
      field_key: "method_title",
      label: "Título do Método Proposto",
      field_type: "text",
      help_text: "Nome científico e comercial do método de ensaio.",
      is_required: true,
      order_index: 1,
      options: [],
      validation_rules: { min_length: 5, max_length: 200 }
    },
    {
      id: "fld_2",
      field_key: "endpoint_target",
      label: "Desfecho / Toxicidade Avaliada",
      field_type: "select",
      help_text: "Selecione o desfecho toxicológico primário contemplado.",
      is_required: true,
      order_index: 2,
      options: [
        { value: "ocular_irritation", label: "Irritação / Corrosão Ocular" },
        { value: "skin_sensitization", label: "Sensibilização Cutânea" },
        { value: "phototoxicity", label: "Fototoxicidade" },
        { value: "acute_toxicity", label: "Toxicidade Aguda Oral/Inalatória" }
      ],
      validation_rules: {}
    },
    {
      id: "fld_3",
      field_key: "scientific_justification",
      label: "Justificativa Científica e Mecanística (3Rs)",
      field_type: "textarea",
      help_text: "Descreva a base mecanicista e o potencial de substituição/redução de animais.",
      is_required: true,
      order_index: 3,
      options: [],
      validation_rules: { min_length: 20 }
    },
    {
      id: "fld_4",
      field_key: "expected_laboratories_count",
      label: "Estimativa de Laboratórios Participantes",
      field_type: "integer",
      help_text: "Número sugerido de laboratórios para o estudo interlaboratorial (mínimo 2).",
      is_required: false,
      order_index: 4,
      options: [],
      validation_rules: { min: 2, max: 50 }
    },
    {
      id: "fld_5",
      field_key: "study_protocol_file",
      label: "Procedimento Operacional Padrão (POP / PDF)",
      field_type: "file_upload",
      help_text: "Anexe o protocolo completo do ensaio em formato PDF.",
      is_required: true,
      order_index: 5,
      options: [],
      validation_rules: { allowed_extensions: ["pdf"], max_size_mb: 25 }
    }
  ]
};

if (typeof window !== "undefined") {
  window.DEFAULT_FORM_TEMPLATE = DEFAULT_FORM_TEMPLATE;
}
