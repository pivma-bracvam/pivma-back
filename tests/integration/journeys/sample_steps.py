"""Passos comuns às jornadas de amostras (Specs 031 e 040).

Leva um processo do template 1 da submissão até a definição das amostras
aberta para o Grupo de Seleção, pela API pública, como a jornada da Spec 031.
"""

from http import HTTPStatus
from types import SimpleNamespace

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import lab_user, new_laboratory
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
PDF = b'%PDF-1.4 ficha'


def ok(response, status=HTTPStatus.OK):
    assert response.status_code == status, response.text
    return response.json()


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def study_team(session, *, lab_count: int) -> SimpleNamespace:
    """Templates carregados, proponente, gestor, Grupo de Seleção e labs."""
    await bootstrap_all_templates(session)
    laboratories = [await new_laboratory(session) for _ in range(lab_count)]
    return SimpleNamespace(
        proponent=await _user(session),
        manager=await _user(session),
        selector=await _user(session),
        laboratories=laboratories,
        lab_users=[await lab_user(session, lab) for lab in laboratories],
    )


def _designate(client, process_id, user, role_key, laboratory=None):
    ok(
        client.post(
            f'/processes/{process_id}/participants',
            json={
                'user_id': str(user.id),
                'role_key': role_key,
                'laboratory_id': str(laboratory.id) if laboratory else None,
            },
            headers=ORIGIN,
        ),
        HTTPStatus.CREATED,
    )


def open_sample_definition(client, team, bracvam_user) -> str:
    """Submissão, triagem aprovada e designações: amostras em andamento."""
    authenticate(client, team.proponent)
    process_id = ok(
        client.post(
            '/processes',
            json={
                'template_key': 'pre_validated_method',
                'title': 'Estudo cego de irritação ocular',
            },
            headers=ORIGIN,
        ),
        HTTPStatus.CREATED,
    )['id']
    ok(
        client.post(
            f'/processes/{process_id}/activities/proposal_submission/form',
            json={'values': {'method_title': 'Ensaio RhCE'}},
            headers=ORIGIN,
        )
    )
    authenticate(client, bracvam_user)
    ok(
        client.post(
            f'/processes/{process_id}/triage/decision',
            json={'outcome': 'APPROVED', 'justification': 'Aderente.'},
            headers=ORIGIN,
        )
    )
    authenticate(client, team.proponent)
    _designate(client, process_id, team.manager, 'group_manager')
    authenticate(client, team.manager)
    _designate(client, process_id, team.selector, 'sample_selection_group')
    for laboratory, user in zip(
        team.laboratories, team.lab_users, strict=True
    ):
        _designate(
            client, process_id, user, 'participating_laboratory', laboratory
        )
    return process_id


def register_substance(client, process_id, payload) -> dict:
    """O Grupo de Seleção cadastra a substância e anexa a SDS."""
    samples = f'/processes/{process_id}/samples'
    substance = ok(
        client.post(samples, json=payload, headers=ORIGIN),
        HTTPStatus.CREATED,
    )
    ok(
        client.put(
            f'{samples}/{substance["id"]}/sds',
            files={'file': ('sds.pdf', PDF, 'application/pdf')},
            headers=ORIGIN,
        )
    )
    return substance


def my_tasks(client, process_id) -> dict:
    """Tarefas visíveis ao usuário, por atividade: a última de cada uma."""
    data = ok(client.get('/tasks', params={'process_id': process_id}))['data']
    return {task['activity_key']: task for task in data}
