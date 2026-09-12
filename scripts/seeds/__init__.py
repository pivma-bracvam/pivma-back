"""Scripts de carga (seeds) para o PIVMA."""

import sys
from pathlib import Path

_src_dir = str(Path(__file__).resolve().parents[2] / 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
