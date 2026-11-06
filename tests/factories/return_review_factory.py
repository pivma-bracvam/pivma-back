"""Retorno ao proponente com dados commitados para corridas reais (Spec 046).

Como em `test_per_laboratory_concurrency.py`, duas conexões independentes só
enxergam dados commitados. O template de sonda evita commitar os oficiais, e
a limpeza apaga tudo o que o caso criou, em ordem de dependência.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from pivma.bootstrap_process_templates import sync_template_from_dict
from pivma.core import pre_evaluation_service
from pivma.core.database.models import EvaluationAssignment, ProcessInstance
from pivma.core.process_engine import (
    RETURN_SOURCE_TRIAGE,
    ConflictError,
    instantiate_process,
    open_return_review,
    submit_activity_form,
)
from tests.ai_eval_helpers import NON_COMPLIANT_STATEMENT
from tests.factories.evaluation_factory import (
    EvaluationCriterionFactory,
    EvaluationDefinitionFactory,
    EvaluationVersionFactory,
)
from tests.factories.sample_factory import _user

PROBE_KEY = 'return_review_probe'
FORM_KEY = 'return_probe_v1'
PROBE_TEMPLATE = {
    'process_template': {
        'key': PROBE_KEY,
        'name': 'Retorno ao proponente',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_submission',
            'name': 'Submissão',
            'order_index': 1,
            'activities': [
                {
                    'key': 'proposal_submission',
                    'name': 'Submissão da Proposta',
                    'order_index': 1,
                    'assigned_role': 'proponent',
                    'access': {'edit': ['proponent'], 'view': []},
                    'form_template_key': FORM_KEY,
                    'dependencies': [],
                },
                {
                    'key': 'triage_evaluation',
                    'name': 'Triagem',
                    'order_index': 2,
                    'assigned_role': 'bracvam',
                    'access': {'edit': ['bracvam'], 'view': []},
                    'dependencies': [
                        {'required_activity_key': 'proposal_submission'}
                    ],
                },
                {
                    'key': 'submission_return_review',
                    'name': 'Revisão do Retorno',
                    'order_index': 3,
                    'assigned_role': 'proponent',
                    'access': {'edit': ['proponent'], 'view': []},
                    'activity_type': 'return_review',
                    'sla_hours': 168,
                    'dependencies': [],
                },
            ],
        }
    ],
    'forms': [
        {
            'key': FORM_KEY,
            'name': 'Submissão de sonda',
            'version': 1,
            'fields': [
                {
                    'field_key': 'summary',
                    'label': 'Resumo',
                    'field_type': 'text',
                    'is_required': True,
                    'order_index': 1,
                }
            ],
        }
    ],
}

PROCESSES = (
    'SELECT i.id FROM process_instances i '
    'JOIN process_template_versions v ON v.id = i.template_version_id '
    'JOIN process_templates t ON t.id = v.template_id '
    f"WHERE t.key = '{PROBE_KEY}'"
)
IN_PROCESS = f'WHERE process_instance_id IN ({PROCESSES})'
ACTIVITIES = f'SELECT id FROM activity_instances {IN_PROCESS}'
RUNS = (
    'SELECT id FROM activity_runs '
    f'WHERE activity_instance_id IN ({ACTIVITIES})'
)
IN_RUN = f'WHERE activity_run_id IN ({RUNS})'
FORM_TEMPLATES = f"SELECT id FROM form_templates WHERE key = '{FORM_KEY}'"
# As definições da avaliação entram como `:d`, lidas antes da limpeza.
PURGE = (
    f'DELETE FROM notifications {IN_PROCESS}',
    f'DELETE FROM direct_review_requests {IN_PROCESS}',
    f'DELETE FROM audit_events {IN_PROCESS}',
    'DELETE FROM evaluation_run_items WHERE run_id IN '
    f'(SELECT id FROM evaluation_runs {IN_PROCESS})',
    f'DELETE FROM evaluation_runs {IN_PROCESS}',
    'DELETE FROM form_values WHERE form_instance_id IN '
    f'(SELECT id FROM form_instances {IN_RUN})',
    f'DELETE FROM artifacts {IN_PROCESS}',
    f'DELETE FROM form_instances {IN_RUN}',
    f'DELETE FROM tasks {IN_RUN}',
    f'DELETE FROM activity_runs WHERE activity_instance_id IN ({ACTIVITIES})',
    'DELETE FROM activity_dependencies '
    f'WHERE dependent_activity_id IN ({ACTIVITIES})',
    f'DELETE FROM assignments {IN_PROCESS}',
    f'DELETE FROM activity_instances {IN_PROCESS}',
    f'DELETE FROM phases {IN_PROCESS}',
    f'DELETE FROM process_instances WHERE id IN ({PROCESSES})',
    'DELETE FROM process_template_versions WHERE template_id IN '
    f"(SELECT id FROM process_templates WHERE key = '{PROBE_KEY}')",
    f"DELETE FROM process_templates WHERE key = '{PROBE_KEY}'",
    'DELETE FROM evaluation_assignments '
    f'WHERE form_template_id IN ({FORM_TEMPLATES})',
    'DELETE FROM evaluation_criteria WHERE version_id IN '
    '(SELECT id FROM evaluation_versions WHERE definition_id = ANY(:d))',
    'DELETE FROM evaluation_versions WHERE definition_id = ANY(:d)',
    'DELETE FROM evaluation_definitions WHERE id = ANY(:d)',
    f'DELETE FROM form_fields WHERE form_template_id IN ({FORM_TEMPLATES})',
    f"DELETE FROM form_templates WHERE key = '{FORM_KEY}'",
    'DELETE FROM process_code_sequences '
    'WHERE created_by = ANY(:u) OR updated_by = ANY(:u)',
    'DELETE FROM users WHERE id = ANY(:u)',
)


async def _publish_blocking_evaluation(session, form_template) -> None:
    """Critério bloqueante que o conteúdo não cumpre, na IA fake."""
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    version = EvaluationVersionFactory(
        definition=definition, status='published'
    )
    session.add(version)
    await session.flush()
    session.add(
        EvaluationCriterionFactory(
            version=version,
            severity='critical',
            statement=NON_COMPLIANT_STATEMENT,
        )
    )
    session.add(
        EvaluationAssignment(
            form_template_id=form_template.id,
            definition_id=definition.id,
            target_type='form',
        )
    )
    await session.commit()


async def _build(session, ctx, state) -> None:
    _, version, [form_template] = await sync_template_from_dict(
        session, PROBE_TEMPLATE
    )
    ctx.proponent = await _user(session)
    ctx.admin = await _user(session)
    if state != 'triage_return':
        await _publish_blocking_evaluation(session, form_template)
    process = await instantiate_process(
        session, version, 'Retorno concorrente', ctx.proponent.id
    )
    await session.commit()
    ctx.process_id = process.id
    _, _, _, evaluation_run = await submit_activity_form(
        session,
        process.id,
        'proposal_submission',
        {'summary': 'Resumo do método.'},
        ctx.proponent.id,
    )
    if state == 'triage_return':
        await open_return_review(
            session,
            process.id,
            source=RETURN_SOURCE_TRIAGE,
            user_id=ctx.admin.id,
        )
        await session.commit()
        return
    ctx.evaluation_run_id = evaluation_run.id
    if state == 'ai_failed':
        await pre_evaluation_service._mark_failed(session, evaluation_run.id)


async def _purge(engine: AsyncEngine, ctx) -> None:
    async with engine.begin() as conn:
        definitions = await conn.scalars(
            sa.text(
                'SELECT definition_id FROM evaluation_assignments '
                f'WHERE form_template_id IN ({FORM_TEMPLATES})'
            )
        )
        params = {
            'd': list(definitions),
            'u': [ctx.proponent.id, ctx.admin.id],
        }
        for statement in PURGE:
            await conn.execute(sa.text(statement), params)


@asynccontextmanager
async def committed_return_review(
    engine: AsyncEngine, state: str
) -> AsyncIterator[SimpleNamespace]:
    """`state`: `triage_return`, `ai_failed` ou `ai_in_progress`."""
    ctx = SimpleNamespace()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as setup:
            await _build(setup, ctx, state)
        yield ctx
    finally:
        await _purge(engine, ctx)
        async with AsyncSession(engine) as check:
            leftover = await check.scalar(
                select(func.count())
                .select_from(ProcessInstance)
                .where(ProcessInstance.id == ctx.process_id)
            )
        assert leftover == 0


def split_outcomes(results: list) -> tuple[list, list]:
    """Separa vitórias de conflitos; qualquer outro erro falha o teste."""
    conflicts = [r for r in results if isinstance(r, BaseException)]
    for error in conflicts:
        assert isinstance(error, ConflictError), repr(error)
    return [r for r in results if r not in conflicts], conflicts


async def count_rows(engine: AsyncEngine, model, *conditions) -> int:
    async with AsyncSession(engine) as check:
        return await check.scalar(
            select(func.count()).select_from(model).where(*conditions)
        )
