import pytest
from pydantic import ValidationError

from pivma.schemas import UserPublic, UserSchema


def make_user(**overrides):
    values = {
        'username': 'valid.user',
        'email': 'Valid.User@Example.COM',
        'password': 'Valid-Passphrase-2026',
    }
    return UserSchema(**(values | overrides))


@pytest.mark.parametrize(
    'username',
    ['ab', 'a' * 65, 'invalid user', 'inválido', 'user/invalid'],
)
def test_user_schema_rejects_invalid_username(username):
    with pytest.raises(ValidationError):
        make_user(username=username)


@pytest.mark.parametrize('username', ['abc', 'a' * 64, 'A._-09'])
def test_user_schema_accepts_username_limits(username):
    assert make_user(username=username).username == username


def test_user_schema_trims_identifiers_and_preserves_case():
    user = make_user(
        username='  User.Name  ', email='  User.Name@Example.COM  '
    )

    assert user.username == 'User.Name'
    assert user.email == 'User.Name@Example.COM'


@pytest.mark.parametrize(
    'password',
    ['a' * 7, 'a' * 129, 'valid password', 'valid\tpassword', 'valid\npass'],
)
def test_user_schema_rejects_invalid_password(password):
    with pytest.raises(ValidationError):
        make_user(password=password)


@pytest.mark.parametrize('password', ['á' * 8, '🧪' * 128])
def test_user_schema_accepts_unicode_password_limits(password):
    assert make_user(password=password).password == password


def test_user_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        make_user(role='admin')


def test_user_email_fields_keep_openapi_format():
    assert UserSchema.model_json_schema()['properties']['email']['format'] == (
        'email'
    )
    assert UserPublic.model_json_schema()['properties']['email']['format'] == (
        'email'
    )
