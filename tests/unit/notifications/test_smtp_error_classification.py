"""Spec 036 — erro permanente x temporário do SMTP (research R5)."""

import smtplib
import socket

import pytest

from pivma.notifications.channels import (
    PermanentDeliveryError,
    TemporaryDeliveryError,
    classify_smtp_error,
)


@pytest.mark.parametrize(
    'exc',
    [
        smtplib.SMTPResponseException(550, b'mailbox unavailable'),
        smtplib.SMTPDataError(554, b'transaction failed'),
        smtplib.SMTPRecipientsRefused({
            'x@exemplo.org': (550, b'no such user')
        }),
        smtplib.SMTPSenderRefused(553, b'sender refused', 'n@pivma.test'),
    ],
    ids=['response-5xx', 'data-5xx', 'recipient-refused', 'sender-refused'],
)
def test_permanent_smtp_errors(exc):
    error = classify_smtp_error(exc)

    assert isinstance(error, PermanentDeliveryError)
    assert error.code == 'smtp_permanent'


@pytest.mark.parametrize(
    'exc',
    [
        smtplib.SMTPResponseException(421, b'try again later'),
        smtplib.SMTPDataError(451, b'local error'),
        smtplib.SMTPAuthenticationError(535, b'bad credentials'),
    ],
    ids=['response-4xx', 'data-4xx', 'authentication'],
)
def test_temporary_smtp_response_errors(exc):
    error = classify_smtp_error(exc)

    assert isinstance(error, TemporaryDeliveryError)
    assert error.code == 'smtp_temporary'


@pytest.mark.parametrize(
    'exc',
    [
        ConnectionRefusedError('refused'),
        socket.timeout('timed out'),
        TimeoutError('timed out'),
        smtplib.SMTPServerDisconnected('gone'),
    ],
    ids=['refused', 'socket-timeout', 'timeout', 'disconnected'],
)
def test_connection_errors_are_temporary(exc):
    error = classify_smtp_error(exc)

    assert isinstance(error, TemporaryDeliveryError)
    assert error.code == 'connection'
