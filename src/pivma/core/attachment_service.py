"""Ciclo de vida de anexos de campo de formulário (Spec 016).

Regras de domínio puras + I/O de disco para os campos ``file_upload``. O
conteúdo do arquivo nunca é interpretado nem enviado a serviços externos
(inclusive o provedor de IA); aqui só se valida extensão declarada e tamanho,
calcula-se a soma de verificação e persiste-se o binário sob
``Settings.ATTACHMENTS_DIR``.
"""

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import UploadFile

from pivma.core.database.models import FormField
from pivma.core.settings import Settings

logger = logging.getLogger(__name__)

_CHUNK_BYTES = 1024 * 1024
_BYTES_PER_MB = 1024 * 1024


class AttachmentError(Exception):
    """Erro de validação/gravação de anexo, com código estável para o HTTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_allowed_extensions(
    field: FormField, settings: Settings
) -> set[str]:
    """Extensões aceitas: as do campo (`allowed_extensions`) ou o padrão."""
    rules = field.validation_rules or {}
    declared = rules.get('allowed_extensions')
    source = declared or settings.ATTACHMENT_DEFAULT_EXTENSIONS
    return {str(ext).lower().lstrip('.') for ext in source}


def resolve_max_bytes(field: FormField, settings: Settings) -> int:
    """Teto de tamanho: `max_size_mb` do campo ou o padrão do sistema."""
    rules = field.validation_rules or {}
    mb = rules.get('max_size_mb')
    if not isinstance(mb, (int, float)) or isinstance(mb, bool) or mb <= 0:
        mb = settings.ATTACHMENT_MAX_SIZE_MB
    return int(mb * _BYTES_PER_MB)


def file_extension(filename: str | None) -> str:
    return Path(filename or '').suffix.lower().lstrip('.')


def validate_extension(filename: str | None, allowed: set[str]) -> str:
    ext = file_extension(filename)
    if not ext or ext not in allowed:
        raise AttachmentError(
            'extension_not_allowed',
            'Extensão de arquivo não permitida para este campo.',
        )
    return ext


def attachment_relpath(process_id: UUID, artifact_id: UUID, ext: str) -> str:
    return f'{process_id}/{artifact_id}.{ext}'


def attachment_abspath(settings: Settings, relpath: str) -> Path:
    return Path(settings.ATTACHMENTS_DIR) / relpath


async def _write_chunks(
    upload: UploadFile, handle: Any, max_bytes: int
) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := await upload.read(_CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise AttachmentError(
                'file_too_large',
                'Arquivo acima do limite de tamanho permitido.',
            )
        digest.update(chunk)
        handle.write(chunk)
    return size, digest.hexdigest()


async def store_upload(
    upload: UploadFile, dest: Path, max_bytes: int
) -> tuple[int, str]:
    """Grava o upload em ``dest`` em blocos, retornando (tamanho, sha256).

    Aborta sem deixar arquivo parcial se exceder ``max_bytes`` ou se o
    conteúdo estiver vazio.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open('wb') as handle:
            size, checksum = await _write_chunks(upload, handle, max_bytes)
    except AttachmentError:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise AttachmentError('empty_file', 'Arquivo vazio ou ausente.')
    return size, checksum


def remove_file_best_effort(path: Path | str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning('attachment.disk_cleanup_failed path=%s', path)


def remove_process_attachments(root: Path | str, process_id: UUID) -> None:
    """Remove todos os binários pertencentes a um processo descartável.

    A operação é estrita para que o serviço de ciclo de vida não confirme a
    exclusão do banco quando a limpeza física falhar. Um diretório ausente já
    representa um processo sem anexos e não impede a operação.
    """
    process_dir = Path(root) / str(process_id)
    if not process_dir.exists():
        return
    if not process_dir.is_dir():
        raise OSError(f'O caminho de anexos não é um diretório: {process_dir}')
    shutil.rmtree(process_dir)
