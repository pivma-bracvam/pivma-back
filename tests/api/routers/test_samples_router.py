"""Rotas de amostras cegas do Grupo de Seleção (Spec 031)."""

import json
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    BlindSampleCode,
    Laboratory,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    StudySubstance,
    Task,
)
from pivma.core.process_engine import instantiate_process
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import (
    VALID_CAS,
    add_participating_lab,
    assign_lab,
    sample_process,
    substance_payload,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
PDF = b'%PDF-1.4 ficha de seguranca'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _url(process_id, suffix=''):
    return f'/processes/{process_id}/samples{suffix}'


def _create(client, process_id, **overrides):
    return client.post(
        _url(process_id), json=substance_payload(**overrides), headers=ORIGIN
    )


def _created(client, process_id, **overrides):
    response = _create(client, process_id, **overrides)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _ready(session, client, *, lab_count=3):
    ctx = await sample_process(session, lab_count=lab_count)
    authenticate(client, ctx.selector)
    return ctx


def _all_codes(client, process_id):
    response = client.get(_url(process_id))
    assert response.status_code == HTTPStatus.OK, response.text
    return [
        code['code']
        for substance in response.json()['substances']
        for code in substance['blind_codes']
    ]


async def _events(session, process_id, event_type):
    return list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == event_type,
            )
        )
    )


def assert_no_identity(blob, substance, codes=()):
    text = json.dumps(blob, ensure_ascii=False, default=str)
    for secret in (
        substance['chemical_name'],
        substance['cas_number'],
        substance['lot'],
        *codes,
    ):
        assert secret not in text


# ---------------------------------------------------------------------------
# US1 — cadastro e códigos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_substance_returns_201_with_one_code_per_lab(
    session, client
):
    ctx = await _ready(session, client)

    body = _created(client, ctx.process_id)

    assert body['chemical_name'] == 'Formaldeído'
    assert body['cas_number'] == '50-00-0'
    assert body['sds'] is None
    codes = body['blind_codes']
    assert {c['laboratory_id'] for c in codes} == {
        str(lab.id) for lab in ctx.labs
    }
    assert len({c['code'] for c in codes}) == len(ctx.labs)
    assert {c['laboratory_name'] for c in codes} == {
        lab.name for lab in ctx.labs
    }


@pytest.mark.asyncio
async def test_four_substances_three_labs_yield_twelve_unique_codes(
    session, client
):
    ctx = await _ready(session, client)

    for cas in VALID_CAS[:4]:
        _created(client, ctx.process_id, cas_number=cas)

    codes = _all_codes(client, ctx.process_id)
    assert len(codes) == 12  # noqa: PLR2004
    assert len(set(codes)) == 12  # noqa: PLR2004


@pytest.mark.asyncio
async def test_create_substance_without_labs_returns_empty_codes(
    session, client
):
    ctx = await _ready(session, client, lab_count=0)

    assert _created(client, ctx.process_id)['blind_codes'] == []


@pytest.mark.asyncio
async def test_lab_with_two_users_gets_single_code(session, client):
    ctx = await _ready(session, client, lab_count=1)
    await assign_lab(session, ctx.process_id, ctx.labs[0])

    codes = _created(client, ctx.process_id)['blind_codes']

    assert [c['laboratory_id'] for c in codes] == [str(ctx.labs[0].id)]


@pytest.mark.asyncio
async def test_revoked_lab_assignment_gets_no_code(session, client):
    ctx = await _ready(session, client, lab_count=2)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.laboratory_id == ctx.labs[0].id,
        )
    )
    assignment.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()

    codes = _created(client, ctx.process_id)['blind_codes']

    assert [c['laboratory_id'] for c in codes] == [str(ctx.labs[1].id)]


@pytest.mark.asyncio
async def test_deleted_laboratory_gets_no_code(session, client):
    ctx = await _ready(session, client, lab_count=2)
    laboratory = await session.get(Laboratory, ctx.labs[0].id)
    laboratory.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()

    codes = _created(client, ctx.process_id)['blind_codes']

    assert [c['laboratory_id'] for c in codes] == [str(ctx.labs[1].id)]


@pytest.mark.asyncio
async def test_lead_laboratory_gets_no_code(session, client):
    ctx = await _ready(session, client, lab_count=1)
    await add_participating_lab(
        session, ctx.process_id, role_key='lead_laboratory'
    )

    codes = _created(client, ctx.process_id)['blind_codes']

    assert [c['laboratory_id'] for c in codes] == [str(ctx.labs[0].id)]


@pytest.mark.asyncio
async def test_create_duplicate_cas_in_same_process_returns_409(
    session, client
):
    ctx = await _ready(session, client)
    _created(client, ctx.process_id)

    response = _create(client, ctx.process_id, chemical_name='Outro nome')

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()['detail']['code'] == 'duplicate_cas'


@pytest.mark.asyncio
async def test_same_cas_in_another_process_is_accepted(session, client):
    first = await _ready(session, client)
    _created(client, first.process_id)
    second = await _ready(session, client)

    response = _create(client, second.process_id)

    assert response.status_code == HTTPStatus.CREATED, response.text


@pytest.mark.asyncio
async def test_create_with_invalid_cas_returns_422(session, client):
    ctx = await _ready(session, client)

    response = _create(client, ctx.process_id, cas_number='50-00-1')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'invalid_cas'
    assert (
        await session.scalar(
            select(StudySubstance.id).where(
                StudySubstance.process_instance_id == ctx.process_id
            )
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'field',
    ['chemical_name', 'cas_number', 'lot', 'safe_handling_instructions'],
)
@pytest.mark.parametrize('mode', ['missing', 'blank'])
async def test_create_missing_required_field_returns_422(
    session, client, field, mode
):
    ctx = await _ready(session, client)
    payload = substance_payload()
    if mode == 'missing':
        del payload[field]
    else:
        payload[field] = '   '

    response = client.post(_url(ctx.process_id), json=payload, headers=ORIGIN)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('field', 'size'), [('chemical_name', 256), ('lot', 65), ('purity', 65)]
)
async def test_create_rejects_field_over_max_length(
    session, client, field, size
):
    ctx = await _ready(session, client)

    response = _create(client, ctx.process_id, **{field: 'x' * size})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_list_substances_ordered_by_creation(
    session, client, mock_db_time
):
    ctx = await _ready(session, client)
    created = []
    # `now()` é o início da transação do teste: fixa horários distintos.
    for day, cas in enumerate(reversed(VALID_CAS[:3]), start=1):
        with mock_db_time(model=StudySubstance, time=datetime(2026, 1, day)):
            created.append(_created(client, ctx.process_id, cas_number=cas))
    created = [s['id'] for s in created]

    response = client.get(_url(ctx.process_id))

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['activity_status'] == 'IN_PROGRESS'
    assert [s['id'] for s in body['substances']] == created


@pytest.mark.asyncio
async def test_patch_substance_updates_data_and_keeps_codes(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)

    response = client.patch(
        _url(ctx.process_id, f'/{created["id"]}'),
        json={'lot': 'L-NOVO', 'purity': '99%'},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body['lot'] == 'L-NOVO'
    assert body['purity'] == '99%'
    assert body['chemical_name'] == created['chemical_name']
    assert body['blind_codes'] == created['blind_codes']


@pytest.mark.asyncio
async def test_patch_to_duplicate_cas_returns_409(session, client):
    ctx = await _ready(session, client)
    _created(client, ctx.process_id, cas_number=VALID_CAS[0])
    other = _created(client, ctx.process_id, cas_number=VALID_CAS[1])

    response = client.patch(
        _url(ctx.process_id, f'/{other["id"]}'),
        json={'cas_number': VALID_CAS[0]},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()['detail']['code'] == 'duplicate_cas'


@pytest.mark.asyncio
async def test_patch_substance_of_other_process_returns_404(session, client):
    first = await _ready(session, client)
    second = await sample_process(session)
    await grant_cargo(
        session,
        process_id=second.process_id,
        user=first.selector,
        role_key='sample_selection_group',
    )
    foreign = _created(client, second.process_id)

    response = client.patch(
        _url(first.process_id, f'/{foreign["id"]}'),
        json={'lot': 'L-X'},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_substance_removes_it_and_its_codes(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)

    response = client.delete(
        _url(ctx.process_id, f'/{created["id"]}'), headers=ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT, response.text
    assert client.get(_url(ctx.process_id)).json()['substances'] == []
    substance = await session.scalar(
        select(StudySubstance)
        .where(StudySubstance.id == created['id'])
        .execution_options(
            skip_soft_delete_filter=True, populate_existing=True
        )
    )
    assert substance.deleted_at is not None
    codes = list(
        await session.scalars(
            select(BlindSampleCode)
            .where(BlindSampleCode.substance_id == created['id'])
            .execution_options(
                skip_soft_delete_filter=True, populate_existing=True
            )
        )
    )
    assert len(codes) == len(ctx.labs)
    assert all(code.deleted_at is not None for code in codes)


@pytest.mark.asyncio
async def test_cas_can_be_reused_after_delete(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)
    client.delete(_url(ctx.process_id, f'/{created["id"]}'), headers=ORIGIN)

    response = _create(client, ctx.process_id)

    assert response.status_code == HTTPStatus.CREATED, response.text


async def _blocked_sample_process(session):
    await bootstrap_all_templates(session)
    version = await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessTemplate,
            ProcessTemplate.id == ProcessTemplateVersion.template_id,
        )
        .where(ProcessTemplate.key == 'pre_validated_method')
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )
    creator = UserFactory()
    selector = UserFactory()
    session.add_all([creator, selector])
    await session.commit()
    process = await instantiate_process(
        session, version, 'Processo bloqueado', creator.id
    )
    await grant_cargo(
        session,
        process_id=process.id,
        user=selector,
        role_key='sample_selection_group',
    )
    return process.id, selector


@pytest.mark.asyncio
async def test_mutation_on_blocked_activity_returns_409(session, client):
    process_id, selector = await _blocked_sample_process(session)
    authenticate(client, selector)

    response = _create(client, process_id)

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()['detail']['code'] == 'invalid_transition'
    listing = client.get(_url(process_id))
    assert listing.status_code == HTTPStatus.OK
    assert listing.json() == {'activity_status': 'BLOCKED', 'substances': []}


@pytest.mark.asyncio
async def test_mutation_on_closed_process_returns_409(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'CLOSED'
    await session.commit()

    responses = [
        _create(client, ctx.process_id, cas_number=VALID_CAS[1]),
        client.patch(
            _url(ctx.process_id, f'/{created["id"]}'),
            json={'lot': 'L-X'},
            headers=ORIGIN,
        ),
        client.delete(
            _url(ctx.process_id, f'/{created["id"]}'), headers=ORIGIN
        ),
    ]

    for response in responses:
        assert response.status_code == HTTPStatus.CONFLICT, response.text
        assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_create_emits_audit_events_without_identity(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)
    codes = [c['code'] for c in created['blind_codes']]

    registered = await _events(
        session, ctx.process_id, 'SAMPLE_SUBSTANCE_REGISTERED'
    )
    generated = await _events(
        session, ctx.process_id, 'SAMPLE_CODES_GENERATED'
    )

    assert len(registered) == 1
    assert len(generated) == 1
    assert registered[0].context_data['substance_id'] == created['id']
    assert generated[0].context_data['substance_id'] == created['id']
    assert generated[0].context_data['code_count'] == len(ctx.labs)
    assert sorted(generated[0].context_data['laboratory_ids']) == sorted(
        str(lab.id) for lab in ctx.labs
    )
    for event in (*registered, *generated):
        assert event.user_id == ctx.selector.id
        assert event.activity_run_id is not None
        assert_no_identity(event.context_data, created, codes)


@pytest.mark.asyncio
async def test_update_and_delete_emit_audit_events_without_identity(
    session, client
):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)
    client.patch(
        _url(ctx.process_id, f'/{created["id"]}'),
        json={'purity': '99%'},
        headers=ORIGIN,
    )
    client.delete(_url(ctx.process_id, f'/{created["id"]}'), headers=ORIGIN)

    for event_type in ('SAMPLE_SUBSTANCE_UPDATED', 'SAMPLE_SUBSTANCE_REMOVED'):
        events = await _events(session, ctx.process_id, event_type)
        assert len(events) == 1, event_type
        assert events[0].context_data['substance_id'] == created['id']
        assert_no_identity(events[0].context_data, created)


# ---------------------------------------------------------------------------
# US2 — SDS e conclusão
# ---------------------------------------------------------------------------


def _upload(client, process_id, substance_id, *, name='sds.pdf', data=PDF):
    return client.put(
        _url(process_id, f'/{substance_id}/sds'),
        files={'file': (name, data, 'application/pdf')},
        headers=ORIGIN,
    )


def _with_sds(client, process_id, **overrides):
    substance = _created(client, process_id, **overrides)
    response = _upload(client, process_id, substance['id'])
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _complete(client, process_id):
    return client.post(_url(process_id, '/complete'), headers=ORIGIN)


async def _artifacts(session, substance_id):
    return list(
        await session.scalars(
            select(Artifact)
            .where(
                Artifact.key == 'sample_sds',
                Artifact.metadata_payload['substance_id'].astext
                == str(substance_id),
            )
            .order_by(Artifact.created_at)
            .execution_options(
                skip_soft_delete_filter=True, populate_existing=True
            )
        )
    )


def _attachments_root():
    import os  # noqa: PLC0415

    return Path(os.environ['ATTACHMENTS_DIR'])


@pytest.mark.asyncio
async def test_upload_sds_pdf_returns_substance_with_sds(session, client):
    ctx = await _ready(session, client)
    substance = _created(client, ctx.process_id)

    response = _upload(client, ctx.process_id, substance['id'])

    assert response.status_code == HTTPStatus.OK, response.text
    sds = response.json()['sds']
    assert sds['filename'] == 'sds.pdf'
    assert sds['size'] == len(PDF)
    (artifact,) = await _artifacts(session, substance['id'])
    run = await session.scalar(
        select(ActivityRun)
        .join(
            ActivityInstance,
            ActivityInstance.id == ActivityRun.activity_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == ctx.process_id,
            ActivityInstance.key == 'sample_definition',
        )
    )
    assert artifact.activity_run_id == run.id
    assert (_attachments_root() / artifact.file_path).read_bytes() == PDF


@pytest.mark.asyncio
async def test_upload_non_pdf_returns_422(session, client):
    ctx = await _ready(session, client)
    substance = _created(client, ctx.process_id)

    response = _upload(client, ctx.process_id, substance['id'], name='a.docx')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'extension_not_allowed'
    assert await _artifacts(session, substance['id']) == []


@pytest.mark.asyncio
async def test_upload_empty_file_returns_400(session, client):
    ctx = await _ready(session, client)
    substance = _created(client, ctx.process_id)

    response = _upload(client, ctx.process_id, substance['id'], data=b'')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail']['code'] == 'empty_file'


@pytest.mark.asyncio
async def test_upload_over_size_limit_returns_413(
    session, client, monkeypatch
):
    monkeypatch.setenv('ATTACHMENT_MAX_SIZE_MB', '1')
    ctx = await _ready(session, client)
    substance = _created(client, ctx.process_id)

    response = _upload(
        client, ctx.process_id, substance['id'], data=b'x' * (1024**2 + 1)
    )

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert response.json()['detail']['code'] == 'file_too_large'
    leftovers = [p for p in _attachments_root().rglob('*') if p.is_file()]
    assert leftovers == []


@pytest.mark.asyncio
async def test_replacing_sds_soft_deletes_previous_artifact_and_file(
    session, client
):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)

    response = _upload(
        client, ctx.process_id, substance['id'], name='nova.pdf', data=b'%PDF2'
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['sds']['filename'] == 'nova.pdf'
    stored = await session.scalar(
        select(StudySubstance.sds_artifact_id)
        .where(StudySubstance.id == substance['id'])
        .execution_options(populate_existing=True)
    )
    artifacts = await _artifacts(session, substance['id'])
    (new,) = [a for a in artifacts if a.id == stored]
    (old,) = [a for a in artifacts if a.id != stored]
    assert old.deleted_at is not None
    assert not (_attachments_root() / old.file_path).exists()
    assert new.deleted_at is None
    assert (_attachments_root() / new.file_path).read_bytes() == b'%PDF2'


@pytest.mark.asyncio
async def test_download_sds_returns_pdf(session, client):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)

    response = client.get(_url(ctx.process_id, f'/{substance["id"]}/sds'))

    assert response.status_code == HTTPStatus.OK
    assert response.content == PDF
    assert response.headers['content-type'] == 'application/pdf'
    assert 'sds.pdf' in response.headers['content-disposition']


@pytest.mark.asyncio
async def test_download_sds_without_upload_returns_404(session, client):
    ctx = await _ready(session, client)
    substance = _created(client, ctx.process_id)

    response = client.get(_url(ctx.process_id, f'/{substance["id"]}/sds'))

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_sds_upload_and_download_emit_audit_without_identity(
    session, client
):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)
    client.get(_url(ctx.process_id, f'/{substance["id"]}/sds'))

    for event_type in ('SAMPLE_SDS_UPLOADED', 'SAMPLE_SDS_DOWNLOADED'):
        events = await _events(session, ctx.process_id, event_type)
        assert len(events) == 1, event_type
        assert events[0].context_data['substance_id'] == substance['id']
        assert_no_identity(events[0].context_data, substance)
        assert 'sds.pdf' not in json.dumps(events[0].context_data)


@pytest.mark.asyncio
async def test_complete_fills_codes_for_lab_added_later(session, client):
    ctx = await _ready(session, client, lab_count=2)
    for cas in VALID_CAS[:2]:
        _with_sds(client, ctx.process_id, cas_number=cas)
    await add_participating_lab(session, ctx.process_id)

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json() == {
        'activity_status': 'COMPLETED',
        'substance_count': 2,
        'laboratory_count': 3,
        'code_count': 6,
    }
    codes = _all_codes(client, ctx.process_id)
    assert len(codes) == len(set(codes)) == 6  # noqa: PLR2004


@pytest.mark.asyncio
async def test_complete_marks_activity_run_and_task_completed(session, client):
    ctx = await _ready(session, client)
    _with_sds(client, ctx.process_id)

    _complete(client, ctx.process_id)

    act = await session.scalar(
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == ctx.process_id,
            ActivityInstance.key == 'sample_definition',
        )
        .execution_options(populate_existing=True)
    )
    runs = list(
        await session.scalars(
            select(ActivityRun)
            .where(ActivityRun.activity_instance_id == act.id)
            .execution_options(populate_existing=True)
        )
    )
    tasks = list(
        await session.scalars(
            select(Task)
            .where(Task.activity_run_id.in_([r.id for r in runs]))
            .execution_options(populate_existing=True)
        )
    )
    assert act.status == 'COMPLETED'
    assert {r.status for r in runs} == {'COMPLETED'}
    assert tasks
    assert {t.status for t in tasks} == {'COMPLETED'}


@pytest.mark.asyncio
async def test_complete_discards_codes_of_lab_that_left(session, client):
    ctx = await _ready(session, client, lab_count=2)
    _with_sds(client, ctx.process_id)
    for assignment in await session.scalars(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.laboratory_id == ctx.labs[0].id,
        )
    ):
        assignment.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['code_count'] == 1
    (substance,) = client.get(_url(ctx.process_id)).json()['substances']
    assert [c['laboratory_id'] for c in substance['blind_codes']] == [
        str(ctx.labs[1].id)
    ]
    discarded = await session.scalar(
        select(BlindSampleCode)
        .where(BlindSampleCode.laboratory_id == ctx.labs[0].id)
        .execution_options(
            skip_soft_delete_filter=True, populate_existing=True
        )
    )
    assert discarded.deleted_at is not None


@pytest.mark.asyncio
async def test_complete_without_substances_returns_422(session, client):
    ctx = await _ready(session, client)

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'no_substances'
    assert client.get(_url(ctx.process_id)).json()['activity_status'] == (
        'IN_PROGRESS'
    )


@pytest.mark.asyncio
async def test_complete_with_substance_missing_sds_returns_422(
    session, client
):
    ctx = await _ready(session, client)
    _with_sds(client, ctx.process_id, cas_number=VALID_CAS[0])
    missing = _created(client, ctx.process_id, cas_number=VALID_CAS[1])

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    detail = response.json()['detail']
    assert detail['code'] == 'missing_sds'
    assert detail['substance_ids'] == [missing['id']]


@pytest.mark.asyncio
async def test_complete_without_participating_labs_returns_422(
    session, client
):
    ctx = await _ready(session, client, lab_count=0)
    _with_sds(client, ctx.process_id)

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'no_laboratories'


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['create', 'patch', 'delete', 'sds'])
async def test_mutations_after_completion_return_409(
    session, client, operation
):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)
    _complete(client, ctx.process_id)
    item = _url(ctx.process_id, f'/{substance["id"]}')

    response = {
        'create': lambda: _create(
            client, ctx.process_id, cas_number=VALID_CAS[1]
        ),
        'patch': lambda: client.patch(
            item, json={'lot': 'L-X'}, headers=ORIGIN
        ),
        'delete': lambda: client.delete(item, headers=ORIGIN),
        'sds': lambda: _upload(client, ctx.process_id, substance['id']),
    }[operation]()

    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_complete_twice_returns_409(session, client):
    ctx = await _ready(session, client)
    _with_sds(client, ctx.process_id)
    _complete(client, ctx.process_id)

    response = _complete(client, ctx.process_id)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_reads_still_work_after_completion(session, client):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)
    _complete(client, ctx.process_id)

    listing = client.get(_url(ctx.process_id))
    sds = client.get(_url(ctx.process_id, f'/{substance["id"]}/sds'))

    assert listing.status_code == HTTPStatus.OK
    assert listing.json()['activity_status'] == 'COMPLETED'
    assert sds.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_complete_emits_audit_with_counts_only(session, client):
    ctx = await _ready(session, client, lab_count=1)
    substance = _with_sds(client, ctx.process_id)
    await add_participating_lab(session, ctx.process_id)

    _complete(client, ctx.process_id)

    (completed,) = await _events(
        session, ctx.process_id, 'SAMPLE_DEFINITION_COMPLETED'
    )
    assert completed.context_data == {
        'substance_count': 1,
        'laboratory_count': 2,
        'code_count': 2,
        'discarded_code_count': 0,
    }
    generated = await _events(
        session, ctx.process_id, 'SAMPLE_CODES_GENERATED'
    )
    assert [e.context_data['code_count'] for e in generated] == [1, 1]
    codes = _all_codes(client, ctx.process_id)
    for event in (completed, *generated):
        assert_no_identity(event.context_data, substance, codes)


# ---------------------------------------------------------------------------
# US3 — etiquetas
# ---------------------------------------------------------------------------


def _labels(client, process_id):
    response = client.get(
        _url(process_id, '/labels'), params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()['data']


@pytest.mark.asyncio
async def test_labels_return_one_per_vial(session, client):
    ctx = await _ready(session, client)
    for cas in VALID_CAS[:4]:
        _created(client, ctx.process_id, cas_number=cas)
    process = await session.get(ProcessInstance, ctx.process_id)

    labels = _labels(client, ctx.process_id)

    assert len(labels) == 12  # noqa: PLR2004
    assert len({label['code'] for label in labels}) == 12  # noqa: PLR2004
    names = {str(lab.id): lab.name for lab in ctx.labs}
    for label in labels:
        assert label['study_code'] == process.code
        assert label['laboratory']['name'] == names[label['laboratory']['id']]
        assert label['lot'] == 'L-2026-04'
        assert label['qr_url']
        assert 'qr_svg' not in label
    assert [(lb['laboratory']['name'], lb['code']) for lb in labels] == sorted(
        (lb['laboratory']['name'], lb['code']) for lb in labels
    )


@pytest.mark.asyncio
async def test_vial_qr_route_returns_svg(session, client):
    ctx = await _ready(session, client, lab_count=1)
    _created(client, ctx.process_id)
    (label,) = _labels(client, ctx.process_id)

    response = client.get(
        _url(ctx.process_id, f'/vials/{label["code"]}/qr.svg')
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers['content-type'].startswith('image/svg+xml')
    assert response.text.lstrip().startswith(('<?xml', '<svg'))


@pytest.mark.asyncio
async def test_vial_qr_route_unknown_code_is_404(session, client):
    ctx = await _ready(session, client, lab_count=1)
    _created(client, ctx.process_id)

    response = client.get(_url(ctx.process_id, '/vials/ZZZZZZZZ/qr.svg'))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_vial_qr_route_hidden_from_laboratory(session, client):
    ctx = await _ready(session, client, lab_count=1)
    _created(client, ctx.process_id)
    (label,) = _labels(client, ctx.process_id)

    authenticate(client, ctx.lab_users[0])
    response = client.get(
        _url(ctx.process_id, f'/vials/{label["code"]}/qr.svg')
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_label_qr_contains_only_vial_url(session, client):
    ctx = await _ready(session, client, lab_count=1)
    substance = _created(client, ctx.process_id)

    (label,) = _labels(client, ctx.process_id)

    assert label['qr_url'].endswith(
        f'/amostras/{ctx.process_id}/frascos/{label["code"]}'
    )
    qr = client.get(_url(ctx.process_id, f'/vials/{label["code"]}/qr.svg'))
    for blob in (label['qr_url'], qr.text):
        for secret in (
            substance['chemical_name'],
            substance['cas_number'],
            substance['lot'],
            substance['id'],
        ):
            assert secret not in blob


@pytest.mark.asyncio
async def test_labels_available_after_completion(session, client):
    ctx = await _ready(session, client)
    for cas in VALID_CAS[:4]:
        _with_sds(client, ctx.process_id, cas_number=cas)
    before = _labels(client, ctx.process_id)

    _complete(client, ctx.process_id)

    assert _labels(client, ctx.process_id) == before


@pytest.mark.asyncio
async def test_labels_empty_without_codes(session, client):
    ctx = await _ready(session, client)

    assert _labels(client, ctx.process_id) == []


# ---------------------------------------------------------------------------
# US4 — visão cega do frasco
# ---------------------------------------------------------------------------


def _vial(client, process_id, code):
    return client.get(_url(process_id, f'/vials/{code}'))


@pytest.mark.asyncio
async def test_vial_returns_blind_view_only(session, client):
    ctx = await _ready(session, client, lab_count=1)
    substance = _created(client, ctx.process_id)
    code = substance['blind_codes'][0]['code']

    response = _vial(client, ctx.process_id, code)

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json() == {
        'code': code,
        'lot': substance['lot'],
        'safe_handling_instructions': substance['safe_handling_instructions'],
    }
    text = json.dumps(response.json(), ensure_ascii=False)
    assert substance['chemical_name'] not in text
    assert substance['cas_number'] not in text


@pytest.mark.asyncio
async def test_vial_unknown_code_returns_404(session, client):
    ctx = await _ready(session, client, lab_count=1)
    _created(client, ctx.process_id)

    assert _vial(client, ctx.process_id, 'ZZZZZZZZ').status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_vial_code_of_other_process_returns_404(session, client):
    first = await _ready(session, client, lab_count=1)
    second = await sample_process(session, lab_count=1)
    await grant_cargo(
        session,
        process_id=second.process_id,
        user=first.selector,
        role_key='sample_selection_group',
    )
    foreign = _created(client, second.process_id)['blind_codes'][0]['code']

    assert _vial(client, first.process_id, foreign).status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_vial_code_of_removed_substance_returns_404(session, client):
    ctx = await _ready(session, client, lab_count=1)
    substance = _created(client, ctx.process_id)
    client.delete(_url(ctx.process_id, f'/{substance["id"]}'), headers=ORIGIN)

    response = _vial(
        client, ctx.process_id, substance['blind_codes'][0]['code']
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Ramos complementares
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_without_sample_activity_returns_404(session, client):
    ctx = await _ready(session, client)
    await session.execute(
        ActivityInstance.__table__
        .update()
        .where(ActivityInstance.process_instance_id == ctx.process_id)
        .values(key='other_activity')
    )
    await session.commit()

    assert client.get(_url(ctx.process_id)).status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_patch_required_field_to_null_returns_422(session, client):
    ctx = await _ready(session, client)
    created = _created(client, ctx.process_id)

    response = client.patch(
        _url(ctx.process_id, f'/{created["id"]}'),
        json={'lot': None},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'required_field'


@pytest.mark.asyncio
async def test_delete_substance_discards_its_sds(session, client):
    ctx = await _ready(session, client)
    substance = _with_sds(client, ctx.process_id)
    (artifact,) = await _artifacts(session, substance['id'])

    client.delete(_url(ctx.process_id, f'/{substance["id"]}'), headers=ORIGIN)

    (artifact,) = await _artifacts(session, substance['id'])
    assert artifact.deleted_at is not None
    assert not (_attachments_root() / artifact.file_path).exists()
