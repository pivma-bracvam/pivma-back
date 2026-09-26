# ruff: noqa: PLR2004
"""API — anexos de campo de formulário (Spec 016, US1/US2/US3)."""

import hashlib
from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    Artifact,
    FormField,
    FormTemplate,
    FormValue,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
FORM_URL = '/processes/{pid}/activities/proposal_submission/form'
ATT_URL = FORM_URL + '/fields/{field}/attachment'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def setup_process_with_file_field(
    client, session, *, required=False, rules=None
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Teste 016'},
    ).json()['id']

    template = (
        await session.execute(
            select(FormTemplate).where(
                FormTemplate.key == 'submission_pre_validated_v1'
            )
        )
    ).scalar_one()
    session.add(
        FormField(
            form_template_id=template.id,
            field_key='pop_document',
            label='POP do Método',
            field_type='file_upload',
            is_required=required,
            order_index=20,
            validation_rules=rules,
        )
    )
    await session.commit()
    return user, pid


def att_url(pid, field='pop_document'):
    return ATT_URL.format(pid=pid, field=field)


def upload(
    client, pid, name='POP.pdf', data=b'%PDF-1.4 data', mime='application/pdf'
):
    return client.post(
        att_url(pid),
        files={'file': (name, data, mime)},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_upload_then_submit_bundles_attachment(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    data = b'%PDF-1.4 corpo do documento'

    resp = upload(client, pid, data=data)
    assert resp.status_code == HTTPStatus.OK, resp.text
    body = resp.json()
    assert body['replaced_previous'] is False
    assert (
        body['attachment']['checksum_sha256']
        == hashlib.sha256(data).hexdigest()
    )

    form = client.get(FORM_URL.format(pid=pid)).json()
    field = next(f for f in form['fields'] if f['field_key'] == 'pop_document')
    assert field['attachment']['filename'] == 'POP.pdf'
    assert 'pop_document' not in form['values']

    submit = client.post(
        FORM_URL.format(pid=pid), json={'values': {'method_title': 'M'}}
    )
    assert submit.status_code == HTTPStatus.OK, submit.text

    dossier = (
        await session.execute(
            select(Artifact).where(
                Artifact.process_instance_id == UUID(pid),
                Artifact.key == 'proposal_dossier',
            )
        )
    ).scalar_one()
    assert dossier.metadata_payload['attachments'][0]['field_key'] == (
        'pop_document'
    )
    assert (
        dossier.metadata_payload['attachments'][0]['artifact_id']
        == (body['attachment']['artifact_id'])
    )

    attachment = (
        await session.execute(
            select(Artifact).where(
                Artifact.process_instance_id == UUID(pid),
                Artifact.key == 'form_attachment',
            )
        )
    ).scalar_one()
    assert attachment.status == 'SUBMITTED'


@pytest.mark.asyncio
async def test_submit_blocked_without_required_attachment(client, session):
    _, pid = await setup_process_with_file_field(
        client, session, required=True
    )

    submit = client.post(
        FORM_URL.format(pid=pid), json={'values': {'method_title': 'M'}}
    )

    assert submit.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        submit.json()['detail']['errors'][0]['code'] == 'attachment_required'
    )
    form = client.get(FORM_URL.format(pid=pid)).json()
    assert form['is_submitted'] is False


@pytest.mark.asyncio
async def test_replace_reports_previous_and_keeps_one_active(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    assert upload(client, pid, name='a.pdf', data=b'aaaa').status_code == 200
    resp = upload(client, pid, name='b.pdf', data=b'bbbbbb')

    assert resp.json()['replaced_previous'] is True
    active = list(
        await session.scalars(
            select(Artifact).where(
                Artifact.key == 'form_attachment',
                Artifact.deleted_at.is_(None),
            )
        )
    )
    assert len(active) == 1
    assert active[0].metadata_payload['original_filename'] == 'b.pdf'


@pytest.mark.asyncio
async def test_delete_clears_form_value(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    upload(client, pid)

    resp = client.delete(att_url(pid), headers=ORIGIN)

    assert resp.status_code == HTTPStatus.OK
    form_value = await session.scalar(select(FormValue))
    assert form_value.file_attachment_id is None
    form = client.get(FORM_URL.format(pid=pid)).json()
    field = next(f for f in form['fields'] if f['field_key'] == 'pop_document')
    assert field['attachment'] is None


@pytest.mark.asyncio
async def test_draft_save_succeeds_with_file_field_present(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    resp = client.put(
        FORM_URL.format(pid=pid), json={'values': {'method_title': 'draft'}}
    )

    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_draft_rejects_inline_file_upload_value(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    resp = client.put(
        FORM_URL.format(pid=pid),
        json={'values': {'pop_document': 'x.pdf'}},
    )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json()['detail']['errors'][0]['code'] == (
        'file_upload_uses_attachment_endpoint'
    )


@pytest.mark.asyncio
async def test_invalid_upload_preserves_previous_attachment(client, session):
    _, pid = await setup_process_with_file_field(
        client,
        session,
        rules={'allowed_extensions': ['pdf'], 'max_size_mb': 1},
    )
    assert upload(client, pid, name='ok.pdf', data=b'bom').status_code == 200

    bad_ext = upload(
        client, pid, name='x.exe', data=b'x', mime='application/octet-stream'
    )
    too_big = upload(
        client, pid, name='big.pdf', data=b'x' * (1024 * 1024 + 8)
    )
    empty = upload(client, pid, name='empty.pdf', data=b'')

    assert bad_ext.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert too_big.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert empty.status_code == HTTPStatus.BAD_REQUEST

    form = client.get(FORM_URL.format(pid=pid)).json()
    field = next(f for f in form['fields'] if f['field_key'] == 'pop_document')
    assert field['attachment']['filename'] == 'ok.pdf'


@pytest.mark.asyncio
async def test_upload_requires_trusted_origin(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    resp = client.post(
        att_url(pid),
        files={'file': ('a.pdf', b'aa', 'application/pdf')},
    )

    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_upload_rejected_after_submission(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    upload(client, pid)
    client.post(
        FORM_URL.format(pid=pid), json={'values': {'method_title': 'M'}}
    )

    resp = upload(client, pid, name='b.pdf', data=b'bb')

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail']['code'] == 'form_submitted'


@pytest.mark.asyncio
async def test_replacing_attachment_after_revision_keeps_submitted_snapshot(
    client, session, bracvam_user
):
    owner, pid = await setup_process_with_file_field(client, session)
    first = upload(client, pid, name='first.pdf', data=b'first')
    assert first.status_code == HTTPStatus.OK
    first_id = first.json()['attachment']['artifact_id']
    submit = client.post(
        FORM_URL.format(pid=pid),
        json={'values': {'method_title': 'Método enviado'}},
    )
    assert submit.status_code == HTTPStatus.OK

    authenticate(client, bracvam_user)
    revision = client.post(
        f'/processes/{pid}/triage/decision',
        headers=ORIGIN,
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Atualizar o protocolo.',
        },
    )
    assert revision.status_code == HTTPStatus.OK

    authenticate(client, owner)
    # Spec 030: o proponente escolhe revisar antes de a submissão reabrir.
    client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'REVISE'},
        headers={'Origin': 'https://testserver'},
    )
    replacement = upload(client, pid, name='second.pdf', data=b'second')
    assert replacement.status_code == HTTPStatus.OK

    previous = await session.get(Artifact, UUID(first_id))
    assert previous is not None
    assert previous.deleted_at is None


@pytest.mark.asyncio
async def test_upload_rejected_on_non_file_field(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    resp = client.post(
        att_url(pid, field='method_title'),
        files={'file': ('a.pdf', b'aa', 'application/pdf')},
        headers=ORIGIN,
    )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json()['detail']['code'] == 'not_a_file_field'


@pytest.mark.asyncio
async def test_owner_downloads_original_during_submission(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    content = b'%PDF binary \x00\x01\x02 bytes'
    upload(client, pid, name='POP.pdf', data=content)

    resp = client.get(att_url(pid))

    assert resp.status_code == HTTPStatus.OK
    assert resp.content == content
    assert 'POP.pdf' in resp.headers['content-disposition']


@pytest.mark.asyncio
async def test_download_denied_for_non_proponent(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    upload(client, pid)

    other = UserFactory()
    session.add(other)
    await session.commit()
    authenticate(client, other)

    resp = client.get(att_url(pid))

    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_download_404_when_field_has_no_attachment(client, session):
    _, pid = await setup_process_with_file_field(client, session)

    resp = client.get(att_url(pid))

    assert resp.status_code == HTTPStatus.NOT_FOUND
