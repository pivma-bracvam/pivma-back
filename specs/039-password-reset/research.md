# Research: Recuperação de Senha por Token Temporário

Cada item registra a decisão, o motivo e as alternativas descartadas. A base é o código no commit `c25f31a`.

## R1. Geração e hash do token

- **Decision**: gerar o token com `secrets.token_urlsafe(32)` e persistir `hashlib.sha256(token).hexdigest()` (64 caracteres), no mesmo formato do convite (Spec 028).
- **Rationale**: 256 bits de entropia tornam o token imprevisível. Com essa entropia, SHA-256 sem sal basta: não há dicionário a atacar, e o hash determinístico permite buscar o token por igualdade com índice único. Argon2 seria lento sem ganho de segurança.
- **Alternatives considered**:
  - Importar `generate_invite_token`/`hash_invite_token` de `invite_service`: acoplaria a autenticação ao módulo de convites, que importa o motor de processos. São duas linhas; repetir é mais simples que criar um módulo compartilhado.
  - Extrair um utilitário comum e refatorar o convite: mudança fora do escopo (Constituição, Princípio V). Fica registrado como possível limpeza futura.
  - JWT assinado como token: não permite uso único nem invalidação sem estado no banco.

## R2. Onde fica a lógica

- **Decision**: novo módulo `src/pivma/core/password_reset_service.py` com duas funções, `request_password_reset` e `reset_password`, que não fazem commit. As rotas ficam em `routers/auth.py`, finas, e fazem o commit.
- **Rationale**: segue o padrão de `core/*_service.py` (convite, participantes). Mantém `auth.py` legível e permite testar a regra sem HTTP. Não é camada nova: são funções, sem classe nem repositório.
- **Alternatives considered**: tudo dentro de `auth.py`, como em `PATCH /auth/me`. Rejeitado porque a regra tem mais passos (bloqueio, invalidação, envio) e ficaria misturada com detalhes HTTP.

## R3. Estado do token e invalidação por novo pedido

- **Decision**: o token é válido quando `used_at IS NULL`, `deleted_at IS NULL` e `expires_at > agora`, e a conta dona tem `deleted_at IS NULL`. Um novo pedido marca os tokens pendentes da conta com `deleted_at` (exclusão lógica do `AuditMixin`). O uso grava `used_at`.
- **Rationale**: o `AuditMixin` já tem `deleted_at`/`deleted_by`, e o projeto usa exclusão lógica para "deixou de valer". Assim não entra coluna nova além das pedidas pela issue, e `used_at` continua significando só "foi usado".
- **Alternatives considered**:
  - Preencher `used_at` ao substituir: mistura dois fatos diferentes e dificulta a auditoria.
  - Apagar fisicamente os tokens anteriores: perde rastro e foge do padrão do projeto.
  - Coluna `status`: redundante com os campos de instante.

## R4. Concorrência (FR-005 e FR-014)

- **Decision**:
  - Pedido: buscar a conta com `SELECT ... FOR UPDATE`. Dois pedidos simultâneos da mesma conta ficam em fila, e o segundo invalida o token do primeiro.
  - Redefinição: buscar o token pelo hash, já com as condições de validade, usando `SELECT ... FOR UPDATE`. A segunda requisição espera a primeira; quando ela confirma, o PostgreSQL reavalia o `WHERE` na versão nova da linha, o token já não está válido e a resposta é 400.
- **Rationale**: o bloqueio de linha resolve as duas corridas sem tabela, fila ou retentativa. O padrão `with_for_update()` já é usado em `cancel_pending_notifications`.
- **Alternatives considered**: `UPDATE ... WHERE used_at IS NULL RETURNING` resolveria a redefinição, mas exigiria um segundo caminho para buscar a conta. Restrição única parcial "um token pendente por conta" não serve, porque a expiração depende do relógio e não pode entrar no índice.

## R5. Relógio

- **Decision**: usar `datetime.utcnow()` ingênuo, calculado na aplicação, tanto para `expires_at` quanto para a comparação, como em `invite_service.compute_expires_at` e `is_expired`. Validade fixa de 30 minutos numa constante do módulo.
- **Rationale**: as colunas de data do projeto são `timestamp without time zone` em UTC. Calcular na aplicação também deixa os testes controlarem o tempo sem depender do relógio do banco.
- **Alternatives considered**: `func.now()` no banco. Rejeitado porque misturaria as duas fontes de relógio usadas no mesmo fluxo.

## R6. Envio do e-mail

- **Decision**:
  - Novo `kind` `password_reset_email` em `notifications/renderers.py`, com payload `{reset_url, expires_at}`. O texto em português traz o link, o prazo e o aviso para ignorar a mensagem se a pessoa não pediu.
  - O envio é registrado com `enqueue_notification`, `actor_id=None` (o pedido é anônimo), `subject=('password_reset', user.id)` e `expires_at` igual ao do token.
  - Antes de emitir um novo token, `cancel_pending_notifications(subject=('password_reset', user.id), reason='cancelled_resent')` cancela os envios ainda pendentes da conta.
- **Rationale**:
  - Reaproveita a base da Spec 036 sem alterá-la.
  - Com o `expires_at` do envio, o worker não entrega link vencido.
  - O assunto por conta permite cancelar os e-mails antigos com uma chamada. Sem isso, a pessoa receberia um link já invalidado.
  - O conteúdo fica cifrado e é apagado ao terminar o envio. Os eventos de auditoria só existem com processo, então não há trilha com e-mail ou link.
- **Alternatives considered**: assunto por token (`subject_id = token.id`). Exigiria um cancelamento por token anterior.

## R7. Configuração

- **Decision**: nova variável `PASSWORD_RESET_URL_TEMPLATE` (opcional, com `{token}` exatamente uma vez). O validador existente de `INVITE_URL_TEMPLATE` passa a cobrir os dois campos. Sem a variável ou sem canal de e-mail (`email_channel_available`), o pedido responde a mensagem neutra, não consulta conta nem emite token, e registra `get_operational_logger().warning('password_reset_unavailable')`, o mesmo logger do worker, sem e-mail nem token.
- **Rationale**: é o mesmo padrão do convite (FR-007 e FR-008). Checar a configuração antes da consulta evita trabalho inútil e não muda a resposta.
- **Alternatives considered**: reaproveitar a origem de `AUTH_ALLOWED_ORIGINS` e montar o caminho no código. Rejeitado porque acoplaria o backend às rotas do frontend.

## R8. Contrato HTTP

- **Decision**:
  - `POST /auth/forgot-password`: corpo `{email}`, `extra='forbid'`, e-mail validado e aparado como em `UserCreate`. Responde 200 com `{"message": "Se o e-mail estiver cadastrado, as instruções foram enviadas."}`.
  - `POST /auth/reset-password`: corpo `{token, new_password}`, `extra='forbid'`. `token` aceita de 1 a 128 caracteres (limite só para conter a entrada; o token gerado tem 43). `new_password` segue a política de 8 a 128 caracteres sem espaço, com o mesmo validador dos outros schemas. Responde 204.
  - Token recusado: `400 invalid_reset_token`, "Link de redefinição inválido ou expirado.", sempre com o mesmo código e a mesma mensagem.
  - Nenhuma das duas rotas usa `CurrentUser` ou `TrustedOrigin`.
- **Rationale**:
  - Não há sessão envolvida, então não há CSRF a mitigar. Um atacante que não tem o token não consegue forjar a redefinição, como já acontece no login, que também não exige origem.
  - `field_errors` (Spec 034) já mascara campos terminados em `password` e nunca ecoa o valor enviado, então o 422 não expõe a senha nem o token.
- **Alternatives considered**: devolver 404 para token desconhecido. Rejeitado porque a issue pede 400 e respostas iguais para todos os motivos.

## R9. Ausência do token nos logs

- **Decision**: o token só passa pela memória da requisição e pelo payload cifrado. Nenhum `logger` recebe o link, o token ou o e-mail. Um teste cobre o fluxo completo e confere que o token bruto não aparece em nenhum registro. Ele usa `caplog` para os loggers que propagam e um handler ligado direto em `pivma.operational`, que não propaga depois de `setup_logging()`.
- **Rationale**: atende FR-004 e a clarificação de 2026-10-02. O token viaja no corpo, não na URL, então não entra em log de acesso de proxy nem em `request.url`.
- **Note**: em desenvolvimento, o link é lido no Mailpit do compose (`http://localhost:8025`). Nos testes, `NOTIFICATION_EMAIL_BACKEND=fake` guarda a mensagem em memória. Os dois caminhos já existem desde a Spec 036. A clarificação fala em "backend de e-mail falso", e o Mailpit cumpre o mesmo papel em desenvolvimento.

## R10. Hash da senha e auditoria

- **Decision**: `hash_password` roda em `run_in_threadpool`, como em `PATCH /auth/me`. Na redefinição aceita, `user.set_update_audit(user.id)` e `token.set_update_audit(user.id)` registram a própria pessoa (FR-015). Na emissão, `created_by` do token fica nulo, porque o pedido é anônimo: quem digitou o e-mail não é necessariamente a dona da conta.
- **Rationale**: não atribui a uma pessoa um pedido que ela talvez não tenha feito. A redefinição prova a posse do link, então atribuí-la à conta é correto.
- **Alternatives considered**: `created_by = user.id` na emissão. Rejeitado pelo motivo acima.

## R11. Fora do escopo, sem débito escondido

- **Decision**: rate limit, revogação de sessões e limpeza de tokens antigos ficam fora, como a spec registra. A diferença de tempo de resposta entre conta existente e inexistente é pequena, porque não há hash Argon2 no pedido e o envio ocorre fora da requisição. Também fica fora, como a spec registra.
- **Rationale**: são lacunas conhecidas e documentadas na spec, não omissões. O README da feature as listará como limites conhecidos.
