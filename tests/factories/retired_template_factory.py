"""Tipo de processo que sai dos YAMLs entre dois deploys (Spec 044)."""

from pathlib import Path

import pivma
from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    load_yaml_template,
    sync_template_from_dict,
)

RETIRED_KEY = 'proof_of_concept'
RETIRED_NAME = 'Prova de Conceito'
BASE_YAML = (
    Path(pivma.__file__).parent
    / 'templates_data'
    / '01_pre_validated_method.yaml'
)


async def seed_retiring_type(session):
    """Registra um tipo que nenhum YAML do próximo deploy declara."""
    data = load_yaml_template(BASE_YAML)
    data['process_template'] |= {'key': RETIRED_KEY, 'name': RETIRED_NAME}
    await sync_template_from_dict(session, data)
    return data['process_template']['version']


async def deploy_without_retiring_type(session):
    """Roda o bootstrap do deploy, que aposenta o tipo fora dos YAMLs.

    Limpa a sessão, compartilhada com o `client`: cada requisição real abre
    uma sessão nova e não herda o template carregado antes do soft delete.
    """
    await bootstrap_all_templates(session)
    session.expunge_all()
