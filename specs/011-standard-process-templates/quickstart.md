# Quickstart: Validação Ponta a Ponta da Feature 011

**Feature**: `011-standard-process-templates`
**Date**: 2026-09-09

---

## 1. Pré-Requisitos

1. Ambiente virtual ativo com as dependências instaladas (`poetry install`).
2. Banco de dados PostgreSQL de teste ativo.
3. Templates sincronizados via comando de bootstrap.

---

## 2. Cenários de Validação

### Cenário 1: Bootstrap e Listagem dos 5 Processos Oficiais
**Objetivo**: Comprovar que o template legado `full_validation` foi extinto e que os 5 processos oficiais estão ativos.

1. Executar o bootstrap:
   ```bash
   poetry run python -m pivma.bootstrap_process_templates
   ```
2. Consultar o catálogo:
   ```bash
   curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/processes/templates | jq .
   ```
3. **Resultado Esperado**:
   - Resposta com array contendo exatamente 5 itens:
     - `pre_validated_method`
     - `scope_extension`
     - `me_too_validation`
     - `validated_method_dossier`
     - `proof_of_concept`
   - Nenhuma menção a `full_validation`.

---

### Cenário 2: Ciclo de Submissão com Avaliação Automatizada por IA
**Objetivo**: Instanciar um processo, enviar dados de proposta e verificar a execução do pipeline de IA da Spec 010.

1. Criar processo para `pre_validated_method`:
   ```bash
   PROCESS_ID=$(curl -s -X POST http://localhost:8000/processes \
     -H "Authorization: Bearer $PROPONENT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"template_key": "pre_validated_method", "title": "Estudo de Teste Cutâneo"}' | jq -r .id)
   ```
2. Submeter o formulário:
   ```bash
   curl -s -X POST http://localhost:8000/processes/$PROCESS_ID/activities/proposal_submission/submit \
     -H "Authorization: Bearer $PROPONENT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "values": {
         "method_title": "Método Alternativo Cutâneo",
         "endpoint_target": "skin_sensitization",
         "scientific_justification": "Fundamentação mecanística do ensaio celular com linhagem imortalizada.",
         "pre_validation_evidence": "Reprodutibilidade observada em 3 repetições preliminares.",
         "study_protocol_file": "https://storage.bracvam.fiocruz.br/protocols/p-01.pdf"
       }
     }' | jq .
   ```
3. **Resultado Esperado**:
   - Status da atividade transiciona para `COMPLETED`.
   - Processo avança para `TRIAGE`.
   - A avaliação de IA é executada pelo `FormAIPipelineEngine` retornando veredito simulado negativo (`NEEDS_ADJUSTMENT` ou `REPROVED`) com inconsistências e recomendações.
   - Eventos gravados em `logs/ai/ai_steps.jsonl` e `logs/application/events.jsonl`.

---

### Cenário 3: Parecer e Deliberação pelo BraCVAM
**Objetivo**: Avaliar a submissão e emitir decisão de aprovação ou diligência.

1. Como triador do BraCVAM (`TRIAGE_LEAD`), consultar a tarefa e emitir aprovação:
   ```bash
   curl -s -X POST http://localhost:8000/processes/$PROCESS_ID/triage/decision \
     -H "Authorization: Bearer $TRIAGE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "outcome": "APPROVED",
       "justification": "Proposta considerada viável e aprovada para fase de planejamento."
     }' | jq .
   ```
2. **Resultado Esperado**:
   - Resposta `200 OK` com `new_process_status: "PLANNING"`.
   - Trilha de auditoria registra o evento `TRIAGE_APPROVED`.

---

### Cenário 4: Execução da Suíte de Testes Automatizados
**Objetivo**: Garantir que todos os testes passem sem regressões.

```bash
poetry run pytest tests/api/routers/test_process_router.py -v
poetry run pytest tests/unit/core/test_template_loader.py -v
poetry run pytest tests/api/routers/test_form_submission.py -v
poetry run pytest tests/integration/test_form_ai_evaluation_api.py -v
```

---

### Cenário 5: Execução do Seed e Validação das Demonstrações (AGENTS.md)
**Objetivo**: Validar que as demos e sementes operam com os novos processos.

```bash
poetry run python -m scripts.seeds.seed_all
```
Acessar `demos/index.html` e verificar os fluxos dos 5 novos processos operando de ponta a ponta.
