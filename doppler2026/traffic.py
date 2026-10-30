"""Benign traffic matrices: the defender's estimated demand D_t (paper §4.3).

The repository's ``*_base_tm_0.00e+00_gravity.txt`` files are all zeros, so
the experiment makes its own benign traffic with a gravity model: each PoP
gets an outgoing and an incoming "mass" drawn from an exponential
distribution, and traffic from i to j is proportional to out_i * in_j. This
is the simple gravity model described by Roughan (``docs/references.md``).

The overall volume is then scaled so that, routed with the network's routing
method, the busiest link reaches a chosen utilization. That makes "how loaded
is the network before any attack" an explicit experiment setting rather than
an accident of the generator.
"""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx
import numpy as np

from .model import Pair, RoutingConfig
from .routing import directed, max_utilization


def gravity_matrix(nodes: Sequence[str], total: float, seed: int) -> dict[Pair, float]:
    """Random gravity-model demand between every ordered pair of ``nodes``.

    Demands sum to ``total``. Reproducible for a given ``seed``.
    """
    names = sorted(nodes)
    rng = np.random.default_rng(seed)
    out_mass = rng.exponential(1.0, len(names))
    in_mass = rng.exponential(1.0, len(names))
    raw = {
        (s, d): out_mass[i] * in_mass[j]
        for i, s in enumerate(names)
        for j, d in enumerate(names)
        if s != d
    }
    scale = total / sum(raw.values())
    return {pair: float(value * scale) for pair, value in raw.items()}


def scale_to_utilization(
    topology: nx.Graph,
    demands: dict[Pair, float],
    target: float,
    routing: RoutingConfig,
) -> dict[Pair, float]:
    """Scale ``demands`` so the busiest link's offered utilization is ``target``.

    Exact for ECMP and MCF, whose maximum utilization grows linearly with a
    uniform scaling of demand.
    """
    current = max_utilization(directed(topology), demands, routing)
    if current <= 0:
        raise ValueError("Demands put no load on the network")
    factor = target / current
    return {pair: amount * factor for pair, amount in demands.items()}


def benign_demand(
    topology: nx.Graph, target_utilization: float, routing: RoutingConfig, seed: int
) -> dict[Pair, float]:
    """Gravity-model benign demand scaled to ``target_utilization``."""
    raw = gravity_matrix(list(topology.nodes), total=1.0, seed=seed)
    return scale_to_utilization(topology, raw, target_utilization, routing)
