"""RTT/Ricci attacker (paper §3.1.1, Eq. 2-4).

The attacker measures round-trip times between its vantage points, keeps
the minimum per pair (Eq. 2), and links two vantage points when that minimum
is at most a threshold ε (Eq. 3). In the resulting graph Ĝ_ε, edges with
strongly negative Ollivier-Ricci curvature behave like bridges between
well-connected regions; the attacker ranks edges by increasing curvature
(Eq. 4) and builds its plan from Ĝ_ε as in §3.3 (``recon/inferred.py``).

An edge of Ĝ_ε links two vantage points and may stand for a multi-hop path
in the real network (§3.1.1). Metrics treat it that way
(``recon/metrics.py``, path-level recovery).

Measurements reach the attacker as ``RttMeasurements``. Today the only
source is ``simulate``; a loader for real RTT data would return the same
type (PLAN §9). The regional reconstruction already in the repository is an
inferred graph, not measurements, so it has its own loader
(``load_regional_reconstruction``).

Choices (``docs/decisions.md``):

- ε is given as a quantile of all measured minimum RTTs (decision D13), so
  the same sweep gives graphs of similar density on networks of very
  different size. The value in milliseconds is reported too.
- Curvature uses the GraphRicciCurvature library (decision P3) with its
  default laziness alpha = 0.5 and exact optimal transport, on Ĝ_ε without
  weights (interpretation I10): Eq. 3 defines Ĝ_ε by the threshold alone.
- Simulated RTT (interpretation I11): propagation delay along the real
  forward and return paths (great-circle length times ``route_factor``, at the
  speed of light in fiber), plus random queuing delay per probe.
"""

from __future__ import annotations

import importlib
import json
import logging
import multiprocessing
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import numpy as np

from ..model import AttackConfig, Pair, RoutingConfig
from ..routing import directed, route
from ..topology import REPO_ROOT, great_circle_km
from .inferred import Edge, ReconResult, edge_key, plan_from_ranking, rank

MECHANISM = "rtt_ricci"

REGIONAL_DIR = REPO_ROOT / "data" / "graphs" / "json" / "regional"


@dataclass(frozen=True)
class RttConfig:
    """Simulated RTT campaign.

    ``vantage_points`` defaults to every PoP. Each pair is probed
    ``samples`` times (|Q_uv| in Eq. 2). Every probe adds queuing delay
    drawn from an exponential distribution with mean ``queue_mean_ms``.
    Light travels ``fiber_km_per_ms`` in fiber (about 2/3 of c), and fiber
    is ``route_factor`` times longer than the great circle.
    """

    vantage_points: tuple[str, ...] | None = None
    samples: int = 10
    queue_mean_ms: float = 1.0
    fiber_km_per_ms: float = 200.0
    route_factor: float = 1.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.samples < 1:
            raise ValueError("samples must be at least 1")
        if (
            self.queue_mean_ms < 0
            or self.fiber_km_per_ms <= 0
            or self.route_factor <= 0
        ):
            raise ValueError("delays and speeds must be positive")


@dataclass(frozen=True)
class RttMeasurements:
    """Minimum RTT d(u, v) in milliseconds per vantage-point pair (Eq. 2).

    Keys are undirected pairs written with the smaller name first. ``source``
    says where the data came from (``"simulated"`` or a dataset name).
    """

    min_rtt_ms: Mapping[Edge, float]
    source: str

    @property
    def vantage_points(self) -> list[str]:
        return sorted({n for pair in self.min_rtt_ms for n in pair})


def simulate(
    topology: nx.Graph, routing: RoutingConfig, config: RttConfig
) -> RttMeasurements:
    """Measure every vantage-point pair on the true network (Eq. 2)."""
    rng = np.random.default_rng(config.seed)
    points = sorted(config.vantage_points or topology.nodes)
    pairs = [(u, v) for i, u in enumerate(points) for v in points[i + 1 :]]
    demands = {p: 1.0 for u, v in pairs for p in ((u, v), (v, u))}
    routes = route(directed(topology), demands, routing)

    def delay_ms(path: tuple[str, ...]) -> float:
        km = sum(great_circle_km(topology, a, b) for a, b in pairwise(path))
        return km * config.route_factor / config.fiber_km_per_ms

    def draw(pair: Pair) -> float:
        options = routes[pair]
        pick = rng.choice(len(options), p=[share for _, share in options])
        return delay_ms(options[pick][0])

    min_rtt: dict[Edge, float] = {}
    for u, v in pairs:
        if (u, v) not in routes or (v, u) not in routes:
            continue  # unreachable: no reply, no measurement
        samples = [
            draw((u, v)) + draw((v, u)) + rng.exponential(config.queue_mean_ms)
            for _ in range(config.samples)
        ]
        min_rtt[(u, v)] = min(samples)
    return RttMeasurements(min_rtt_ms=min_rtt, source="simulated")


def epsilon_graph(
    measurements: RttMeasurements, quantile: float
) -> tuple[nx.Graph, float]:
    """Ĝ_ε (Eq. 3) with ε at the given quantile of all minimum RTTs.

    Returns the graph and ε in milliseconds. Every vantage point is a node,
    including ones left without edges.
    """
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be in (0, 1]")
    epsilon = float(np.quantile(list(measurements.min_rtt_ms.values()), quantile))
    graph = nx.Graph()
    graph.add_nodes_from(measurements.vantage_points)
    graph.add_edges_from(p for p, d in measurements.min_rtt_ms.items() if d <= epsilon)
    return graph, epsilon


class _SerialPool:
    """Stands in for ``multiprocessing.Pool``: runs each task in this process."""

    def __init__(self, processes: int | None = None) -> None:
        pass

    def __enter__(self) -> _SerialPool:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def imap_unordered(self, func, iterable, chunksize: int = 1) -> list:
        # A list, not a generator: the library reads results after the pool closes.
        return [func(item) for item in iterable]

    def close(self) -> None:
        pass

    def join(self) -> None:
        pass


class _InProcess:
    """Stands in for the ``multiprocessing`` module inside GraphRicciCurvature."""

    @staticmethod
    def get_context(method: str | None = None) -> type:
        return _InProcessContext

    cpu_count = staticmethod(multiprocessing.cpu_count)


class _InProcessContext:
    Pool = _SerialPool


def ricci_curvature(graph: nx.Graph) -> dict[Edge, float]:
    """Ollivier-Ricci curvature κ(e) of every edge, via GraphRicciCurvature.

    The graph is copied without attributes, so every edge has length 1.
    Uses exact optimal transport, so results are deterministic.

    The library always forks a process pool, even with ``proc=1``. Forking a
    process that already has threads running (HiGHS and networkit leave
    worker threads behind) can deadlock the child. So the library's
    ``multiprocessing`` is replaced, for the duration of the call, by a
    stand-in that runs the same per-edge function in this process. The
    curvature computation itself is the library's, unchanged; tests check
    that the result equals the library's own pooled run, including after
    other graphs were computed first.
    """
    if graph.number_of_edges() == 0:
        return {}
    # Imported here so the rest of the package works without the optional
    # dependency (see README, "Installing the Ricci dependency").
    library = importlib.import_module("GraphRicciCurvature.OllivierRicci")

    plain = nx.Graph()
    plain.add_nodes_from(graph.nodes)
    plain.add_edges_from(graph.edges)
    orc = library.OllivierRicci(plain, alpha=0.5, method="OTD", proc=1, verbose="ERROR")
    # The library logs a line per call even at ERROR; keep test output quiet.
    logging.getLogger("GraphRicciCurvature").setLevel(logging.ERROR)
    # The library memoizes per-node results by node index. Under fork the
    # memo lived in short-lived child processes; in-process it would carry
    # one graph's neighbours over to the next, so clear it before and after.
    caches = (
        library._get_single_node_neighbors_distributions,
        library._source_target_shortest_path,
        library._source_target_shortest_paths,
    )
    for cache in caches:
        cache.cache_clear()
    try:
        with patch.object(library, "mp", _InProcess):
            orc.compute_ricci_curvature()
    finally:
        for cache in caches:
            cache.cache_clear()
    return {
        edge_key(u, v): float(k)
        for (u, v), k in nx.get_edge_attributes(orc.G, "ricciCurvature").items()
    }


def ricci_attack(
    inferred: nx.Graph,
    attack: AttackConfig,
    *,
    topology_id: str,
    details: Mapping[str, object] | None = None,
) -> ReconResult:
    """Rank Ĝ's edges by increasing curvature (Eq. 4) and plan the attack."""
    ranking = rank(ricci_curvature(inferred), ascending=True)
    plan = plan_from_ranking(
        inferred, ranking, attack, mechanism=MECHANISM, topology_id=topology_id
    )
    return ReconResult(
        plan=plan,
        inferred=inferred,
        ranking=tuple(ranking),
        details=dict(details or {}),
    )


def rtt_attack(
    measurements: RttMeasurements,
    attack: AttackConfig,
    quantile: float,
    *,
    topology_id: str,
) -> ReconResult:
    """The full RTT/Ricci attacker for one threshold: Eq. 3, Eq. 4, then §3.3."""
    graph, epsilon = epsilon_graph(measurements, quantile)
    return ricci_attack(
        graph,
        attack,
        topology_id=topology_id,
        details={
            "source": measurements.source,
            "epsilon_quantile": quantile,
            "epsilon_ms": epsilon,
        },
    )


def _load_json_graph(path: Path) -> nx.Graph:
    graph = nx.adjacency_graph(json.loads(path.read_text()))
    return nx.relabel_nodes(graph, str)


def load_regional_reconstruction(directory: Path = REGIONAL_DIR) -> nx.Graph:
    """The precomputed Ricci reconstruction of the regional network.

    Only an edge list: no RTTs, ε, curvature, or coordinates are stored, so
    curvature is recomputed on it (``ricci_attack``). Provenance is unknown
    (audit #8; ``docs/references.md``).
    """
    return _load_json_graph(directory / "reconstruction_regional.json")


def load_regional_ground_truth(directory: Path = REGIONAL_DIR) -> nx.Graph:
    """The regional network's "ground truth" graph, with link capacities.

    Not independently validated (audit #8), so ``recon/metrics.py`` refuses
    topology-recovery numbers against it. Capacities in the file are in
    unknown units; they are used only relative to each other.
    """
    return _load_json_graph(directory / "ground_truth_regional.json")
