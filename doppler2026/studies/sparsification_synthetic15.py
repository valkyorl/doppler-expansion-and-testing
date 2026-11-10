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

from ..synthetic import SyntheticConfig
from .common import run_study

STUDY = "sparsification_synthetic15"
NETWORK = SyntheticConfig()
EPOCHS = 30
MODES = ("static", "doppler", "churn")


def main() -> None:
    run_study(STUDY, NETWORK, EPOCHS, MODES, __doc__.split("\n")[0])


if __name__ == "__main__":
    main()
