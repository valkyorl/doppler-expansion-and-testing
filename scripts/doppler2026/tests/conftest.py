"""Pytest setup for the Doppler 2026 tests.

pytest puts this tests folder on ``sys.path``, not the repository root, so
``import scripts.doppler2026`` would fail. Adding the root here lets the
tests import the experiment the same way ``python -m scripts.doppler2026...``
does, without changing the repository-wide pytest configuration.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
