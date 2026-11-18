"""Shared runners for the sparsification studies on synthetic networks.

``run_study`` runs the controller (§4.14) on one synthetic network in several
modes and prints one summary line per epoch. ``run_layout_study`` does the
same over several layouts, in parallel, and adds one summary row per layout
and mode plus the average over layouts. Both write the summaries and the full
controller output (``docs/results_schema.md``) to
``data/results/doppler2026/studies/<study>/<run_id>/``.
"""

from __future__ import annotations

import argparse
import dataclasses
import multiprocessing
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor

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


def _config(network: SyntheticConfig, epochs: int, mode: str) -> ControllerConfig:
    return ControllerConfig(
        network=network.name,
        topology_dir=str(TOPOLOGY_DIR.relative_to(REPO_ROOT)),
        epochs=epochs,
        mode=mode,
    )


def layout_summary(network: str, mode: str, epochs: Sequence[dict]) -> dict:
    """One layout and mode: how far it sparsified and what the attack did.

    ``end_links`` is the link count in force during the last epoch; a move
    chosen in that epoch has not taken effect yet, but it is counted in
    ``moves``, ``added``, and ``removed``.
    """
    links = [row["links"] for row in epochs]
    moved = [
        row["epoch"]
        for row in epochs
        if row["transition_added"] + row["transition_removed"] > 0
    ]
    losses = [row["stale_benign_loss"] for row in epochs if "stale_benign_loss" in row]
    return {
        "network": network,
        "mode": mode,
        "start_links": links[0],
        "end_links": links[-1],
        "lowest_links": min(links),
        "links_lost": links[0] - links[-1],
        "moves": len(moved),
        "last_move": moved[-1] if moved else None,
        "added": sum(row["transition_added"] for row in epochs),
        "removed": sum(row["transition_removed"] for row in epochs),
        "first_stale_loss": losses[0] if losses else None,
        "last_stale_loss": losses[-1] if losses else None,
        "max_stale_loss": max(losses) if losses else None,
        "max_mlu": max(row["current_mlu"] for row in epochs),
        "max_stretch": max(row["current_max_stretch"] for row in epochs),
    }


def layout_averages(rows: Sequence[dict]) -> list[dict]:
    """Mean of each ``layout_summary`` number over the layouts, per mode.

    ``last_move`` is left out: layouts that never moved have none.
    """
    averages = []
    for mode in dict.fromkeys(row["mode"] for row in rows):
        group = [row for row in rows if row["mode"] == mode]
        average = {"mode": mode, "layouts": len(group)}
        for key in group[0]:
            if key in ("network", "mode", "last_move"):
                continue
            values = [row[key] for row in group if row[key] is not None]
            average[key] = sum(values) / len(values) if values else None
        averages.append(average)
    return averages


def run_layout_study(
    study: str,
    networks: Sequence[SyntheticConfig],
    epochs: int,
    modes: Sequence[str],
    description: str,
    jobs: int = 6,
) -> None:
    """Command-line entry point of a study over several network layouts.

    Each run is its own process, so results do not depend on ``--jobs``.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run-id")
    parser.add_argument("--epochs", type=int, default=epochs)
    parser.add_argument("--jobs", type=int, default=jobs)
    args = parser.parse_args()

    for network in networks:
        ensure(network)
    configs = [_config(n, args.epochs, mode) for n in networks for mode in modes]
    run_dir = new_run_dir(f"studies/{study}", args.run_id)
    write_config(
        run_dir,
        {
            "study": study,
            "networks": [dataclasses.asdict(n) for n in networks],
            "runs": [dataclasses.asdict(c) for c in configs],
        },
    )

    rows, candidates, transfers, transitions, summary, layouts = [], [], [], [], [], []
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        args.jobs, mp_context=context, max_tasks_per_child=1
    ) as pool:
        for config, result in zip(configs, pool.map(run, configs), strict=True):
            mode = config.mode
            rows += result.epochs
            candidates += result.candidates
            transfers += result.transferability
            transitions += [{"mode": mode, **t} for t in result.transitions]
            summary += [
                {"network": config.network, **summary_row(mode, row)}
                for row in result.epochs
            ]
            layouts.append(layout_summary(config.network, mode, result.epochs))
            print(
                "  ".join(f"{k}={_fmt(v)}" for k, v in layouts[-1].items()),
                flush=True,
            )

    averages = layout_averages(layouts)
    print("== average over layouts", flush=True)
    for average in averages:
        print("  ".join(f"{k}={_fmt(v)}" for k, v in average.items()), flush=True)
    write_csv(run_dir, "layouts.csv", layouts)
    write_csv(run_dir, "averages.csv", averages)
    write_csv(run_dir, "summary.csv", summary)
    write_csv(run_dir, "epochs.csv", rows)
    write_csv(run_dir, "candidates.csv", candidates)
    write_csv(run_dir, "transferability.csv", transfers)
    write_jsonl(run_dir, "transitions.jsonl", transitions)
    print(run_dir)


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
    configs = {mode: _config(network, epochs, mode) for mode in modes}
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
