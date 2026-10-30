"""Building attack plans A = {(s_i, d_i, r_i)} (paper §2.1 Eq. 7, §3.3 Eq. 8).

Every reconnaissance mechanism ends by choosing source-destination pairs.
This module turns that choice into a plan: the aggregate budget R_A is split
equally over the chosen pairs, r_i = R_A / |A| (Eq. 8). The paper uses an
equal split on purpose, so the attacker never relies on knowing exact link
capacities (§3.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import AttackFlow, AttackPlan, Pair


def make_plan(
    pairs: Sequence[Pair],
    budget: float,
    *,
    mechanism: str,
    topology_id: str,
    target: Pair | None = None,
) -> AttackPlan:
    """Split ``budget`` equally over ``pairs`` (Eq. 8) and return the plan.

    ``pairs`` must be distinct and non-empty; the order is kept, so plans are
    reproducible.
    """
    if not pairs:
        raise ValueError("An attack plan needs at least one pair")
    if len(set(pairs)) != len(pairs):
        raise ValueError("Attack pairs must be distinct")
    rate = budget / len(pairs)
    flows = tuple(AttackFlow(source=s, target=d, rate=rate) for s, d in pairs)
    return AttackPlan(
        flows=flows,
        budget=budget,
        mechanism=mechanism,
        topology_id=topology_id,
        target=target,
    )


def budget_from_capacity(multiple: float, capacity: float) -> float:
    """Attack budget R_A as a multiple of a link capacity (decision D4).

    The paper sweeps R_A (§3.3); expressing it relative to link capacity
    keeps budgets comparable across networks with different capacities.
    """
    if multiple <= 0:
        raise ValueError("multiple must be positive")
    return multiple * capacity
