"""No-knowledge attacker: random pairs, no topology information (paper §3.2).

This baseline shows how much an attacker gains from reconnaissance at all.
If measured plans do no better than random ones, there is little
reconnaissance-dependent threat for Doppler to defend against.

The attacker draws N_A distinct ordered pairs of its endpoints uniformly at
random and splits the budget equally (Eq. 8). Draws are seeded so every
result can be reproduced.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from ..attack_plans import make_plan
from ..model import AttackConfig, AttackPlan, Pair
from ..topology import topology_id as compute_topology_id

MECHANISM = "random"


def random_plan(
    topology: nx.Graph,
    attack: AttackConfig,
    seed: int,
    *,
    topology_id: str | None = None,
) -> AttackPlan:
    """Draw a random attack plan with ``attack.n_pairs`` pairs, seeded by ``seed``.

    If the attacker has fewer ordered pairs than ``n_pairs``, all are used.
    """
    endpoints = sorted(attack.endpoints or topology.nodes)
    pairs: list[Pair] = [(s, d) for s in endpoints for d in endpoints if s != d]
    if not pairs:
        raise ValueError("The attacker needs at least two endpoints")
    rng = np.random.default_rng(seed)
    count = min(attack.n_pairs, len(pairs))
    picked = rng.choice(len(pairs), size=count, replace=False)
    return make_plan(
        [pairs[i] for i in sorted(picked)],
        attack.budget,
        mechanism=MECHANISM,
        topology_id=topology_id or compute_topology_id(topology),
    )
