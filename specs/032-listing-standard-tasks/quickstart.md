# Quickstart: Padrão de listagens e lista de tarefas

Guia de verificação ponta a ponta. Contrato em [contracts/http-api.md](contracts/http-api.md); modelos em [data-model.md](data-model.md).

## Testes automatizados

```bash
poetry run pytest tests/api/routers/test_tasks_router.py tests/api/routers/test_tasks_visibility.py
poetry run pytest tests/api/routers/test_tasks_listing.py      # envelope, paginação, filtros, ordem, facets, summary
poetry run pytest tests/integration/journeys                   # jornadas usando o formato novo
poetry run pytest                                              # suíte completa, sem regressão
poetry run ruff check . && poetry run ruff format --check .
```

O nome final dos arquivos de teste novos sai do `tasks.md`.

## Verificação manual

Pré-requisito: API local com o banco migrado e o fluxo das jornadas executado, para ter processos em etapas diferentes.

1. Como BraCVAM, `GET /tasks?phase_order=1&status=READY&include=facets&include=summary`:
   - `facets.activity_key` bate com o número de submissões, triagens e revisões abertas;
   - `summary.ai_pre_evaluation_in_progress` bate com os processos em avaliação pela IA;
   - `filters_applied.current_run` é `true` sem ter sido pedido.
2. O mesmo pedido com `actionable=true`: só triagens, todas com `can_act: true`.
3. Como Admin, `actionable=true`: nenhuma triagem.
4. `per_page=1&page=2`: um item, `has_prev: true`, e as contagens iguais às do passo 1.
5. `current_run=false` num processo com revisão: aparecem as rodadas anteriores.
6. `status=FOO`, `per_page=101` e `sort_by=title`: todos respondem `422`.
7. Como proponente, `include=summary`: a contagem da IA considera só os processos dele.

Os resultados esperados vêm dos cenários de aceitação das US1 a US5 da spec.
