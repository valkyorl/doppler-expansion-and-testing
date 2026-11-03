"""Operational filter (paper §4.6-4.7, Eq. 15-17).

A candidate from the MILP can carry the benign demand with *some* routing
(the MILP's multicommodity flow). The network uses its own TE method (ECMP
by default), so each candidate is re-checked with that routing (PLAN §4,
"Operational filter"):

- Connectivity (§4.7, D20): the topology is connected and every benign
  demand has a route. 2-edge-connectivity (no single link failure
  disconnects it) is always reported and required only when
  ``require_two_edge_connected`` is set.
- Maximum link utilization (Eq. 16, D5): the highest offered utilization
  under the network's routing is at most U_max.
- Path stretch (Eq. 17, D19): for every demand, l(P') / l(P⁰) <= S_max,
  where P' is its route on the candidate and P⁰ its route on the original
  topology G_0 (so stretch cannot creep up over epochs). l is the
  great-circle length in km along the path (``stretch_metric="km"``) or
  the hop count (``"hops"``). Under ECMP a demand may use several paths;
  the longest path it uses counts, on both topologies.

The filter never sees attack traffic (§4.3; PLAN §2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import pairwise

import networkx as nx

from .model import Pair, RoutingConfig
from .routing import Route, deliver, directed, route
from .topology import great_circle_km

STRETCH_METRICS = ("km", "hops")


@dataclass(frozen=True)
class OperationalConfig:
    """Operator constraints (decisions D5, D19, D20)."""

    u_max: float = 0.8
    s_max: float | None = 3.0
    """Largest allowed stretch ratio l(P')/l(P⁰); ``None`` turns the check off
    (still reported). Default 3 (D5, revised 2026-11-03 from 1.5, open issue
    O4): at 1.5 almost no candidate passed, because removing a short link
    sends its traffic on a detour many times as long."""
    stretch_metric: str = "km"
    require_two_edge_connected: bool = False

    def __post_init__(self) -> None:
        if self.stretch_metric not in STRETCH_METRICS:
            raise ValueError(f"stretch_metric must be one of {STRETCH_METRICS}")


@dataclass(frozen=True)
class OperationalResult:
    passed: bool
    reasons: tuple[str, ...]
    """Why it failed: any of ``disconnected``, ``unroutable``, ``mlu``,
    ``stretch``, ``not_2_edge_connected``. Empty when it passed."""
    mlu: float
    max_stretch: float
    mean_stretch: float
    """Demand-weighted mean stretch."""
    unroutable_demand: float
    """Share of benign demand with no route."""
    connected: bool
    two_edge_connected: bool
    routes: Mapping[Pair, list[Route]] = field(repr=False, compare=False)


def path_length(topology: nx.Graph, path: tuple[str, ...], metric: str) -> float:
    """l(P): km along the path, or its number of hops."""
    if metric == "hops":
        return float(len(path) - 1)
    return sum(great_circle_km(topology, a, b) for a, b in pairwise(path))


def longest_route(topology: nx.Graph, routes: list[Route], metric: str) -> float:
    """The longest path a demand uses (D19)."""
    return max(path_length(topology, path, metric) for path, _ in routes)


@dataclass(frozen=True)
class ReferenceLengths:
    """l(P⁰) per demand on the original topology G_0, in one metric."""

    metric: str
    lengths: Mapping[Pair, float]


def reference_lengths(
    original: nx.Graph,
    benign: Mapping[Pair, float],
    routing: RoutingConfig,
    metric: str,
) -> ReferenceLengths:
    """l(P⁰) for every demand on the original topology G_0."""
    routes = route(directed(original), benign, routing)
    return ReferenceLengths(
        metric,
        {
            pair: longest_route(original, paths, metric)
            for pair, paths in routes.items()
            if paths and benign[pair] > 0
        },
    )


def operational_check(
    candidate: nx.Graph,
    benign: Mapping[Pair, float],
    reference: ReferenceLengths,
    routing: RoutingConfig,
    config: OperationalConfig,
) -> OperationalResult:
    """Check one candidate topology. ``reference`` is from ``reference_lengths``."""
    if reference.metric != config.stretch_metric:
        raise ValueError(
            f"reference lengths are in {reference.metric!r}, "
            f"the filter uses {config.stretch_metric!r}"
        )
    reasons: list[str] = []
    connected = nx.is_connected(candidate)
    two_edge = connected and nx.is_k_edge_connected(candidate, 2)
    if not connected:
        reasons.append("disconnected")
    if config.require_two_edge_connected and not two_edge:
        reasons.append("not_2_edge_connected")

    graph = directed(candidate)
    demands = {pair: amount for pair, amount in benign.items() if amount > 0}
    routes = route(graph, demands, routing)
    total = sum(demands.values())
    missing = sum(a for pair, a in demands.items() if not routes.get(pair))
    if missing > 0:
        reasons.append("unroutable")

    flows = {pair: (pair, amount) for pair, amount in demands.items()}
    loads = deliver(graph, flows, routes).expected_loads
    mlu = max(
        (load / graph.edges[edge]["capacity"] for edge, load in loads.items()),
        default=0.0,
    )
    if mlu > config.u_max:
        reasons.append("mlu")

    stretches = {
        pair: longest_route(candidate, routes[pair], config.stretch_metric)
        / reference.lengths[pair]
        for pair in demands
        if routes.get(pair) and reference.lengths.get(pair)
    }
    max_stretch = max(stretches.values(), default=1.0)
    weight = sum(demands[p] for p in stretches)
    mean_stretch = (
        sum(demands[p] * s for p, s in stretches.items()) / weight if weight else 1.0
    )
    if config.s_max is not None and max_stretch > config.s_max:
        reasons.append("stretch")

    return OperationalResult(
        passed=not reasons,
        reasons=tuple(reasons),
        mlu=mlu,
        max_stretch=max_stretch,
        mean_stretch=mean_stretch,
        unroutable_demand=missing / total if total else 0.0,
        connected=connected,
        two_edge_connected=two_edge,
        routes=routes,
    )
