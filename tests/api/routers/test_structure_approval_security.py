"""Autorização, isolamento e cegamento da homologação (Spec 042).

A homologação só é vista por Admin e BraCVAM e só é decidida pelo BraCVAM
sem conflito de interesse (FR-017). Quem não vê recebe 404, sem saber que a
atividade existe; quem vê sem editar recebe 403. Toda recusa da decisão
confere que nada mudou.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    Artifact,
    BlindSampleCode,
    StudySubstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import (
    AssignmentFactory,
    ConflictInterestDeclarationFactory,
)
from tests.factories.structure_approval_factory import (
    decide,
    panel,
    snapshot,
    structure_process,
)

APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}


async def _assert_hidden(client, session, ctx, user):
    """Painel e decisão respondem 404 e nada muda."""
    before = await snapshot(session, ctx.process_id)
    authenticate(client, user)

    seen = panel(client, ctx.process_id)
    decided = decide(client, ctx.process_id, **APPROVE)

    assert seen.status_code == HTTPStatus.NOT_FOUND, seen.text
    assert decided.status_code == HTTPStatus.NOT_FOUND, decided.text
    assert decided.json()['detail']['code'] == 'not_found'
    assert await snapshot(session, ctx.process_id) == before


@pytest.mark.asyncio
async def test_panel_and_decision_require_session(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    client.cookies.clear()

    seen = panel(client, ctx.process_id)
    decided = decide(client, ctx.process_id, **APPROVE)

    assert seen.status_code == HTTPStatus.UNAUTHORIZED
    assert decided.status_code == HTTPStatus.UNAUTHORIZED
    assert decided.json()['detail']['code'] == 'not_authenticated'


@pytest.mark.asyncio
async def test_user_outside_the_process_gets_not_found(
    client, session, bracvam_user, user
):
    ctx = await structure_process(session, bracvam_user)
    await _assert_hidden(client, session, ctx, user)


@pytest.mark.asyncio
async def test_group_manager_gets_not_found(client, session, bracvam_user):
    ctx = await structure_process(session, bracvam_user)
    await _assert_hidden(client, session, ctx, ctx.manager)


@pytest.mark.asyncio
async def test_participating_laboratory_gets_not_found(
    client, session, bracvam_user
):
    """O painel lista designações de outros laboratórios."""
    ctx = await structure_process(session, bracvam_user)
    await _assert_hidden(client, session, ctx, ctx.lab_users[1])


@pytest.mark.asyncio
async def test_sample_selection_group_gets_not_found(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    await _assert_hidden(client, session, ctx, ctx.selector)


@pytest.mark.asyncio
async def test_admin_reads_the_panel_but_cannot_decide(
    client, session, bracvam_user, ai_eval_admin
):
    ctx = await structure_process(session, bracvam_user)
    before = await snapshot(session, ctx.process_id)
    authenticate(client, ai_eval_admin)

    seen = panel(client, ctx.process_id)
    decided = decide(client, ctx.process_id, **APPROVE)

    assert seen.status_code == HTTPStatus.OK, seen.text
    assert decided.status_code == HTTPStatus.FORBIDDEN
    assert decided.json()['detail']['code'] == 'forbidden'
    assert await snapshot(session, ctx.process_id) == before


@pytest.mark.asyncio
async def test_bracvam_with_conflict_of_interest_cannot_decide(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    assignment = AssignmentFactory(
        process_instance_id=ctx.process_id,
        user_id=bracvam_user.id,
        assigned_by=bracvam_user.id,
        role_key='adhoc_evaluator',
    )
    session.add(assignment)
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()
    before = await snapshot(session, ctx.process_id)
    authenticate(client, bracvam_user)

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'
    assert await snapshot(session, ctx.process_id) == before


@pytest.mark.asyncio
async def test_decision_requires_trusted_origin(client, session, bracvam_user):
    ctx = await structure_process(session, bracvam_user)
    before = await snapshot(session, ctx.process_id)
    authenticate(client, bracvam_user)

    response = client.post(
        f'/processes/{ctx.process_id}/structure-approval/decision',
        json=APPROVE,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'invalid_origin'
    assert await snapshot(session, ctx.process_id) == before


@pytest.mark.asyncio
async def test_process_without_the_activity_gets_not_found(
    client, session, bracvam_user
):
    """FR-003: processo criado com a versão anterior do template."""
    ctx = await structure_process(session, bracvam_user, previous_version=True)
    authenticate(client, bracvam_user)

    seen = panel(client, ctx.process_id)
    decided = decide(client, ctx.process_id, **APPROVE)

    assert seen.status_code == HTTPStatus.NOT_FOUND
    assert decided.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_panel_never_shows_blinded_data(client, session, bracvam_user):
    """SC-005: nada do cegamento aparece no painel."""
    ctx = await structure_process(session, bracvam_user)
    substance = await session.get(StudySubstance, ctx.substance['id'])
    artifact = await session.get(Artifact, substance.sds_artifact_id)
    codes = list(
        await session.scalars(
            select(BlindSampleCode.code).where(
                BlindSampleCode.process_instance_id == ctx.process_id
            )
        )
    )
    assert codes
    authenticate(client, bracvam_user)

    text = panel(client, ctx.process_id).text

    secrets = [
        substance.chemical_name,
        substance.cas_number,
        str(substance.id),
        str(artifact.id),
        artifact.name,
        *codes,
    ]
    for secret in secrets:
        assert secret not in text, secret
