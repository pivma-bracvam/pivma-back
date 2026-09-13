# ruff: noqa: PLR2004
"""Integração (banco) — vínculo campo ↔ anexo ativo (Spec 016)."""

import pytest
from sqlalchemy import select

from pivma.core.database.models import Artifact, FormValue
from tests.api.routers.test_form_attachments import (
    ORIGIN,
    att_url,
    setup_process_with_file_field,
    upload,
)


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


@pytest.mark.asyncio
async def test_replace_soft_deletes_previous_keeps_one_active(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    upload(client, pid, name='v1.pdf', data=b'v1')
    upload(client, pid, name='v2.pdf', data=b'v2')

    artifacts = list(
        await session.scalars(
            select(Artifact)
            .where(Artifact.key == 'form_attachment')
            .execution_options(skip_soft_delete_filter=True)
        )
    )
    assert len(artifacts) == 2
    active = [a for a in artifacts if a.deleted_at is None]
    deleted = [a for a in artifacts if a.deleted_at is not None]
    assert len(active) == 1
    assert len(deleted) == 1
    assert deleted[0].deleted_by is not None
    assert active[0].metadata_payload['original_filename'] == 'v2.pdf'

    form_value = await session.scalar(select(FormValue))
    assert form_value.file_attachment_id == active[0].id


@pytest.mark.asyncio
async def test_delete_soft_deletes_artifact_and_unlinks_value(client, session):
    _, pid = await setup_process_with_file_field(client, session)
    upload(client, pid)

    client.delete(att_url(pid), headers=ORIGIN)

    artifact = await session.scalar(
        select(Artifact)
        .where(Artifact.key == 'form_attachment')
        .execution_options(skip_soft_delete_filter=True)
    )
    assert artifact.deleted_at is not None
    form_value = await session.scalar(select(FormValue))
    assert form_value.file_attachment_id is None
