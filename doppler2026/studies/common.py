"""Shared runner for the sparsification studies on synthetic networks.

Runs the controller (§4.14) on one synthetic network in several modes,
prints one summary line per epoch, and writes the summary plus the full
controller output (``docs/results_schema.md``) to
``data/results/doppler2026/studies/<study>/<run_id>/``.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Sequence

from ..controller import ControllerConfig, run
from ..results import new_run_dir, write_config, write_csv, write_jsonl
from ..synthetic import TOPOLOGY_DIR, SyntheticConfig, ensure
from ..topology import REPO_ROOT

COLUMNS = {
    "epoch": "epoch",
    "links": "links",
    "transition_added": "added",
    "transition_removed": "removed",
    "safe": "safe",
    "stale_transferability": "stale_tau",
    "selected_transferability": "selected_T",
    "current_mlu": "mlu",
    "current_max_stretch": "max_stretch",
    "current_mean_stretch": "mean_stretch",
    "stale_benign_loss": "stale_loss",
}
"""Controller column -> summary column, in print order."""


def summary_row(mode: str, epoch: dict) -> dict:
    return {"mode": mode, **{new: epoch.get(old) for old, new in COLUMNS.items()}}


def _fmt(value) -> str:
    if value is None or value != value:  # None or NaN
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def run_study(
    study: str,
    network: SyntheticConfig,
    epochs: int,
    modes: Sequence[str],
    description: str,
) -> None:
    """Command-line entry point of a study: parse ``--run-id``, run, write."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run-id")
    args = parser.parse_args()

    ensure(network)
    configs = {
        mode: ControllerConfig(
            network=network.name,
            topology_dir=str(TOPOLOGY_DIR.relative_to(REPO_ROOT)),
            epochs=epochs,
            mode=mode,
        )
        for mode in modes
    }
    run_dir = new_run_dir(f"studies/{study}", args.run_id)
    write_config(
        run_dir,
        {
            "study": study,
            "network": dataclasses.asdict(network),
            "runs": {m: dataclasses.asdict(c) for m, c in configs.items()},
        },
    )

    rows, candidates, transfers, transitions, summary = [], [], [], [], []
    for mode, config in configs.items():
        print(f"== {mode}", flush=True)
        print("  ".join(f"{c:>12}" for c in COLUMNS.values()), flush=True)

        def progress(row: dict, mode: str = mode) -> None:
            values = list(summary_row(mode, row).values())[1:]  # drop the mode
            print("  ".join(f"{_fmt(v):>12}" for v in values), flush=True)

        result = run(config, progress=progress)
        rows += result.epochs
        candidates += result.candidates
        transfers += result.transferability
        transitions += [{"mode": mode, **t} for t in result.transitions]
        summary += [summary_row(mode, row) for row in result.epochs]

    write_csv(run_dir, "summary.csv", summary)
    write_csv(run_dir, "epochs.csv", rows)
    write_csv(run_dir, "candidates.csv", candidates)
    write_csv(run_dir, "transferability.csv", transfers)
    write_jsonl(run_dir, "transitions.jsonl", transitions)
    print(run_dir)
