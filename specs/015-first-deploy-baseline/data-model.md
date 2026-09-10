# Phase 1 — Data Model: Formulários de Submissão

Escopo: apenas o formulário vinculado à atividade `proposal_submission` de cada um dos
cinco templates. `triage_review_v1` **não** é alterado. Nenhuma tabela nova; os campos
são linhas de `FormField` produzidas por `bootstrap_process_templates` a partir do YAML.

Convenção: `field_key` em inglês `snake_case` (padrão do sistema); `label` e `section`
em português (clarificação 2026-09-10). `section` é declarado **dentro de**
`validation_rules` (ver research R1).

Tipos suportados: `text`, `textarea`, `integer`, `float`, `boolean`, `date`, `select`,
`file_upload`.

---

## 1. `submission_pre_validated_v1` (processo `pre_validated_method`)

| field_key | label | field_type | is_required | help_text |
| :-- | :-- | :-- | :-- | :-- |
| `method_title` | Título do método | `text` | true | Nome do método alternativo proposto. |

Um único campo. Sem `select`, sem IA, sem anexo.

## 2. `submission_scope_extension_v1` (processo `scope_extension`)

| field_key | label | field_type | is_required | help_text |
| :-- | :-- | :-- | :-- | :-- |
| `method_title` | Título do método | `text` | true | Nome do método alternativo proposto. |

## 3. `submission_me_too_v1` (processo `me_too_validation`)

| field_key | label | field_type | is_required | help_text |
| :-- | :-- | :-- | :-- | :-- |
| `method_title` | Título do método | `text` | true | Nome do método alternativo proposto. |

---

## 4. `submission_validated_dossier_v1` (processo `validated_method_dossier`)

Exemplo raso de uso da IA: o proponente descreve um conceito/termo do método e a IA
verifica se a terminologia está atualizada com a nomenclatura científica moderna.

| field_key | label | field_type | is_required | order | config |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `method_title` | Título do método validado | `text` | true | 1 | help_text: "Nome do método com validação concluída." |
| `terminology_notes` | Conceito-chave do método e terminologia usada | `textarea` | true | 2 | `ai_evaluation_enabled: true`; `ai_context_instructions: "Verificar se os termos usados para descrever o conceito estão alinhados à nomenclatura científica e regulatória atual (OCDE, IATA, NAM). Apontar termos desatualizados e sugerir equivalentes modernos."`; `ai_validation_rules: { min_length: 30 }`; help_text: "Descreva o conceito central em 1–2 parágrafos." |

**Seed de IA (`seed_ai_evaluations`)** associa a este formulário uma definição de
avaliação publicada — sugestão: nome "Atualidade da terminologia", modo `simple`,
objetivo "Verificar se a terminologia do conceito está atualizada", com 2–3 critérios
(`check_type: quality`/`conformity`) sobre nomenclatura moderna — via
`replace_assignments('submission_validated_dossier_v1', [... field_keys=['terminology_notes'] ...])`.
A instância `[DEMO 4] …` é então submetida (provedor `fake`) e roteada para triagem,
alimentando as demos de **triagem** e **observabilidade de IA**.

---

## 5. `submission_proof_of_concept_v1` (processo `proof_of_concept`) — Formulário Preliminar (FP)

Reprodução do FP do BraCVAM. Todas as 9 seções presentes. `order_index` sequencial na
ordem abaixo. Nenhum campo de IA. Campos "SIM/NÃO + descrição" do FP viram um par
`boolean` + `textarea`. `help_text` dos campos com limite do FP: `"Máx. N palavras
(orientação; não validada)."`

### Seção "1. Informações Gerais"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `proponent_organization` | Organização/Empresa (proponente) | text | true |
| `proponent_unit` | Departamento/Faculdade/Instituto/Outro | text | false |
| `proponent_address` | Endereço | text | false |
| `proponent_postal_code` | CEP | text | false |
| `proponent_city` | Cidade | text | false |
| `proponent_country` | País | text | false |
| `contact_title` | Titulação do contato responsável | select (`mr`/`ms`/`dr`/`prof`) | false |
| `contact_first_name` | Primeiro nome | text | true |
| `contact_last_name` | Último nome | text | true |
| `contact_role` | Função | text | false |
| `contact_phone` | Telefone | text | false |
| `contact_mobile` | Celular | text | false |
| `contact_email` | E-mail | text | true |
| `additional_contact_title` | Titulação (contato adicional) | select | false |
| `additional_contact_first_name` | Primeiro nome (contato adicional) | text | false |
| `additional_contact_last_name` | Último nome (contato adicional) | text | false |
| `additional_contact_role` | Função (contato adicional) | text | false |
| `additional_contact_phone` | Telefone (contato adicional) | text | false |
| `additional_contact_mobile` | Celular (contato adicional) | text | false |
| `additional_contact_email` | E-mail (contato adicional) | text | false |
| `alt_organization` | Organização/Empresa (se diferente do proponente) | text | false |
| `alt_unit` | Departamento/Faculdade/Instituto/Outro (alternativo) | text | false |
| `alt_address` | Endereço (alternativo) | text | false |
| `alt_postal_code` | CEP (alternativo) | text | false |
| `alt_city` | Cidade (alternativa) | text | false |
| `alt_country` | País (alternativo) | text | false |

### Seção "2. Informações do Método de Teste"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `method_name` | Nome do método de teste | text | true |
| `method_abbreviations` | Abreviaturas usadas | text | false |

### Seção "3. Resumo do Método de Teste"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `addresses_human_health` | Aborda efeitos na saúde humana? | boolean | false |
| `addresses_human_health_detail` | Especifique (saúde humana) | textarea | false |
| `addresses_environmental` | Aborda efeitos ambientais? | boolean | false |
| `addresses_environmental_detail` | Especifique (efeitos ambientais) | textarea | false |
| `addresses_other` | Aborda outros efeitos? | boolean | false |
| `addresses_other_detail` | Especifique (outros) | textarea | false |
| `mechanistic_relevance` | Relevância mecanicista (3.2) | textarea | false |
| `test_system_description` | Sistema de teste usado e relevância biológica (3.3) | textarea | false |
| `measured_variables_outcomes` | Variáveis e desfechos medidos (3.4) | textarea | false |
| `intended_purpose` | Finalidade pretendida (3.5) | textarea | false |
| `three_rs_impact` | Impacto nos 3Rs (3.6) | textarea | false |
| `animal_derived_reagents` | Uso de soro/anticorpos de origem animal (3.7) | textarea | false |
| `improvement_over_existing` | Melhoria frente a método existente (3.8) | textarea | false |
| `method_limitations` | Limitações do método (3.9) | textarea | false |
| `ip_status` | Propriedade intelectual / confidencialidade de componentes (3.10) | textarea | false |

### Seção "4. Avaliação Preliminar do Nível de Otimização do Protocolo"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `protocol_stepwise_described` | Procedimento descrito passo a passo, com reagentes e instrumentos? (4.1) | boolean | false |
| `protocol_sop_status` | Status atual do(s) POP(s) | textarea | false |
| `sop_files` | Procedimentos Operacionais Padrão (PDF) | file_upload (`pdf`, 25 MB) | false |
| `control_positive` | Usa controle positivo? (4.2) | boolean | false |
| `control_positive_detail` | Especifique o controle positivo | textarea | false |
| `control_negative` | Usa controle negativo? | boolean | false |
| `control_negative_detail` | Especifique o controle negativo | textarea | false |
| `control_reference` | Usa controle de referência? | boolean | false |
| `control_reference_detail` | Especifique o controle de referência | textarea | false |
| `quality_criteria_defined` | Critérios de qualidade do sistema de teste especificados? (4.3) | boolean | false |
| `quality_criteria_detail` | Descreva os critérios de qualidade | textarea | false |
| `acceptance_criteria_defined` | Critérios de aceitação para dados de teste e controles? (4.4) | boolean | false |
| `acceptance_criteria_detail` | Descreva os critérios de aceitação | textarea | false |
| `data_processing_required` | Requer procedimento sobre os dados brutos para os desfechos? (4.5) | boolean | false |
| `data_processing_detail` | Descreva como os dados são resumidos/expressos | textarea | false |
| `prediction_model_available` | Modelo de previsão / interpretação de dados disponível? (4.6) | boolean | false |
| `prediction_model_detail` | Descreva o modelo de previsão | textarea | false |

### Seção "5. Avaliação Preliminar da Confiabilidade"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `within_lab_reproducibility` | Reprodutibilidade intra-laboratorial avaliada? (5.1) | boolean | false |
| `within_lab_reproducibility_detail` | Como foi feito e resultados | textarea | false |
| `transferability_assessed` | Transferibilidade para outros laboratórios avaliada? (5.2) | boolean | false |
| `transferability_detail` | Como foi feito e resultados | textarea | false |
| `between_lab_reproducibility` | Reprodutibilidade inter-laboratorial avaliada? (5.3) | boolean | false |
| `between_lab_reproducibility_detail` | Como foi feito e resultados | textarea | false |

### Seção "6. Avaliação Preliminar da Capacidade Preditiva"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `predictions_possible` | Permite previsões sobre saúde humana / ambiente / outros efeitos? (6.1) | boolean | false |
| `predictions_detail` | Tipo de previsões obtidas | textarea | false |
| `additional_information` | Fornece informações adicionais (modo de ação/mecanismo)? (6.2) | boolean | false |
| `additional_information_detail` | Especifique | textarea | false |
| `items_tested_count` | Nº de itens testados e classes químicas abrangidas (6.3) | textarea | false |
| `reference_data_used` | Dados de referência usados (in vivo/in vitro/humanos) (6.4) | textarea | false |
| `predictive_capacity_summary` | Resumo da capacidade preditiva (especificidade/sensibilidade/acurácia) (6.5) | textarea | false |
| `raw_data_available_independent` | Dados brutos disponíveis para avaliação independente? (6.6) | boolean | false |

### Seção "7. Referências"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `bibliographic_references` | Referências bibliográficas relevantes (máx. 10, uma por linha) | textarea | false |

### Seção "8. Declaração sobre Informação Confidencial"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `contains_confidential` | O FP contém informações consideradas confidenciais? | boolean | false |
| `confidential_items` | Itens confidenciais e justificativa (um por linha: nº do item — explicação, máx. 100 palavras) | textarea | false |

### Seção "9. Solicitação do Método de Teste para BraCVAM"

| field_key | label | type | required |
| :-- | :-- | :-- | :-- |
| `bracvam_validation_request` | Submete o método para consideração de prontidão ao processo de validação do BraCVAM? | boolean | false |
| `bracvam_validation_request_detail` | Especifique o pedido exato ao BraCVAM (máx. 150 palavras) | textarea | false |

---

## Pendências do FP (registro consolidado)

Cada item abaixo é uma aproximação assumida (clarificação: aproximar, nunca omitir):

1. **Grupos de múltipla escolha** (3.1 tipos de efeito; 4.2 controles) → representados
   como campos `boolean` separados; a UI não os mostra como um grupo de checkboxes.
2. **Sub-campos condicionais** ("se sim, especifique") → `textarea` sempre visível; sem
   dependência de visibilidade do `boolean` correspondente.
3. **Tabela repetível da seção 8** (até 20 linhas: item + explicação) → um único
   `textarea` (`confidential_items`).
4. **Lista de referências da seção 7** (até 10, estruturada) → um único `textarea`.
5. **Repetição de blocos de contato/endereço** (contato adicional; "se diferente do
   proponente") → conjuntos de campos fixos sempre visíveis, sem "adicionar outro".
6. **Limite por número de palavras** (150/100 palavras) → apenas `help_text`; sem
   validação (motor só tem `min_length` em caracteres).
7. **Validação de e-mail** (`contact_email`, `additional_contact_email`) → tipo `text`;
   sem verificação de formato de e-mail (não há `field_type` de e-mail).
8. **Marcação de confidencialidade por parágrafo** → sem vínculo estrutural entre um
   campo do formulário e sua marcação como confidencial.

---

## Massa de dados de demonstração (produzida por `seed_all`)

| Entidade | Origem | Estado alvo |
| :-- | :-- | :-- |
| Usuários `admin`, `proponent_user`, `triage_evaluator` (+ 3 de amostra) e perfis RBAC | `seed_users` | criados, idempotente |
| 5 processos `[DEMO 1..5] …` instanciados | `seed_forms` (`bootstrap_all_templates` + `instantiate_process`) | `SUBMISSION` |
| `[DEMO 1] …` (`pre_validated_method`) | `seed_triage` submete `{method_title}` | `TRIAGE` |
| Definição de avaliação "Atualidade da terminologia" publicada + referência normativa | `seed_ai_evaluations` | publicada, atribuída a `submission_validated_dossier_v1` / `terminology_notes` |
| `[DEMO 4] …` (`validated_method_dossier`) | `seed_ai_evaluations` submete + `_execute` (provedor `fake`) + roteamento | `TRIAGE` com pré-avaliação executada |

Idempotência: cada seed usa guard de existência por `username`/`title`/`slug`.
