"""Catálogo de templates de coleta de dados (Spec 041, issue #26).

O template define as colunas do arquivo de resultados da Etapa 3 e os
mínimos de experimentos e réplicas. A estrutura trava quando um processo
vinculado conclui a definição das amostras; o travamento é calculado por
consulta, sem marcador gravado (research R2).

Toda alteração estrutural trava antes a linha do template, a mesma que
``sample_service.complete_sample_definition`` trava antes de concluir: as
duas operações se serializam (FR-019, research R4). Sob essa trava, as
regras de chave e posição não têm corrida (research R5).
"""

import csv
import io
from typing import Any
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import (
    ActivityInstance,
    CollectionTemplate,
    CollectionTemplateColumn,
    ProcessInstance,
)
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from pivma.core.sample_service import SAMPLE_ACTIVITY_KEY
from pivma.schemas import MAX_INTEGER

# Colunas fixas do arquivo, na ordem do cabeçalho.
RESERVED_COLUMN_KEYS = ('codigo_amostra', 'experimento', 'replica')
MINIMUM_FIELDS = ('min_experiments', 'min_replicates')
CSV_MEDIA_TYPE = 'text/csv; charset=utf-8'
XLSX_MEDIA_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)
XLSX_SHEET_TITLE = 'resultados'


# ---------------------------------------------------------------------------
# Consultas e travamento
# ---------------------------------------------------------------------------


async def get_template(
    session: AsyncSession, template_id: UUID
) -> CollectionTemplate:
    template = await session.get(CollectionTemplate, template_id)
    if template is None:
        raise NotFoundError('Template de coleta não encontrado.')
    return template


async def active_columns(
    session: AsyncSession, template_id: UUID
) -> list[CollectionTemplateColumn]:
    """Colunas ativas do template, por posição."""
    return list(
        await session.scalars(
            select(CollectionTemplateColumn)
            .where(
                CollectionTemplateColumn.collection_template_id == template_id,
                CollectionTemplateColumn.deleted_at.is_(None),
            )
            .order_by(CollectionTemplateColumn.position)
        )
    )


async def locked_template_ids(
    session: AsyncSession, template_ids: list[UUID]
) -> set[UUID]:
    """Templates com um processo vinculado que concluiu as amostras.

    Conta também os processos excluídos: a exclusão não reabre a definição
    das amostras, e o template não destrava (FR-017, research R2).
    """
    return set(
        await session.scalars(
            select(ProcessInstance.collection_template_id)
            .distinct()
            .join(
                ActivityInstance,
                ActivityInstance.process_instance_id == ProcessInstance.id,
            )
            .where(
                ProcessInstance.collection_template_id.in_(template_ids),
                ActivityInstance.key == SAMPLE_ACTIVITY_KEY,
                ActivityInstance.status == 'COMPLETED',
                ActivityInstance.deleted_at.is_(None),
            )
            .execution_options(skip_soft_delete_filter=True)
        )
    )


async def lock_template_row(
    session: AsyncSession, template_id: UUID
) -> CollectionTemplate:
    """Trava a linha do template até o fim da transação (FR-019, R4).

    Chamada pelas alterações estruturais e por
    ``sample_service.complete_sample_definition``.
    """
    template = await session.scalar(
        select(CollectionTemplate)
        .where(CollectionTemplate.id == template_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if template is None:
        raise NotFoundError('Template de coleta não encontrado.')
    return template


async def _ensure_unlocked(session: AsyncSession, template_id: UUID) -> None:
    if template_id in await locked_template_ids(session, [template_id]):
        raise ConflictError(
            'A estrutura do template está travada: um processo vinculado '
            'já concluiu a definição das amostras.',
            code='template_locked',
        )


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


async def create_template(
    session: AsyncSession, actor_id: UUID, data: dict[str, Any]
) -> CollectionTemplate:
    template = CollectionTemplate(**data)
    template.set_creation_audit(actor_id)
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def update_template(
    session: AsyncSession,
    template_id: UUID,
    actor_id: UUID,
    changes: dict[str, Any],
) -> CollectionTemplate:
    """Aplica os campos enviados.

    Um mínimo só conta como mudança estrutural quando difere do valor atual,
    relido sob a trava (research R3).
    """
    if any(field in changes for field in MINIMUM_FIELDS):
        template = await lock_template_row(session, template_id)
        if any(
            field in changes and changes[field] != getattr(template, field)
            for field in MINIMUM_FIELDS
        ):
            await _ensure_unlocked(session, template_id)
    else:
        template = await get_template(session, template_id)
    for field, value in changes.items():
        setattr(template, field, value)
    template.set_update_audit(actor_id)
    await session.commit()
    await session.refresh(template)
    return template


# ---------------------------------------------------------------------------
# Colunas
# ---------------------------------------------------------------------------


def _check_column(
    state: dict[str, Any], others: list[CollectionTemplateColumn]
) -> None:
    """Regras de uma coluna no estado final, contra as outras ativas."""
    if state['key'] in RESERVED_COLUMN_KEYS:
        raise ConflictError(
            'A chave é reservada às colunas fixas do arquivo.',
            code='reserved_key',
        )
    if any(other.key == state['key'] for other in others):
        raise ConflictError(
            'Já existe uma coluna ativa com esta chave.', code='duplicate_key'
        )
    if any(other.position == state['position'] for other in others):
        raise ConflictError(
            'Já existe uma coluna ativa nesta posição.', code='position_taken'
        )
    options = state['options']
    if state['type'] == 'select':
        if not options or len(set(options)) != len(options):
            raise ValidationError(
                'O tipo select exige ao menos uma opção, sem repetição.',
                code='invalid_options',
            )
    elif options is not None:
        raise ValidationError(
            'Só o tipo select aceita opções.', code='invalid_options'
        )


def _model_fields(state: dict[str, Any]) -> dict[str, Any]:
    return {
        'key': state['key'],
        'label': state['label'],
        'column_type': state['type'],
        'required': state['required'],
        'options': state['options'],
        'position': state['position'],
    }


async def _columns_under_lock(
    session: AsyncSession, template_id: UUID
) -> list[CollectionTemplateColumn]:
    """Trava o template e devolve as colunas ativas.

    Quem chama confere a coluna antes de `_ensure_unlocked`: coluna
    inexistente é 404 mesmo com o template travado.
    """
    await lock_template_row(session, template_id)
    return await active_columns(session, template_id)


def _column(
    columns: list[CollectionTemplateColumn], column_id: UUID
) -> CollectionTemplateColumn:
    column = next((c for c in columns if c.id == column_id), None)
    if column is None:
        raise NotFoundError('Coluna não encontrada.')
    return column


async def add_column(
    session: AsyncSession,
    template_id: UUID,
    actor_id: UUID,
    data: dict[str, Any],
) -> CollectionTemplateColumn:
    """Sem posição, a coluna vai para o fim: maior posição ativa + 1."""
    columns = await _columns_under_lock(session, template_id)
    await _ensure_unlocked(session, template_id)
    state = dict(data)
    if state['position'] is None:
        state['position'] = max((c.position for c in columns), default=0) + 1
        if state['position'] > MAX_INTEGER:
            raise ConflictError(
                'Não há posição depois da última coluna; informe a posição.',
                code='position_limit_reached',
            )
    _check_column(state, columns)
    column = CollectionTemplateColumn(
        collection_template_id=template_id, **_model_fields(state)
    )
    column.set_creation_audit(actor_id)
    session.add(column)
    await session.commit()
    await session.refresh(column)
    return column


async def update_column(
    session: AsyncSession,
    template_id: UUID,
    column_id: UUID,
    actor_id: UUID,
    changes: dict[str, Any],
) -> CollectionTemplateColumn:
    """Valida o estado resultante, sem contar a própria coluna."""
    columns = await _columns_under_lock(session, template_id)
    column = _column(columns, column_id)
    await _ensure_unlocked(session, template_id)
    state = {
        'key': column.key,
        'label': column.label,
        'type': column.column_type,
        'required': column.required,
        'options': column.options,
        'position': column.position,
        **changes,
    }
    _check_column(state, [c for c in columns if c.id != column_id])
    for field, value in _model_fields(state).items():
        setattr(column, field, value)
    column.set_update_audit(actor_id)
    await session.commit()
    await session.refresh(column)
    return column


async def delete_column(
    session: AsyncSession, template_id: UUID, column_id: UUID, actor_id: UUID
) -> None:
    """Exclusão lógica: libera a chave e a posição (FR-010)."""
    columns = await _columns_under_lock(session, template_id)
    column = _column(columns, column_id)
    await _ensure_unlocked(session, template_id)
    column.set_deletion_audit(actor_id)
    await session.commit()


# ---------------------------------------------------------------------------
# Arquivo-modelo (research R7)
# ---------------------------------------------------------------------------


def file_header(columns: list[CollectionTemplateColumn]) -> list[str]:
    """Colunas fixas e as chaves das ativas por posição crescente."""
    ordered = sorted(columns, key=lambda column: column.position)
    return [*RESERVED_COLUMN_KEYS, *(column.key for column in ordered)]


def render_csv(header: list[str]) -> bytes:
    """Uma linha, separada por `;`, em UTF-8 com BOM para o Excel."""
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=';').writerow(header)
    return buffer.getvalue().encode('utf-8-sig')


def render_xlsx(header: list[str]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = XLSX_SHEET_TITLE
    sheet.append(header)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
