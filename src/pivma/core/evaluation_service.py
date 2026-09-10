"""Serviço de configuração de avaliações por IA (Spec 013, US1/US5/US6).

Cobre a biblioteca de avaliações, o versionamento imutável, o assistente
de sugestão de critérios, o modo de teste, o catálogo de referências
normativas e a associação de avaliações a alvos de formulários.
"""

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pivma.ai.evaluation_pipeline import (
    PipelineCriterion,
    PipelineRequest,
    run_evaluation_pipeline,
)
from pivma.ai.provider import ModelProvider
from pivma.core.database.models import (
    EvaluationAssignment,
    EvaluationCriterion,
    EvaluationDefinition,
    EvaluationReference,
    EvaluationRunItem,
    EvaluationTestRun,
    EvaluationVersion,
    FormTemplate,
    ReviewerFeedback,
)
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
)

_SLUG_MAX = 80
_FIELD_TARGET_TYPES = frozenset({'field', 'field_set', 'document'})


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-')
    return slug[:_SLUG_MAX] or 'avaliacao'


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_definition(
    session: AsyncSession, definition_id: UUID
) -> EvaluationDefinition:
    definition = await session.scalar(
        select(EvaluationDefinition).where(
            EvaluationDefinition.id == definition_id,
            EvaluationDefinition.deleted_at.is_(None),
        )
    )
    if definition is None:
        raise NotFoundError('Avaliação não encontrada.')
    return definition


async def _active_versions(
    session: AsyncSession, definition_id: UUID
) -> list[EvaluationVersion]:
    return list(
        await session.scalars(
            select(EvaluationVersion)
            .where(
                EvaluationVersion.definition_id == definition_id,
                EvaluationVersion.deleted_at.is_(None),
            )
            .order_by(EvaluationVersion.version_number)
        )
    )


async def _get_version(
    session: AsyncSession, definition_id: UUID, number: int
) -> EvaluationVersion:
    version = await session.scalar(
        select(EvaluationVersion)
        .where(
            EvaluationVersion.definition_id == definition_id,
            EvaluationVersion.version_number == number,
            EvaluationVersion.deleted_at.is_(None),
        )
        .options(selectinload(EvaluationVersion.criteria))
    )
    if version is None:
        raise NotFoundError('Versão de avaliação não encontrada.')
    return version


def _active_criteria(version: EvaluationVersion) -> list[EvaluationCriterion]:
    return sorted(
        (c for c in version.criteria if c.deleted_at is None),
        key=lambda c: c.order_index,
    )


# --------------------------------------------------------------------------
# Biblioteca / definições
# --------------------------------------------------------------------------


async def create_definition(  # noqa: PLR0913
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    mode: str,
    objective: str,
    user_id: UUID,
) -> tuple[EvaluationDefinition, EvaluationVersion]:
    slug = _slugify(name)
    clash = await session.scalar(
        select(EvaluationDefinition).where(
            EvaluationDefinition.slug == slug,
            EvaluationDefinition.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise ConflictError('Já existe uma avaliação com esse nome.')

    definition = EvaluationDefinition(
        name=name.strip(), slug=slug, description=description, mode=mode
    )
    definition.set_creation_audit(user_id)
    session.add(definition)
    await session.flush()

    version = EvaluationVersion(
        definition_id=definition.id,
        version_number=1,
        objective=objective.strip(),
        status='draft',
    )
    version.set_creation_audit(user_id)
    session.add(version)
    await session.commit()
    await session.refresh(definition)
    fresh_version = await _get_version(session, definition.id, 1)
    return definition, fresh_version


async def get_definition_detail(
    session: AsyncSession, definition_id: UUID
) -> tuple[EvaluationDefinition, list[EvaluationVersion]]:
    definition = await _get_definition(session, definition_id)
    versions = list(
        await session.scalars(
            select(EvaluationVersion)
            .where(
                EvaluationVersion.definition_id == definition_id,
                EvaluationVersion.deleted_at.is_(None),
            )
            .order_by(EvaluationVersion.version_number)
            .options(selectinload(EvaluationVersion.criteria))
        )
    )
    return definition, versions


async def list_definitions(
    session: AsyncSession, *, search: str | None, offset: int, limit: int
) -> list[dict[str, Any]]:
    stmt = (
        select(EvaluationDefinition)
        .where(EvaluationDefinition.deleted_at.is_(None))
        .order_by(func.lower(EvaluationDefinition.name))
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(EvaluationDefinition.versions).selectinload(
                EvaluationVersion.criteria
            ),
            selectinload(EvaluationDefinition.assignments),
        )
    )
    if search:
        stmt = stmt.where(
            EvaluationDefinition.name.ilike(f'%{search.strip()}%')
        )

    result: list[dict[str, Any]] = []
    for definition in await session.scalars(stmt):
        versions = [v for v in definition.versions if v.deleted_at is None]
        latest = max(versions, key=lambda v: v.version_number, default=None)
        result.append({
            'id': definition.id,
            'name': definition.name,
            'slug': definition.slug,
            'mode': definition.mode,
            'latest_version': latest,
            'published_versions': sum(
                1 for v in versions if v.status == 'published'
            ),
            'assignments_count': sum(
                1
                for a in definition.assignments
                if a.deleted_at is None and a.enabled
            ),
        })
    return result


async def soft_delete_definition(
    session: AsyncSession,
    definition_id: UUID,
    *,
    force: bool,
    user_id: UUID,
) -> None:
    definition = await _get_definition(session, definition_id)
    active_assignment = await session.scalar(
        select(EvaluationAssignment).where(
            EvaluationAssignment.definition_id == definition_id,
            EvaluationAssignment.deleted_at.is_(None),
        )
    )
    if active_assignment is not None and not force:
        raise ConflictError(
            'Avaliação associada a um formulário; use force=true.'
        )
    definition.deleted_at = utc_now()
    definition.deleted_by = user_id
    await session.commit()


# --------------------------------------------------------------------------
# Versões / critérios
# --------------------------------------------------------------------------


async def get_version(
    session: AsyncSession, definition_id: UUID, number: int
) -> EvaluationVersion:
    await _get_definition(session, definition_id)
    return await _get_version(session, definition_id, number)


async def _resolve_references(
    session: AsyncSession, reference_ids: list[UUID]
) -> list[dict[str, Any]]:
    if not reference_ids:
        return []
    refs = list(
        await session.scalars(
            select(EvaluationReference).where(
                EvaluationReference.id.in_(reference_ids),
                EvaluationReference.deleted_at.is_(None),
            )
        )
    )
    found = {r.id for r in refs}
    missing = [rid for rid in reference_ids if rid not in found]
    if missing:
        raise ValidationError('Referência normativa inexistente.')
    return [
        {
            'reference_id': str(r.id),
            'identifier': r.identifier,
            'version_label': r.version_label,
        }
        for r in refs
    ]


def _apply_criteria(
    session: AsyncSession,
    version: EvaluationVersion,
    payload: list[dict[str, Any]],
    user_id: UUID,
) -> None:
    existing = {c.id: c for c in _active_criteria(version)}
    kept: set[UUID] = set()

    for entry in payload:
        cid = entry.get('id')
        if cid is not None and cid in existing:
            crit = existing[cid]
            kept.add(cid)
            crit.statement = entry['statement']
            crit.check_type = entry['check_type']
            crit.polarity = entry['polarity']
            crit.order_index = entry['order_index']
            crit.required_evidence = entry.get('required_evidence')
            crit.severity = entry['severity']
            crit.on_missing_info = entry['on_missing_info']
            crit.recommendation_hint = entry.get('recommendation_hint')
            crit.set_update_audit(user_id)
        else:
            crit = EvaluationCriterion(
                version_id=version.id,
                statement=entry['statement'],
                check_type=entry['check_type'],
                order_index=entry['order_index'],
                polarity=entry['polarity'],
                required_evidence=entry.get('required_evidence'),
                severity=entry['severity'],
                on_missing_info=entry['on_missing_info'],
                recommendation_hint=entry.get('recommendation_hint'),
            )
            crit.set_creation_audit(user_id)
            crit.version = version
            session.add(crit)

    for cid, crit in existing.items():
        if cid not in kept:
            crit.deleted_at = utc_now()
            crit.deleted_by = user_id


async def patch_draft_version(  # noqa: PLR0913
    session: AsyncSession,
    definition_id: UUID,
    number: int,
    *,
    objective: str | None,
    reference_ids: list[UUID] | None,
    criteria: list[dict[str, Any]] | None,
    user_id: UUID,
) -> EvaluationVersion:
    await _get_definition(session, definition_id)
    version = await _get_version(session, definition_id, number)
    if version.status != 'draft':
        raise ConflictError(
            'Versão publicada é imutável; crie uma nova versão.'
        )

    if objective is not None:
        version.objective = objective.strip()
    if reference_ids is not None:
        version.references = await _resolve_references(session, reference_ids)
    if criteria is not None:
        _apply_criteria(session, version, criteria, user_id)
    version.set_update_audit(user_id)

    await session.commit()
    return await _get_version(session, definition_id, number)


async def create_new_version(
    session: AsyncSession, definition_id: UUID, user_id: UUID
) -> EvaluationVersion:
    await _get_definition(session, definition_id)
    versions = await _active_versions(session, definition_id)
    if any(v.status == 'draft' for v in versions):
        raise ConflictError('Já existe uma versão em rascunho.')
    if not versions:
        raise NotFoundError('Versão de avaliação não encontrada.')

    latest = max(versions, key=lambda v: v.version_number)
    source = await _get_version(session, definition_id, latest.version_number)

    new_version = EvaluationVersion(
        definition_id=definition_id,
        version_number=latest.version_number + 1,
        objective=source.objective,
        status='draft',
        references=source.references,
    )
    new_version.set_creation_audit(user_id)
    session.add(new_version)
    await session.flush()

    for crit in _active_criteria(source):
        clone = EvaluationCriterion(
            version_id=new_version.id,
            statement=crit.statement,
            check_type=crit.check_type,
            order_index=crit.order_index,
            polarity=crit.polarity,
            required_evidence=crit.required_evidence,
            severity=crit.severity,
            on_missing_info=crit.on_missing_info,
            recommendation_hint=crit.recommendation_hint,
        )
        clone.set_creation_audit(user_id)
        clone.version = new_version
        session.add(clone)

    await session.commit()
    return await _get_version(
        session, definition_id, new_version.version_number
    )


async def publish_version(
    session: AsyncSession,
    definition_id: UUID,
    number: int,
    user_id: UUID,
) -> tuple[EvaluationVersion, bool]:
    await _get_definition(session, definition_id)
    version = await _get_version(session, definition_id, number)
    if version.status == 'published':
        raise ConflictError('Versão já publicada.')
    if not _active_criteria(version):
        raise ValidationError(
            'A versão precisa de pelo menos um critério para publicar.'
        )

    version.status = 'published'
    version.published_at = utc_now()
    version.published_by = user_id
    version.set_update_audit(user_id)
    test_warning = version.test_run_count == 0
    await session.commit()
    return version, test_warning


# --------------------------------------------------------------------------
# Assistente e modo de teste
# --------------------------------------------------------------------------


async def suggest_criteria(
    provider: ModelProvider, *, objective: str, target_type: str
) -> list[dict[str, Any]]:
    suggestions = await provider.suggest_criteria(objective, target_type)
    return [
        {
            'statement': s.statement,
            'check_type': s.check_type,
            'polarity': s.polarity,
            'suggested_severity': s.suggested_severity,
        }
        for s in suggestions
    ]


async def run_test(  # noqa: PLR0913
    session: AsyncSession,
    provider: ModelProvider,
    definition_id: UUID,
    number: int,
    *,
    sample_content: str,
    user_id: UUID,
) -> dict[str, Any]:
    await _get_definition(session, definition_id)
    version = await _get_version(session, definition_id, number)
    if version.status != 'draft':
        raise ConflictError('Só versões em rascunho podem ser testadas.')

    criteria = _active_criteria(version)
    request = PipelineRequest(
        objective=version.objective,
        references=version.references or [],
        criteria=[
            PipelineCriterion(
                statement=c.statement,
                check_type=c.check_type,
                polarity=c.polarity,
                severity=c.severity,
                content=sample_content,
                required_evidence=c.required_evidence,
                criterion_id=c.id,
                evaluation_version_id=version.id,
            )
            for c in criteria
        ],
    )
    outcome = await run_evaluation_pipeline(request, provider)

    results = [
        {
            'criterion_id': item.criterion.criterion_id,
            'statement': item.criterion.statement,
            'check_type': item.criterion.check_type,
            'severity': item.criterion.severity,
            'conclusion': item.conclusion,
            'is_alert': item.is_alert,
            'evidence_excerpt': item.evidence_excerpt,
            'evidence_location': item.evidence_location,
            'justification': item.justification,
            'recommendation': item.recommendation,
        }
        for item in outcome.items
    ]

    test_run = EvaluationTestRun(
        version_id=version.id,
        sample_content=sample_content,
        result_payload={
            'consolidated_result': outcome.consolidated_result,
            'summary': outcome.summary,
            'results': [
                {**r, 'criterion_id': str(r['criterion_id'])}
                if r['criterion_id']
                else r
                for r in results
            ],
        },
        real_cost=outcome.real_cost,
    )
    test_run.set_creation_audit(user_id)
    session.add(test_run)
    version.test_run_count += 1
    version.set_update_audit(user_id)
    await session.commit()

    return {
        'results': results,
        'consolidated_result': outcome.consolidated_result,
        'real_cost': outcome.real_cost,
    }


# --------------------------------------------------------------------------
# Referências normativas
# --------------------------------------------------------------------------


async def list_references(
    session: AsyncSession,
) -> list[EvaluationReference]:
    return list(
        await session.scalars(
            select(EvaluationReference)
            .where(EvaluationReference.deleted_at.is_(None))
            .order_by(EvaluationReference.identifier)
        )
    )


async def create_reference(  # noqa: PLR0913
    session: AsyncSession,
    *,
    identifier: str,
    label: str,
    version_label: str,
    reference_date,
    user_id: UUID,
) -> EvaluationReference:
    clash = await session.scalar(
        select(EvaluationReference).where(
            EvaluationReference.identifier == identifier,
            EvaluationReference.version_label == version_label,
            EvaluationReference.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise ConflictError('Referência com esse identificador e versão.')
    reference = EvaluationReference(
        identifier=identifier,
        label=label,
        version_label=version_label,
        reference_date=reference_date,
    )
    reference.set_creation_audit(user_id)
    session.add(reference)
    await session.commit()
    await session.refresh(reference)
    return reference


async def reference_impact(
    session: AsyncSession, reference_id: UUID
) -> dict[str, Any]:
    ref_id = str(reference_id)
    versions = list(
        await session.scalars(
            select(EvaluationVersion).where(
                EvaluationVersion.deleted_at.is_(None),
                EvaluationVersion.references.contains([
                    {'reference_id': ref_id}
                ]),
            )
        )
    )
    runs_count = await session.scalar(
        select(func.count())
        .select_from(EvaluationRunItem)
        .join(
            EvaluationVersion,
            EvaluationVersion.id == EvaluationRunItem.evaluation_version_id,
        )
        .where(
            EvaluationRunItem.deleted_at.is_(None),
            EvaluationVersion.references.contains([{'reference_id': ref_id}]),
        )
    )
    return {
        'evaluation_versions': [
            {
                'definition_id': v.definition_id,
                'version_number': v.version_number,
            }
            for v in versions
        ],
        'runs_count': runs_count or 0,
    }


# --------------------------------------------------------------------------
# Associação a alvos de formulário
# --------------------------------------------------------------------------


async def _get_template(
    session: AsyncSession, template_key: str
) -> FormTemplate:
    template = await session.scalar(
        select(FormTemplate)
        .where(
            FormTemplate.key == template_key,
            FormTemplate.deleted_at.is_(None),
        )
        .options(selectinload(FormTemplate.fields))
    )
    if template is None:
        raise NotFoundError('Template de formulário não encontrado.')
    return template


async def _latest_published_number(
    session: AsyncSession, definition_id: UUID
) -> int | None:
    return await session.scalar(
        select(func.max(EvaluationVersion.version_number)).where(
            EvaluationVersion.definition_id == definition_id,
            EvaluationVersion.status == 'published',
            EvaluationVersion.deleted_at.is_(None),
        )
    )


async def _assignment_view(
    session: AsyncSession, assignment: EvaluationAssignment
) -> dict[str, Any]:
    definition = await session.get(
        EvaluationDefinition, assignment.definition_id
    )
    if assignment.pinned_version_id is not None:
        pinned = await session.get(
            EvaluationVersion, assignment.pinned_version_id
        )
        effective = pinned.version_number if pinned else None
    else:
        effective = await _latest_published_number(
            session, assignment.definition_id
        )
    return {
        'id': assignment.id,
        'definition_id': assignment.definition_id,
        'definition_name': definition.name if definition else '',
        'pinned_version_id': assignment.pinned_version_id,
        'effective_version_number': effective,
        'target_type': assignment.target_type,
        'field_keys': assignment.field_keys or [],
        'enabled': assignment.enabled,
    }


async def get_assignments(
    session: AsyncSession, template_key: str
) -> list[dict[str, Any]]:
    template = await _get_template(session, template_key)
    assignments = await session.scalars(
        select(EvaluationAssignment).where(
            EvaluationAssignment.form_template_id == template.id,
            EvaluationAssignment.deleted_at.is_(None),
        )
    )
    return [await _assignment_view(session, a) for a in assignments]


async def replace_assignments(
    session: AsyncSession,
    template_key: str,
    assignments: list[dict[str, Any]],
    user_id: UUID,
) -> list[dict[str, Any]]:
    template = await _get_template(session, template_key)
    field_keys = {f.field_key for f in template.fields if f.deleted_at is None}

    for entry in assignments:
        await _validate_assignment(session, entry, field_keys)

    current = await session.scalars(
        select(EvaluationAssignment).where(
            EvaluationAssignment.form_template_id == template.id,
            EvaluationAssignment.deleted_at.is_(None),
        )
    )
    for existing in current:
        existing.deleted_at = utc_now()
        existing.deleted_by = user_id

    await session.flush()

    for entry in assignments:
        assignment = EvaluationAssignment(
            form_template_id=template.id,
            definition_id=entry['definition_id'],
            target_type=entry['target_type'],
            pinned_version_id=entry.get('pinned_version_id'),
            field_keys=entry.get('field_keys') or [],
            enabled=entry.get('enabled', True),
        )
        assignment.set_creation_audit(user_id)
        session.add(assignment)

    await session.commit()
    return await get_assignments(session, template_key)


async def _validate_assignment(
    session: AsyncSession,
    entry: dict[str, Any],
    template_field_keys: set[str],
) -> None:
    definition = await session.scalar(
        select(EvaluationDefinition).where(
            EvaluationDefinition.id == entry['definition_id'],
            EvaluationDefinition.deleted_at.is_(None),
        )
    )
    if definition is None:
        raise ValidationError('Avaliação inexistente na associação.')

    published = await _latest_published_number(session, entry['definition_id'])
    if published is None:
        raise ValidationError(
            'A avaliação precisa de uma versão publicada para ser associada.'
        )

    target_type = entry['target_type']
    keys = entry.get('field_keys') or []
    if target_type in _FIELD_TARGET_TYPES:
        unknown = [k for k in keys if k not in template_field_keys]
        if not keys or unknown:
            raise ValidationError('field_keys inválidos para o template.')
    elif keys:
        raise ValidationError(
            'field_keys deve ser vazio para alvo form/process.'
        )

    pinned_id = entry.get('pinned_version_id')
    if pinned_id is not None:
        pinned = await session.scalar(
            select(EvaluationVersion).where(
                EvaluationVersion.id == pinned_id,
                EvaluationVersion.definition_id == entry['definition_id'],
                EvaluationVersion.status == 'published',
                EvaluationVersion.deleted_at.is_(None),
            )
        )
        if pinned is None:
            raise ValidationError(
                'pinned_version_id inválido ou não publicado.'
            )


async def get_evaluable_fields(
    session: AsyncSession, template_key: str
) -> list[dict[str, Any]]:
    template = await _get_template(session, template_key)
    assignments = list(
        await session.scalars(
            select(EvaluationAssignment).where(
                EvaluationAssignment.form_template_id == template.id,
                EvaluationAssignment.deleted_at.is_(None),
            )
        )
    )
    names: dict[UUID, str] = {}
    for a in assignments:
        if a.definition_id not in names:
            definition = await session.get(
                EvaluationDefinition, a.definition_id
            )
            names[a.definition_id] = definition.name if definition else ''

    fields = []
    for field in template.fields:
        if field.deleted_at is not None or not field.ai_evaluation_enabled:
            continue
        field_assignments = [
            {
                'definition_id': a.definition_id,
                'definition_name': names.get(a.definition_id, ''),
            }
            for a in assignments
            if field.field_key in (a.field_keys or [])
        ]
        fields.append({
            'field_key': field.field_key,
            'label': field.label,
            'assignments': field_assignments,
        })
    return fields


# --------------------------------------------------------------------------
# Métricas de concordância humano–IA (US4)
# --------------------------------------------------------------------------


async def agreement_metrics(
    session: AsyncSession, *, check_type: str | None = None
) -> dict[str, Any]:
    stmt = (
        select(
            ReviewerFeedback.verdict,
            EvaluationRunItem.check_type,
            EvaluationRunItem.criterion_id,
            EvaluationRunItem.criterion_statement,
            EvaluationRunItem.run_id,
        )
        .join(
            EvaluationRunItem,
            EvaluationRunItem.id == ReviewerFeedback.run_item_id,
        )
        .where(ReviewerFeedback.deleted_at.is_(None))
    )
    if check_type:
        stmt = stmt.where(EvaluationRunItem.check_type == check_type)

    rows = list(await session.execute(stmt))
    total = len(rows)
    if total == 0:
        return {
            'overall_agreement_rate': None,
            'total_feedback': 0,
            'by_check_type': {},
            'most_contested_criteria': [],
            'runs_with_most_disagreements': [],
        }

    agree = sum(1 for r in rows if r.verdict == 'agree')

    by_type: dict[str, list[int]] = {}
    by_criterion: dict[Any, dict[str, Any]] = {}
    by_run: dict[Any, int] = {}
    for row in rows:
        bucket = by_type.setdefault(row.check_type, [0, 0])
        bucket[0] += 1
        bucket[1] += 1 if row.verdict == 'agree' else 0
        crit = by_criterion.setdefault(
            row.criterion_id or row.criterion_statement,
            {
                'criterion_id': row.criterion_id,
                'statement': row.criterion_statement,
                'total': 0,
                'disagree': 0,
            },
        )
        crit['total'] += 1
        if row.verdict == 'disagree':
            crit['disagree'] += 1
            by_run[row.run_id] = by_run.get(row.run_id, 0) + 1

    contested = sorted(
        (
            {
                'criterion_id': c['criterion_id'],
                'statement': c['statement'],
                'disagree_rate': round(c['disagree'] / c['total'], 3),
            }
            for c in by_criterion.values()
            if c['disagree'] > 0
        ),
        key=lambda c: c['disagree_rate'],
        reverse=True,
    )
    runs_ranked = sorted(
        (
            {'run_id': run_id, 'disagreements': count}
            for run_id, count in by_run.items()
        ),
        key=lambda r: r['disagreements'],
        reverse=True,
    )

    return {
        'overall_agreement_rate': round(agree / total, 3),
        'total_feedback': total,
        'by_check_type': {
            ct: round(vals[1] / vals[0], 3) for ct, vals in by_type.items()
        },
        'most_contested_criteria': contested[:10],
        'runs_with_most_disagreements': runs_ranked[:10],
    }
