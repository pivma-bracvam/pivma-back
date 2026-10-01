"""Spec 036 — conteúdo do envio cifrado no banco (FR-009, research R3)."""

import pytest
from cryptography.fernet import Fernet

from pivma.notifications.crypto import (
    PayloadDecryptError,
    decrypt_payload,
    encrypt_payload,
)

PAYLOAD = {
    'invite_url': 'https://front.test/convites/segredo-do-token',
    'process_code': 'PRC-0001',
}


def test_encrypt_then_decrypt_returns_same_payload():
    key = Fernet.generate_key().decode()

    assert decrypt_payload(encrypt_payload(PAYLOAD, key), key) == PAYLOAD


def test_encrypted_payload_does_not_contain_original_values():
    key = Fernet.generate_key().decode()

    encrypted = encrypt_payload(PAYLOAD, key)

    assert 'segredo-do-token' not in encrypted
    assert 'PRC-0001' not in encrypted


def test_decrypt_with_other_key_raises_decrypt_error():
    encrypted = encrypt_payload(PAYLOAD, Fernet.generate_key().decode())

    with pytest.raises(PayloadDecryptError):
        decrypt_payload(encrypted, Fernet.generate_key().decode())
