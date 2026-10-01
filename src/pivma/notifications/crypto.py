"""Cifragem do conteúdo dos envios (Spec 036, FR-009, research R3).

O conteúdo de um envio pode ter dado sensível — no convite, o link com o
token bruto, que a Spec 028 nunca grava. Ele fica cifrado com Fernet
(cifragem autenticada) enquanto o envio não termina.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class PayloadDecryptError(Exception):
    """O conteúdo não decifra com a chave atual (chave trocada ou dado
    corrompido)."""


def encrypt_payload(payload: dict[str, Any], key: str) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return Fernet(key.encode()).encrypt(data).decode('ascii')


def decrypt_payload(encrypted: str, key: str) -> dict[str, Any]:
    try:
        data = Fernet(key.encode()).decrypt(encrypted.encode('ascii'))
    except InvalidToken as exc:
        raise PayloadDecryptError from exc
    return json.loads(data)
