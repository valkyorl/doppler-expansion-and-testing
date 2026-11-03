"""Writing result files in the schema of PLAN.md §10.

Every run gets its own folder, ``data/results/doppler2026/<experiment>/<run_id>/``,
with a ``config.json`` that is enough to rerun it (the resolved settings,
seeds, git commit, and package versions) and tidy CSV files: one
observation per row, so any figure is a filter and a group-by away. Figure
scripts in ``figures/`` read only these files (rule 6 in ``CLAUDE.md``).
"""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from .topology import REPO_ROOT

RESULTS_ROOT = REPO_ROOT / "data" / "results" / "doppler2026"

PACKAGES = (
    "networkx",
    "numpy",
    "scipy",
    "highspy",
    "GraphRicciCurvature",
    "POT",
    "networkit",
)
"""Packages whose versions are recorded with every run."""


def new_run_dir(
    experiment: str, run_id: str | None = None, root: Path = RESULTS_ROOT
) -> Path:
    """Create and return the folder for one run. ``run_id`` defaults to a UTC timestamp."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / experiment / run_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def provenance() -> dict[str, object]:
    """Git commit (and whether the tree had uncommitted changes), Python, packages."""

    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"

    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "python": platform.python_version(),
        "packages": versions,
        "written_at": datetime.now(UTC).isoformat(),
    }


def write_config(run_dir: Path, config: Mapping[str, object]) -> None:
    """Write ``config.json``: the run's settings plus ``provenance()``."""
    payload = {"config": dict(config), "provenance": provenance()}
    (run_dir / "config.json").write_text(json.dumps(payload, indent=2, default=str))


def write_csv(run_dir: Path, name: str, rows: Iterable[Mapping[str, object]]) -> Path:
    """Write rows to ``<run_dir>/<name>``. Columns are the union of all keys, in first-seen order."""
    rows = list(rows)
    columns: dict[str, None] = {}
    for row in rows:
        columns.update(dict.fromkeys(row))
    path = run_dir / name
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path
