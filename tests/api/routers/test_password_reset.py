"""Spec 039 — recuperação e redefinição de senha por token temporário."""

import io
import json
import logging
import re
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select

from pivma.core.database.models import (
    Notification,
    PasswordResetToken,
)
from pivma.core.password_reset_service import hash_reset_token
from pivma.core.security import create_access_token, verify_password
from pivma.core.settings import Settings
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.worker import process_next
from tests.conftest import email_settings
from tests.factories.institutional_factory import (
    InstitutionFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)

NEUTRAL_MESSAGE = (
    'Se o e-mail estiver cadastrado, as instruções foram enviadas.'
)
INVALID_TOKEN_DETAIL = {
    'code': 'invalid_reset_token',
    'message': 'Link de redefinição inválido ou expirado.',
}
RESET_URL_PREFIX = 'https://front.test/redefinir-senha/'
RESET_URL_TEMPLATE = RESET_URL_PREFIX + '{token}'
NEW_PASSWORD = 'NovaSenha-Segura-2026'
FACTORY_PASSWORD = 'Factory-Passphrase-2026'

UNAVAILABLE_SETTINGS = {
    'without_template': {'PASSWORD_RESET_URL_TEMPLATE': None},
    'without_channel': {
        'NOTIFICATION_EMAIL_BACKEND': None,
        'PASSWORD_RESET_URL_TEMPLATE': RESET_URL_TEMPLATE,
    },
}


@pytest.fixture
def reset_settings(use_settings):
    return use_settings(
        email_settings(PASSWORD_RESET_URL_TEMPLATE=RESET_URL_TEMPLATE)
    )


@pytest.fixture(params=UNAVAILABLE_SETTINGS.values(), ids=UNAVAILABLE_SETTINGS)
def unavailable_settings(request, use_settings):
    """Implantação sem canal de e-mail ou sem modelo de link (FR-008)."""
    return use_settings(email_settings(**request.param))


@pytest.fixture
def operational_log():
    """`pivma.operational` não propaga; o `caplog` não o vê."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s'))
    target = logging.getLogger('pivma.operational')
    target.addHandler(handler)
    yield stream
    target.removeHandler(handler)


def forgot(client, email):
    return client.post('/auth/forgot-password', json={'email': email})


def reset(client, token, new_password=NEW_PASSWORD):
    return client.post(
        '/auth/reset-password',
        json={'token': token, 'new_password': new_password},
    )


async def deliver_reset_token(session, settings):
    """Roda o worker e extrai o token do link, como a pessoa o recebe."""
    channel = FakeEmailChannel()
    await process_next(session, channel, settings)
    match = re.search(
        re.escape(RESET_URL_PREFIX) + r'([A-Za-z0-9_-]+)',
        channel.sent[-1].text,
    )
    return match.group(1)


async def issue_token(client, session, settings, user):
    forgot(client, user.email)
    return await deliver_reset_token(session, settings)


def login(client, user, password):
    return client.post(
        '/auth/login',
        json={'identifier': user.username, 'password': password},
    )


async def reset_tokens_of(session, user):
    """Todos os tokens da conta, inclusive os substituídos (`deleted_at`)."""
    return list(
        await session.scalars(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.expires_at)
            .execution_options(
                populate_existing=True, skip_soft_delete_filter=True
            )
        )
    )


async def reset_notifications_of(session, user):
    return list(
        await session.scalars(
            select(Notification)
            .where(
                Notification.subject_type == 'password_reset',
                Notification.subject_id == user.id,
            )
            .order_by(Notification.requested_at)
            .execution_options(populate_existing=True)
        )
    )


async def count_rows(session, model):
    return await session.scalar(select(func.count()).select_from(model))


# --- US1: pedir a recuperação de senha ---


def test_forgot_password_returns_neutral_message(client, user, reset_settings):
    response = forgot(client, user.email)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': NEUTRAL_MESSAGE}


@pytest.mark.asyncio
async def test_forgot_password_stores_valid_token(
    client, session, user, reset_settings
):
    forgot(client, user.email)

    [token] = await reset_tokens_of(session, user)
    assert token.used_at is None
    assert token.deleted_at is None


@pytest.mark.asyncio
async def test_forgot_password_token_expires_in_30_minutes(
    client, session, user, reset_settings
):
    before = datetime.utcnow()
    forgot(client, user.email)
    after = datetime.utcnow()

    [token] = await reset_tokens_of(session, user)
    ttl = timedelta(minutes=30)
    assert before + ttl <= token.expires_at <= after + ttl


@pytest.mark.asyncio
async def test_forgot_password_stores_only_token_hash(
    client, session, user, reset_settings
):
    """FR-004, US1-4: o banco guarda o hash, nunca o token entregue."""
    forgot(client, user.email)
    delivered = await deliver_reset_token(session, reset_settings)

    [token] = await reset_tokens_of(session, user)
    assert token.token_hash == hash_reset_token(delivered)
    assert all(
        delivered not in str(getattr(token, column.key))
        for column in PasswordResetToken.__table__.columns
    )


@pytest.mark.asyncio
async def test_forgot_password_enqueues_reset_email(
    client, session, user, reset_settings
):
    forgot(client, user.email)

    [notification] = await reset_notifications_of(session, user)
    [token] = await reset_tokens_of(session, user)
    assert notification.kind == 'password_reset_email'
    assert notification.recipient == user.email
    assert notification.expires_at == token.expires_at


@pytest.mark.asyncio
async def test_forgot_password_email_carries_reset_link(
    client, session, user, reset_settings
):
    forgot(client, user.email)
    channel = FakeEmailChannel()

    await process_next(session, channel, reset_settings)

    [message] = channel.sent
    [link] = re.findall(re.escape(RESET_URL_PREFIX) + r'\S+', message.text)
    assert message.to == user.email
    assert link in message.html


@pytest.mark.asyncio
async def test_forgot_password_matches_email_case_insensitively(
    client, session, user, reset_settings
):
    """US1-2."""
    forgot(client, user.email.upper())

    assert len(await reset_tokens_of(session, user)) == 1


@pytest.mark.asyncio
async def test_second_request_supersedes_previous_token(
    client, session, user, reset_settings
):
    """FR-005."""
    forgot(client, user.email)
    forgot(client, user.email)

    first, second = await reset_tokens_of(session, user)
    assert first.deleted_at is not None
    assert second.deleted_at is None


@pytest.mark.asyncio
async def test_second_request_cancels_pending_email(
    client, session, user, reset_settings
):
    forgot(client, user.email)
    forgot(client, user.email)

    first, _second = await reset_notifications_of(session, user)
    assert first.status == 'cancelled'
    assert first.error_code == 'cancelled_resent'


@pytest.mark.asyncio
async def test_forgot_password_is_not_attributed_to_anyone(
    client, session, user, reset_settings
):
    """Research R10: o pedido é anônimo."""
    forgot(client, user.email)

    [token] = await reset_tokens_of(session, user)
    [notification] = await reset_notifications_of(session, user)
    assert token.created_by is None
    assert notification.created_by is None


@pytest.mark.asyncio
async def test_forgot_password_does_not_touch_other_accounts(
    client, session, user, other_user, reset_settings
):
    forgot(client, user.email)

    assert await reset_tokens_of(session, other_user) == []
    assert await reset_notifications_of(session, other_user) == []


def test_forgot_password_without_email_setup_returns_neutral_message(
    client, user, unavailable_settings
):
    """FR-008."""
    response = forgot(client, user.email)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': NEUTRAL_MESSAGE}


@pytest.mark.asyncio
async def test_forgot_password_without_email_setup_emits_nothing(
    client, session, user, unavailable_settings
):
    forgot(client, user.email)

    assert await count_rows(session, PasswordResetToken) == 0
    assert await count_rows(session, Notification) == 0


def test_forgot_password_without_email_setup_logs_unavailable(
    client, user, unavailable_settings, operational_log
):
    forgot(client, user.email)

    output = operational_log.getvalue()
    events = [json.loads(line) for line in output.splitlines()]
    assert [(event['event'], event['level']) for event in events] == [
        ('password_reset_unavailable', 'warning')
    ]
    assert user.email not in output


# --- US2: não revelar quais e-mails têm conta ---


def test_forgot_password_for_unknown_email_matches_registered_response(
    client, user, reset_settings
):
    """US2-1, SC-002."""
    registered = forgot(client, user.email)
    unknown = forgot(client, 'ninguem@exemplo.org')

    assert unknown.status_code == registered.status_code
    assert unknown.json() == registered.json()


@pytest.mark.asyncio
async def test_forgot_password_for_unknown_email_emits_nothing(
    client, session, reset_settings
):
    forgot(client, 'ninguem@exemplo.org')

    assert await count_rows(session, PasswordResetToken) == 0
    assert await count_rows(session, Notification) == 0


def test_forgot_password_for_deleted_account_returns_neutral_message(
    client, deleted_user, reset_settings
):
    """US2-2."""
    response = forgot(client, deleted_user.email)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': NEUTRAL_MESSAGE}


@pytest.mark.asyncio
async def test_forgot_password_for_deleted_account_emits_nothing(
    client, session, deleted_user, reset_settings
):
    forgot(client, deleted_user.email)

    assert await reset_tokens_of(session, deleted_user) == []
    assert await reset_notifications_of(session, deleted_user) == []


def test_forgot_password_rejects_invalid_email_format(client, reset_settings):
    """US2-3."""
    response = forgot(client, 'nao-e-email')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


def test_forgot_password_requires_email(client, reset_settings):
    response = client.post('/auth/forgot-password', json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_forgot_password_rejects_extra_field(client, user, reset_settings):
    response = client.post(
        '/auth/forgot-password',
        json={'email': user.email, 'username': user.username},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_forgot_password_with_extra_field_emits_nothing(
    client, session, user, reset_settings
):
    client.post(
        '/auth/forgot-password',
        json={'email': user.email, 'username': user.username},
    )

    assert await reset_tokens_of(session, user) == []


# --- US3: redefinir a senha com o token ---


@pytest.mark.asyncio
async def test_reset_password_returns_no_content(
    client, session, user, reset_settings
):
    """US3-1."""
    token = await issue_token(client, session, reset_settings, user)

    response = reset(client, token)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


@pytest.mark.asyncio
async def test_reset_password_stores_new_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(user)
    assert verify_password(user.password_hash, NEW_PASSWORD)


@pytest.mark.asyncio
async def test_reset_password_marks_token_as_used(
    client, session, user, reset_settings
):
    """FR-013."""
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    [stored] = await reset_tokens_of(session, user)
    assert stored.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_records_token_update_audit(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    [stored] = await reset_tokens_of(session, user)
    assert stored.updated_by == user.id


@pytest.mark.asyncio
async def test_reset_password_records_account_update_audit(
    client, session, user, reset_settings
):
    """FR-015."""
    updated_at_before = user.updated_at
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(user)
    assert user.updated_by == user.id
    assert user.updated_at is not None
    assert user.updated_at != updated_at_before


@pytest.mark.asyncio
async def test_login_accepts_new_password_after_reset(
    client, session, user, reset_settings
):
    """US3-2, FR-016."""
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token)

    assert login(client, user, NEW_PASSWORD).status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_login_rejects_old_password_after_reset(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token)

    response = login(client, user, FACTORY_PASSWORD)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_reset_password_rejects_reused_token(
    client, session, user, reset_settings
):
    """US3-3."""
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token)

    response = reset(client, token, 'OutraSenha-2026')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == INVALID_TOKEN_DETAIL


@pytest.mark.asyncio
async def test_reused_token_keeps_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token)
    await session.refresh(user)
    password_hash = user.password_hash

    reset(client, token, 'OutraSenha-2026')

    await session.refresh(user)
    assert user.password_hash == password_hash


async def expire(session, user):
    [stored] = await reset_tokens_of(session, user)
    stored.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await session.commit()


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(
    client, session, user, reset_settings
):
    """US3-4."""
    token = await issue_token(client, session, reset_settings, user)
    await expire(session, user)

    response = reset(client, token)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == INVALID_TOKEN_DETAIL


@pytest.mark.asyncio
async def test_expired_token_keeps_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    await expire(session, user)
    password_hash = user.password_hash

    reset(client, token)

    await session.refresh(user)
    assert user.password_hash == password_hash


def test_reset_password_rejects_unknown_token(client, reset_settings):
    """US3-5."""
    response = reset(client, 'x' * 43)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == INVALID_TOKEN_DETAIL


@pytest.mark.asyncio
async def test_reset_password_rejects_superseded_token(
    client, session, user, reset_settings
):
    """US3-6."""
    first = await issue_token(client, session, reset_settings, user)
    await issue_token(client, session, reset_settings, user)

    response = reset(client, first)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == INVALID_TOKEN_DETAIL


@pytest.mark.asyncio
async def test_superseded_token_keeps_password(
    client, session, user, reset_settings
):
    """SC-003."""
    first = await issue_token(client, session, reset_settings, user)
    await issue_token(client, session, reset_settings, user)
    password_hash = user.password_hash

    reset(client, first)

    await session.refresh(user)
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_reset_password_accepts_latest_token(
    client, session, user, reset_settings
):
    await issue_token(client, session, reset_settings, user)
    latest = await issue_token(client, session, reset_settings, user)

    assert reset(client, latest).status_code == HTTPStatus.NO_CONTENT


@pytest.mark.asyncio
async def test_reset_password_rejects_token_of_deleted_account(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    user.deleted_at = datetime.utcnow()
    await session.commit()

    response = reset(client, token)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == INVALID_TOKEN_DETAIL


@pytest.mark.asyncio
async def test_token_of_deleted_account_keeps_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    user.deleted_at = datetime.utcnow()
    await session.commit()
    password_hash = user.password_hash

    reset(client, token)

    await session.refresh(user)
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_reset_password_hides_password_rule_and_value(
    client, session, user, reset_settings
):
    """US3-7."""
    token = await issue_token(client, session, reset_settings, user)

    response = reset(client, token, 'Nova Senha-2026')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['fields'] == [
        {
            'location': 'body',
            'field': 'new_password',
            'code': 'invalid',
            'message': 'Senha inválida.',
        }
    ]
    assert 'Nova Senha-2026' not in response.text


@pytest.mark.asyncio
async def test_invalid_new_password_keeps_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    password_hash = user.password_hash

    reset(client, token, 'Nova Senha-2026')

    await session.refresh(user)
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_token_still_works_after_invalid_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token, 'Nova Senha-2026')

    assert reset(client, token).status_code == HTTPStatus.NO_CONTENT


def test_reset_password_requires_token(client, reset_settings):
    response = client.post(
        '/auth/reset-password', json={'new_password': NEW_PASSWORD}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_reset_password_requires_new_password(client, reset_settings):
    response = client.post('/auth/reset-password', json={'token': 'x' * 43})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_reset_password_rejects_extra_field(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)

    response = client.post(
        '/auth/reset-password',
        json={'token': token, 'new_password': NEW_PASSWORD, 'email': 'x'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_reset_password_with_extra_field_keeps_password(
    client, session, user, reset_settings
):
    token = await issue_token(client, session, reset_settings, user)
    password_hash = user.password_hash

    client.post(
        '/auth/reset-password',
        json={'token': token, 'new_password': NEW_PASSWORD, 'email': 'x'},
    )

    await session.refresh(user)
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_reset_password_works_with_active_session(
    client, session, user, reset_settings
):
    """Spec, Edge Cases: a sessão aberta não interfere."""
    token = await issue_token(client, session, reset_settings, user)
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )

    assert reset(client, token).status_code == HTTPStatus.NO_CONTENT


# --- Segredo fora dos logs (FR-004, SC-006) ---


@pytest_asyncio.fixture
async def full_flow_logs(  # noqa: PLR0913, PLR0917
    client, session, user, reset_settings, caplog, operational_log
):
    """Pedido, envio e redefinição; devolve o token e todo o log gerado."""
    caplog.set_level(logging.DEBUG)
    token = await issue_token(client, session, reset_settings, user)
    reset(client, token)
    return token, caplog.text + operational_log.getvalue()


def test_full_flow_does_not_log_token(full_flow_logs):
    token, logs = full_flow_logs

    assert token not in logs


def test_full_flow_does_not_log_reset_link(full_flow_logs):
    token, logs = full_flow_logs

    assert RESET_URL_PREFIX + token not in logs


def test_full_flow_does_not_log_new_password(full_flow_logs):
    _token, logs = full_flow_logs

    assert NEW_PASSWORD not in logs


# --- Escopo da alteração (FR-017) ---


def snapshot(row):
    return {
        attr.key: getattr(row, attr.key)
        for attr in inspect(type(row)).column_attrs
    }


@pytest.mark.asyncio
async def test_reset_password_changes_only_password_and_update_audit(
    client, session, user, reset_settings
):
    before = snapshot(user)
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(user)
    changed = {
        key for key, value in snapshot(user).items() if value != before[key]
    }
    assert changed == {'password_hash', 'updated_at', 'updated_by'}


@pytest.mark.asyncio
async def test_reset_password_keeps_access_profiles(
    client, session, user, reset_settings
):
    profile = AccessProfileFactory()
    session.add(profile)
    await session.flush()
    link = UserAccessProfileFactory(user=user, profile=profile)
    session.add(link)
    await session.commit()
    before = snapshot(link)
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(link)
    assert snapshot(link) == before


@pytest.mark.asyncio
async def test_reset_password_keeps_institutional_affiliations(
    client, session, user, reset_settings
):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution
    )
    session.add(affiliation)
    await session.commit()
    before = snapshot(affiliation)
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(affiliation)
    assert snapshot(affiliation) == before


@pytest.mark.asyncio
async def test_forgot_password_does_not_change_account(
    client, session, user, reset_settings
):
    before = snapshot(user)

    forgot(client, user.email)

    await session.refresh(user)
    assert snapshot(user) == before


@pytest.mark.asyncio
async def test_reset_password_keeps_other_account_password(
    client, session, user, other_user, reset_settings
):
    password_hash = other_user.password_hash
    token = await issue_token(client, session, reset_settings, user)

    reset(client, token)

    await session.refresh(other_user)
    assert other_user.password_hash == password_hash


# --- Contrato publicado ---


def test_openapi_exposes_password_reset_routes(client):
    paths = client.get('/openapi.json').json()['paths']

    assert paths['/auth/forgot-password']['post']['operationId'] == (
        'forgotPassword'
    )
    reset_operation = paths['/auth/reset-password']['post']
    assert reset_operation['operationId'] == 'resetPassword'
    assert '400' in reset_operation['responses']
