"""Spec 036 — envio SMTP real contra um Mailpit em contêiner (US3, FR-008)."""

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from pivma.core.settings import Settings
from pivma.notifications.channels import (
    OutgoingEmail,
    SmtpEmailChannel,
    TemporaryDeliveryError,
)

MESSAGE = OutgoingEmail(
    to='ana@exemplo.org',
    subject='Convite para o processo PRC-0001',
    text='Acesse https://front.test/convites/abc',
    html='<p>Acesse <a href="https://front.test/convites/abc">o link</a></p>',
)


@pytest.fixture(scope='module')
def mailpit():
    container = (
        DockerContainer('axllent/mailpit')
        .with_exposed_ports(1025, 8025)
        .waiting_for(LogMessageWaitStrategy('accessible via'))
    )
    with container:
        host = container.get_container_host_ip()
        yield (
            host,
            int(container.get_exposed_port(1025)),
            f'http://{host}:{container.get_exposed_port(8025)}',
        )


def _settings(host, port):
    return Settings(
        NOTIFICATION_EMAIL_BACKEND='smtp',
        SMTP_HOST=host,
        SMTP_PORT=port,
        SMTP_SECURITY='none',
        SMTP_TIMEOUT_SECONDS=5,
        NOTIFICATION_FROM_ADDRESS='nao-responda@pivma.test',
        NOTIFICATION_FROM_NAME='pi*VMA',
    )


@pytest.mark.asyncio
async def test_smtp_channel_delivers_message_to_mailpit(mailpit):
    host, smtp_port, api = mailpit

    await SmtpEmailChannel(_settings(host, smtp_port)).send(MESSAGE)

    [summary] = httpx.get(f'{api}/api/v1/messages').json()['messages']
    assert summary['From'] == {
        'Name': 'pi*VMA',
        'Address': 'nao-responda@pivma.test',
    }
    assert [to['Address'] for to in summary['To']] == ['ana@exemplo.org']
    assert summary['Subject'] == MESSAGE.subject
    detail = httpx.get(f'{api}/api/v1/message/{summary["ID"]}').json()
    assert detail['Text'].strip() == MESSAGE.text
    assert detail['HTML'].strip() == MESSAGE.html
    assert detail['MessageID']


@pytest.mark.asyncio
async def test_smtp_channel_without_server_raises_temporary_error():
    # Porta 9 (discard) sem servidor: conexão recusada.
    channel = SmtpEmailChannel(_settings('127.0.0.1', 9))

    with pytest.raises(TemporaryDeliveryError) as exc_info:
        await channel.send(MESSAGE)

    assert exc_info.value.code == 'connection'
