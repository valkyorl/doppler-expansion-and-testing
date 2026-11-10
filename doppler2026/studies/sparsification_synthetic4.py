"""Study: does the baseline Doppler make a fully linked 4-PoP network sparser?

Question. On the 15-PoP synthetic network the baseline Doppler never moves
(floods do too little damage there for any candidate to pass the τ filter),
while churn shows the generator's bias toward removals. On the smallest
network where every candidate must be a removal, every PoP pair linked, does
Doppler itself remove links, and what happens to transferability, MLU, path
stretch, and the stale attack's damage as it does? Small enough (36 distinct
candidates in the first epoch) to inspect candidate by candidate.

Setup (decided by the user, 2026-11-10):

- Network ``synthetic4`` from ``doppler2026.synthetic``: 4 PoPs at random
  in the 1,500 km Midwest square (seed 0), all 6 PoP pairs linked
  (``mean_degree`` 3), 100 Gb/s each. With every pair linked, the generator's
  link rule does not matter.
- 30 epochs in each of three modes: ``static`` (never changes), ``doppler``,
  and ``churn`` (Eq. 18 baseline, no security filter).
- Everything else is the controller's default (baseline BL1,
  ``docs/decisions.md``), including the gravity benign traffic at 50% peak
  utilization (I5), random MILP weights (D22), the traceroute attacker with
  10% silent routers, and 10 attacked pairs (of 12 ordered pairs here).

Recorded per epoch and mode (``summary.csv``, also printed): active links,
links added and removed by the transition, safe candidates, τ of the stale
attack running in the epoch, T(G') of the selected topology, MLU, and the
largest and demand-weighted mean path stretch against G_0. The full
controller output (``epochs.csv``, ``candidates.csv``,
``transferability.csv``, ``transitions.jsonl``) is saved alongside.

    python -m doppler2026.studies.sparsification_synthetic4 [--run-id ID]

Output: ``data/results/doppler2026/studies/sparsification_synthetic4/<run_id>/``.
"""

from __future__ import annotations

from ..synthetic import SyntheticConfig
from .common import run_study

STUDY = "sparsification_synthetic4"
NETWORK = SyntheticConfig(name="synthetic4", nodes=4, mean_degree=3.0)
EPOCHS = 30
MODES = ("static", "doppler", "churn")


def main() -> None:
    run_study(STUDY, NETWORK, EPOCHS, MODES, __doc__.split("\n")[0])


if __name__ == "__main__":
    main()
