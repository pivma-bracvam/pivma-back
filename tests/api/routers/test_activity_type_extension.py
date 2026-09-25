# ruff: noqa: PLR2004

"""Spec 017 - roteiro de duas fases e atividade sem formulário.

Cobre a User Story 1 (roteiro completo declarado, incluindo a Fase 2 que
ainda não começou) e a User Story 2 (atividade classificada como algo além
de formulário avança sem gerar ``FormInstance``) usando o método oficial
``validated_method_dossier`` (Spec 011).

A Fase 2 era, até a Spec 017/018 (v3), uma prévia ``placeholder`` sem regra
de negócio real — documentada como estando ali só para provar que o motor
suporta um ``activity_type`` além de ``form``. A Spec 028 (v4) substitui essa
prévia pelo conteúdo real da Etapa 2 (8 atividades ``role_assignment``);
estes testes foram atualizados para a v4 sem perder a cobertura original do
mecanismo genérico de avanço (Spec 017 FR-005).
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
        'phase_2_role_assignment',
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
        for a in phases_by_key['phase_2_role_assignment']['activities']
    }
    assert phase_2_activities == {
        'assign_sponsor': 'role_assignment',
        'assign_group_manager': 'role_assignment',
        'assign_sample_selection_group': 'role_assignment',
        'assign_lead_laboratory': 'role_assignment',
        'assign_participating_laboratory': 'role_assignment',
        'assign_statistician': 'role_assignment',
        'assign_collaborator': 'role_assignment',
        'assign_adhoc_evaluator': 'role_assignment',
    }


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
async def test_role_assignment_activities_unlock_on_triage_approval(
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
            'title': 'Dossiê com Fase 2 de atribuição de cargo',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']
    assert resp.json()['version_number'] == 4

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

    # 2. A Fase 2 ainda não existe como tarefa (dependência não satisfeita).
    tasks_before = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    assert not [
        t for t in tasks_before if t['title'] == 'Definir o Patrocinador'
    ]

    # 3. Triador aprova a triagem
    authenticate(client, triador)
    approve_resp = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers={'Origin': 'https://testserver'},
    )
    assert approve_resp.status_code == HTTPStatus.OK
    assert approve_resp.json()['process_status'] == 'OPEN'

    # 4. As duas atividades sem dependência extra (Patrocinador e Grupo
    #    Gestor, executadas pelo Proponente) aparecem prontas, sem exigir
    #    formulário; as demais 6 continuam bloqueadas (dependem de
    #    group_manager COMPLETED).
    tasks_after = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    ready_titles = {
        t['title']
        for t in tasks_after
        if t['title']
        in {'Definir o Patrocinador', 'Definir os integrantes do Grupo Gestor'}
    }
    assert ready_titles == {
        'Definir o Patrocinador',
        'Definir os integrantes do Grupo Gestor',
    }
    for t in tasks_after:
        if t['title'] == 'Definir o Patrocinador':
            assert t['status'] == 'READY'
            assert t['assigned_role'] == 'proponent'

    # 5. Confirmação direta no banco: atividade ativada com o tipo declarado
    #    e nenhum FormInstance criado para ela (Spec 017 FR-005).
    act_stmt = select(ActivityInstance).where(
        ActivityInstance.process_instance_id == process_id,
        ActivityInstance.key == 'assign_sponsor',
    )
    sponsor_act = (await session.execute(act_stmt)).scalar_one()
    assert sponsor_act.activity_type == 'role_assignment'
    assert sponsor_act.status == 'IN_PROGRESS'

    form_stmt = (
        select(FormInstance)
        .join(ActivityRun, FormInstance.activity_run_id == ActivityRun.id)
        .where(ActivityRun.activity_instance_id == sponsor_act.id)
    )
    orphan_forms = (await session.execute(form_stmt)).scalars().all()
    assert orphan_forms == []
