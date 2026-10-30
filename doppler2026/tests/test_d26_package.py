"""Smoke test: the experiment package imports the way it will be run.

Test files in this folder are prefixed ``test_d26_`` so their names never
collide with tests in the repository-wide ``tests/`` folder.
"""

import importlib


def test_package_imports_from_repo_root():
    package = importlib.import_module("doppler2026")
    assert "Doppler 2026" in package.__doc__
