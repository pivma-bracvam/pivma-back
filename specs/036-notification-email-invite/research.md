# Phase 0 Research: Base de notificações e envio do convite por e-mail

**Feature**: [spec.md](./spec.md) · **Plano**: [plan.md](./plan.md)

## R1 — Fila: tabela própria no Postgres, sem biblioteca de fila

**Decision**: uma tabela `notifications` faz os dois papéis: registro do pedido
(outbox) e fila de trabalho. O código de negócio insere a linha na mesma
sessão da operação (FR-002). Um processo separado busca linhas pendentes com
`SELECT ... FOR UPDATE SKIP LOCKED`, envia e atualiza a linha na mesma
transação (FR-003, FR-006).

**Rationale**: a spec exige situação consultável por envio (FR-005), o que já
pede uma tabela nossa. Com ela, a fila sai quase de graça. Não acrescenta
serviço (Redis) nem dependência. O volume esperado (convites, avisos) é baixo.

**Alternatives considered**:
- `procrastinate` (fila em Postgres com tarefas periódicas): bom para os
  relatórios e o aviso de atraso, mas criaria tabelas próprias e ainda
  precisaríamos da nossa para a situação do envio. Fica para quando houver
  tarefas periódicas de verdade.
- Redis com Celery/arq/Dramatiq: um serviço a mais na implantação sem ganho
  para este volume.
- `BackgroundTasks` do FastAPI: roda no processo da API, sem nova tentativa e
  sem garantia após reinício. Viola FR-003.

## R2 — Concorrência e duplicidade

**Decision**: o processo de envio trava uma linha por vez com `FOR UPDATE SKIP
LOCKED`, envia e grava o resultado antes de liberar o lock. Dois processos
nunca pegam a mesma linha (SC-004).

**Rationale**: é o mecanismo mais simples que o Postgres oferece para fila com
vários consumidores.

**Limite conhecido**: se o processo morrer depois que o servidor SMTP aceitou a
mensagem e antes do commit, a linha volta a pendente e a mensagem pode sair de
novo. Nenhum protocolo de e-mail permite entrega exatamente uma vez. A janela
é de milissegundos e só existe em queda do processo, não em concorrência. A
spec (FR-006) cobre concorrência e reprocessamento após falha registrada;
esse caso fica documentado.

## R3 — Proteção do link do convite

**Decision**: o conteúdo de cada envio é guardado cifrado com Fernet
(biblioteca `cryptography`), com chave em `NOTIFICATION_ENCRYPTION_KEY`. Ao
chegar a um estado final (enviado, falho, cancelado), o campo cifrado é apagado
(FR-009). O conteúdo nunca é registrado em log nem em auditoria (FR-010).

**Rationale**: a Spec 028 nunca guarda o token bruto. Como o envio é
assíncrono, o link precisa existir em algum lugar até sair. Cifrado e apagado
ao fim, quem lê o banco não consegue montar o link. Fernet é cifragem
autenticada pronta, sem escolha de modo ou de IV.

**Nova dependência**: `cryptography`. É a biblioteca de referência em Python e
o projeto ainda não a tem.

**Alternatives considered**:
- Token derivado por HMAC de um segredo e do id do convite, sem guardar nada:
  muda a geração de tokens da Spec 028 (R1 dela) para todos os convites e
  amarra todos os tokens a um único segredo. Mais invasivo.
- Enviar dentro da requisição: viola FR-003 e FR-016 (falha do provedor
  afetaria a resposta).
- Guardar só o id do convite e girar o token no momento do envio: o token da
  resposta (FR-016) deixaria de valer.

## R4 — Canal de e-mail: SMTP da biblioteca padrão

**Decision**: `smtplib` + `email.message.EmailMessage` da biblioteca padrão,
chamados com `asyncio.to_thread` no processo de envio. Segurança configurável:
`starttls` (padrão, porta 587), `ssl` (465) ou `none` (Mailpit em
desenvolvimento).

**Rationale**: SMTP é aceito por SES, Brevo, Postmark, Mailgun, Resend e
outros; trocar de provedor é trocar variáveis (FR-008, SC-006). A biblioteca
padrão evita dependência. O processo de envio trata uma mensagem por vez, então
a chamada bloqueante em thread não pesa.

**Alternatives considered**: `aiosmtplib` (dependência a mais sem ganho
real aqui); APIs HTTP específicas de cada provedor (prendem ao provedor).

## R5 — Classificação de erro e novas tentativas

**Decision**:
- Erro **permanente** (resposta SMTP 5xx, destinatário recusado, remetente
  recusado): falho na hora, sem nova tentativa.
- Erro **temporário** (resposta 4xx, falha de conexão, timeout, falha de
  autenticação): nova tentativa em `min(BASE * 2^(tentativas-1), MAX)`
  segundos. Padrões: base 30 s, máximo 900 s, 5 tentativas.
- Se o envio tem prazo (`expires_at`, preenchido com o prazo do convite) e o
  prazo passou, ele vira falho com motivo `expired` sem tentar (edge case da
  spec).

**Rationale**: com o convite de 1 hora, 5 tentativas (30 s, 60 s, 120 s, 240 s)
cabem em cerca de 8 minutos, bem dentro do prazo. Falha de autenticação SMTP é
tratada como temporária porque costuma ser credencial em rotação, não
destinatário inválido.

## R6 — Cancelamento ligado ao objeto de negócio

**Decision**: cada envio guarda `subject_type` e `subject_id` (aqui,
`role_assignment_invite` e o id do convite). O reenvio, a revogação e o aceite
do convite chamam `cancel_pending_notifications(subject)`, que marca os envios
pendentes como cancelados e apaga o conteúdo (FR-013, FR-014, FR-015). O
processo de envio não precisa conhecer regras do convite: só confere o prazo.

**Rationale**: mantém a base genérica. Quem conhece a regra de negócio é quem
cancela.

## R7 — Processo de envio

**Decision**: módulo `pivma.notifications.worker`, executado com
`python -m pivma.notifications.worker`. Laço: processa pendentes até esvaziar,
dorme `NOTIFICATION_POLL_SECONDS` (padrão 5 s) e repete. Novo serviço `worker`
no `compose.yaml` com a mesma imagem da API. A função que processa um envio
(`process_next`) é chamada diretamente nos testes, sem laço nem `sleep`.

**Rationale**: polling de 5 s atende SC-001 (até 1 minuto) com carga
desprezível. `LISTEN/NOTIFY` reduziria a latência, mas é complexidade sem
necessidade agora.

## R8 — Escolha do canal por configuração

**Decision**: `NOTIFICATION_EMAIL_BACKEND` aceita `smtp`, `fake` ou vazio.
Vazio significa canal não configurado: criar convite com canal `email` é
recusado com `409 channel_unavailable` (FR-019). O mesmo vale se faltar
`NOTIFICATION_FROM_ADDRESS`, `NOTIFICATION_ENCRYPTION_KEY` ou
`INVITE_URL_TEMPLATE`. `fake` guarda as mensagens numa lista em memória do
próprio processo (testes). Segue o padrão de `AI_PROVIDER` (Spec 013).

**Rationale**: a recusa explícita evita convites "por e-mail" que nunca vão
sair numa implantação sem SMTP.

## R9 — Link do convite

**Decision**: `INVITE_URL_TEMPLATE` é o endereço completo com o marcador
`{token}` (por exemplo, `https://app.exemplo/convites/{token}`). A
configuração é validada na carga: precisa conter `{token}` uma vez. O token
entra codificado para URL (já é `token_urlsafe`).

**Rationale**: decisão do usuário na sessão de 2026-10-01; o frontend ainda
não tem a página de convite.

## R10 — Situação do envio no convite

**Decision**: `InvitePublic` ganha o campo `delivery`, nulo para convites com
canal `link`. Para canal `email`, traz a situação do envio mais recente do
convite: `status`, `attempts`, `last_attempt_at`, `sent_at`, `error_code`. A
listagem carrega os envios de todos os convites da página numa consulta só.

**Rationale**: FR-017. Campo novo em resposta é mudança compatível.

## R11 — Auditoria

**Decision**: eventos `NOTIFICATION_SENT`, `NOTIFICATION_FAILED` (gravados
pelo processo de envio, `user_id` nulo) e `NOTIFICATION_CANCELLED` (gravado por
quem cancela). Contexto: `notification_id`, `kind`, `channel`, `subject_type`,
`subject_id`, `attempts`, `error_code`. Sem destinatário nem conteúdo. Só é
gravado quando o envio tem `process_instance_id`, porque `AuditEvent` exige
processo.

**Rationale**: FR-021. O e-mail do convite já está no evento
`INVITE_CREATED`; não precisa repetir.

## R12 — Modelo da mensagem

**Decision**: um renderizador por tipo de aviso (`kind`), em código Python,
que recebe o conteúdo decifrado e devolve assunto, texto simples e HTML. O
HTML escapa os valores com `html.escape`. Sem motor de templates.

**Rationale**: um único tipo de aviso nesta entrega. Jinja2 fica para quando
houver vários modelos ou edição por não desenvolvedores.

## R13 — Testes

**Decision**:
- Unidade: cálculo do intervalo de nova tentativa, classificação de erro SMTP,
  validação de `INVITE_URL_TEMPLATE`, cifragem de ida e volta, renderizador.
- Integração com banco (Postgres do `testcontainers`): registro na mesma
  transação, `process_next` com canal falso, concorrência com duas sessões,
  prazo vencido, cancelamento por reenvio, revogação e aceite, conteúdo apagado
  no fim, auditoria.
- API: criação com canal `email`, recusa sem canal configurado, `delivery` na
  listagem, canal `link` inalterado.
- Um teste do adaptador SMTP contra um contêiner Mailpit, conferindo a
  mensagem pela API HTTP do Mailpit.

Cobertura e granularidade seguem `fastapi-testing-methodology` no
`/speckit-tasks`.
