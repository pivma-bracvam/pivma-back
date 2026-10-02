"""Processo pronto para a atividade de amostras (Spec 031).

Usa um template mínimo em que ``sample_definition`` não tem dependências e
já nasce ``IN_PROGRESS``, para que os testes de amostras não dependam da
Fase 2 dos templates reais.
"""

import itertools
from types import SimpleNamespace

from pivma.bootstrap_process_templates import sync_template_from_dict
from pivma.core.database.models import Assignment, Laboratory, User
from pivma.core.process_engine import instantiate_process
from tests.factories.institutional_factory import (
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory

SAMPLE_TEMPLATE = {
    'process_template': {
        'key': 'sample_probe',
        'name': 'Amostras cegas',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_samples',
            'name': 'Amostras',
            'order_index': 1,
            'activities': [
                {
                    'key': 'sample_definition',
                    'name': 'Definição e Preparação das Amostras',
                    'order_index': 1,
                    'assigned_role': 'sample_selection_group',
                    'access': {
                        'edit': ['sample_selection_group'],
                        'view': [],
                    },
                    'activity_type': 'sample_definition',
                    'dependencies': [],
                }
            ],
        }
    ],
    'forms': [],
}

# CAS válidos (dígito verificador correto), distintos entre si.
VALID_CAS = (
    '50-00-0',
    '7732-18-5',
    '64-17-5',
    '67-64-1',
    '71-43-2',
    '1310-73-2',
    '7647-14-5',
    '108-88-3',
)
_cas_cycle = itertools.count()


def next_cas() -> str:
    return VALID_CAS[next(_cas_cycle) % len(VALID_CAS)]


def substance_payload(**overrides) -> dict:
    payload = {
        'chemical_name': 'Formaldeído',
        'cas_number': '50-00-0',
        'lot': 'L-2026-04',
        'purity': '≥ 37%',
        'solubility': 'Miscível em água',
        'safe_handling_instructions': (
            'Tóxico por inalação. Usar luvas nitrílicas e capela.'
        ),
    }
    payload.update(overrides)
    return payload


async def _user(session) -> User:
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def lab_user(session, laboratory: Laboratory) -> User:
    """Usuário afiliado ao laboratório (pré-condição dos cargos de lab)."""
    user = await _user(session)
    affiliation = UserInstitutionalAffiliationFactory(
        user=user,
        institution=SimpleNamespace(id=laboratory.institution_id),
        laboratory=laboratory,
    )
    session.add(affiliation)
    await session.commit()
    return user


async def assign_lab(
    session,
    process_id,
    laboratory: Laboratory,
    *,
    role_key: str = 'participating_laboratory',
    user: User | None = None,
) -> Assignment:
    user = user or await lab_user(session, laboratory)
    assignment = Assignment(
        process_instance_id=process_id,
        user_id=user.id,
        assigned_by=user.id,
        role_key=role_key,
        laboratory_id=laboratory.id,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def new_laboratory(session) -> Laboratory:
    institution = InstitutionFactory()
    session.add(institution)
    await session.commit()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()
    return laboratory


async def add_participating_lab(
    session, process_id, *, role_key: str = 'participating_laboratory'
) -> SimpleNamespace:
    laboratory = await new_laboratory(session)
    assignment = await assign_lab(
        session, process_id, laboratory, role_key=role_key
    )
    user = await session.get(User, assignment.user_id)
    return SimpleNamespace(
        laboratory=laboratory, user=user, assignment=assignment
    )


async def sample_process(
    session, *, lab_count: int = 3, template: dict = SAMPLE_TEMPLATE
) -> SimpleNamespace:
    """Processo com `sample_definition` aberta, Grupo de Seleção e labs."""
    _, version, _ = await sync_template_from_dict(session, template)
    creator = await _user(session)
    process = await instantiate_process(
        session, version, 'Estudo cego', creator.id
    )
    selector = await _user(session)
    await grant_cargo(
        session,
        process_id=process.id,
        user=selector,
        role_key='sample_selection_group',
    )
    labs = [
        await add_participating_lab(session, process.id)
        for _ in range(lab_count)
    ]
    return SimpleNamespace(
        process_id=process.id,
        process=process,
        creator=creator,
        selector=selector,
        labs=[lab.laboratory for lab in labs],
        lab_users=[lab.user for lab in labs],
    )
