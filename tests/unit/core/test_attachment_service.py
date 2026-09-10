# ruff: noqa: PLR2004
"""Unidade — validação e gravação de anexos (Spec 016)."""

import hashlib
import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.datastructures import UploadFile

from pivma.core.attachment_service import (
    AttachmentError,
    attachment_relpath,
    resolve_allowed_extensions,
    resolve_max_bytes,
    store_upload,
    validate_extension,
)
from pivma.core.settings import Settings

FIELD_DEFAULT = SimpleNamespace(
    validation_rules=None, field_type='file_upload'
)
FIELD_RULES = SimpleNamespace(
    validation_rules={'allowed_extensions': ['pdf'], 'max_size_mb': 1},
    field_type='file_upload',
)


def test_allowed_extensions_default_set():
    assert resolve_allowed_extensions(FIELD_DEFAULT, Settings()) == {
        'pdf',
        'docx',
        'doc',
        'png',
        'jpg',
        'jpeg',
    }


def test_allowed_extensions_from_field_rules():
    assert resolve_allowed_extensions(FIELD_RULES, Settings()) == {'pdf'}


def test_max_bytes_default_is_25_mb():
    assert resolve_max_bytes(FIELD_DEFAULT, Settings()) == 25 * 1024 * 1024


def test_max_bytes_from_field_rules():
    assert resolve_max_bytes(FIELD_RULES, Settings()) == 1024 * 1024


@pytest.mark.parametrize('name', ['pop.exe', 'pop', '', 'pop.pdfx'])
def test_validate_extension_rejects_outside_allowlist(name):
    with pytest.raises(AttachmentError) as exc:
        validate_extension(name, {'pdf'})
    assert exc.value.code == 'extension_not_allowed'


def test_validate_extension_is_case_insensitive():
    assert validate_extension('POP.PDF', {'pdf'}) == 'pdf'


def test_relpath_layout_is_process_then_artifact():
    process_id, artifact_id = uuid4(), uuid4()
    assert (
        attachment_relpath(process_id, artifact_id, 'pdf')
        == f'{process_id}/{artifact_id}.pdf'
    )


@pytest.mark.asyncio
async def test_store_upload_returns_size_and_sha256(tmp_path):
    content = b'%PDF-1.4 conteudo de teste'
    upload = UploadFile(io.BytesIO(content), filename='a.pdf')
    dest = tmp_path / 'a.pdf'

    size, checksum = await store_upload(upload, dest, 1024)

    assert size == len(content)
    assert checksum == hashlib.sha256(content).hexdigest()
    assert dest.read_bytes() == content


@pytest.mark.asyncio
async def test_store_upload_rejects_empty_file_without_writing(tmp_path):
    upload = UploadFile(io.BytesIO(b''), filename='a.pdf')
    dest = tmp_path / 'a.pdf'

    with pytest.raises(AttachmentError) as exc:
        await store_upload(upload, dest, 1024)

    assert exc.value.code == 'empty_file'
    assert not dest.exists()


@pytest.mark.asyncio
async def test_store_upload_aborts_oversize_without_partial_file(tmp_path):
    upload = UploadFile(io.BytesIO(b'x' * 5000), filename='a.pdf')
    dest = tmp_path / 'a.pdf'

    with pytest.raises(AttachmentError) as exc:
        await store_upload(upload, dest, 1024)

    assert exc.value.code == 'file_too_large'
    assert not dest.exists()
