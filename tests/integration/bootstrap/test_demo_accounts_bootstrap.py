"""Contas de demonstração do deploy de desenvolvimento (TEMPORÁRIO).

Jornada: a equipe sobe o deploy de dev com o arquivo de contas. A pessoa do
BraCVAM de demonstração entra e vê o perfil BraCVAM; a do laboratório entra
e vê o vínculo com o laboratório. Uma segunda subida não duplica nada.
"""

from http import HTTPStatus

import pytest
import yaml
from sqlalchemy import func, select

from pivma.bootstrap_demo_accounts import (
    DEMO_ACCOUNTS_FILE,
    sync_demo_accounts,
)
from pivma.bootstrap_system import sync_canonical_profiles
from pivma.core.database.models import Laboratory, User
from pivma.core.security import hash_password
from tests.integration.journeys.conftest import (
    PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
)

DEMO_FILE = """
institution: "Instituição de Demonstração"
laboratories: ["Laboratório Demo A"]
accounts:
  - username: "demo.bracvam"
    full_name: "Demo BraCVAM"
    password_hash: "{hash}"
    profile: "bracvam"
  - username: "demo.lab.a"
    full_name: "Demo Laboratório A"
    password_hash: "{hash}"
    laboratory: "Laboratório Demo A"
"""
DEMO_ACCOUNT_COUNT = 2


async def _deploy_with_demo_file(session, monkeypatch, file_path):
    await bootstrap_fresh_deploy(session, monkeypatch)
    profiles = await sync_canonical_profiles(session)
    await sync_demo_accounts(session, profiles, file_path)
    await session.commit()


@pytest.mark.asyncio
async def test_contas_de_demonstracao_entram_com_perfil_e_laboratorio(
    client, session, monkeypatch, tmp_path
):
    # O login exige Origin confiável, como faria o navegador.
    client.headers['Origin'] = 'https://testserver'
    demo_file = tmp_path / 'demo_accounts.yaml'
    demo_file.write_text(
        DEMO_FILE.format(hash=hash_password(PASSWORD)), encoding='utf-8'
    )

    # 1. A equipe sobe o deploy com o arquivo de contas.
    await _deploy_with_demo_file(session, monkeypatch, demo_file)

    # 2. A pessoa do BraCVAM entra e vê o perfil BraCVAM.
    log_in(client, 'demo.bracvam')
    me = client.get('/auth/me').json()
    assert me['user']['email'] == 'demo.bracvam@example.com'
    assert [p['name'] for p in me['access']['profiles']] == ['BraCVAM']

    # 3. A pessoa do laboratório entra, sem perfil, e vê o vínculo.
    log_in(client, 'demo.lab.a')
    assert client.get('/auth/me').json()['access']['profiles'] == []
    response = client.get('/institutional/me/affiliations')
    assert response.status_code == HTTPStatus.OK, response.text
    assert [
        (a['institution']['name'], a['laboratory']['name'])
        for a in response.json()['data']
    ] == [('Instituição de Demonstração', 'Laboratório Demo A')]

    # 4. A segunda subida não duplica contas nem laboratórios.
    profiles = await sync_canonical_profiles(session)
    await sync_demo_accounts(session, profiles, demo_file)
    await session.commit()
    assert (
        await session.scalar(
            select(func.count(User.id)).where(User.username.like('demo.%'))
        )
        == DEMO_ACCOUNT_COUNT
    )
    assert await session.scalar(select(func.count(Laboratory.id))) == 1


@pytest.mark.asyncio
async def test_sem_o_arquivo_nenhuma_conta_de_demonstracao_e_criada(
    session, monkeypatch, tmp_path
):
    await _deploy_with_demo_file(
        session, monkeypatch, tmp_path / 'ausente.yaml'
    )

    assert (
        await session.scalar(
            select(func.count(User.id)).where(User.username.like('demo.%'))
        )
        == 0
    )


def test_arquivo_versionado_tem_so_hashes_e_referencias_validas():
    data = yaml.safe_load(DEMO_ACCOUNTS_FILE.read_text(encoding='utf-8'))

    usernames = [a['username'] for a in data['accounts']]
    assert len(usernames) == len(set(usernames))
    for account in data['accounts']:
        assert set(account) <= {
            'username',
            'full_name',
            'password_hash',
            'profile',
            'laboratory',
        }
        assert account['password_hash'].startswith('$argon2id$')
        assert account.get('profile') in {None, 'administrator', 'bracvam'}
        assert account.get('laboratory') in {None, *data['laboratories']}
