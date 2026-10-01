"""Canais de envio (Spec 036, research R4, R5, R8).

O processo de envio só conhece `EmailChannel`. Qual implementação vale é
decidido pela configuração (`NOTIFICATION_EMAIL_BACKEND`), no mesmo padrão
do provedor de IA (Spec 013): `smtp` para qualquer provedor que aceite SMTP
e `fake` para testes, sem rede.
"""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Protocol

from pivma.core.settings import Settings

PERMANENT_SMTP_STATUS = 500


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class DeliveryError(Exception):
    """Falha de envio com o código gravado em `Notification.error_code`."""

    def __init__(self, code: str, detail: str = '') -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class PermanentDeliveryError(DeliveryError):
    """Não adianta tentar de novo (ex.: destinatário inexistente)."""


class TemporaryDeliveryError(DeliveryError):
    """Pode dar certo numa nova tentativa (ex.: servidor fora do ar)."""


class EmailChannel(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


def classify_smtp_error(exc: Exception) -> DeliveryError:
    """Erro permanente x temporário (research R5).

    Falha de autenticação é temporária: costuma ser credencial em rotação,
    não um problema do destinatário.
    """
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return TemporaryDeliveryError('smtp_temporary', _detail(exc))
    if isinstance(
        exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused)
    ):
        return PermanentDeliveryError('smtp_permanent', _detail(exc))
    if isinstance(exc, smtplib.SMTPResponseException):
        if exc.smtp_code >= PERMANENT_SMTP_STATUS:
            return PermanentDeliveryError('smtp_permanent', _detail(exc))
        return TemporaryDeliveryError('smtp_temporary', _detail(exc))
    return TemporaryDeliveryError('connection', _detail(exc))


def _detail(exc: Exception) -> str:
    return f'{type(exc).__name__}: {exc}'


class SmtpEmailChannel:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: OutgoingEmail) -> None:
        try:
            await asyncio.to_thread(self._send_sync, message)
        except DeliveryError:
            raise
        except Exception as exc:
            raise classify_smtp_error(exc) from exc

    def _build(self, message: OutgoingEmail) -> EmailMessage:
        s = self._settings
        email = EmailMessage()
        email['From'] = formataddr((
            s.NOTIFICATION_FROM_NAME,
            s.NOTIFICATION_FROM_ADDRESS,
        ))
        email['To'] = message.to
        email['Subject'] = message.subject
        email['Date'] = formatdate(localtime=False)
        email['Message-ID'] = make_msgid()
        email.set_content(message.text)
        email.add_alternative(message.html, subtype='html')
        return email

    def _send_sync(self, message: OutgoingEmail) -> None:
        s = self._settings
        timeout = s.SMTP_TIMEOUT_SECONDS
        if s.SMTP_SECURITY == 'ssl':
            smtp = smtplib.SMTP_SSL(
                s.SMTP_HOST,
                s.SMTP_PORT,
                timeout=timeout,
                context=ssl.create_default_context(),
            )
        else:
            smtp = smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=timeout)
        with smtp:
            if s.SMTP_SECURITY == 'starttls':
                smtp.starttls(context=ssl.create_default_context())
            if s.SMTP_USERNAME:
                smtp.login(s.SMTP_USERNAME, s.SMTP_PASSWORD or '')
            smtp.send_message(self._build(message))


@dataclass
class FakeEmailChannel:
    """Sem rede: guarda as mensagens em `sent`.

    `failures` é uma fila de exceções levantadas, uma por envio, antes de
    qualquer sucesso; `delay` segura o envio para testes de concorrência.
    """

    sent: list[OutgoingEmail] = field(default_factory=list)
    failures: list[Exception] = field(default_factory=list)
    delay: float = 0.0

    async def send(self, message: OutgoingEmail) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(message)


def email_channel_available(settings: Settings) -> bool:
    """Canal de e-mail configurado o bastante para aceitar pedidos (R8)."""
    backend = settings.NOTIFICATION_EMAIL_BACKEND
    if backend is None:
        return False
    if not (
        settings.NOTIFICATION_FROM_ADDRESS
        and settings.NOTIFICATION_ENCRYPTION_KEY
    ):
        return False
    return backend != 'smtp' or bool(settings.SMTP_HOST)


def get_email_channel(settings: Settings) -> EmailChannel | None:
    if not email_channel_available(settings):
        return None
    if settings.NOTIFICATION_EMAIL_BACKEND == 'smtp':
        return SmtpEmailChannel(settings)
    return FakeEmailChannel()
