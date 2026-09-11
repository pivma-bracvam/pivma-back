# Contratos de API: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Feature**: 020-decouple-triage-form  
**Date**: 2026-09-11  

---

## 1. Rotas de Triagem

### `POST /processes/{id}/triage/reviews`
- Permanece inalterado.
- Registra pareceres periciais sobre campos da proposta submetida (`form_instance_id` do formulário da submissão).

### `POST /processes/{id}/triage/decision`
- Permanece inalterado no contrato externo.
- Internamente, não consulta nem altera nenhuma instância de formulário para a atividade `triage_evaluation`.
- Registra a deliberação formal na tabela `decisions`.

### `GET /processes/{id}/activities/{activity_key}/form`
- Quando invocado para `activity_key = "triage_evaluation"`, o endpoint retorna `404 Not Found` (ou equivalente informativo), evidenciando que a atividade não possui formulário declarativo associado.
