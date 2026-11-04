"""Jornadas: perfil do usuário, cargos globais e cargos locais.

Spec 045, US1. Persona: uma pessoa recém-cadastrada. Ela abre o próprio perfil
com o `id` de `GET /auth/me` e vê os dados da conta, sem o nome de usuário,
e nenhum cargo global. O Administrador concede o perfil BraCVAM, e a pessoa
passa a ver o cargo com a data da atribuição. Depois da revogação, o cargo
some do perfil.

Spec 045, US2. Persona: uma proponente com dois processos. Ela vê um item por
processo, o mais recente primeiro, cada um com o seu cargo. Quando o
Administrador a designa estatística no primeiro processo, esse processo passa
à frente com os dois cargos. Depois da revogação, a estatística sai dos
cargos ativos e aparece só entre os revogados, com a data da revogação.

Spec 045, US3. Persona: o Administrador. Ele acha uma pessoa na listagem de
contas e abre o perfil e os cargos locais dela, que são os mesmos que a pessoa
vê. Depois de desativar a conta, ele ainda abre o perfil, agora inativo, e os
cargos continuam listados. Uma pessoa comum que tenta abrir o perfil do
Administrador é recusada.
"""

from datetime import datetime
from http import HTTPStatus

import pytest

from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)


def ok(response, status=HTTPStatus.OK):
    assert response.status_code == status, response.text
    return response.json()


def profile_id_by_name(client, name):
    profiles = ok(client.get('/rbac/profiles', params={'per_page': 100}))
    return next(
        item['id'] for item in profiles['data'] if item['name'] == name
    )


@pytest.mark.asyncio
async def test_pessoa_ve_o_proprio_perfil_com_cargos_globais_vigentes(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. A pessoa se cadastra e entra.
    sign_up(client, 'ana')
    log_in(client, 'ana')

    # 2. Ela abre o próprio perfil e vê os dados da conta, sem username.
    user_id = ok(client.get('/auth/me'))['user']['id']
    profile = ok(client.get(f'/users/{user_id}'))
    assert profile['id'] == user_id
    assert profile['full_name'] == 'Usuário ana'
    assert profile['email'] == 'ana@example.com'
    assert profile['active'] is True
    assert datetime.fromisoformat(profile['created_at'])
    assert profile['global_profiles'] == []
    assert 'username' not in profile

    # 3. O Administrador entra e concede o perfil BraCVAM.
    log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    bracvam_id = profile_id_by_name(client, 'BraCVAM')
    ok(
        client.post(f'/rbac/users/{user_id}/profiles/{bracvam_id}'),
        HTTPStatus.CREATED,
    )

    # 4. A pessoa entra de novo e vê o BraCVAM com a data da atribuição.
    log_out(client)
    log_in(client, 'ana')
    profile = ok(client.get(f'/users/{user_id}'))
    [granted] = profile['global_profiles']
    assert granted['id'] == bracvam_id
    assert granted['name'] == 'BraCVAM'
    assert datetime.fromisoformat(granted['assigned_at'])

    # 5. O Administrador revoga o perfil.
    log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.delete(f'/rbac/users/{user_id}/profiles/{bracvam_id}')
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    # 6. A pessoa entra de novo e não vê mais cargo global.
    log_out(client)
    log_in(client, 'ana')
    assert ok(client.get(f'/users/{user_id}'))['global_profiles'] == []


def create_process(client, title):
    return ok(
        client.post(
            '/processes',
            json={'template_key': 'pre_validated_method', 'title': title},
        ),
        HTTPStatus.CREATED,
    )['id']


def process_roles(client, user_id, **params):
    page = ok(client.get(f'/users/{user_id}/process-roles', params=params))
    return [
        (item['process']['id'], [role['role_key'] for role in item['roles']])
        for item in page['data']
    ], page


@pytest.mark.asyncio
async def test_proponente_ve_cargos_ativos_e_revogados_por_processo(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. A pessoa se cadastra, entra e cria dois processos.
    sign_up(client, 'bia')
    log_in(client, 'bia')
    user_id = ok(client.get('/auth/me'))['user']['id']
    first = create_process(client, 'Método A')
    second = create_process(client, 'Método B')

    # 2. Ela vê dois itens, o segundo processo primeiro, cada um com o
    #    cargo de proponente ainda vigente.
    items, page = process_roles(client, user_id)
    assert items == [(second, ['proponent']), (first, ['proponent'])]
    assert all(
        role['revoked_at'] is None
        for item in page['data']
        for role in item['roles']
    )

    # 3. O Administrador entra e designa a pessoa estatística no primeiro.
    log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    designation = ok(
        client.post(
            f'/processes/{first}/participants',
            json={'user_id': user_id, 'role_key': 'statistician'},
        ),
        HTTPStatus.CREATED,
    )

    # 4. A pessoa entra de novo: o primeiro processo passa à frente, com a
    #    designação nova antes da de proponente.
    log_out(client)
    log_in(client, 'bia')
    items, _ = process_roles(client, user_id)
    assert items == [
        (first, ['statistician', 'proponent']),
        (second, ['proponent']),
    ]

    # 5. O Administrador revoga a designação de estatística.
    log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.delete(
        f'/processes/{first}/participants/{designation["id"]}'
    )
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    # 6. A pessoa entra de novo: nos ativos, o primeiro processo tem só o
    #    cargo de proponente e volta para trás; nos revogados, aparece só a
    #    estatística, com a data da revogação.
    log_out(client)
    log_in(client, 'bia')
    items, _ = process_roles(client, user_id)
    assert items == [(second, ['proponent']), (first, ['proponent'])]
    items, page = process_roles(client, user_id, active='false')
    assert items == [(first, ['statistician'])]
    [revoked] = page['data'][0]['roles']
    assert revoked['id'] == designation['id']
    assert datetime.fromisoformat(revoked['revoked_at'])


@pytest.mark.asyncio
async def test_administrador_abre_perfil_de_pessoa_achada_na_listagem(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. A pessoa se cadastra, entra, cria um processo e abre o próprio
    #    perfil e os próprios cargos locais.
    sign_up(client, 'caio')
    log_in(client, 'caio')
    user_id = ok(client.get('/auth/me'))['user']['id']
    create_process(client, 'Método C')
    own_profile = ok(client.get(f'/users/{user_id}'))
    own_roles = ok(client.get(f'/users/{user_id}/process-roles'))

    # 2. O Administrador entra, acha a pessoa na listagem e vê o mesmo
    #    perfil e os mesmos cargos locais.
    log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_id = ok(client.get('/auth/me'))['user']['id']
    listing = ok(client.get('/users', params={'search': 'caio'}))
    assert [item['id'] for item in listing['data']] == [user_id]
    assert ok(client.get(f'/users/{user_id}')) == own_profile
    assert ok(client.get(f'/users/{user_id}/process-roles')) == own_roles

    # 3. O Administrador desativa a conta.
    response = client.delete(f'/users/{user_id}')
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    # 4. Ele abre o perfil de novo e vê a conta inativa, com os cargos
    #    locais ainda listados.
    assert ok(client.get(f'/users/{user_id}'))['active'] is False
    assert ok(client.get(f'/users/{user_id}/process-roles')) == own_roles

    # 5. Uma pessoa comum entra e tenta abrir o perfil do Administrador.
    log_out(client)
    sign_up(client, 'duda')
    log_in(client, 'duda')
    response = client.get(f'/users/{admin_id}')
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
