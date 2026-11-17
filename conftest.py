# ==============================================================================
# NOVA — pytest bootstrap
# ------------------------------------------------------------------------------
# Makes the repo root importable so tests can `import local_agent` no matter
# where pytest is invoked from. (pytest's default import mode adds tests/,
# not the project root, to sys.path.)
# ==============================================================================

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
