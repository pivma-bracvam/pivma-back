"""Helpers compartilhados dos testes de avaliação por IA (Spec 013)."""

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}
AI_EVAL_CODES = ('ai_evaluations.read', 'ai_evaluations.manage')

SUBMISSION_TEMPLATE = 'submission_validated_dossier_v1'
AI_FIELD = 'terminology_notes'
FULL_VALUES = {
    'method_title': 'Método 3T3 NRU',
    'terminology_notes': (
        'O conceito central usa metodologia detalhada de captação de '
        'vermelho neutro (NRU) como marcador de viabilidade celular, com '
        'terminologia alinhada às diretrizes da OCDE.'
    ),
}


# Com o provedor fake: se o enunciado tiver palavra-chave presente no
# conteúdo submetido, o critério é "compliant"; senão "non_compliant".
COMPLIANT_STATEMENT = 'Deve apresentar metodologia detalhada'
NON_COMPLIANT_STATEMENT = 'Deve conter cronograma financeiro aprovado'


def publish_evaluation_and_assign(
    client, *, severity: str, statement: str = COMPLIANT_STATEMENT
) -> str:
    """Cria/publica uma avaliação e a associa ao campo de IA do template."""
    created = client.post(
        '/ai-evaluations',
        json={
            'name': f'Avaliação {severity} {statement[:20]}',
            'mode': 'simple',
            'objective': 'Avaliar a justificativa científica submetida.',
        },
        headers=TRUSTED_ORIGIN,
    )
    definition_id = created.json()['id']
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={
            'criteria': [
                {
                    'order_index': 0,
                    'statement': statement,
                    'check_type': 'quality',
                    'severity': severity,
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    client.put(
        f'/form-templates/{SUBMISSION_TEMPLATE}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [AI_FIELD],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    return definition_id


def create_and_submit_process(client, *, values: dict | None = None) -> dict:
    """Cria uma instância de processo e submete o formulário."""
    process_id = client.post(
        '/processes',
        json={
            'template_key': 'validated_method_dossier',
            'title': 'Estudo de Pré-avaliação',
        },
    ).json()['id']
    submit = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': values or FULL_VALUES},
    )
    return {
        'process_id': process_id,
        'status_code': submit.status_code,
        'body': submit.json(),
    }
