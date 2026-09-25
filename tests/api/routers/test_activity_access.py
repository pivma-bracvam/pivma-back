"""Matriz de acesso por atividade da fase 1 (Spec 030, US2).

Proponente edita a submissão; `sponsor` participa do processo mas não tem
concessão na submissão; BraCVAM e Admin veem tudo e só o BraCVAM edita a
triagem.
"""

from datetime import datetime
from http import HTTPStatus
from types import SimpleNamespace
from uuid import UUID

import pytest
import pytest_asyncio

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_form_attachments import (
    att_url,
    setup_process_with_file_field,
    upload,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
    grant_cargo,
)
from tests.factories.user_factory import UserFactory

FORM = '/processes/{pid}/activities/proposal_submission/form'
VALUES = {'method_title': 'Ensaio RhCE para irritação'}


def _form(pid):
    return FORM.format(pid=pid)


@pytest_asyncio.fixture
async def world(client, session, bracvam_user, ai_eval_admin):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    sponsor = UserFactory()
    session.add_all([proponent, sponsor])
    await session.commit()

    client.headers['Origin'] = 'https://testserver'
    authenticate(client, proponent)
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Processo 1'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    pid = response.json()['id']
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )
    return SimpleNamespace(
        pid=pid,
        proponent=proponent,
        sponsor=sponsor,
        bracvam=bracvam_user,
        admin=ai_eval_admin,
    )


def _submit(client, world):
    authenticate(client, world.proponent)
    response = client.post(_form(world.pid), json={'values': VALUES})
    assert response.status_code == HTTPStatus.OK, response.text


def _decide(client, pid, outcome='APPROVED'):
    return client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': 'Justificativa.'},
    )


@pytest.mark.asyncio
async def test_proponent_reads_submission_form(client, world):
    authenticate(client, world.proponent)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_proponent_saves_submission_draft(client, world):
    authenticate(client, world.proponent)

    response = client.put(_form(world.pid), json={'values': VALUES})

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_sponsor_gets_404_on_submission_form(client, world):
    authenticate(client, world.sponsor)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_sponsor_gets_404_on_submission_draft_save(client, world):
    authenticate(client, world.sponsor)

    response = client.put(_form(world.pid), json={'values': VALUES})

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_second_proponent_edits_submission(client, session, world):
    second = UserFactory()
    session.add(second)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(world.pid), user=second, role_key='proponent'
    )
    authenticate(client, second)

    response = client.put(_form(world.pid), json={'values': VALUES})

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_revoked_proponent_loses_access_immediately(
    client, session, world
):
    second = UserFactory()
    session.add(second)
    await session.commit()
    assignment = await grant_cargo(
        session, process_id=UUID(world.pid), user=second, role_key='proponent'
    )
    assignment.revoked_at = datetime(2026, 9, 1)
    await session.commit()
    authenticate(client, second)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_bracvam_reads_submission_draft(client, world):
    authenticate(client, world.bracvam)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_bracvam_cannot_save_submission_draft(client, world):
    authenticate(client, world.bracvam)

    response = client.put(_form(world.pid), json={'values': VALUES})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_reads_submission_draft_but_cannot_submit(client, world):
    authenticate(client, world.admin)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.OK
    response = client.post(_form(world.pid), json={'values': VALUES})
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_proponent_reads_submitted_form_but_cannot_edit(client, world):
    _submit(client, world)

    assert client.get(_form(world.pid)).status_code == HTTPStatus.OK
    response = client.put(_form(world.pid), json={'values': VALUES})
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_proponent_cannot_decide_triage(client, world):
    _submit(client, world)

    response = _decide(client, world.pid)

    # `triage.review` é exigida antes da concessão: sem ela, 403.
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_cannot_decide_triage(client, world):
    _submit(client, world)
    authenticate(client, world.admin)

    response = _decide(client, world.pid)

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_cannot_save_triage_field_reviews(client, world):
    _submit(client, world)
    authenticate(client, world.admin)

    response = client.post(
        f'/processes/{world.pid}/triage/reviews',
        json={'reviews': [{'field_key': 'method_title', 'status': 'OK'}]},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_bracvam_decides_triage(client, world):
    _submit(client, world)
    authenticate(client, world.bracvam)

    response = _decide(client, world.pid)

    assert response.status_code == HTTPStatus.OK, response.text


@pytest.mark.asyncio
async def test_conflict_of_interest_blocks_bracvam_despite_grant(
    client, session, world
):
    _submit(client, world)
    assignment = await grant_cargo(
        session,
        process_id=UUID(world.pid),
        user=world.bracvam,
        role_key='collaborator',
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()
    authenticate(client, world.bracvam)

    response = _decide(client, world.pid)

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_attachment_upload_requires_edit_grant(
    client, session, bracvam_user, tmp_path, monkeypatch
):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))
    _, pid = await setup_process_with_file_field(client, session)
    sponsor = UserFactory()
    session.add(sponsor)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )

    authenticate(client, sponsor)
    assert upload(client, pid).status_code == HTTPStatus.NOT_FOUND

    authenticate(client, bracvam_user)
    assert upload(client, pid).status_code == HTTPStatus.FORBIDDEN
    assert client.get(att_url(pid)).status_code != HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_submission_versions_require_view_grant(client, world):
    authenticate(client, world.sponsor)
    response = client.get(f'/processes/{world.pid}/submission-versions')
    assert response.status_code == HTTPStatus.NOT_FOUND

    authenticate(client, world.proponent)
    response = client.get(f'/processes/{world.pid}/submission-versions')
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_pre_evaluation_read_requires_view_on_submission(client, world):
    authenticate(client, world.sponsor)

    response = client.get(f'/processes/{world.pid}/pre-evaluation')

    assert response.status_code == HTTPStatus.NOT_FOUND
