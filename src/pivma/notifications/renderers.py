"""Modelo de cada tipo de aviso (Spec 036, research R12).

Um renderizador recebe o conteúdo decifrado e devolve assunto, texto simples
e HTML. Valores entram no HTML sempre escapados.
"""

from collections.abc import Callable
from datetime import datetime
from html import escape
from typing import Any

Renderer = Callable[[dict[str, Any]], tuple[str, str, str]]

RENDERERS: dict[str, Renderer] = {}

INVITE_EMAIL = 'invite_email'


def get_renderer(kind: str) -> Renderer:
    try:
        return RENDERERS[kind]
    except KeyError:
        raise ValueError(
            f'Nenhum renderizador registrado para o kind {kind!r}.'
        ) from None


# --- Convite de designação (Spec 028 + Spec 036) ---

# Nomes dos papéis como aparecem nas atividades de atribuição de cargo dos
# templates; papéis fora dos templates usam o nome do Plano de Trabalho.
ROLE_LABELS = {
    'sponsor': 'Patrocinador',
    'group_manager': 'Grupo Gestor',
    'sample_selection_group': 'Grupo de Seleção de Amostras',
    'lead_laboratory': 'Laboratório Líder',
    'participating_laboratory': 'Laboratório Participante',
    'statistician': 'Estatístico',
    'collaborator': 'Colaboradores e Observadores',
    'adhoc_evaluator': 'Especialistas Temáticos (Comitê ADHOC)',
    'study_manager': 'Gerente do Estudo',
    'peer_reviewer': 'Revisor',
    'proponent': 'Proponente',
    'regulatory_observer': 'Observador Regulatório',
}


def _format_deadline(value: str) -> str:
    return datetime.fromisoformat(value).strftime('%d/%m/%Y %H:%M (UTC)')


def render_invite_email(payload: dict[str, Any]) -> tuple[str, str, str]:
    role = ROLE_LABELS.get(payload['role_key'], payload['role_key'])
    process = f'{payload["process_code"]} — {payload["process_title"]}'
    deadline = _format_deadline(payload['expires_at'])
    url = payload['invite_url']
    laboratory = payload.get('laboratory_name')

    lines = [
        'Você foi convidado para participar de um processo na pi*VMA.',
        '',
        f'Processo: {process}',
        f'Papel: {role}',
    ]
    if laboratory:
        lines.append(f'Laboratório: {laboratory}')
    lines += [
        f'Válido até: {deadline}',
        '',
        'Para aceitar, acesse o link abaixo e entre com este e-mail:',
        url,
        '',
        'Se você não esperava este convite, ignore esta mensagem.',
    ]

    def item(label: str, value: str) -> str:
        return f'<li><strong>{label}:</strong> {escape(value)}</li>'

    items = [item('Processo', process), item('Papel', role)]
    if laboratory:
        items.append(item('Laboratório', laboratory))
    items.append(item('Válido até', deadline))
    safe_url = escape(url, quote=True)
    html = (
        '<p>Você foi convidado para participar de um processo na pi*VMA.</p>'
        f'<ul>{"".join(items)}</ul>'
        '<p>Para aceitar, acesse o link abaixo e entre com este e-mail:</p>'
        f'<p><a href="{safe_url}">{safe_url}</a></p>'
        '<p>Se você não esperava este convite, ignore esta mensagem.</p>'
    )
    subject = f'Convite para o processo {payload["process_code"]} na pi*VMA'
    return subject, '\n'.join(lines), html


RENDERERS[INVITE_EMAIL] = render_invite_email


# --- Redefinição de senha (Spec 039) ---

PASSWORD_RESET_EMAIL = 'password_reset_email'


def render_password_reset_email(
    payload: dict[str, Any],
) -> tuple[str, str, str]:
    deadline = _format_deadline(payload['expires_at'])
    url = payload['reset_url']
    text = '\n'.join([
        'Recebemos um pedido para redefinir a sua senha na pi*VMA.',
        '',
        'Para criar uma nova senha, acesse o link abaixo:',
        url,
        '',
        f'Válido até: {deadline}',
        '',
        'Se você não pediu a redefinição, ignore esta mensagem.',
    ])
    safe_url = escape(url, quote=True)
    html = (
        '<p>Recebemos um pedido para redefinir a sua senha na pi*VMA.</p>'
        '<p>Para criar uma nova senha, acesse o link abaixo:</p>'
        f'<p><a href="{safe_url}">{safe_url}</a></p>'
        f'<p><strong>Válido até:</strong> {deadline}</p>'
        '<p>Se você não pediu a redefinição, ignore esta mensagem.</p>'
    )
    return 'Redefinição de senha na pi*VMA', text, html


RENDERERS[PASSWORD_RESET_EMAIL] = render_password_reset_email


# --- Problema no recebimento de amostras (Spec 040) ---

SAMPLE_NONCONFORMITY_EMAIL = 'sample_receipt_nonconformity_email'

DEVIATION_LABELS = {
    'temperature_out_of_range': 'temperatura fora da faixa',
    'package_damaged': 'embalagem avariada',
    'package_violated': 'embalagem violada',
}


def render_sample_nonconformity_email(
    payload: dict[str, Any],
) -> tuple[str, str, str]:
    """Aviso ao Grupo de Seleção: só processo, laboratório e código cego."""
    process = f'{payload["process_code"]} — {payload["process_title"]}'
    reasons = ', '.join(
        DEVIATION_LABELS.get(d, d) for d in payload['deviations']
    )
    rows = [
        ('Processo', process),
        ('Laboratório', payload['laboratory_name']),
        ('Código do frasco', payload['blind_code']),
        ('Motivo', reasons),
    ]
    intro = 'Um laboratório registrou um problema no recebimento de amostras.'
    action = (
        'Acesse a pi*VMA para ver o registro e decidir: aceitar com '
        'ressalva, reenviar ou desclassificar.'
    )
    text = '\n'.join([
        intro,
        '',
        *(f'{label}: {value}' for label, value in rows),
        '',
        action,
    ])
    items = ''.join(
        f'<li><strong>{label}:</strong> {escape(value)}</li>'
        for label, value in rows
    )
    html = f'<p>{intro}</p><ul>{items}</ul><p>{escape(action)}</p>'
    subject = (
        f'Problema no recebimento de amostras — {payload["process_code"]}'
    )
    return subject, text, html


RENDERERS[SAMPLE_NONCONFORMITY_EMAIL] = render_sample_nonconformity_email


# --- Decisão sobre o problema no recebimento (Spec 040, FR-049) ---

SAMPLE_DECISION_EMAIL = 'sample_receipt_decision_email'

DECISION_STATUS_LABELS = {
    'accepted_with_caveat': 'aceito com ressalva: o frasco vale como recebido',
    'replaced': (
        'substituído: um novo frasco, com outro código, será enviado ao '
        'laboratório'
    ),
    'disqualified': (
        'desclassificado: o laboratório foi dispensado nesta etapa'
    ),
}


def render_sample_decision_email(
    payload: dict[str, Any],
) -> tuple[str, str, str]:
    """Aviso ao laboratório: situação do frasco e orientação, sem
    justificativa nem código novo."""
    process = f'{payload["process_code"]} — {payload["process_title"]}'
    guidance = payload.get('lab_guidance') or 'Nenhuma orientação adicional.'
    rows = [
        ('Processo', process),
        ('Laboratório', payload['laboratory_name']),
        ('Código do frasco', payload['blind_code']),
        ('Situação', DECISION_STATUS_LABELS[payload['vial_status']]),
        ('Orientação', guidance),
    ]
    intro = (
        'A equipe responsável pelas amostras decidiu sobre o problema '
        'registrado no recebimento.'
    )
    action = 'Acesse a pi*VMA para ver a situação dos frascos do laboratório.'
    text = '\n'.join([
        intro,
        '',
        *(f'{label}: {value}' for label, value in rows),
        '',
        action,
    ])
    items = ''.join(
        f'<li><strong>{label}:</strong> {escape(value)}</li>'
        for label, value in rows
    )
    html = f'<p>{intro}</p><ul>{items}</ul><p>{action}</p>'
    subject = (
        f'Decisão sobre o recebimento de amostras — {payload["process_code"]}'
    )
    return subject, text, html


RENDERERS[SAMPLE_DECISION_EMAIL] = render_sample_decision_email
