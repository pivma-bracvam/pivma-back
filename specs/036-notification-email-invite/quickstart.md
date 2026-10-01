# Quickstart: validar o convite por e-mail

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/http-api.md](./contracts/http-api.md)

## Pré-requisitos

1. Gerar uma chave Fernet:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. No `.env`:

   ```env
   NOTIFICATION_EMAIL_BACKEND=smtp
   SMTP_HOST=mailpit
   SMTP_PORT=1025
   SMTP_SECURITY=none
   NOTIFICATION_FROM_ADDRESS=nao-responda@pivma.local
   NOTIFICATION_ENCRYPTION_KEY=<chave gerada>
   INVITE_URL_TEMPLATE=http://localhost:3000/convites/{token}
   ```

3. `docker compose up -d` sobe `db`, `api`, `worker` e `mailpit`. A caixa do
   Mailpit fica em `http://localhost:8025`.

## Cenários

### 1. Convite chega por e-mail (US1)

1. Com um usuário que pode convidar (ver quickstart da Spec 028),
   `POST /processes/{id}/participants/invites` com `channel: "email"`.
2. Esperar `201`, `token` presente e `delivery.status = "pending"`.
3. Em até alguns segundos, a mensagem aparece no Mailpit para o e-mail do
   convite, com processo, papel, prazo e o link
   `http://localhost:3000/convites/<token>`.
4. `GET /processes/{id}/participants/invites` → `delivery.status = "sent"`.
5. `GET /invites/<token do e-mail>` responde `200`.

### 2. Reenvio (US1)

1. `POST .../invites/{invite_id}/resend` → `delivery.status = "pending"`.
2. Nova mensagem no Mailpit com outro link. `GET /invites/<token antigo>` → `404`.

### 3. Serviço de e-mail fora do ar (US2)

1. `docker compose stop mailpit`.
2. Criar convite com `channel: "email"` → `201`, token devolvido.
3. A listagem mostra `delivery.status = "pending"` e `attempts` subindo.
4. `docker compose start mailpit` antes de 5 tentativas → `sent`.
5. Repetir sem religar → depois da 5ª tentativa, `failed` com
   `error_code = "max_attempts"`.

### 4. Revogação com envio pendente (US2)

1. Parar o `worker` (`docker compose stop worker`).
2. Criar convite `email`, revogar em seguida → `delivery.status = "cancelled"`.
3. Religar o `worker` → nada chega no Mailpit.

### 5. Canal não configurado (FR-019)

1. Remover `NOTIFICATION_EMAIL_BACKEND` do `.env` e reiniciar a `api`.
2. Convite com `channel: "email"` → `409 channel_unavailable`.
3. Convite com `channel: "link"` → `201`, `delivery: null`.

### 6. Nada legível no banco (FR-009, FR-010)

1. Depois do cenário 1:
   `SELECT status, payload_encrypted FROM notifications;` → `sent`, `NULL`.
2. Procurar o token nos logs da `api` e do `worker` → nenhuma ocorrência.

## Testes automatizados

`poetry run pytest tests -k notification` e os testes de convite da Spec 028
(`-k invite`), que precisam continuar passando sem alteração.
