"""Regras puras das amostras cegas (Spec 031): CAS, código e QR."""

import itertools
from collections import Counter
from uuid import uuid4

import pytest

from pivma.core import sample_service
from pivma.core.process_engine import ValidationError
from pivma.core.sample_service import (
    CODE_ALPHABET,
    CODE_LENGTH,
    generate_code,
    unique_code,
    validate_cas,
    vial_qr_url,
)
from pivma.core.settings import Settings

AMBIGUOUS = set('0O1IL')


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('50-00-0', '50-00-0'),
        ('7732-18-5', '7732-18-5'),
        ('64-17-5', '64-17-5'),
        (' 1310-73-2 ', '1310-73-2'),
    ],
)
def test_validate_cas_accepts_valid_numbers(raw, expected):
    assert validate_cas(raw) == expected


@pytest.mark.parametrize('raw', ['50-00-1', '7732-18-4'])
def test_validate_cas_rejects_wrong_check_digit(raw):
    with pytest.raises(ValidationError) as exc_info:
        validate_cas(raw)
    assert exc_info.value.code == 'invalid_cas'


@pytest.mark.parametrize(
    'raw',
    ['', '5-00-0', '12345678-00-0', '50-0-0', '50000', 'ab-cd-e'],
)
def test_validate_cas_rejects_bad_format(raw):
    with pytest.raises(ValidationError) as exc_info:
        validate_cas(raw)
    assert exc_info.value.code == 'invalid_cas'


def test_generate_code_has_eight_chars_from_safe_alphabet():
    codes = [generate_code() for _ in range(1000)]

    assert all(len(code) == CODE_LENGTH for code in codes)
    assert set(''.join(codes)) <= set(CODE_ALPHABET)


def test_generate_code_never_uses_ambiguous_characters():
    codes = ''.join(generate_code() for _ in range(1000))

    assert not set(codes) & AMBIGUOUS


def _choices_spelling(monkeypatch, *codes):
    letters = itertools.chain.from_iterable(codes)
    monkeypatch.setattr(
        sample_service.secrets, 'choice', lambda _alphabet: next(letters)
    )


def test_unique_code_retries_on_collision(monkeypatch):
    _choices_spelling(monkeypatch, 'AAAAAAAA', 'BBBBBBBB')

    assert unique_code({'AAAAAAAA'}) == 'BBBBBBBB'


def test_unique_code_gives_up_after_ten_collisions(monkeypatch):
    _choices_spelling(monkeypatch, *['AAAAAAAA'] * 11)

    with pytest.raises(RuntimeError):
        unique_code({'AAAAAAAA'})


def _settings(**overrides):
    return Settings(
        DATABASE_URL='postgresql+psycopg://x:y@localhost/z',
        JWT_SECRET_KEY='k' * 32,
        AUTH_ALLOWED_ORIGINS=['https://origem.exemplo', 'https://outra'],
        **overrides,
    )


def test_qr_url_uses_configured_base_url():
    process_id = uuid4()

    url = vial_qr_url(
        _settings(SAMPLE_QR_BASE_URL='https://front.exemplo'),
        process_id,
        'K7Q2M9XD',
    )

    assert (
        url == f'https://front.exemplo/amostras/{process_id}/frascos/K7Q2M9XD'
    )


@pytest.mark.parametrize('base', [None, 'https://origem.exemplo/'])
def test_qr_url_falls_back_to_first_allowed_origin(base):
    process_id = uuid4()

    url = vial_qr_url(
        _settings(SAMPLE_QR_BASE_URL=base), process_id, 'K7Q2M9XD'
    )

    assert url == (
        f'https://origem.exemplo/amostras/{process_id}/frascos/K7Q2M9XD'
    )


def test_thousand_codes_are_unique_and_unpatterned():
    taken: set[str] = set()
    for _ in range(1000):
        taken.add(unique_code(taken))

    assert len(taken) == 1000  # noqa: PLR2004
    for piece in (lambda c: c[:3], lambda c: c[-3:]):
        most_common = Counter(piece(code) for code in taken).most_common(1)
        assert most_common[0][1] <= 10  # noqa: PLR2004 (1% de 1.000)
