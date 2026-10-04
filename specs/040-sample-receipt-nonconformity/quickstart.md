# Quickstart: Spec 040

## Pré-requisitos

- Banco de testes (Testcontainers) e dependências instaladas (`poetry install`).
- Nenhum acesso à rede: o PubChem é simulado por `httpx.MockTransport`.

## Validação

```bash
poetry run pytest tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py
poetry run pytest tests/api/routers/test_sample_receipt_router.py tests/api/routers/test_sample_nonconformity_router.py tests/api/routers/test_sample_lookup.py tests/api/routers/test_samples_router.py
poetry run pytest
poe docs-build
```

## Resultados esperados

1. Jornada (US3, US6, US7): processo do template 1 até a Etapa 3; Lab A
   recebe um frasco a 21 °C (faixa 2–8); o Grupo de Seleção vê a tarefa e o
   e-mail na fila, reenvia; o Lab A registra o frasco novo em ordem e o
   recebimento dele conclui; o Lab B não vê nada disso.
2. Cadastro (US1): substância sem classificação de referência → `422`;
   visão cega sem nome, CAS, SDS e classificação.
3. Consulta (US2): CAS conhecido → sugestões e nenhuma substância nova; CAS
   desconhecido → `404 compound_not_found`; fonte fora → `503`.
4. A suíte completa continua verde e o manual compila.

Contratos: [contracts/http-api.md](contracts/http-api.md). Modelo:
[data-model.md](data-model.md).
