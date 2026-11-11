# ruff: noqa: PLR2004
"""Revisão do retorno ao proponente (Spec 030, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    DirectReviewRequest,
    EvaluationRun,
    FieldReview,
    FormInstance,
    Notification,
    ProcessInstance,
    Task,
)
from pivma.core.process_engine import get_current_form_instance
from tests.activity_state import activity_status, in_triage
from tests.ai_eval_helpers import (
    FULL_VALUES,
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.structure_approval_factory import (
    decide,
    runs,
    structure_process,
)
from tests.factories.submission_factory import submission_values
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
KEY = 'submission_return_review'
VALUES = submission_values('Ensaio RhCE para irritação')
SUBMISSION_FORM = 'submission_pre_validated_v1'


def _review_url(pid):
    return f'/processes/{pid}/return-review'


def _choose(client, pid, choice, justification=None, headers=ORIGIN):
    return client.post(
        _review_url(pid),
        json={'choice': choice, 'justification': justification},
        headers=headers,
    )


async def _review_runs(session, pid):
    return list(
        await session.scalars(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == pid,
                ActivityInstance.key == KEY,
            )
            .order_by(ActivityRun.run_number)
            .execution_options(populate_existing=True)
        )
    )


async def _review_tasks(session, pid):
    return list(
        await session.scalars(
            select(Task)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == pid,
                ActivityInstance.key == KEY,
            )
            .execution_options(populate_existing=True)
        )
    )


async def _submission_run_count(session, pid):
    return len(
        list(
            await session.scalars(
                select(ActivityRun.id)
                .join(ActivityInstance)
                .where(
                    ActivityInstance.process_instance_id == pid,
                    ActivityInstance.key == 'proposal_submission',
                )
            )
        )
    )


async def _created_process(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Processo 1'},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return proponent, response.json()['id']


def _form(client, pid, activity='proposal_submission', **params):
    response = client.get(
        f'/processes/{pid}/activities/{activity}/form', params=params
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _version(client, pid, run_number):
    response = client.get(f'/processes/{pid}/submission-versions/{run_number}')
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _save_review(client, pid, field_key, comments):
    return client.post(
        f'/processes/{pid}/triage/reviews',
        json={
            'reviews': [
                {
                    'field_key': field_key,
                    'status': 'NAO_CONFORME',
                    'comments': comments,
                }
            ]
        },
        headers=ORIGIN,
    )


def _submit_and_return(  # noqa: PLR0913, PLR0917
    client, pid, proponent, bracvam_user, justification, reviews
):
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return _triage_decides_return(
        client, pid, proponent, bracvam_user, justification, reviews
    )


def _triage_decides_return(  # noqa: PLR0913, PLR0917
    client, pid, proponent, bracvam_user, justification, reviews
):
    authenticate(client, bracvam_user)
    for field_key, comments in reviews.items():
        saved = _save_review(client, pid, field_key, comments)
        assert saved.status_code == HTTPStatus.OK, saved.text
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': justification or 'Incluir histórico.',
        },
        headers=ORIGIN,
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    authenticate(client, proponent)
    return decision.json()


async def _triage_return(
    client, session, bracvam_user, *, justification=None, reviews=None
):
    proponent, pid = await _created_process(client, session)
    decision = _submit_and_return(
        client, pid, proponent, bracvam_user, justification, reviews or {}
    )
    return proponent, pid, decision


async def _ai_submission(client, session, ai_eval_admin):
    """Submissão com a pré-avaliação por IA em andamento."""
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    return proponent, result['process_id'], run_id


async def _ai_return(client, session, ai_eval_admin, *, failed=False):
    proponent, pid, run_id = await _ai_submission(
        client, session, ai_eval_admin
    )
    if failed:
        await svc._mark_failed(session, run_id)
    else:
        await svc._execute(session, run_id)
    authenticate(client, proponent)
    return proponent, pid, run_id


# --- Abertura -------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_process_has_blocked_return_review_without_run(
    client, session
):
    _, pid = await _created_process(client, session)

    assert await activity_status(session, pid, KEY) == 'BLOCKED'
    assert await _review_runs(session, pid) == []
    assert await _review_tasks(session, pid) == []


@pytest.mark.asyncio
async def test_triage_needs_revision_opens_return_review(
    client, session, bracvam_user
):
    _, pid, decision = await _triage_return(client, session, bracvam_user)

    runs = await _review_runs(session, pid)
    tasks = await _review_tasks(session, pid)
    assert [r.status for r in runs] == ['IN_PROGRESS']
    assert [(t.status, t.assigned_role) for t in tasks] == [
        ('READY', 'proponent')
    ]
    assert decision['return_review_run'] == 1
    assert 'next_activity_run' not in decision
    assert await _submission_run_count(session, pid) == 1


@pytest.mark.asyncio
async def test_triage_rejection_does_not_open_return_review(
    client, session, bracvam_user
):
    _, pid = await _created_process(client, session)
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    authenticate(client, bracvam_user)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'REJECTED', 'justification': 'Fora do escopo.'},
        headers=ORIGIN,
    )

    assert response.json()['return_review_run'] is None
    assert await _review_runs(session, pid) == []


@pytest.mark.asyncio
async def test_triage_approval_does_not_open_return_review(
    client, session, bracvam_user
):
    _, pid = await _created_process(client, session)
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    authenticate(client, bracvam_user)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers=ORIGIN,
    )

    assert response.json()['return_review_run'] is None
    assert await _review_runs(session, pid) == []


@pytest.mark.asyncio
async def test_return_review_opened_event_is_audited(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == pid,
            AuditEvent.event_type == 'RETURN_REVIEW_OPENED',
        )
    )
    assert event is not None
    assert event.context_data['source'] == 'TRIAGE'


# --- Leitura --------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_return_review_from_triage_shows_decision(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(
        client, session, bracvam_user, justification='Faltam controles.'
    )

    response = client.get(_review_url(pid))

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body['source'] == 'TRIAGE'
    assert body['run_number'] == 1
    assert body['triage_decision']['outcome'] == 'NEEDS_REVISION'
    assert body['triage_decision']['justification'] == 'Faltam controles.'
    assert body['ai_pre_evaluation'] is None
    assert body['available_choices'] == ['REVISE', 'WITHDRAW']


@pytest.mark.asyncio
async def test_get_return_review_from_ai_shows_pre_evaluation(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(client, session, ai_eval_admin)

    body = client.get(_review_url(pid)).json()

    assert body['source'] == 'AI_PRE_EVALUATION'
    assert body['ai_pre_evaluation']['run_id'] == str(run_id)
    assert body['triage_decision'] is None
    assert 'CONTEST_AI' in body['available_choices']


@pytest.mark.asyncio
async def test_get_return_review_404_when_none_open(client, session):
    _, pid = await _created_process(client, session)

    assert client.get(_review_url(pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_return_review_404_for_sponsor(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    sponsor = UserFactory()
    session.add(sponsor)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )
    authenticate(client, sponsor)

    assert client.get(_review_url(pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_return_review_200_for_bracvam_and_admin(
    client, session, bracvam_user, ai_eval_admin
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    for user in (bracvam_user, ai_eval_admin):
        authenticate(client, user)
        assert client.get(_review_url(pid)).status_code == HTTPStatus.OK


# --- Escolhas -------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_opens_new_submission_draft_with_previous_values(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'REVISE')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['submission_run'] == 2
    assert response.json()['process_status'] == 'OPEN'
    form = client.get(
        f'/processes/{pid}/activities/proposal_submission/form'
    ).json()
    assert form['is_submitted'] is False
    assert form['values']['method_title'] == VALUES['method_title']
    assert [r.status for r in await _review_runs(session, pid)] == [
        'COMPLETED'
    ]
    assert await activity_status(session, pid, KEY) == 'BLOCKED'


@pytest.mark.asyncio
async def test_contest_ai_moves_to_triage(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(client, session, ai_eval_admin)

    response = _choose(client, pid, 'CONTEST_AI', 'Discordo da IA.')

    assert response.status_code == HTTPStatus.OK, response.text
    assert await in_triage(session, pid)
    request = await session.scalar(
        select(DirectReviewRequest).where(
            DirectReviewRequest.evaluation_run_id == run_id
        )
    )
    assert request is not None


@pytest.mark.asyncio
async def test_contest_ai_rejected_for_triage_source(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'CONTEST_AI')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_withdraw_closes_process(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'WITHDRAW', 'Vamos reformular o método.')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['process_status'] == 'CLOSED'
    process = await session.get(ProcessInstance, pid, populate_existing=True)
    assert process.status == 'CLOSED'
    assert process.closure_reason
    pending = [
        t
        for t in await session.scalars(
            select(Task)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == pid)
            .execution_options(populate_existing=True)
        )
        if t.status not in {'COMPLETED', 'CANCELLED'}
    ]
    assert pending == []


@pytest.mark.asyncio
async def test_choice_is_audited(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    _choose(client, pid, 'REVISE', 'Vou ajustar.')

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == pid,
            AuditEvent.event_type == 'RETURN_REVIEW_DECIDED',
        )
    )
    assert event.context_data == {
        'choice': 'REVISE',
        'source': 'TRIAGE',
        'justification': 'Vou ajustar.',
        'run_number': 1,
    }


@pytest.mark.asyncio
async def test_bracvam_cannot_choose(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    authenticate(client, bracvam_user)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_cannot_choose(
    client, session, bracvam_user, ai_eval_admin
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    authenticate(client, ai_eval_admin)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_sponsor_choice_is_404(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    sponsor = UserFactory()
    session.add(sponsor)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )
    authenticate(client, sponsor)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_second_choice_is_conflict(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    response = _choose(client, pid, 'WITHDRAW')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_choice_on_closed_process_is_conflict(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    process = await session.get(ProcessInstance, pid)
    process.status = 'CANCELLED'
    await session.commit()

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_choice_requires_trusted_origin(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'REVISE', headers={})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_submission_locked_while_return_review_open(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = client.put(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_admin_retry_cancels_open_return_review(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert [r.status for r in await _review_runs(session, pid)] == [
        'IN_PROGRESS'
    ]
    authenticate(client, ai_eval_admin)

    response = client.post(
        f'/admin/pre-evaluations/{run_id}/retry', headers=ORIGIN
    )

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    assert [r.status for r in await _review_runs(session, pid)] == [
        'CANCELLED'
    ]
    assert [t.status for t in await _review_tasks(session, pid)] == [
        'CANCELLED'
    ]
    assert await activity_status(session, pid, KEY) == 'BLOCKED'


# --- Pareceres da rodada devolvida (Spec 046, US1) ------------------------


async def _revised(client, session, bracvam_user, reviews):
    """Rodada 1 devolvida com pareceres e rodada 2 aberta pelo proponente."""
    proponent, pid, _ = await _triage_return(
        client, session, bracvam_user, reviews=reviews
    )
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK
    return proponent, pid


def _remove_field(client, admin, field_key):
    url = f'/processes/templates/pre_validated_method/forms/{SUBMISSION_FORM}'
    authenticate(client, admin)
    detail = client.get(url).json()
    response = client.put(
        url,
        json={
            'name': detail['name'],
            'description': detail['description'],
            'fields': [
                field
                for field in detail['fields']
                if field['field_key'] != field_key
            ],
        },
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


@pytest.mark.asyncio
async def test_form_previous_reviews_empty_on_first_run(client, session):
    _, pid = await _created_process(client, session)

    assert _form(client, pid)['previous_reviews'] == {}


@pytest.mark.asyncio
async def test_form_previous_reviews_empty_when_previous_run_has_no_reviews(
    client, session, bracvam_user
):
    _, pid = await _revised(client, session, bracvam_user, {})

    assert _form(client, pid)['previous_reviews'] == {}


@pytest.mark.asyncio
async def test_form_previous_reviews_empty_for_other_activities(
    client, session, bracvam_user
):
    """O plano na execução 2 não pode herdar os pareceres da submissão 1."""
    ctx = await structure_process(session, bracvam_user)
    _, _, form, _, fields = await get_current_form_instance(
        session, ctx.process_id, 'proposal_submission'
    )
    [triage_run] = await runs(session, ctx.process_id, 'triage_evaluation')
    session.add(
        FieldReview(
            form_instance_id=form.id,
            form_field_id=fields[0].id,
            activity_run_id=triage_run.id,
            status='NAO_CONFORME',
            reviewed_by=bracvam_user.id,
        )
    )
    await session.commit()
    authenticate(client, bracvam_user)
    rejected = decide(
        client,
        ctx.process_id,
        outcome='REJECTED',
        justification='Plano incompleto.',
        rejected_points=[
            {'activity_key': 'statistical_plan', 'reason': 'Refazer o plano.'}
        ],
    )
    assert rejected.status_code == HTTPStatus.OK, rejected.text

    form = _form(client, ctx.process_id, 'statistical_plan', run_number=2)

    assert form['previous_reviews'] == {}
    assert _form(client, ctx.process_id)['reviews'] != {}


@pytest.mark.asyncio
async def test_form_previous_reviews_follows_requested_run_number(
    client, session, bracvam_user
):
    proponent, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rodada 1.'}
    )
    _submit_and_return(
        client,
        pid,
        proponent,
        bracvam_user,
        None,
        {'application_area': 'Rodada 2.'},
    )
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    second = _form(client, pid, run_number=2)
    first = _form(client, pid, run_number=1)

    assert list(second['previous_reviews']) == ['method_title']
    assert list(second['reviews']) == ['application_area']
    assert first['previous_reviews'] == {}


@pytest.mark.asyncio
async def test_form_previous_reviews_keeps_removed_field(
    client, session, bracvam_user, ai_eval_admin
):
    proponent, pid = await _revised(
        client, session, bracvam_user, {'application_area': 'Rever.'}
    )
    _remove_field(client, ai_eval_admin, 'application_area')
    authenticate(client, proponent)

    form = _form(client, pid)

    assert form['previous_reviews']['application_area']['comments'] == 'Rever.'
    assert 'application_area' not in {f['field_key'] for f in form['fields']}


@pytest.mark.asyncio
async def test_version_reviews_keeps_removed_field(
    client, session, bracvam_user, ai_eval_admin
):
    proponent, pid = await _revised(
        client, session, bracvam_user, {'application_area': 'Rever.'}
    )
    _remove_field(client, ai_eval_admin, 'application_area')
    authenticate(client, proponent)

    version = _version(client, pid, 1)

    assert version['reviews']['application_area']['comments'] == 'Rever.'


@pytest.mark.asyncio
async def test_form_previous_reviews_only_immediately_previous_run(
    client, session, ai_eval_admin, bracvam_user, fake_provider
):
    """Rodada 1 devolvida pela triagem e rodada 2 devolvida pela IA."""
    del fake_provider
    proponent, pid, _ = await _ai_return(client, session, ai_eval_admin)
    assert _choose(client, pid, 'CONTEST_AI').status_code == HTTPStatus.OK
    _triage_decides_return(
        client, pid, proponent, bracvam_user, None, {'method_title': 'Rever.'}
    )
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK
    submitted = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': FULL_VALUES},
        headers=ORIGIN,
    )
    assert submitted.status_code == HTTPStatus.OK, submitted.text
    await svc._execute(
        session, UUID(submitted.json()['pre_evaluation']['run_id'])
    )
    authenticate(client, proponent)
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    assert _form(client, pid)['previous_reviews'] == {}
    assert list(_version(client, pid, 1)['reviews']) == ['method_title']


@pytest.mark.asyncio
async def test_version_reviews_empty_when_returned_by_ai(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, _ = await _ai_return(client, session, ai_eval_admin)
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    assert _version(client, pid, 1)['reviews'] == {}


@pytest.mark.asyncio
async def test_triage_cannot_change_reviews_of_returned_run(
    client, session, bracvam_user
):
    proponent, pid, _ = await _triage_return(
        client, session, bracvam_user, reviews={'method_title': 'Original.'}
    )
    before = _version(client, pid, 1)['reviews']
    authenticate(client, bracvam_user)

    response = _save_review(client, pid, 'method_title', 'Alterado.')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'
    authenticate(client, proponent)
    assert _version(client, pid, 1)['reviews'] == before


@pytest.mark.asyncio
async def test_reviews_responses_do_not_identify_reviewer(
    client, session, bracvam_user
):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rever.'}
    )

    form = client.get(f'/processes/{pid}/activities/proposal_submission/form')
    version = client.get(f'/processes/{pid}/submission-versions/1')

    for parecer in (
        form.json()['previous_reviews']['method_title'],
        version.json()['reviews']['method_title'],
    ):
        assert set(parecer) == {'status', 'comments', 'reviewed_at'}
    for body in (form.text, version.text):
        assert str(bracvam_user.id) not in body
        assert bracvam_user.full_name not in body
        assert bracvam_user.email not in body


@pytest.mark.asyncio
async def test_timeline_does_not_identify_reviewer_to_proponent(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(
        client, session, bracvam_user, reviews={'method_title': 'Rever.'}
    )

    response = client.get(
        f'/processes/{pid}/timeline', params={'per_page': 100}
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert str(bracvam_user.id) not in response.text


@pytest.mark.asyncio
async def test_timeline_keeps_return_author_for_bracvam(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    authenticate(client, bracvam_user)

    events = client.get(
        f'/processes/{pid}/timeline', params={'per_page': 100}
    ).json()['data']

    [opened] = [e for e in events if e['event_type'] == 'RETURN_REVIEW_OPENED']
    assert opened['user_id'] == str(bracvam_user.id)


@pytest.mark.asyncio
async def test_stranger_gets_404_on_form_with_previous_reviews(
    client, session, bracvam_user, other_user
):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Segredo da rodada.'}
    )
    authenticate(client, other_user)

    response = client.get(
        f'/processes/{pid}/activities/proposal_submission/form'
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Segredo da rodada.' not in response.text


@pytest.mark.asyncio
async def test_stranger_gets_404_on_version_with_reviews(
    client, session, bracvam_user, other_user
):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Segredo da rodada.'}
    )
    authenticate(client, other_user)

    response = client.get(f'/processes/{pid}/submission-versions/1')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Segredo da rodada.' not in response.text


@pytest.mark.asyncio
async def test_versions_listing_has_no_reviews(client, session, bracvam_user):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rever.'}
    )

    [item] = client.get(f'/processes/{pid}/submission-versions').json()['data']

    assert 'reviews' not in item


@pytest.mark.asyncio
async def test_return_review_404_after_decision_with_reviews(
    client, session, bracvam_user
):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rever.'}
    )

    assert client.get(_review_url(pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_soft_deleted_review_is_hidden(client, session, bracvam_user):
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rever.'}
    )
    assert list(_form(client, pid)['previous_reviews']) == ['method_title']
    review = await session.scalar(
        select(FieldReview)
        .join(FormInstance)
        .join(ActivityRun, ActivityRun.id == FormInstance.activity_run_id)
        .join(ActivityInstance)
        .where(ActivityInstance.process_instance_id == pid)
    )
    review.set_deletion_audit(bracvam_user.id)
    await session.commit()

    assert _form(client, pid)['previous_reviews'] == {}
    assert _version(client, pid, 1)['reviews'] == {}


# --- Reprocessamento da IA (Spec 046, FR-016a) -----------------------------


def _retry(client, admin, run_id):
    authenticate(client, admin)
    return client.post(
        f'/admin/pre-evaluations/{run_id}/retry', headers=ORIGIN
    )


async def _evaluation_run_count(session, pid):
    return len(
        list(
            await session.scalars(
                select(EvaluationRun.id).where(
                    EvaluationRun.process_instance_id == pid
                )
            )
        )
    )


def _assert_conflict(response):
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()['detail']['code'] == 'conflict'


@pytest.mark.asyncio
async def test_retry_in_progress_run_is_conflict(
    client, session, ai_eval_admin
):
    _, pid, run_id = await _ai_submission(client, session, ai_eval_admin)

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 1


@pytest.mark.asyncio
async def test_retry_older_failed_run_is_conflict(
    client, session, ai_eval_admin
):
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    first = _retry(client, ai_eval_admin, run_id)
    assert first.status_code == HTTPStatus.ACCEPTED, first.text

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 2


@pytest.mark.asyncio
async def test_retry_after_revise_is_conflict(client, session, ai_eval_admin):
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 1
    assert await _submission_run_count(session, pid) == 2


@pytest.mark.asyncio
async def test_retry_after_contest_is_conflict(client, session, ai_eval_admin):
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert _choose(client, pid, 'CONTEST_AI').status_code == HTTPStatus.OK

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 1
    assert await in_triage(session, pid)
    request = await session.scalar(
        select(DirectReviewRequest).where(
            DirectReviewRequest.evaluation_run_id == run_id
        )
    )
    assert request is not None


@pytest.mark.asyncio
async def test_retry_after_contest_and_triage_return_is_conflict(
    client, session, ai_eval_admin, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert _choose(client, pid, 'CONTEST_AI').status_code == HTTPStatus.OK
    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 1
    last_return = (await _review_runs(session, pid))[-1]
    assert (last_return.status, last_return.execution_reason) == (
        'IN_PROGRESS',
        'TRIAGE',
    )
    tasks = await _review_tasks(session, pid)
    assert 'READY' in {t.status for t in tasks}
    pending = await session.scalar(
        select(Notification).where(
            Notification.subject_id == last_return.id,
        )
    )
    assert pending.status == 'pending'


@pytest.mark.asyncio
async def test_version_hides_reviews_until_triage_decides(
    client, session, ai_eval_admin, bracvam_user
):
    proponent, pid, _ = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert _choose(client, pid, 'CONTEST_AI').status_code == HTTPStatus.OK
    authenticate(client, bracvam_user)
    saved = _save_review(client, pid, 'method_title', 'Ainda em edição.')
    assert saved.status_code == HTTPStatus.OK, saved.text

    authenticate(client, proponent)
    assert _version(client, pid, 1)['reviews'] == {}

    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})
    assert (
        _version(client, pid, 1)['reviews']['method_title']['comments']
        == 'Ainda em edição.'
    )


@pytest.mark.asyncio
async def test_retry_completed_run_is_conflict(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(client, session, ai_eval_admin)

    _assert_conflict(_retry(client, ai_eval_admin, run_id))

    assert await _evaluation_run_count(session, pid) == 1


@pytest.mark.asyncio
async def test_rejected_retry_leaves_no_partial_effect(
    client, session, ai_eval_admin, return_email_settings
):
    """Execução antiga com retorno aberto pela execução mais recente."""
    del return_email_settings
    _, pid, old_run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    accepted = _retry(client, ai_eval_admin, old_run_id)
    assert accepted.status_code == HTTPStatus.ACCEPTED, accepted.text
    await svc._mark_failed(session, UUID(accepted.json()['new_run_id']))

    _assert_conflict(_retry(client, ai_eval_admin, old_run_id))

    last_return = (await _review_runs(session, pid))[-1]
    assert last_return.status == 'IN_PROGRESS'
    assert 'READY' in {t.status for t in await _review_tasks(session, pid)}
    pending = await session.scalar(
        select(Notification)
        .where(Notification.subject_id == last_return.id)
        .execution_options(populate_existing=True)
    )
    assert pending.status == 'pending'
