"""Spec 039 — geração e hash do token de redefinição (research R1)."""

import hashlib
import re

from pivma.core.password_reset_service import (
    generate_reset_token,
    hash_reset_token,
)


def test_generate_reset_token_returns_43_url_safe_characters():
    assert re.fullmatch(r'[A-Za-z0-9_-]{43}', generate_reset_token())


def test_generate_reset_token_returns_distinct_values():
    assert generate_reset_token() != generate_reset_token()


def test_hash_reset_token_is_sha256_hex_digest():
    assert hash_reset_token('abc') == hashlib.sha256(b'abc').hexdigest()
