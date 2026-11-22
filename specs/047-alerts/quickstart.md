# Quickstart: Alerts na plataforma

Roteiro para conferir a entrega de ponta a ponta. O contrato está em [contracts/alerts-api.md](contracts/alerts-api.md), e os tipos e destinatários em [data-model.md](data-model.md).

## Pré-requisitos

- Banco com as migrações aplicadas (`alembic upgrade head` ou o compose de desenvolvimento).
- Contas de demonstração do bootstrap: proponente, duas pessoas do BraCVAM e designados dos laboratórios Demo A e Demo B.
- `$API` apontando para o backend e um token por conta (`$TOKEN_PROPONENTE`, `$TOKEN_BRACVAM_1`, `$TOKEN_BRACVAM_2`).

## 1. Tarefa nova para o BraCVAM

1. Como proponente, crie um processo e envie a proposta.
2. Espere a pré-avaliação por IA positiva (provedor fake).
3. Como cada pessoa do BraCVAM:

```bash
curl -s "$API/alerts?unread=true" -H "Authorization: Bearer $TOKEN_BRACVAM_1"
```

Esperado: um alert `task_opened` com `params.activity_key = "triage_evaluation"`, `target.type = "task"` e `unread_count` igual a 1.

4. Como proponente, liste os alerts. Esperado: um alert `submission_status_changed` com `params.status = "in_triage"` e nenhum `task_opened` da própria submissão.

## 2. Ler e limpar

```bash
curl -s -X POST "$API/alerts/$ALERT_ID/read" -H "Authorization: Bearer $TOKEN_BRACVAM_1"
curl -s "$API/alerts?per_page=1" -H "Authorization: Bearer $TOKEN_BRACVAM_1"
curl -s -X POST "$API/alerts/read-all" -H "Authorization: Bearer $TOKEN_BRACVAM_1"
```

Esperado: `read_at` preenchido, `unread_count` caindo a cada passo e `{"updated": n}` no fim. O mesmo `$ALERT_ID` com o token de `$TOKEN_BRACVAM_2` responde `404`.

## 3. Devolução sem revelar a origem detalhada

1. Como BraCVAM, peça revisão na triagem.
2. Como proponente, liste os alerts.

Esperado: um `task_opened` com `params.activity_key = "submission_return_review"`, sem justificativa, pareceres nem nome do triador.

## 4. Isolamento por laboratório

Leve um processo até o recebimento de amostras com os laboratórios Demo A e Demo B, e dispense a execução de B.

Esperado: os designados por B recebem `laboratory_run_waived`, e os de A não. Os alerts de A trazem só `laboratory_name` de A, e nenhum alert de laboratório traz nome químico, CAS ou SDS.

## Verificação automatizada

```bash
poe test -- -k alerts
poe lint
poe docs-build
```

Os testes de jornada ficam em `tests/integration/journeys/`, e os testes focados em `tests/api/routers/test_alerts*.py`.
