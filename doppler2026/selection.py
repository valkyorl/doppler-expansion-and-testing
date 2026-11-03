"""Choosing one topology from the safe pool (paper §4.11).

The paper warns that always picking "the unique topology minimizing a
public objective" lets an adaptive attacker predict the next state, so
Doppler ranks the safe candidates by an operator-defined secondary
objective, keeps an acceptable subset, and picks one of those at random.

- Secondary objective (D24): ``"mlu"`` (default; the highest benign
  utilization under the network's routing), ``"stretch"`` (the largest
  path stretch), or ``"changes"`` (links added plus links dropped). Lower
  is better for all three.
- Acceptable subset (D9): candidates whose score is within ``tolerance``
  (default 10%) of the best score.
- The choice is uniform over the acceptable subset, with a seeded random
  generator so a run can be reproduced exactly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

SECONDARY_OBJECTIVES = ("mlu", "stretch", "changes")


@dataclass(frozen=True)
class SelectionConfig:
    """Selection settings (decisions D9 and D24)."""

    objective: str = "mlu"
    tolerance: float = 0.10

    def __post_init__(self) -> None:
        if self.objective not in SECONDARY_OBJECTIVES:
            raise ValueError(f"objective must be one of {SECONDARY_OBJECTIVES}")
        if self.tolerance < 0:
            raise ValueError("tolerance must be non-negative")


@dataclass(frozen=True)
class Selection:
    chosen: str
    acceptable: tuple[str, ...]
    best_score: float


def select(
    scores: Mapping[str, float], config: SelectionConfig, rng: np.random.Generator
) -> Selection:
    """Pick one safe candidate. ``scores`` maps candidate IDs to the secondary score."""
    if not scores:
        raise ValueError("The safe pool is empty: nothing to select")
    best = min(scores.values())
    limit = best + config.tolerance * abs(best)
    acceptable = tuple(sorted(c for c, s in scores.items() if s <= limit))
    chosen = acceptable[int(rng.integers(len(acceptable)))]
    return Selection(chosen=chosen, acceptable=acceptable, best_score=best)
