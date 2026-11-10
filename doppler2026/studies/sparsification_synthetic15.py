"""Study: does the baseline Doppler make a dense synthetic network sparser?

Question. Under the 2026-11-10 baseline (no spare transponders, no link
floor, security filter = τ only), the candidate generator mostly offers link
removals. On a 15-PoP network with 6 links per PoP on average, does the
network lose links epoch after epoch, and what happens to transferability,
MLU, and path stretch as it does?

Setup (decided by the user, 2026-11-10):

- Network ``synthetic15`` from ``doppler2026.synthetic`` with its defaults:
  15 PoPs at random in a 1,500 km square in the US Midwest, each linked to
  its 2 nearest PoPs, then the closest pairs up to 45 links, 100 Gb/s each.
- 30 epochs in each of three modes: ``static`` (never changes), ``doppler``,
  and ``churn`` (Eq. 18 baseline, no security filter).
- Everything else is the controller's default (``docs/decisions.md``),
  including the gravity benign traffic at 50% peak utilization (I5).

Recorded per epoch and mode (``summary.csv``, also printed): active links,
links added and removed by the transition, safe candidates, τ of the stale
attack running in the epoch, T(G') of the selected topology, MLU, and the
largest and demand-weighted mean path stretch against G_0. The full
controller output (``epochs.csv``, ``candidates.csv``,
``transferability.csv``, ``transitions.jsonl``) is saved alongside.

    python -m doppler2026.studies.sparsification_synthetic15 [--run-id ID]

Output: ``data/results/doppler2026/studies/sparsification_synthetic15/<run_id>/``.
"""

from __future__ import annotations

import argparse
import dataclasses

from ..controller import ControllerConfig, run
from ..results import new_run_dir, write_config, write_csv, write_jsonl
from ..synthetic import TOPOLOGY_DIR, SyntheticConfig, ensure
from ..topology import REPO_ROOT

STUDY = "studies/sparsification_synthetic15"
NETWORK = SyntheticConfig()
EPOCHS = 30
MODES = ("static", "doppler", "churn")

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


def summary_row(mode: str, epoch: dict) -> dict:
    return {"mode": mode, **{new: epoch.get(old) for old, new in COLUMNS.items()}}


def _fmt(value) -> str:
    if value is None or value != value:  # None or NaN
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run-id")
    args = parser.parse_args()

    ensure(NETWORK)
    configs = {
        mode: ControllerConfig(
            network=NETWORK.name,
            topology_dir=str(TOPOLOGY_DIR.relative_to(REPO_ROOT)),
            epochs=EPOCHS,
            mode=mode,
        )
        for mode in MODES
    }
    run_dir = new_run_dir(STUDY, args.run_id)
    write_config(
        run_dir,
        {
            "study": STUDY,
            "network": dataclasses.asdict(NETWORK),
            "runs": {m: dataclasses.asdict(c) for m, c in configs.items()},
        },
    )

    epochs, candidates, transfers, transitions, summary = [], [], [], [], []
    for mode, config in configs.items():
        print(f"== {mode}", flush=True)
        print("  ".join(f"{c:>12}" for c in COLUMNS.values()), flush=True)

        def progress(row: dict, mode: str = mode) -> None:
            print(
                "  ".join(
                    f"{_fmt(v):>12}"
                    for v in summary_row(mode, row).values()
                    if v != mode
                ),
                flush=True,
            )

        result = run(config, progress=progress)
        epochs += result.epochs
        candidates += result.candidates
        transfers += result.transferability
        transitions += [{"mode": mode, **t} for t in result.transitions]
        summary += [summary_row(mode, row) for row in result.epochs]

    write_csv(run_dir, "summary.csv", summary)
    write_csv(run_dir, "epochs.csv", epochs)
    write_csv(run_dir, "candidates.csv", candidates)
    write_csv(run_dir, "transferability.csv", transfers)
    write_jsonl(run_dir, "transitions.jsonl", transitions)
    print(run_dir)


if __name__ == "__main__":
    main()
