# Quickstart: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Feature**: `010-form-ai-evaluation-pipeline`  
**Date**: 2026-09-09  
**Status**: Completed

Este guia descreve os passos para inicializar, executar a carga de teste e validar ponta a ponta o pipeline de avaliação de formulários por IA e a observabilidade em tempo real (conforme [AGENTS.md](../../AGENTS.md)).

---

## 1. Pré-Requisitos

1. Ambiente virtual ativo com as dependências instaladas:
   ```bash
   poetry install
   ```
2. Banco de dados de desenvolvimento em execução:
   ```bash
   docker compose up -d postgres
   ```
3. Migrações aplicadas:
   ```bash
   poetry run alembic upgrade head
   ```

---

## 2. Execução da Carga de Teste (Seed)

Execute o script de seed correspondente para provisionar o template de formulário com campos marcados para IA (`ai_evaluation_enabled = true`), instâncias de submissão e credenciais de administrador:

```bash
poetry run python scripts/seeds/seed_form_ai_demo.py
```

*Saída esperada:*
- Usuário administrador de teste: `admin@pivma.local` (senha de teste gerada/configurada).
- `FormTemplate` criado contendo campos com `ai_evaluation_enabled = True` (ex.: `scientific_justification`).
- `FormInstance` criada e preenchida com ID retornado no terminal.

---

## 3. Inicialização do Backend

Inicie o servidor de desenvolvimento:

```bash
poetry run fastapi dev src/pivma/__init__.py
```

O backend estará acessível em `http://127.0.0.1:8000`.

---

## 4. Validação do Pipeline de Avaliação de IA

Consulte o contrato em [contracts/admin_logs.openapi.yaml](./contracts/admin_logs.openapi.yaml).

### 4.1 Disparar Avaliação por IA

Submeta a requisição para avaliar a instância criada no seed:

```bash
curl -X POST "http://127.0.0.1:8000/forms/instances/<FORM_INSTANCE_ID>/evaluate-ai" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json"
```

*Resultado esperado:*
- HTTP 200 com JSON contendo:
  - `status`: `"COMPLETED"`
  - `evaluations`: lista de vereditos com status `"REPROVED"` ou `"NEEDS_ADJUSTMENT"`, score de confiança simulado, inconformidades e recomendações.

---

## 5. Validação dos Arquivos de Log e Rotação

Verifique a geração dos eventos nas duas camadas em disco:

1. **Índice Operacional (`logs/application/`):**
   ```bash
   cat logs/application/events_$(date +%Y-%m-%d).jsonl | tail -n 1 | jq .
   ```
   *Resultado esperado:* Registro JSONL único com `operation_type: "FORM_AI_EVALUATION"`, `total_duration_ms` e `correlation_id`.

2. **Log Granular de Etapas de IA (`logs/ai/`):**
   ```bash
   grep "<CORRELATION_ID>" logs/ai/ai_steps_$(date +%Y-%m-%d).jsonl | jq .
   ```
   *Resultado esperado:* Exatamente 3 registros JSONL sequenciais correspondentes a:
   - Etapa 1: `context_extraction`
   - Etapa 2: `mock_evaluation`
   - Etapa 3: `verdict_synthesis`
   Todos com latência individual em milissegundos e custo simulado atribuído.

---

## 6. Validação das Demonstrações Interativas (AGENTS.md)

Abra o catálogo de demonstrações no navegador:

```bash
# Pode ser aberto via navegador ou servido estaticamente
xdg-open demos/index.html
# ou acessar via http://127.0.0.1:8000/demos/ se servido estaticamente
```

### 6.1 Módulo 1: Visualização Geral (Índice Operacional em Tempo Real)
- Acesse `demos/operational-index/index.html`.
- Forneça o token de administrador.
- Conecte ao stream: novos eventos da plataforma e requisições HTTP aparecem em tempo real na tabela cronológica.

### 6.2 Módulo 2: Visualização da IA (Pipelines Agrupados em Tempo Real)
- Acesse `demos/ai-pipeline/index.html`.
- Forneça o token de administrador.
- Acione uma avaliação pelo painel interativo.
- Observe o card do pipeline sendo atualizado em tempo real:
  - As 3 etapas são exibidas em linha do tempo sob o mesmo `correlation_id`;
  - Ao expandir cada etapa, são visíveis os payloads de entrada/saída, latência e custo simulado;
  - O veredito canônico final negativo é exibido no rodapé do card com as inconformidades e recomendações.

---

## 7. Execução dos Testes Automatizados

Para executar a suíte de testes de unidade e integração:

```bash
poetry run pytest tests/unit/test_ai_pipeline.py tests/integration/test_admin_logs.py -vv
```
