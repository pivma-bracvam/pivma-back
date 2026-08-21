# Quickstart: Validação de Processos e Fase 1 (Submissão e Triagem)

**Feature**: 004-process-submission-triage  
**Date**: 2026-08-21  
**Spec**: [spec.md](spec.md) | **Contracts**: [processes.openapi.yaml](contracts/processes.openapi.yaml)

Este guia apresenta o roteiro para validar ponta a ponta o fluxo de instanciação de processos, preenchimento de formulário de submissão, avaliação campo a campo e decisão de triagem (com suporte a diligência e reexecução).

---

## 1. Pré-requisitos e Preparação do Ambiente

Certifique-se de que o ambiente de banco de dados PostgreSQL está ativo:
```bash
# Iniciar banco de dados local via Docker Compose (se aplicável)
docker compose up -d

# Executar as migrações mais recentes do Alembic
poetry run alembic upgrade head

# Carregar templates declarativos de processos e formulários
poetry run python -m pivma.bootstrap_process_templates
```

---

## 2. Cenários de Validação

### Cenário 1: Jornada Feliz — Submissão e Aprovação Direta na Triagem

1. **Autenticar como Proponente e Criar Processo**:
   - `POST /processes` com corpo `{"template_key": "full_validation", "title": "Método de Triagem Fototóxica 3T3 NRU"}`.
   - Resposta: `HTTP 201 Created` retornando o `id` da `ProcessInstance` no status `SUBMISSION`.
   - Verificar que a atividade `proposal_submission` está em status `IN_PROGRESS` e a tarefa correspondente gerada.

2. **Preencher e Submeter o Formulário de Submissão**:
   - `GET /processes/{id}/activities/proposal_submission/form` para inspecionar os campos.
   - `POST /processes/{id}/activities/proposal_submission/form` enviando os valores obrigatórios (`method_title`, `endpoint_target`, `scientific_justification`, etc.).
   - Resposta: `HTTP 200 OK` indicando que `proposal_submission` foi para `COMPLETED` com `run_number = 1`.
   - O processo transiciona automaticamente para o status `TRIAGE`.

3. **Verificar Liberação da Atividade de Triagem**:
   - `GET /tasks` como usuário do Grupo Gestor/Triador.
   - A tarefa "Realizar Triagem da Proposta" aparece com status `READY` (não mais `BLOCKED`).

4. **Revisar Campos e Emitir Decisão de Aprovação**:
   - `POST /processes/{id}/triage/review` registrando `CONFORME` para os campos inspecionados.
   - `POST /processes/{id}/triage/decision` enviando:
     ```json
     {
       "outcome": "APPROVED",
       "justification": "Proposta atende integralmente às diretrizes metodológicas."
     }
     ```
   - Resposta: `HTTP 200 OK`. A `ProcessInstance` conclui a Fase 1 e fica apta para o Planejamento.

---

### Cenário 2: Diligência e Reexecução Preservando Histórico

1. **Submeter Proposta Inicial** (Run #1 gerado e concluído).
2. **Triador Identifica Pendência**:
   - `POST /processes/{id}/triage/review` com campo `scientific_justification` como `NAO_CONFORME` ("Faltam dados de citotoxicidade prévia").
   - `POST /processes/{id}/triage/decision` com `outcome: "NEEDS_REVISION"`.
3. **Verificar Nova Execução Criada**:
   - O sistema cria automaticamente `ActivityRun` com `run_number = 2` na atividade de submissão.
   - O `FormInstance` do Run 2 é pré-populado com os dados do Run 1.
   - `GET /processes/{id}/timeline` exibe a trilha completa:
     - `ActivityRun #1` (Submetido)
     - `Decision` (`NEEDS_REVISION`)
     - `ActivityRun #2` (Em andamento)
4. **Proponente Ajusta e Reenvia**:
   - `POST /processes/{id}/activities/proposal_submission/form` (Run #2) enviando a justificativa corrigida.
   - Triador aprova a nova submissão. Ambas as submissões continuam auditadas no banco de dados.

---

### Cenário 3: Rejeição Formal na Triagem

1. **Submissão Inviável**:
   - Proponente submete proposta.
2. **Decisão de Rejeição**:
   - Triador emite `POST /processes/{id}/triage/decision` com `outcome: "REJECTED"`, `justification: "Método não se enquadra no escopo do PIVMA"`.
3. **Bloqueio de Edição**:
   - Processo atinge o estado `CLOSED`.
   - Tentativas de salvar ou submeter formulários subsequentes retornam `HTTP 409 Conflict`.

---

## 3. Execução da Suíte de Testes Automatizados

Execute os testes automatizados para verificar a conformidade com as regras:
```bash
# Executar todos os testes da feature
poetry run pytest tests/api/routers/test_process_router.py tests/integration/database/test_process_constraints.py

# Executar suite completa com cobertura
poetry run pytest
```
