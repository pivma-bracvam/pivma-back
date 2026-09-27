"""Jornada: do processo novo ao conjunto de códigos cegos congelado
(Spec 031, SC-001, SC-003 a SC-006).

Usa a API pública do submetedor ao Grupo de Seleção: submissão, triagem,
designação dos cargos da Fase 2, cadastro de 4 substâncias com SDS para 3
laboratórios, conclusão, etiquetas e visão cega do frasco.
"""

import json
from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import (
    VALID_CAS,
    lab_user,
    new_laboratory,
    substance_payload,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
PDF = b'%PDF-1.4 ficha'
SUBSTANCES = 4
LABS = 3


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _ok(response, status=HTTPStatus.OK):
    assert response.status_code == status, response.text
    return response.json()


def _designate(client, process_id, user, role_key, laboratory=None):
    _ok(
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


@pytest.mark.asyncio
async def test_blind_sample_journey_four_substances_three_labs(  # noqa: PLR0914
    session, client, bracvam_user
):
    await bootstrap_all_templates(session)
    proponent = await _user(session)
    manager = await _user(session)
    selector = await _user(session)
    laboratories = [await new_laboratory(session) for _ in range(LABS)]
    lab_users = [await lab_user(session, lab) for lab in laboratories]

    # 1. Proponente cria o processo do template 1 e envia a submissão.
    authenticate(client, proponent)
    process_id = _ok(
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
    _ok(
        client.post(
            f'/processes/{process_id}/activities/proposal_submission/form',
            json={'values': {'method_title': 'Ensaio RhCE'}},
            headers=ORIGIN,
        )
    )

    # 2. BraCVAM aprova a triagem: a Fase 2 abre.
    authenticate(client, bracvam_user)
    _ok(
        client.post(
            f'/processes/{process_id}/triage/decision',
            json={'outcome': 'APPROVED', 'justification': 'Aderente.'},
            headers=ORIGIN,
        )
    )

    # 3. Proponente designa o Grupo Gestor; o Gestor designa o Grupo de
    #    Seleção e os três laboratórios participantes.
    authenticate(client, proponent)
    _designate(client, process_id, manager, 'group_manager')
    authenticate(client, manager)
    _designate(client, process_id, selector, 'sample_selection_group')
    for lab, user in zip(laboratories, lab_users, strict=True):
        _designate(client, process_id, user, 'participating_laboratory', lab)

    # 4. O Grupo de Seleção recebe a tarefa de amostras.
    authenticate(client, selector)
    tasks = _ok(client.get('/tasks', params={'process_id': process_id}))
    assert [
        t['status'] for t in tasks if t['activity_key'] == 'sample_definition'
    ] == ['READY']

    # 5. Cadastra 4 substâncias com SDS (SC-006: códigos no mesmo salvar).
    samples = f'/processes/{process_id}/samples'
    created = []
    for cas in VALID_CAS[:SUBSTANCES]:
        substance = _ok(
            client.post(
                samples,
                json=substance_payload(cas_number=cas),
                headers=ORIGIN,
            ),
            HTTPStatus.CREATED,
        )
        assert len(substance['blind_codes']) == LABS
        _ok(
            client.put(
                f'{samples}/{substance["id"]}/sds',
                files={'file': ('sds.pdf', PDF, 'application/pdf')},
                headers=ORIGIN,
            )
        )
        created.append(substance)

    # 6. Conclui: 12 códigos únicos e congelados (SC-001).
    completion = _ok(client.post(f'{samples}/complete', headers=ORIGIN))
    assert completion['code_count'] == SUBSTANCES * LABS
    codes = [
        c['code']
        for s in _ok(client.get(samples))['substances']
        for c in s['blind_codes']
    ]
    assert len(set(codes)) == SUBSTANCES * LABS

    # 7. Etiquetas e visão cega sem identidade química (SC-004).
    labels = _ok(client.get(f'{samples}/labels'))
    assert len(labels) == SUBSTANCES * LABS
    vial = _ok(client.get(f'{samples}/vials/{labels[0]["code"]}'))
    blob = json.dumps([vial, [lb['qr_url'] for lb in labels]])
    for substance in created:
        assert substance['chemical_name'] not in blob
        assert substance['cas_number'] not in blob

    # 8. Nenhum laboratório participante vê o conteúdo (SC-003).
    for user in lab_users:
        authenticate(client, user)
        assert client.get(samples).status_code == HTTPStatus.NOT_FOUND
        assert (
            client.get(f'{samples}/vials/{labels[0]["code"]}').status_code
            == HTTPStatus.NOT_FOUND
        )
