"""How well reconnaissance worked (paper §3.4, Eq. 9; RQ1 and RQ2 of §3.7).

Three levels, from least to most security-relevant (§3.4):

1. Topology recovery (RQ1): precision, recall, and F1 of inferred edges
   against the true edge set. The paper reports these only against
   independently validated ground truth, so ``topology_recovery`` refuses
   to run otherwise (PLAN §9, "Independent ground truth"). In simulation the
   true network is the one the measurements were generated on, so it is
   ground truth by construction (interpretation I12); results are labelled
   with their ground-truth source so simulated numbers are never mistaken
   for operational ones.
2. Critical-link recovery (RQ2): P@k (Eq. 9), the share of the attacker's
   top k edges that are among the k true critical links C_k. C_k is the
   oracle's link ranking (I3, ``recon/oracle.rank_links``) with directions
   merged. Because an inferred edge may stand for a multi-hop path,
   ``path_level_recovery`` also counts an inferred edge as a hit when the
   real route between its ends crosses a link in C_k (§3.4).
3. Attack effectiveness (RQ3) is damage and η, in ``damage.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx

from ..model import AttackConfig, RoutingConfig
from ..routing import directed, route
from .inferred import Edge, edge_key
from .oracle import rank_links


class GroundTruthNotIndependentError(ValueError):
    """Raised when topology recovery is requested against unvalidated ground truth."""


@dataclass(frozen=True)
class GroundTruth:
    """A true topology and whether it may be used for RQ1 numbers.

    ``source`` says where it came from (for example ``"simulation"`` or
    ``"regional (provenance unknown)"``). ``independent`` must be True only
    when the topology was validated independently of the measurements
    (§3.4); router-proxy output does not qualify.
    """

    graph: nx.Graph
    source: str
    independent: bool


def topology_recovery(inferred: nx.Graph, truth: GroundTruth) -> dict[str, float]:
    """Edge precision, recall, and F1 of ``inferred`` against ``truth`` (§3.4).

    Edges are compared undirected. Raises ``GroundTruthNotIndependentError`` if
    the ground truth is not independently validated.
    """
    if not truth.independent:
        raise GroundTruthNotIndependentError(
            f"Ground truth {truth.source!r} is not independently validated; "
            "topology recovery is not reported against it (paper §3.4)"
        )
    found = {edge_key(u, v) for u, v in inferred.edges}
    real = {edge_key(u, v) for u, v in truth.graph.edges}
    common = len(found & real)
    precision = common / len(found) if found else 0.0
    recall = common / len(real) if real else 0.0
    f1 = 2 * precision * recall / (precision + recall) if common else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "inferred_edges": float(len(found)),
        "true_edges": float(len(real)),
        "common_edges": float(common),
    }


def critical_links(
    topology: nx.Graph, attack: AttackConfig, routing: RoutingConfig, k: int
) -> list[Edge]:
    """C_k: the k most attack-relevant physical links, best first.

    The oracle ranks directed links; a link counts once, at the rank of its
    better direction.
    """
    out: list[Edge] = []
    for score in rank_links(topology, attack, routing):
        edge = edge_key(*score.link)
        if edge not in out:
            out.append(edge)
            if len(out) == k:
                break
    return out


def top_k(ranking: Sequence[tuple[Edge, float]], k: int) -> list[Edge]:
    """Ĉ_k: the attacker's k highest-ranked inferred edges."""
    return [edge for edge, _ in ranking[:k]]


def precision_at_k(
    ranking: Sequence[tuple[Edge, float]], critical: Sequence[Edge], k: int
) -> float:
    """P@k = |C_k ∩ Ĉ_k| / k (Eq. 9)."""
    if k < 1:
        raise ValueError("k must be at least 1")
    return len(set(top_k(ranking, k)) & set(critical[:k])) / k


def path_level_recovery(
    ranking: Sequence[tuple[Edge, float]],
    critical: Sequence[Edge],
    k: int,
    topology: nx.Graph,
    routing: RoutingConfig,
) -> float:
    """Share of Ĉ_k whose real route contains a link of C_k (§3.4).

    An inferred edge {u, v} is a hit when any route the network uses
    between u and v, in either direction, crosses a critical link. Edges
    whose ends are not both in the real network count as misses.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    targets = set(critical[:k])
    inferred = top_k(ranking, k)
    demands = {
        p: 1.0
        for u, v in inferred
        if u in topology and v in topology
        for p in ((u, v), (v, u))
    }
    routes = route(directed(topology), demands, routing) if demands else {}

    def hit(u: str, v: str) -> bool:
        for pair in ((u, v), (v, u)):
            for path, _ in routes.get(pair, []):
                if any(edge_key(a, b) in targets for a, b in pairwise(path)):
                    return True
        return False

    return sum(hit(u, v) for u, v in inferred) / k
