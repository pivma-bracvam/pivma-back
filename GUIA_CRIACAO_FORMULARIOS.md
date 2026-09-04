# Guia Prático: Como o BraCVAM Cria e Gerencia Formulários de Submissão

Este guia apresenta, passo a passo e sob a perspectiva da equipe do **BraCVAM**, como estruturar, configurar e gerenciar os formulários preenchidos pelos proponentes ao submeterem métodos alternativos para validação.

O documento inclui os **schemas JSON** de definição e os **endpoints HTTP da API** utilizados em cada etapa do ciclo de vida.

---

## O Cenário: A Jornada do BraCVAM

O BraCVAM precisa padronizar o recebimento de propostas de validação de métodos alternativos ao uso de animais (por exemplo, o ensaio de irritação ocular HET-CAM). A equipe precisa:
1. Identificar o método;
2. Entender a base mecanicista de redução/substituição animal (3Rs);
3. Obter os parâmetros operacionais do ensaio;
4. Receber o Procedimento Operacional Padrão (POP) em PDF.

Abaixo está o fluxo percorrido pelo gestor do BraCVAM para modelar essa estrutura e acompanhar seu preenchimento.

---

## 1. "Quero criar um formulário novo. Como faz?"

O gestor define o cabeçalho do template de formulário com identificadores unívocos e orientações gerais ao proponente.

### Estrutura JSON do Template (`FormTemplate`)

```json
{
  "key": "submission_full_validation_v1",
  "name": "Formulário de Submissão de Método Alternativo",
  "version": 1,
  "description": "Preencha as informações técnicas, mecanísticas e regulatórias do método proposto para validação."
}
```

* **`key`:** chave técnica imutável usada pelo backend para indexação.
* **`name`:** título legível exibido no cabeçalho da página do proponente.
* **`version`:** versão estrutural. Caso o BraCVAM altere os campos futuramente, gera-se uma nova versão (`v2`), mantendo intactos os processos já submetidos.

---

## 2. "Quero dividir o formulário em sessões. Como faz?"

Para facilitar a leitura e o preenchimento, o BraCVAM organiza o questionário em blocos lógicos:

```text
┌───────────────────────────────────────────────────────────────────┐
│ SESSÃO 1: Identificação e Propósito                               │
│   • Título do Método                                              │
│   • Desfecho / Toxicidade Avaliada                                │
│   • Justificativa Científica e dos 3Rs                            │
├───────────────────────────────────────────────────────────────────┤
│ SESSÃO 2: Parâmetros Técnicos do Ensaio                           │
│   • Estimativa de Laboratórios Participantes                      │
├───────────────────────────────────────────────────────────────────┤
│ SESSÃO 3: Documentação e Protocolos                               │
│   • Procedimento Operacional Padrão (POP em PDF)                  │
└───────────────────────────────────────────────────────────────────┘
```

Na definição dos campos, essa sequência é governada pelo atributo `order_index`.

---

## 3. "Quero que a sessão tenha os campos X, Y e Z. Como faz?"

O BraCVAM adiciona a lista de campos ao formulário. Cada campo declara seu tipo de dado, se é obrigatório e suas orientações contextuais.

### Estrutura JSON dos Campos (`FormFieldDefinition`)

```json
[
  {
    "field_key": "method_title",
    "label": "Título do Método Proposto",
    "field_type": "text",
    "help_text": "Nome científico e comercial do método de ensaio.",
    "is_required": true,
    "order_index": 1,
    "validation_rules": {
      "min_length": 5,
      "max_length": 200
    }
  },
  {
    "field_key": "endpoint_target",
    "label": "Desfecho / Toxicidade Avaliada",
    "field_type": "select",
    "help_text": "Selecione o desfecho toxicológico primário contemplado.",
    "is_required": true,
    "order_index": 2,
    "options": [
      { "value": "ocular_irritation", "label": "Irritação / Corrosão Ocular" },
      { "value": "skin_sensitization", "label": "Sensibilização Cutânea" },
      { "value": "phototoxicity", "label": "Fototoxicidade" },
      { "value": "acute_toxicity", "label": "Toxicidade Aguda Oral" }
    ]
  },
  {
    "field_key": "scientific_justification",
    "label": "Justificativa Científica e dos 3Rs",
    "field_type": "textarea",
    "help_text": "Descreva a base mecanicista e o potencial de substituição/redução de animais.",
    "is_required": true,
    "order_index": 3,
    "validation_rules": {
      "min_length": 20
    }
  },
  {
    "field_key": "expected_laboratories_count",
    "label": "Estimativa de Laboratórios Participantes",
    "field_type": "integer",
    "help_text": "Número sugerido de laboratórios para o estudo interlaboratorial.",
    "is_required": false,
    "order_index": 4,
    "validation_rules": {
      "min": 1,
      "max": 50
    }
  },
  {
    "field_key": "study_protocol_file",
    "label": "Procedimento Operacional Padrão (POP / PDF)",
    "field_type": "file_upload",
    "help_text": "Anexe o protocolo completo do ensaio em formato PDF.",
    "is_required": true,
    "order_index": 5,
    "validation_rules": {
      "allowed_extensions": ["pdf"],
      "max_size_mb": 25
    }
  }
]
```

### O papel de cada campo para o BraCVAM:
* **Campo X (`method_title`):** texto curto obrigatório para registro do nome do método no catálogo e em portarias.
* **Campo Y (`endpoint_target`):** seleção única restrita a opções predefinidas, permitindo que a triagem encaminhe a proposta ao comitê de especialistas correto.
* **Campo Z (`scientific_justification`):** parágrafo obrigatório que fundamenta a redução/substituição do modelo animal em relação à diretriz de referência (ex.: OECD TG 405).
* **Parâmetros e Anexos (`expected_laboratories_count` e `study_protocol_file`):** viabilizam o dimensionamento do estudo colaborativo e a conferência minuciosa das etapas laboratoriais.

---

## 4. "Como garanto que o proponente preencha certo?"

O BraCVAM aplica restrições automáticas no objeto `validation_rules` de cada campo:
* **`min_length` / `max_length`:** evita respostas monossilábicas ou textos excessivos.
* **`allowed_extensions` e `max_size_mb`:** impede o envio de formatos incompatíveis (exigindo `.pdf` de até 25 MB).
* **Apoio Opcional por IA:** em campos descritivos, o BraCVAM pode configurar prompts de verificação para alertar inconsistências ao proponente antes da submissão final.

---

## 5. Endpoints Utilizados no Ciclo de Preenchimento e Triagem

A seguir, a sequência de requisições HTTP que operam a proposta entre o Proponente e o BraCVAM.

### 5.1. Proponente Cria o Processo

* **Endpoint:** `POST /processes`
* **Descrição:** Instancia um processo baseado no template ativo.

**Payload de Requisição:**
```json
{
  "template_key": "full_validation",
  "title": "Validação do Método de Irritação Corneana HET-CAM"
}
```

**Resposta do Servidor (HTTP 201):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "code": "BRA-2026-001",
  "title": "Validação do Método de Irritação Corneana HET-CAM",
  "status": "DRAFT",
  "template_key": "full_validation",
  "version_number": 1
}
```

---

### 5.2. Proponente Consulta a Estrutura do Formulário

* **Endpoint:** `GET /processes/{id}/activities/{activity_key}/form`
* **Parâmetros:** `activity_key = proposal_submission`
* **Descrição:** Retorna os campos configurados pelo BraCVAM, valores atuais e eventuais pareceres de triagem.

**Resposta do Servidor (HTTP 200):**
```json
{
  "form_instance_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "template_key": "submission_full_validation_v1",
  "is_submitted": false,
  "fields": [
    {
      "field_key": "method_title",
      "label": "Título do Método Proposto",
      "field_type": "text",
      "is_required": true,
      "order_index": 1
    },
    {
      "field_key": "endpoint_target",
      "label": "Desfecho / Toxicidade Avaliada",
      "field_type": "select",
      "is_required": true,
      "order_index": 2
    }
  ],
  "values": {},
  "reviews": {}
}
```

---

### 5.3. Proponente Salva Rascunho

* **Endpoint:** `PUT /processes/{id}/activities/{activity_key}/form`
* **Descrição:** Permite salvamento parcial progressivo. Campos obrigatórios não bloqueiam o rascunho.

**Payload de Requisição:**
```json
{
  "values": {
    "method_title": "Ensaio HET-CAM para Irritação Corneana",
    "endpoint_target": "ocular_irritation",
    "scientific_justification": "O ensaio avalia danos vasculares na membrana corioalantoide..."
  }
}
```

**Resposta do Servidor (HTTP 200):**
```json
{
  "message": "Rascunho salvo com sucesso.",
  "form_instance_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

---

### 5.4. Proponente Submete a Proposta Formalmente ("Dar OK")

* **Endpoint:** `POST /processes/{id}/activities/{activity_key}/form`
* **Descrição:** Valida todos os campos obrigatórios. Se aprovado, congela a edição e avança a etapa do processo.

**Payload de Requisição:**
```json
{
  "values": {
    "method_title": "Ensaio HET-CAM para Irritação Corneana",
    "endpoint_target": "ocular_irritation",
    "scientific_justification": "O método de ensaio da membrana corioalantoide (HET-CAM) é uma alternativa ao teste de Draize em coelhos (OECD TG 405), reduzindo integralmente o uso de animais.",
    "expected_laboratories_count": 4,
    "study_protocol_file": "POP_HET_CAM_Protocolo_v2.1.pdf"
  }
}
```

**Resposta do Servidor (HTTP 200):**
```json
{
  "activity_key": "proposal_submission",
  "run_number": 1,
  "status": "COMPLETED",
  "artifact_id": "8e3b4a20-3129-4d2c-8067-ff7025816b3c"
}
```

---

### 5.5. BraCVAM Avalia os Campos na Triagem

* **Endpoint:** `POST /processes/{id}/triage/reviews`
* **Perfil Requerido:** Triador BraCVAM / Grupo Gestor
* **Descrição:** O avaliador técnico inspeciona cada campo individualmente e registra pareceres com apontamentos.

**Payload de Requisição:**
```json
{
  "reviews": [
    {
      "field_key": "method_title",
      "status": "OK",
      "comments": "Título claro e de acordo com o escopo."
    },
    {
      "field_key": "scientific_justification",
      "status": "NEEDS_REVISION",
      "comments": "Favor citar o limite de sensibilidade em comparação com o teste de Draize."
    },
    {
      "field_key": "study_protocol_file",
      "status": "OK",
      "comments": "POP completo com descrição detalhada de reagentes."
    }
  ]
}
```

**Resposta do Servidor (HTTP 200):**
```json
{
  "message": "Avaliações de campo registradas com sucesso."
}
```

---

### 5.6. BraCVAM Emite a Decisão de Triagem

* **Endpoint:** `POST /processes/{id}/triage/decision`
* **Perfil Requerido:** Triador BraCVAM / Grupo Gestor
* **Opções de Resultado (`outcome`):**
  * `APPROVED`: Proposta aceita; avança para a Fase de Planejamento.
  * `DILIGENCE`: Solicita ajustes; reabre o formulário para correção do proponente.
  * `REJECTED`: Proposta recusada e processo encerrado.

**Payload de Requisição (Exemplo de Diligência):**
```json
{
  "outcome": "DILIGENCE",
  "justification": "Solicitada complementação técnica na justificativa científica dos 3Rs para inclusão dos limites de sensibilidade antes do prosseguimento."
}
```

**Resposta do Servidor (HTTP 200):**
```json
{
  "process_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "new_process_status": "IN_DILIGENCE",
  "decision_id": "a9d0c24e-7b19-4f81-8172-123456789abc",
  "outcome": "DILIGENCE",
  "next_activity_run": 2
}
```
