# Contrato: e-mail de devolução

**Tipo**: `submission_returned_email`

**Gatilho**: abertura de retorno pela triagem ou pela IA.

**Destinatários**: um envio por e-mail de proponente ativo no processo.

**Assunto**: `Submissão devolvida — {process_code}`

**Corpo**, em texto e HTML:

| Linha | Valor |
|---|---|
| Processo | `{process_code} — {process_title}` |
| Origem | `Triagem` ou `Pré-avaliação por IA` |
| Prazo | `dd/mm/aaaa HH:MM (UTC)`; a linha some sem prazo |

O corpo orienta acessar a pi\*VMA para ler o retorno e responder.

**Proibido no conteúdo**: justificativa, pareceres, resultado da IA, indicação
de falha da IA e nome de quem avaliou.

**Sem canal configurado**: nenhum pedido de envio, e a devolução conclui.

**Cancelamento**: o reprocessamento da IA e a exclusão do processo cancelam os
envios pendentes do retorno, com `error_code` `return_review_cancelled`, e grava
`NOTIFICATION_CANCELLED`.
