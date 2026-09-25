from pivma.core.invite_service import (
    generate_invite_token,
    hash_invite_token,
    mask_email,
)

SAMPLE_SIZE = 20
MIN_TOKEN_LENGTH = 32


def test_hash_invite_token_is_deterministic():
    """U-T01: mesma entrada produz sempre o mesmo hash."""
    token = 'a-fixed-token-value'
    assert hash_invite_token(token) == hash_invite_token(token)


def test_hash_invite_token_differs_for_different_tokens():
    assert hash_invite_token('token-a') != hash_invite_token('token-b')


def test_generate_invite_token_produces_distinct_values():
    """U-T01: cada chamada produz um valor diferente."""
    tokens = {generate_invite_token() for _ in range(SAMPLE_SIZE)}
    assert len(tokens) == SAMPLE_SIZE


def test_generate_invite_token_has_high_entropy_length():
    token = generate_invite_token()
    assert len(token) >= MIN_TOKEN_LENGTH


def test_mask_email_keeps_first_character_and_domain():
    assert mask_email('joana@exemplo.org') == 'j****@exemplo.org'


def test_mask_email_handles_single_character_local_part():
    assert mask_email('j@exemplo.org') == '*@exemplo.org'
