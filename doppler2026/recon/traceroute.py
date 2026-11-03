"""Traceroute attacker (paper §3.1.2, Eq. 5-6).

From each vantage point the attacker probes every destination and records
the routers that answer along the way. Joining those hop sequences gives the
observed graph Ĝ_tr (Eq. 5). Links are ranked by shortest-path betweenness
over the measured pairs (Eq. 6), and the plan is built from Ĝ_tr as in §3.3
(``recon/inferred.py``).

Measurements reach the attacker as a ``TracerouteObservation``. Today the
only source is ``simulate``; a loader for real traceroute data would return
the same type (PLAN §9, "Real RTT / traceroute measurements").

How the simulation works (interpretation I9 in ``docs/decisions.md``):

- Each probe follows one of the network's real forwarding paths. With ECMP,
  the path is drawn by its routing share, as for a traceroute that keeps its
  flow identifier fixed (Paris traceroute).
- Each router is silent with probability ``non_response``, drawn once per
  router: silent routers never answer when they are an intermediate hop.
  Destinations always answer, and the vantage point knows itself.
- Hops are reported at PoP level, which is the same as perfect alias
  resolution (§3.1.2 asks for the alias-resolution procedure to be stated).
- A silent hop breaks the path (decision D12): only two consecutive hops
  that both answered give an edge of Ĝ_tr. A gap is not read as a link.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx
import numpy as np

from ..model import AttackConfig, Pair, RoutingConfig
from ..routing import directed, route
from .inferred import ReconResult, betweenness, plan_from_ranking, rank

MECHANISM = "traceroute"

Hop = str | None
"""A router that answered, or None for a hop that did not."""


@dataclass(frozen=True)
class TracerouteConfig:
    """Simulated traceroute campaign.

    ``vantage_points`` and ``destinations`` default to every PoP.
    ``non_response`` is the probability that a router never answers
    (decision D12 default 0.1; swept in the reconnaissance experiment).
    """

    vantage_points: tuple[str, ...] | None = None
    destinations: tuple[str, ...] | None = None
    non_response: float = 0.1
    seed: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.non_response <= 1.0:
            raise ValueError("non_response must be between 0 and 1")


@dataclass(frozen=True)
class TracerouteObservation:
    """Hop sequences the attacker recorded, one per probed (source, destination).

    Each sequence starts at the vantage point and ends at the destination;
    ``None`` marks a hop that did not answer. ``source`` says where the data
    came from (``"simulated"`` or a dataset name).
    """

    paths: Mapping[Pair, tuple[Hop, ...]]
    source: str

    def path_stats(self) -> dict[str, float]:
        """Share of complete, partial, and non-responsive paths (§3.5).

        A path is non-responsive when no hop after the vantage point
        answered, partial when some did, complete when all did.
        """
        total = len(self.paths)
        if not total:
            return {"complete": 0.0, "partial": 0.0, "non_responsive": 0.0}
        answered = [[h is not None for h in hops[1:]] for hops in self.paths.values()]
        complete = sum(all(a) for a in answered)
        silent = sum(not any(a) for a in answered)
        return {
            "complete": complete / total,
            "partial": (total - complete - silent) / total,
            "non_responsive": silent / total,
        }


def simulate(
    topology: nx.Graph, routing: RoutingConfig, config: TracerouteConfig
) -> TracerouteObservation:
    """Probe the true network as described in the module docstring."""
    rng = np.random.default_rng(config.seed)
    nodes = sorted(topology.nodes)
    silent = {
        n
        for n, draw in zip(nodes, rng.random(len(nodes)), strict=True)
        if draw < config.non_response
    }
    sources = sorted(config.vantage_points or nodes)
    targets = sorted(config.destinations or nodes)
    demands = {(s, d): 1.0 for s in sources for d in targets if s != d}
    routes = route(directed(topology), demands, routing)

    paths: dict[Pair, tuple[Hop, ...]] = {}
    for pair in sorted(routes):
        options = routes[pair]
        pick = rng.choice(len(options), p=[share for _, share in options])
        path = options[pick][0]
        middle = tuple(None if hop in silent else hop for hop in path[1:-1])
        paths[pair] = (path[0], *middle, path[-1])
    return TracerouteObservation(paths=paths, source="simulated")


def observed_graph(observation: TracerouteObservation) -> nx.Graph:
    """Ĝ_tr (Eq. 5): every answering router, linked where two consecutive hops answered."""
    graph = nx.Graph()
    for hops in observation.paths.values():
        graph.add_nodes_from(h for h in hops if h is not None)
        for a, b in pairwise(hops):
            if a is not None and b is not None:
                graph.add_edge(a, b)
    return graph


def traceroute_attack(
    observation: TracerouteObservation,
    attack: AttackConfig,
    *,
    topology_id: str,
) -> ReconResult:
    """Build Ĝ_tr, rank its links by betweenness (Eq. 6), and plan the attack.

    Betweenness counts the measured pairs: vantage points to destinations.
    ``topology_id`` is the network the measurements were taken on.
    """
    graph = observed_graph(observation)
    sources = {s for s, _ in observation.paths if s in graph}
    targets = {d for _, d in observation.paths if d in graph}
    ranking = rank(betweenness(graph, sources, targets), ascending=False)
    plan = plan_from_ranking(
        graph, ranking, attack, mechanism=MECHANISM, topology_id=topology_id
    )
    return ReconResult(
        plan=plan,
        inferred=graph,
        ranking=tuple(ranking),
        details={"source": observation.source, **observation.path_stats()},
    )
