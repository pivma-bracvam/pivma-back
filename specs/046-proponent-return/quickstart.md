# Quickstart: Retorno ao Proponente

Pré-requisito: Docker ativo para os Testcontainers e dependências instaladas com
`poetry install`.

## Jornadas

```bash
poetry run pytest tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_feedback.py
poetry run pytest tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_email.py
```

| Jornada | Resultado esperado |
|---|---|
| Triagem devolve com pareceres e o proponente revisa | `previous_reviews` traz os pareceres, `reviews` vem vazio, e a versão 1 mantém os mesmos pareceres depois do reenvio |
| Rodada 2 devolvida | Cada versão mostra só os próprios pareceres |
| IA devolve e o proponente revisa | `previous_reviews` vazio; o resultado segue na pré-avaliação |
| Devoluções pela triagem e pela IA | O canal falso recebe o aviso, sem justificativa, pareceres ou avaliador |
| Reprocessamento com envio pendente | Envio `cancelled`, `RETURN_REVIEW_CANCELLED` com o administrador como autor e novo envio se a IA devolver de novo |

## Testes focados

```bash
poetry run pytest tests/api/routers/test_return_review.py tests/api/routers/test_process_submission_update.py
poetry run pytest tests/integration/notifications/test_submission_returned_email.py tests/unit/notifications/test_submission_returned_email_renderer.py
```

Cobrem campo removido, atividades que não são a submissão, `404` de quem não vê
a submissão, canal indisponível, dois proponentes, conta desativada, exclusão do processo
com envio pendente e os `409`, inclusive o de retorno da triagem depois de uma
contestação, de [`pre-evaluation-retry.md`](contracts/pre-evaluation-retry.md).

## Concorrência

```bash
poetry run pytest tests/integration/database/test_return_review_concurrency.py tests/integration/database/test_pre_evaluation_concurrency.py
```

As disputas estão em [research R6](research.md#r6-testes-de-concorrência). Rode
os testes do reprocessamento antes da correção: eles devem falhar.

## Fechamento

```bash
grep -rn "TODO(spec-030)" src
```

O comando não deve listar nada.

```bash
poetry run poe lint
```

```bash
poetry run poe test
```

Leia o resultado do pytest na saída: a tarefa usa `-x` e `ignore_fail`, então
sai com código 0 mesmo com falha.

```bash
poetry run poe docs-build
```
