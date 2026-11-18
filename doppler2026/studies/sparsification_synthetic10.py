"""Study: the sparsification baseline on eight 10-PoP synthetic layouts.

Question. Under the current defaults (baseline BL1, recon lag 2, the Eq. 19
history), how far does Doppler itself make a 10-PoP network sparser, how
consistently across network layouts, and what happens to the stale attack's
damage, MLU, and path stretch? This is the reference that proposed fixes for
the sparsification (``variants/``) are compared against.

Setup (decided by the user, 2026-11-18; baseline BN1 in ``docs/decisions.md``):

- Eight networks ``synthetic10_s0`` ... ``synthetic10_s7`` from
  ``doppler2026.synthetic``: the same generator with layout seeds 0-7, each
  with 10 PoPs in the 1,500 km Midwest square, average degree 4 (20 links),
  100 Gb/s links. Every layout is kept, including those that barely move, so
  results are reported per layout and as the average over all eight.
- 30 epochs in each of three modes: ``static``, ``doppler``, and ``churn``
  (Eq. 18 baseline, no security filter). Use ``--epochs 15`` for quicker
  comparisons while iterating; the first 15 epochs are the same.
- Everything else is the controller's default (``docs/decisions.md``).

Recorded: ``layouts.csv`` (per layout and mode: links at the start and end,
the lowest count, moves, links added and removed, stale damage, largest MLU
and stretch), ``averages.csv`` (their mean over the layouts), ``summary.csv``
(per epoch), and the full controller output (``epochs.csv``,
``candidates.csv``, ``transferability.csv``, ``transitions.jsonl``).

    python -m doppler2026.studies.sparsification_synthetic10 \\
        [--run-id ID] [--epochs N] [--jobs N]

Output: ``data/results/doppler2026/studies/sparsification_synthetic10/<run_id>/``.
"""

from __future__ import annotations

from ..synthetic import SyntheticConfig
from .common import run_layout_study

STUDY = "sparsification_synthetic10"
LAYOUTS = tuple(
    SyntheticConfig(name=f"synthetic10_s{seed}", nodes=10, mean_degree=4.0, seed=seed)
    for seed in range(8)
)
EPOCHS = 30
MODES = ("static", "doppler", "churn")


def main() -> None:
    run_layout_study(STUDY, LAYOUTS, EPOCHS, MODES, __doc__.split("\n")[0])


if __name__ == "__main__":
    main()
