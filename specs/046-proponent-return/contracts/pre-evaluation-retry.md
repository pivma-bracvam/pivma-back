# Contrato: reprocessamento da pré-avaliação

`POST /admin/pre-evaluations/{run_id}/retry`

| Situação | Resposta |
|---|---|
| Execução mais recente, `failed`, com retorno da IA aberto | `202`, como hoje |
| Execução inexistente | `404`, como hoje |
| Processo imutável ou execução `completed` | `409`, como hoje |
| Execução `in_progress` | `409` (era `202`) |
| Execução que não é a mais recente | `409` (era `202`) |
| Retorno já decidido ou cancelado | `409` (era `202`) |
| Retorno aberto de origem `TRIAGE` | `409` (era `202`) |

O `409` usa o formato atual da rota, que passa por `domain_error`.

No `202`, a linha do tempo ganha `RETURN_REVIEW_CANCELLED`, com o administrador
como autor e `source` e `run_number` no contexto. Nada muda no corpo da
resposta.
