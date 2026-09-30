"""Validade da designação laboratorial (Spec 035, issue #60).

Uma designação de cargo laboratorial só concede acesso enquanto o vínculo da
pessoa com o laboratório, o laboratório e a instituição estiverem ativos. A
perda e a volta da validade ficam na trilha dos processos em andamento.
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select

from pivma.bootstrap_process_templates import sync_template_from_dict
from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
    PROCESS_PARTICIPANTS_MANAGE,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Assignment,
    Task,
)
from pivma.core.process_engine import (
    NotFoundError,
    instantiate_process,
    require_activity_access,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.conftest import _make_rbac_user
from tests.factories import (
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.task_listing_factory import _activity
from tests.factories.user_factory import UserFactory

LAB_TEMPLATE = {
    'process_template': {
        'key': 'lab_validity_probe',
        'name': 'Validade laboratorial',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_1_bench',
            'name': 'Bancada',
            'order_index': 1,
            'activities': [
                _activity(
                    'lab_bench', 'Bancada', 1, 'participating_laboratory'
                ),
                _activity('stats_review', 'Estatística', 2, 'statistician'),
            ],
        },
    ],
    'forms': [],
}


async def new_process(session, proponent, title='Processo'):
    _, version, _ = await sync_template_from_dict(session, LAB_TEMPLATE)
    process = await instantiate_process(session, version, title, proponent.id)
    await session.commit()
    return process


async def new_laboratory(session):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()
    return institution, laboratory


async def new_affiliation(session, user, institution, laboratory):
    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    session.add(affiliation)
    await session.commit()
    return affiliation


async def designate_laboratory(
    session, process, user, laboratory, role_key='participating_laboratory'
):
    assignment = Assignment(
        process_instance_id=process.id,
        user_id=user.id,
        assigned_by=user.id,
        role_key=role_key,
        laboratory_id=laboratory.id,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def activity(session, process, key):
    return await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process.id,
            ActivityInstance.key == key,
        )
    )


async def task_of(session, process, key):
    return await session.scalar(
        select(Task)
        .join(ActivityRun, ActivityRun.id == Task.activity_run_id)
        .join(
            ActivityInstance,
            ActivityInstance.id == ActivityRun.activity_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == process.id,
            ActivityInstance.key == key,
        )
    )


async def can_view(session, user, process, key='lab_bench') -> bool:
    try:
        await require_activity_access(
            session, user.id, await activity(session, process, key), 'view'
        )
    except NotFoundError:
        return False
    return True


def as_actor(client, world):
    client.headers['Origin'] = 'https://testserver'
    authenticate(client, world.actor)


def end_affiliation(client, world, affiliation=None):
    affiliation = affiliation or world.affiliation
    as_actor(client, world)
    response = client.delete(
        f'/institutional/users/{affiliation.user_id}/affiliations/'
        f'{affiliation.id}'
    )
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text


def deactivate_laboratory(client, world, laboratory=None):
    as_actor(client, world)
    laboratory = laboratory or world.laboratory
    response = client.delete(f'/institutional/laboratories/{laboratory.id}')
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text


def deactivate_institution(client, world):
    as_actor(client, world)
    response = client.delete(
        f'/institutional/institutions/{world.institution.id}'
    )
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text


def recreate_affiliation(client, world):
    as_actor(client, world)
    response = client.post(
        f'/institutional/users/{world.lab_user.id}/affiliations',
        json={
            'institution_id': str(world.institution.id),
            'laboratory_id': str(world.laboratory.id),
        },
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


@pytest_asyncio.fixture
async def world(session):
    actor = await _make_rbac_user(
        session,
        system_key='administrator',
        name='Administrador',
        codes=(
            INSTITUTIONAL_AFFILIATIONS_MANAGE,
            INSTITUTIONAL_CATALOGS_MANAGE,
            PROCESS_PARTICIPANTS_MANAGE,
        ),
    )
    proponent = UserFactory()
    lab_user = UserFactory()
    session.add_all([proponent, lab_user])
    await session.commit()
    process = await new_process(session, proponent)
    institution, laboratory = await new_laboratory(session)
    affiliation = await new_affiliation(
        session, lab_user, institution, laboratory
    )
    assignment = await designate_laboratory(
        session, process, lab_user, laboratory
    )
    assert await task_of(session, process, 'lab_bench') is not None
    return SimpleNamespace(
        process=process,
        proponent=proponent,
        lab_user=lab_user,
        institution=institution,
        laboratory=laboratory,
        affiliation=affiliation,
        assignment=assignment,
        actor=actor,
    )


def listed_task_keys(client, world, **params):
    authenticate(client, world.lab_user)
    response = client.get('/tasks', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return {
        item['activity_key']
        for item in response.json()['data']
        if item['process']['id'] == str(world.process.id)
    }


# --- US1: fim do vínculo retira o acesso do cargo ---------------------------


@pytest.mark.asyncio
async def test_ended_affiliation_denies_activity_view(client, session, world):
    end_affiliation(client, world)

    assert not await can_view(session, world.lab_user, world.process)


@pytest.mark.asyncio
async def test_active_affiliation_allows_activity_edit(session, world):
    await require_activity_access(
        session,
        world.lab_user.id,
        await activity(session, world.process, 'lab_bench'),
        'edit',
    )


@pytest.mark.asyncio
async def test_ended_affiliation_hides_cargo_tasks(client, world):
    assert 'lab_bench' in listed_task_keys(client, world)

    end_affiliation(client, world)

    assert 'lab_bench' not in listed_task_keys(client, world)


@pytest.mark.asyncio
async def test_ended_affiliation_hides_cargo_tasks_from_actionable(
    client, world
):
    assert 'lab_bench' in listed_task_keys(client, world, actionable=True)

    end_affiliation(client, world)

    assert 'lab_bench' not in listed_task_keys(client, world, actionable=True)


@pytest.mark.asyncio
async def test_ended_affiliation_hides_process_from_listing(client, world):
    end_affiliation(client, world)

    authenticate(client, world.lab_user)
    response = client.get('/processes')

    assert response.status_code == HTTPStatus.OK
    assert str(world.process.id) not in {
        item['id'] for item in response.json()['data']
    }


@pytest.mark.asyncio
async def test_ended_affiliation_gets_not_found_on_process_detail(
    client, session, world
):
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)
    never_had_cargo = client.get(f'/processes/{world.process.id}')
    end_affiliation(client, world)

    authenticate(client, world.lab_user)
    response = client.get(f'/processes/{world.process.id}')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == never_had_cargo.json()


@pytest.mark.asyncio
async def test_ended_affiliation_gets_not_found_on_timeline(client, world):
    end_affiliation(client, world)

    authenticate(client, world.lab_user)
    response = client.get(f'/processes/{world.process.id}/timeline')

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_other_effective_cargo_keeps_its_access(client, session, world):
    await grant_cargo(
        session,
        process_id=world.process.id,
        user=world.lab_user,
        role_key='statistician',
    )

    end_affiliation(client, world)

    assert await can_view(
        session, world.lab_user, world.process, 'stats_review'
    )
    assert not await can_view(session, world.lab_user, world.process)
    authenticate(client, world.lab_user)
    assert (
        client.get(f'/processes/{world.process.id}').status_code
        == HTTPStatus.OK
    )


@pytest.mark.asyncio
async def test_ended_affiliation_keeps_designation_and_task(
    client, session, world
):
    task = await task_of(session, world.process, 'lab_bench')
    status_before = task.status

    end_affiliation(client, world)

    await session.refresh(world.assignment)
    await session.refresh(task)
    assert world.assignment.revoked_at is None
    assert world.assignment.deleted_at is None
    assert task.status == status_before
