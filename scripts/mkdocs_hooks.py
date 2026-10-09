"""Hooks do MkDocs: gera a lista de rotas a partir do OpenAPI da aplicação.

A página `referencia/rotas.md` contém o marcador `<!-- ROTAS -->`, trocado no
build por uma tabela por grupo. Assim a lista nunca diverge do código.
"""

import os
from collections import defaultdict

MARKER = '<!-- ROTAS -->'

# Importar a aplicação valida `Settings`; o build não acessa o banco.
os.environ.setdefault(
    'DATABASE_URL', 'postgresql+psycopg://docs:docs@localhost:5432/docs'
)
os.environ.setdefault('JWT_SECRET_KEY', 'docs-build-' + 'x' * 32)
os.environ.setdefault('AUTH_ALLOWED_ORIGINS', '["http://localhost:3000"]')

GROUPS = {
    'auth': 'Sessão e conta',
    'users': 'Usuários',
    'rbac': 'Perfis e permissões',
    'institutional': 'Catálogo institucional',
    'Processes': 'Processos',
    'Forms': 'Formulários',
    'Triage': 'Triagem',
    'Return Review': 'Revisão do retorno',
    'AI Pre-Evaluation': 'Pré-avaliação por IA',
    'AI Evaluations': 'Configuração da IA',
    'Process Participants': 'Participantes e convites',
    'Role Assignment Invites': 'Aceite de convite',
    'Tasks': 'Tarefas',
    'Samples': 'Amostras cegas',
    'collection-templates': 'Templates de coleta',
    'Laboratory Runs': 'Execução por laboratório',
}


def _routes_markdown() -> str:
    from pivma import app  # noqa: PLC0415

    grouped = defaultdict(list)
    for path, operations in app.openapi()['paths'].items():
        for method, operation in operations.items():
            tags = operation.get('tags') or []
            if not tags:
                continue
            success = sorted(
                code
                for code in operation.get('responses', {})
                if code.startswith('2')
            )
            grouped[tags[0]].append((
                path,
                method.upper(),
                operation.get('summary', ''),
                ', '.join(success),
            ))

    lines = []
    for tag, title in GROUPS.items():
        if tag not in grouped:
            continue
        lines += [
            f'## {title}',
            '',
            '| Método | Rota | Operação | Sucesso |',
            '|---|---|---|---|',
        ]
        for path, method, summary, success in grouped.pop(tag):
            lines.append(f'| `{method}` | `{path}` | {summary} | {success} |')
        lines.append('')
    for tag, routes in grouped.items():
        lines += [f'## {tag}', '', '| Método | Rota | Operação | Sucesso |']
        lines.append('|---|---|---|---|')
        for path, method, summary, success in routes:
            lines.append(f'| `{method}` | `{path}` | {summary} | {success} |')
        lines.append('')
    return '\n'.join(lines)


def on_page_markdown(markdown, page, **kwargs):
    if MARKER in markdown:
        return markdown.replace(MARKER, _routes_markdown())
    return markdown
