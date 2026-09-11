# ruff: noqa: PLR2004

"""Spec 017 - roteiro de duas fases e atividade sem formulário.

Cobre a User Story 1 (roteiro completo declarado, incluindo a Fase 2 que
ainda não começou) e a User Story 2 (atividade classificada como
``placeholder`` avança sem gerar ``FormInstance``) usando o método oficial
``validated_method_dossier`` (Spec 011), agora na versão 2 do template.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    FormInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_template_detail_declares_both_phases_with_activity_type(
    client, session
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.get('/processes/templates/validated_method_dossier')
    assert resp.status_code == HTTPStatus.OK
    definition = resp.json()['definition']

    phases_by_key = {p['key']: p for p in definition['phases']}
    assert set(phases_by_key) == {
        'phase_1_submission_triage',
        'phase_2_planning_preview',
    }

    phase_1_activities = {
        a['key']: a['activity_type']
        for a in phases_by_key['phase_1_submission_triage']['activities']
    }
    assert phase_1_activities == {
        'proposal_submission': 'form',
        'triage_evaluation': 'form',
    }

    phase_2_activities = {
        a['key']: a['activity_type']
        for a in phases_by_key['phase_2_planning_preview']['activities']
    }
    assert phase_2_activities == {'planning_preview': 'placeholder'}


@pytest.mark.asyncio
async def test_template_detail_defaults_activity_type_for_legacy_templates(
    client, session
):
    """Métodos anteriores à Spec 017 não declaram `activity_type` no YAML.

    `GET /processes/templates/{key}` deve preencher o padrão `form` na
    leitura (FR-006), em vez de omitir o campo — do contrário, um cliente
    que exige `activity_type` em toda atividade (como o guia de frontend
    orienta) quebra para os 4 métodos que não foram tocados por esta spec.
    """
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    for template_key in (
        'pre_validated_method',
        'scope_extension',
        'me_too_validation',
        'proof_of_concept',
    ):
        resp = client.get(f'/processes/templates/{template_key}')
        assert resp.status_code == HTTPStatus.OK
        for phase in resp.json()['definition']['phases']:
            for activity in phase['activities']:
                assert activity['activity_type'] == 'form'


@pytest.mark.asyncio
async def test_placeholder_activity_unlocks_on_triage_approval(
    client, session, bracvam_user
):
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    triador = bracvam_user
    session.add(proponente)
    await session.commit()

    # 1. Proponente cria e envia a submissão
    authenticate(client, proponente)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'validated_method_dossier',
            'title': 'Dossiê com Fase 2 de exemplo',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']
    assert resp.json()['version_number'] == 2

    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Método com roteiro de duas fases',
                'terminology_notes': (
                    'Conceito descrito com nomenclatura atual e '
                    'detalhamento suficiente para avaliação.'
                ),
            }
        },
    )

    # 2. A Fase 2 ainda não existe como tarefa (dependência não satisfeita)
    tasks_before = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    assert not [
        t for t in tasks_before if t['assigned_role'] == 'BRACVAM_ADMIN'
    ]

    # 3. Triador aprova a triagem
    authenticate(client, triador)
    approve_resp = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers={'Origin': 'https://testserver'},
    )
    assert approve_resp.status_code == HTTPStatus.OK
    assert approve_resp.json()['new_process_status'] == 'PLANNING'

    # 4. A atividade de exemplo aparece pronta, sem exigir formulário
    tasks_after = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    preview_tasks = [
        t for t in tasks_after if t['assigned_role'] == 'BRACVAM_ADMIN'
    ]
    assert len(preview_tasks) == 1
    assert preview_tasks[0]['status'] == 'READY'

    # 5. Confirmação direta no banco: atividade ativada com o tipo declarado
    #    e nenhum FormInstance criado para ela (Spec 017 FR-005).
    act_stmt = select(ActivityInstance).where(
        ActivityInstance.process_instance_id == process_id,
        ActivityInstance.key == 'planning_preview',
    )
    preview_act = (await session.execute(act_stmt)).scalar_one()
    assert preview_act.activity_type == 'placeholder'
    assert preview_act.status == 'IN_PROGRESS'

    form_stmt = (
        select(FormInstance)
        .join(ActivityRun, FormInstance.activity_run_id == ActivityRun.id)
        .where(ActivityRun.activity_instance_id == preview_act.id)
    )
    orphan_forms = (await session.execute(form_stmt)).scalars().all()
    assert orphan_forms == []
