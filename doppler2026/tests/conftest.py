"""Pytest setup for the Doppler 2026 tests.

pytest puts this tests folder on ``sys.path``, not the repository root, so
``import doppler2026`` would fail. Adding the root here lets the tests import
the experiment the same way ``python -m doppler2026...`` does, without
changing the repository-wide pytest configuration.
"""

import sys
from pathlib import Path

# doppler2026/tests/conftest.py -> parents[2] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
