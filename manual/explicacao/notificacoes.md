# Notificações

Usos atuais: convite por e-mail e recuperação de senha.

## Gravar junto, enviar depois

```mermaid
sequenceDiagram
    participant API
    participant DB as Banco
    participant W as Worker
    participant S as SMTP
    API->>DB: operação de negócio + pedido de envio<br/>(mesma transação)
    W->>DB: pega um pendente (FOR UPDATE SKIP LOCKED)
    W->>S: envia
    W->>DB: grava o resultado, apaga o conteúdo
```

A operação de negócio e o pedido de envio são gravados na mesma transação.
Se a operação for desfeita, nada é enviado. Se o servidor de e-mail estiver
fora do ar, a operação não falha: o envio fica pendente e o worker tenta
depois.

O worker pega um envio por vez com `FOR UPDATE SKIP LOCKED`, então vários
workers podem rodar sem enviar a mesma mensagem duas vezes.

## Tentativas

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> sent: SMTP aceitou
    pending --> pending: erro temporário<br/>espera e tenta de novo
    pending --> failed: erro permanente, prazo vencido,<br/>tentativas esgotadas, chave errada
    pending --> cancelled: convite aceito ou revogado,<br/>novo pedido de senha
```

| Erro | Tratamento |
|---|---|
| Temporário (4xx do SMTP, conexão, timeout) | Tenta de novo após 30 s, 60 s, 120 s… até 900 s, no máximo 5 vezes |
| Permanente (5xx, destinatário recusado) | Falha na hora |
| Prazo do convite ou do link vencido | Falha como `expired`, sem enviar |

## Conteúdo protegido

O conteúdo da mensagem fica cifrado no banco com `NOTIFICATION_ENCRYPTION_KEY`
(Fernet) enquanto está pendente, e é apagado quando o envio termina. Logs e
auditoria registram só identificadores, o tipo e o canal.

## Rastro

Envios ligados a um processo (convites) gravam `NOTIFICATION_SENT`,
`NOTIFICATION_FAILED` ou `NOTIFICATION_CANCELLED` na linha do tempo. O convite
mostra a situação em `delivery`.

## Limite conhecido

Se o worker cair depois que o servidor SMTP aceitou a mensagem e antes de
gravar o resultado, a mensagem pode sair de novo.

## Estender

Um novo tipo de aviso precisa de um `kind`, um renderizador em
`src/pivma/notifications/renderers.py` (assunto, texto e HTML) e uma chamada a
`enqueue_notification` dentro da transação da operação.
