# API Contract: Ciclo de Vida da Fase 1 dos Processos Padrão

**Feature**: `011-standard-process-templates`
**Date**: 2026-09-09

---

## 1. Listagem dos 5 Templates Oficiais

### `GET /processes/templates`
Retorna a lista completa dos 5 processos ativos disponíveis para o usuário autenticado.

#### Response: `200 OK`
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "key": "pre_validated_method",
    "name": "Método Pré-Validado",
    "description": "Método 100% novo já desenvolvido, protocolo estabelecido e validação interlaboratorial ainda por ser executada (Candidato à Validação Interlaboratorial / Validation-Ready Method).",
    "current_version": 1
  },
  {
    "id": "7fa85f64-5717-4562-b3fc-2c963f66afa7",
    "key": "scope_extension",
    "name": "Extensão de Escopo de Aplicação",
    "description": "Método já validado sendo proposta uma nova aplicação regulatória ou nova finalidade de uso (Fitness-for-Purpose Validation).",
    "current_version": 1
  },
  {
    "id": "8fa85f64-5717-4562-b3fc-2c963f66afa8",
    "key": "me_too_validation",
    "name": "Validação Me-Too",
    "description": "Método já validado sendo proposto um novo sistema teste ou método mecanisticamente e funcionalmente semelhante (Transferência / Adaptação de Sistema-Teste).",
    "current_version": 1
  },
  {
    "id": "9fa85f64-5717-4562-b3fc-2c963f66afa9",
    "key": "validated_method_dossier",
    "name": "Método Validado – Dossiê Submetido",
    "description": "Método 100% novo já desenvolvido, protocolo estabelecido e toda validação já concluída – dossiê pronto para revisão por pares e adoção regulatória (Peer-Review Ready).",
    "current_version": 1
  },
  {
    "id": "afa85f64-5717-4562-b3fc-2c963f66afaa",
    "key": "proof_of_concept",
    "name": "Prova de Conceito (PoC)",
    "description": "Ideia de método ainda a ser desenvolvido ou em estágio inicial de desenvolvimento e otimização (Método Conceitual / Early-Stage Pipeline).",
    "current_version": 1
  }
]
```

---

## 2. Instanciação de Processo

### `POST /processes`
Cria uma nova instância de processo vinculada a qualquer um dos 5 templates.

#### Request Body
```json
{
  "template_key": "pre_validated_method",
  "title": "Método Alternativo X para Irritação Ocular"
}
```

#### Response: `201 Created`
```json
{
  "id": "4fa85f64-5717-4562-b3fc-2c963f66afa6",
  "code": "VAL-2026-c4d3e2f1",
  "title": "Método Alternativo X para Irritação Ocular",
  "status": "SUBMISSION",
  "template_key": "pre_validated_method",
  "template_version": 1,
  "created_at": "2026-09-09T18:00:00Z"
}
```

---

## 3. Submissão e Disparo de IA

### `POST /processes/{process_id}/activities/proposal_submission/submit`
Envia formalmente a submissão preenchida pelo proponente, acionando o pipeline de IA e desbloqueando a triagem do BraCVAM.

#### Request Body
```json
{
  "values": {
    "method_title": "Método Alternativo X",
    "endpoint_target": "ocular_irritation",
    "scientific_justification": "Justificativa detalhada do mecanismo celular...",
    "pre_validation_evidence": "Dados preliminares de repetibilidade obtidos...",
    "study_protocol_file": "https://storage.bracvam.fiocruz.br/protocols/prot-01.pdf",
    "expected_laboratories_count": 4
  }
}
```

#### Response: `200 OK`
```json
{
  "activity_status": "COMPLETED",
  "process_status": "TRIAGE",
  "run_number": 1,
  "artifact": {
    "key": "proposal_dossier",
    "name": "Dossiê de Submissão - Submissão da Proposta (Run #1)",
    "status": "SUBMITTED"
  },
  "ai_evaluation": {
    "status": "COMPLETED",
    "verdict": {
      "status": "NEEDS_ADJUSTMENT",
      "confidence_score": 0.85,
      "inconformities": [
        "Fundamentação teórica requer detalhamento adicional da rota metabólica."
      ],
      "recommendations": [
        "Complementar a seção de justificativa científica com literatura da OCDE."
      ]
    }
  }
}
```

---

## 4. Deliberação de Triagem pelo BraCVAM

### `POST /processes/{process_id}/triage/decision`
Emite a deliberação formal dos avaliadores do BraCVAM.

#### Request Body
```json
{
  "outcome": "APPROVED",
  "justification": "Proposta atende aos critérios regulatórios e aos requisitos de viabilidade técnica."
}
```

#### Response: `200 OK`
```json
{
  "decision_id": "5fa85f64-5717-4562-b3fc-2c963f66afa6",
  "outcome": "APPROVED",
  "justification": "Proposta atende aos critérios regulatórios e aos requisitos de viabilidade técnica.",
  "new_process_status": "PLANNING",
  "next_run_number": null
}
```

*(Em caso de `NEEDS_REVISION`, `new_process_status` retorna `"SUBMISSION"` e `next_run_number` retorna `2`)*
*(Em caso de `REJECTED`, `new_process_status` retorna `"CLOSED"`)*
