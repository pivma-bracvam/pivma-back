# Contrato interno: módulo de notificações

**Feature**: [../spec.md](../spec.md) · **Research**: [../research.md](../research.md)

Interface que outras entregas (aviso de atraso, recuperação de senha,
comprovante de assinatura, relatório pronto) vão usar. Assinaturas
indicativas; os nomes finais saem da implementação.

## Pedir um envio

```python
async def enqueue_notification(
    session: AsyncSession,
    *,
    kind: str,                      # tipo de aviso com renderizador registrado
    channel: Literal['email'],
    recipient: str,
    payload: dict[str, Any],        # cifrado antes de gravar
    actor_id: UUID | None,
    subject: tuple[str, UUID] | None = None,
    process_instance_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> Notification
```

- Só adiciona à sessão; **não comita**. O envio existe se, e somente se, a
  transação de quem chamou for confirmada (FR-002).
- Levanta `ChannelUnavailableError` se o canal não está configurado.

## Cancelar envios pendentes de um objeto

```python
async def cancel_pending_notifications(
    session: AsyncSession,
    *,
    subject: tuple[str, UUID],
    reason: str,                    # vira error_code, ex. 'cancelled_resent'
    actor_id: UUID | None,
) -> int                            # quantos foram cancelados
```

## Canal

```python
@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class EmailChannel(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...
```

- Falha permanente: `PermanentDeliveryError`. Falha temporária:
  `TemporaryDeliveryError`. Outras exceções são tratadas como temporárias.
- Implementações: `SmtpEmailChannel`, `FakeEmailChannel` (guarda em `sent`,
  pode ser programado para falhar).

## Renderizador

```python
Renderer = Callable[
    [dict[str, Any]], tuple[str, str, str]
]  # assunto, texto, html
```

Registrado por `kind`. Um `kind` sem renderizador é erro de programação e
falha no `enqueue_notification`.

## Processo de envio

```python
async def process_next(session_factory, channel, settings, *, now=None) -> bool
```

Processa no máximo um envio devido e devolve se havia algum. O laço do
`python -m pivma.notifications.worker` chama até devolver `False` e dorme
`NOTIFICATION_POLL_SECONDS`.
