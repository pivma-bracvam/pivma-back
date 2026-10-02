"""Matriz de acesso à execução de um laboratório no motor (Spec 037).

Laboratório A é `labs[0]`, laboratório B é `labs[1]`. O template concede ver
o recebimento ao líder, ao Grupo de Seleção de Amostras e ao estatístico,
para que a negação venha do filtro de laboratório (research R4).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from pivma.core.database.models import Assignment, RoleAssignmentInvite
from pivma.core.invite_service import accept_invite, hash_invite_token
from pivma.core.process_engine import (
    LABORATORY_RUN_NOT_FOUND,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    complete_laboratory_run,
    require_laboratory_run_access,
)
from tests.factories.laboratory_run_factory import (
    LAB_ACCESS_TEMPLATE,
    activity,
    affiliate,
    all_labs_done,
    complete_lab,
    end_affiliation,
    frozen_lab_process,
    lead_and_participant,
    lead_of_lab,
    runs_by_lab,
)
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
)
from tests.factories.sample_factory import new_laboratory

LAB_A, LAB_B = 0, 1


async def _process(session):
    return await frozen_lab_process(session, template=LAB_ACCESS_TEMPLATE)


async def _read(session, ctx, user_id, lab_index, key='receipt'):
    act = await activity(session, ctx.process_id, key)
    run = (await runs_by_lab(session, ctx.process_id, key))[
        ctx.labs[lab_index].id
    ]
    await require_laboratory_run_access(session, user_id, act, run, 'view')


async def _complete(session, ctx, user_id, laboratory_id):
    return await complete_laboratory_run(
        session, ctx.process_id, 'receipt', laboratory_id, user_id
    )


async def _lead_of_lab_b(session, ctx):
    return await lead_of_lab(session, ctx, LAB_B)


async def _lead_of_b_participant_of_a(session, ctx):
    return await lead_and_participant(session, ctx, LAB_B, LAB_A)


async def _unaffiliated_participant_of_b(session, ctx):
    await end_affiliation(session, ctx.lab_users[LAB_B])
    return ctx.lab_users[LAB_B]


async def _user(session, ctx, profile):
    builders = {
        'lead_of_b': _lead_of_lab_b,
        'unaffiliated_b': _unaffiliated_participant_of_b,
    }
    if profile in builders:
        return await builders[profile](session, ctx)
    return {
        'sample_selection_group': ctx.selector,
        'statistician': ctx.statistician,
        'group_manager': ctx.group_manager,
    }[profile]


# --- US1: outro laboratório recebe "não encontrado" -------------------------


@pytest.mark.asyncio
async def test_other_lab_run_and_missing_run_get_identical_error(session):
    """SC-002: a resposta não distingue "de outro" de "não existe"."""
    ctx = await _process(session)
    stranger_id = (await new_laboratory(session)).id
    user_id, lab_b = ctx.lab_users[LAB_A].id, ctx.labs[LAB_B].id

    with pytest.raises(NotFoundError) as other_lab:
        await _complete(session, ctx, user_id, lab_b)
    await session.rollback()
    with pytest.raises(NotFoundError) as missing:
        await _complete(session, ctx, user_id, stranger_id)

    assert str(other_lab.value) == str(missing.value)
    assert str(other_lab.value) == LABORATORY_RUN_NOT_FOUND


@pytest.mark.asyncio
async def test_other_lab_cannot_read_run(session):
    ctx = await _process(session)

    with pytest.raises(NotFoundError, match=LABORATORY_RUN_NOT_FOUND):
        await _read(session, ctx, ctx.lab_users[LAB_A].id, LAB_B)


@pytest.mark.asyncio
async def test_completed_run_of_other_lab_stays_not_found(session):
    ctx = await _process(session)
    await complete_lab(session, ctx, 'receipt', LAB_B)

    with pytest.raises(NotFoundError) as denied:
        await _complete(
            session, ctx, ctx.lab_users[LAB_A].id, ctx.labs[LAB_B].id
        )

    assert str(denied.value) == LABORATORY_RUN_NOT_FOUND


# --- US2: o próprio laboratório segue trabalhando ---------------------------


@pytest.mark.asyncio
async def test_owner_reads_own_run(session):
    ctx = await _process(session)

    await _read(session, ctx, ctx.lab_users[LAB_A].id, LAB_A)


@pytest.mark.asyncio
async def test_owner_completes_own_run(session):
    ctx = await _process(session)

    run = await _complete(
        session, ctx, ctx.lab_users[LAB_A].id, ctx.labs[LAB_A].id
    )

    assert run.status == 'COMPLETED'


@pytest.mark.asyncio
async def test_process_wide_run_follows_activity_rule_only(session):
    ctx = await _process(session)
    await all_labs_done(session, ctx)
    act = await activity(session, ctx.process_id, 'statistics')
    run = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]

    await require_laboratory_run_access(
        session, ctx.statistician.id, act, run, 'view'
    )


# --- US3: regras por perfil -------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'profile',
    [
        'lead_of_b',
        'sample_selection_group',
        'statistician',
        'unaffiliated_b',
    ],
)
async def test_profile_without_lab_access_cannot_read_lab_b_run(
    session, profile
):
    ctx = await _process(session)
    user = await _user(session, ctx, profile)

    with pytest.raises(NotFoundError):
        await _read(session, ctx, user.id, LAB_B)


@pytest.mark.asyncio
@pytest.mark.parametrize('profile', ['group_manager', 'admin', 'bracvam'])
async def test_process_manager_reads_lab_b_run(
    session, profile, ai_eval_admin, bracvam_user
):
    ctx = await _process(session)
    user = {'admin': ai_eval_admin, 'bracvam': bracvam_user}.get(profile)
    user = user or await _user(session, ctx, profile)

    await _read(session, ctx, user.id, LAB_B)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'profile', ['lead_of_b', 'sample_selection_group', 'statistician']
)
async def test_viewer_without_edit_grant_is_refused_by_activity(
    session, profile
):
    """A negação cita só a atividade, nunca o laboratório."""
    ctx = await _process(session)
    user = await _user(session, ctx, profile)

    with pytest.raises(AuthorizationError) as denied:
        await _complete(session, ctx, user.id, ctx.labs[LAB_B].id)

    assert 'laboratório' not in str(denied.value)


@pytest.mark.asyncio
async def test_bracvam_without_edit_grant_cannot_complete(
    session, bracvam_user
):
    ctx = await _process(session)

    with pytest.raises(AuthorizationError):
        await _complete(session, ctx, bracvam_user.id, ctx.labs[LAB_B].id)


@pytest.mark.asyncio
async def test_group_manager_with_conflict_reads_but_cannot_complete(
    session,
):
    ctx = await _process(session)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.user_id == ctx.group_manager.id,
        )
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    await _read(session, ctx, ctx.group_manager.id, LAB_B)
    with pytest.raises(AuthorizationError):
        await _complete(session, ctx, ctx.group_manager.id, ctx.labs[LAB_B].id)


@pytest.mark.asyncio
async def test_lead_of_b_and_participant_of_a_works_only_on_a(session):
    ctx = await _process(session)
    user = await _lead_of_b_participant_of_a(session, ctx)

    await _read(session, ctx, user.id, LAB_A)
    run = await _complete(session, ctx, user.id, ctx.labs[LAB_A].id)

    assert run.status == 'COMPLETED'


@pytest.mark.asyncio
async def test_lead_of_b_and_participant_of_a_cannot_read_b(session):
    ctx = await _process(session)
    user = await _lead_of_b_participant_of_a(session, ctx)

    with pytest.raises(NotFoundError):
        await _read(session, ctx, user.id, LAB_B)


@pytest.mark.asyncio
async def test_lead_of_b_and_participant_of_a_cannot_complete_b(session):
    ctx = await _process(session)
    user = await _lead_of_b_participant_of_a(session, ctx)

    with pytest.raises(NotFoundError):
        await _complete(session, ctx, user.id, ctx.labs[LAB_B].id)


# --- US4: uma designação de participante por usuário no processo ------------


@pytest.mark.asyncio
async def test_invite_for_second_participating_lab_is_duplicate(session):
    """Regra existente: o índice único de designação ativa (research R3)."""
    ctx = await _process(session)
    user = ctx.lab_users[LAB_A]
    await affiliate(session, user, ctx.labs[LAB_B])
    invite = RoleAssignmentInvite(
        process_instance_id=ctx.process_id,
        role_key='participating_laboratory',
        email=user.email,
        token_hash=hash_invite_token('second-lab'),
        expires_at=datetime.utcnow() + timedelta(days=1),
        laboratory_id=ctx.labs[LAB_B].id,
    )
    session.add(invite)
    await session.commit()
    process_id, user_id = ctx.process_id, user.id
    lab_a = ctx.labs[LAB_A].id

    with pytest.raises(ConflictError) as denied:
        await accept_invite(session, invite, user)

    assert denied.value.code == 'duplicate'
    designations = await session.scalars(
        select(Assignment.laboratory_id).where(
            Assignment.process_instance_id == process_id,
            Assignment.user_id == user_id,
        )
    )
    assert list(designations) == [lab_a]
