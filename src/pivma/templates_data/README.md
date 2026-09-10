# Especificação de Sintaxe para Formulários (YAML) — `src/pivma/templates_data`

Este documento define a sintaxe completa, os tipos suportados, as regras de validação e as diretrizes de integração para a construção de formulários declarativos nos arquivos YAML de templates de processo do PIVMA (`src/pivma/templates_data/`).

---

## 1. Visão Geral da Estrutura do Arquivo YAML

Cada arquivo YAML em `src/pivma/templates_data/` descreve um template de processo ponta a ponta e é composto por três blocos principais:

```yaml
process_template:
  key: "identificador_do_processo"
  name: "Nome do Processo"
  description: "Descrição detalhada..."
  version: 1
  is_active: true

phases:
  - key: "fase_1"
    name: "Fase 1"
    order_index: 1
    activities:
      - key: "atividade_submissao"
        name: "Submissão da Proposta"
        order_index: 1
        assigned_role: "PROPONENT"
        form_template_key: "chave_do_formulario_v1" # Vincula ao bloco 'forms'
        dependencies: []

forms:
  - key: "chave_do_formulario_v1" # Chave correspondente
    name: "Nome do Formulário"
    version: 1
    description: "Descrição do formulário..."
    fields:
      - field_key: "campo_exemplo"
        label: "Rótulo do Campo"
        field_type: "text"
        is_required: true
        order_index: 1
```

O script `bootstrap_process_templates.py` lê esses arquivos, registra as entidades `FormTemplate` e mapeia cada elemento da lista `fields` para instâncias de `FormField`.

---

## 2. Estrutura do Objeto Formulário (`forms`)

Cada item da lista `forms` possui as seguintes propriedades:

| Propriedade | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `key` | `string` | **Sim** | Identificador único do formulário (máx. 64 caracteres). Usado em `form_template_key` nas atividades. |
| `name` | `string` | **Sim** | Nome amigável de exibição do formulário (máx. 255 caracteres). |
| `version` | `integer` | Não | Versão do formulário (padrão: `1`). |
| `description` | `string` | Não | Descrição de contexto e propósito do formulário. |
| `fields` | `list` | **Sim** | Lista de definições dos campos que compõem o formulário. |

---

## 3. Estrutura de Campos (`fields`)

Cada campo dentro da lista `fields` suporta as seguintes propriedades:

| Propriedade | Tipo | Padrão | Descrição |
| :--- | :--- | :---: | :--- |
| `field_key` | `string` | — | Identificador técnico único do campo dentro do formulário (máx. 64 caracteres, ex: `method_title`). |
| `label` | `string` | — | Rótulo/título visível exibido na interface para o usuário (máx. 255 caracteres). |
| `field_type` | `string` | `"text"` | Tipo de dado e de componente visual do campo (detalhes na Seção 4). |
| `is_required` | `boolean` | `false` | Se `true`, o campo torna-se obrigatório na submissão formal. |
| `order_index` | `integer` | `0` | Posição ordinal de ordenação do campo na tela. |
| `help_text` | `string` | `null` | Texto de auxílio/orientação explicativo ao lado ou abaixo do campo. |
| `section` | `string` | `null` | Nome da seção/agrupador visual (ex: `"Dados Básicos"`, `"Evidências"`). |
| `options` | `list` | `null` | Lista de opções (obrigatório para `field_type: "select"`). |
| `validation_rules` | `dict` | `null` | Regras técnicas de validação aplicadas pelo backend (detalhes na Seção 5). |
| `ai_evaluation_enabled` | `boolean` | `false` | Habilita a avaliação automatizada deste campo pela IA do BraCVAM. |
| `ai_context_instructions` | `string` | `null` | Diretrizes de contexto passadas para o prompt do avaliador de IA. |
| `ai_validation_rules` | `dict` | `null` | Regras estruturadas de triagem da IA (ex: `min_length`). |

---

## 4. Tipos de Campo Suportados (`field_type`)

O motor de formulários do PIVMA (`pivma.core.process_engine`) e o modelo `FormField` suportam os seguintes tipos:

| `field_type` | Componente UI Sugerido | Armazenamento no Banco (`FormValue`) | Descrição e Comportamento |
| :--- | :--- | :--- | :--- |
| `"text"` | `input[type="text"]` | `text_value` (`str`) | Linha única de texto curto (ex: títulos, identificadores, nomes). |
| `"textarea"` | `textarea` | `text_value` (`str`) | Bloco de texto longo / parágrafos (ex: justificativas científicas, resumos). |
| `"integer"` | `input[type="number"]` | `numeric_value` (`int`) | Número inteiro. Rejeita booleanos e pontos flutuantes. |
| `"float"` | `input[type="number"]` | `numeric_value` (`float`) | Número decimal de ponto flutuante. |
| `"boolean"` | `input[type="checkbox"]` / Switch | `boolean_value` (`bool`) | Booleano simples (`true` ou `false`). |
| `"date"` | `input[type="date"]` | `date_value` (`date`) | Data no formato ISO `YYYY-MM-DD`. Valida string ISO na API. |
| `"select"` | `select` / Dropdown | `json_value` ou `text_value` | Escolha de opção única a partir da lista fornecida em `options`. |
| `"file_upload"` | Upload / Anexo | `text_value` (`str`) | Armazena o identificador/URI do artefato enviado. *(Nota: anexos não são salvos no modo rascunho sem upload prévio).* |

---

## 5. Regras de Validação Técnica (`validation_rules`)

O objeto `validation_rules` permite definir restrições validadas tanto na gravação de rascunho (`PUT /processes/{id}/activities/{activity}/form`) quanto na submissão final:

### 5.1 Campos Numéricos (`integer` e `float`)
- `min`: Valor numérico mínimo permitido.
- `max`: Valor numérico máximo permitido.

```yaml
- field_key: "expected_laboratories_count"
  label: "Estimativa de Laboratórios Participantes"
  field_type: "integer"
  is_required: false
  order_index: 4
  validation_rules:
    min: 1
    max: 50
```

### 5.2 Upload de Arquivos (`file_upload`)
- `allowed_extensions`: Lista de extensões permitidas (sem o ponto).
- `max_size_mb`: Tamanho limite do arquivo em Megabytes.

```yaml
- field_key: "study_protocol_file"
  label: "Protocolo Detalhado do Estudo (PDF)"
  field_type: "file_upload"
  is_required: true
  order_index: 5
  validation_rules:
    allowed_extensions: ["pdf"]
    max_size_mb: 25
```

### 5.3 Agrupamento Visual (`section`)
Pode ser declarado como chave de primeiro nível no campo ou dentro de `validation_rules`:
```yaml
validation_rules:
  section: "Documentação de Suporte"
```

---

## 6. Configuração de Opções (`options` para `select`)

Para campos do tipo `select`, as opções são definidas sob a chave `options`.

### Formato Recomendado: Lista de Objetos `value` / `label`
```yaml
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
```

> **Nota:** A validação do backend verifica se o valor submetido confere exatamente com um dos `value` configurados.

---

## 7. Integração com Pré-Avaliação por IA (`ai_*`)

O PIVMA integra um pipeline de pré-avaliação automatizada por Inteligência Artificial para apoiar a triagem do BraCVAM. Campos de texto e justificativa podem acionar esse pipeline configurando as três chaves:

- `ai_evaluation_enabled`: Ativa (`true`) ou desativa (`false`) a avaliação por IA para o campo.
- `ai_context_instructions`: String contendo o direcionamento específico e critérios de qualidade que a IA deve buscar na resposta.
- `ai_validation_rules`: Dicionário com regras prévias (ex: `min_length` para exigir um mínimo de caracteres antes de submeter ao LLM).

```yaml
- field_key: "scientific_justification"
  label: "Justificativa Científica e Mecanística"
  field_type: "textarea"
  is_required: true
  order_index: 3
  ai_evaluation_enabled: true
  ai_context_instructions: "Avaliar se a justificativa descreve claramente o mecanismo biológico, relevância científica e alinhamento com métodos alternativos 3R."
  ai_validation_rules:
    min_length: 50
```

---

## 8. Exemplo Completo de Formulário

Abaixo um exemplo prático contendo campos de diversos tipos e configurações:

```yaml
forms:
  - key: "submission_exemplo_v1"
    name: "Formulário de Submissão Completo"
    version: 1
    description: "Exemplo abrangente de todos os recursos de sintaxe disponíveis para formulários."
    fields:
      # Campo de texto curto obrigatório
      - field_key: "method_title"
        label: "Título da Proposta"
        field_type: "text"
        is_required: true
        order_index: 1
        help_text: "Informe o título formal do método alternativo proposto."

      # Campo de seleção única
      - field_key: "regulatory_category"
        label: "Categoria Regulatória"
        field_type: "select"
        is_required: true
        order_index: 2
        options:
          - value: "cosmetics"
            label: "Cosméticos e Higiene Pessoal"
          - value: "pesticides"
            label: "Agrotóxicos e Afins"
          - value: "pharmaceuticals"
            label: "Medicamentos e Fármacos"

      # Campo de texto longo com avaliação por IA
      - field_key: "scientific_rationale"
        label: "Fundamentação Científica"
        field_type: "textarea"
        is_required: true
        order_index: 3
        section: "Justificativa Técnica"
        ai_evaluation_enabled: true
        ai_context_instructions: "Verificar consistência com os princípios 3R e viabilidade biológica."
        ai_validation_rules:
          min_length: 100

      # Campo numérico inteiro com faixa de valores
      - field_key: "collaborating_labs"
        label: "Número de Laboratórios Parceiros"
        field_type: "integer"
        is_required: false
        order_index: 4
        validation_rules:
          min: 1
          max: 20

      # Campo de data no formato ISO
      - field_key: "expected_completion_date"
        label: "Data Prevista de Conclusão dos Ensaios"
        field_type: "date"
        is_required: false
        order_index: 5

      # Campo booleano (checkbox)
      - field_key: "has_preliminary_glp_data"
        label: "Os ensaios preliminares seguiram Boas Práticas de Laboratório (BPL)?"
        field_type: "boolean"
        is_required: false
        order_index: 6

      # Campo de upload de documento em PDF
      - field_key: "dossier_pdf"
        label: "Dossiê Preliminar (PDF)"
        field_type: "file_upload"
        is_required: true
        order_index: 7
        section: "Anexos e Documentação"
        validation_rules:
          allowed_extensions: ["pdf"]
          max_size_mb: 50
```

---

## 9. Como Aplicar as Alterações

1. Edite ou adicione o arquivo `.yaml` desejado na pasta `src/pivma/templates_data/`.
2. Execute o script de bootstrap para sincronizar o banco de dados:
   ```bash
   poetry run python -m pivma.bootstrap_process_templates
   ```
   *(Ou execute através do container ou suite de migrações correspondente).*
3. Os formulários atualizados estarão imediatamente disponíveis nas APIs de processo e no endpoint `GET /processes/{id}/activities/{activity_key}/form`.

> **Exemplo real completo:** `05_proof_of_concept.yaml` reproduz o Formulário Preliminar (FP) do BraCVAM — 9 seções via `validation_rules.section`, campos `boolean` + `textarea` para os itens "SIM/NÃO + especifique", e `file_upload` restrito a PDF. Ver `specs/015-first-deploy-baseline/data-model.md` para o mapeamento campo a campo e as aproximações assumidas (limites por nº de palavras, grupos de checkbox, tabelas repetíveis não são suportados nativamente).
