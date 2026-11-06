"""Respostas de um formulário de submissão pronto para envio."""

from typing import Any


def submission_values(
    method_title: str = 'Método de teste', **extra: Any
) -> dict[str, Any]:
    """Os 12 campos obrigatórios dos formulários de submissão oficiais."""
    return {
        'institution_name': 'Instituto de Testes',
        'institution_nature': 'Pública',
        'proposal_owner': 'Pessoa Proponente',
        'owner_position': 'Pesquisadora',
        'contact_email': 'proponente@example.org',
        'contact_phone': '+55 21 0000-0000',
        'country': 'Brasil',
        'method_title': method_title,
        'method_kind': 'new_method',
        'application_area': 'Toxicologia',
        'method_description': 'Ensaio in vitro de viabilidade celular.',
        'submission_objective': 'Avaliar a prontidão para validação.',
        **extra,
    }
