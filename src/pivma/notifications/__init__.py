"""Base de notificações (Spec 036).

O código de negócio pede um envio com `enqueue_notification`, na mesma
transação da operação; `pivma.notifications.worker` envia fora da
requisição, pelo canal escolhido na configuração.
"""

from pivma.notifications.service import (
    ChannelUnavailableError,
    cancel_pending_notifications,
    enqueue_notification,
    latest_by_subject,
)

__all__ = [
    'ChannelUnavailableError',
    'cancel_pending_notifications',
    'enqueue_notification',
    'latest_by_subject',
]
