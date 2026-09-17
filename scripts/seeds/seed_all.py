"""Script legado mantido para compatibilidade retrospectiva (Spec 025).

Delega diretamente para o orquestrador unificado scripts/seeds/runner.py.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ruff: noqa: E402
from scripts.seeds.runner import main as runner_main
from scripts.seeds.runner import run_seeds


async def run_all_seeds() -> None:
    """Compatibilidade retrospectiva para chamadas de função."""
    await run_seeds(profile='dev')


def main() -> None:
    """Delega argumentos de linha de comando para a CLI do runner."""
    runner_main(sys.argv[1:])


if __name__ == '__main__':
    main()
