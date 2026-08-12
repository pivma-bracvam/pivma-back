from pivma.core.security import hash_password, verify_password


def test_hash_password_uses_argon2id_and_random_salt():
    password = 'Unique-Passphrase-2026'

    first = hash_password(password)
    second = hash_password(password)

    assert first.startswith('$argon2id$')
    assert first != second
    assert password not in first
    assert verify_password(first, password)
    assert not verify_password(first, 'incorrect-password')


def test_hash_password_preserves_128_unicode_code_points():
    password = '🧪' * 128

    password_hash = hash_password(password)

    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, password[:-1])


def test_verify_password_rejects_malformed_hash():
    assert not verify_password('not-an-argon2-hash', 'password')
