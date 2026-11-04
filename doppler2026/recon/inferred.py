"""From an inferred graph to an attack plan (paper §3.3), shared by the
measured attackers.

The traceroute attacker (§3.1.2) and the RTT/Ricci attacker (§3.1.1) measure
different things, but both end with:

- an inferred graph Ĝ, which can differ from the real network (missing
  links, extra links, or edges that stand for multi-hop paths), and
- a ranking of Ĝ's edges: by betweenness (Eq. 6) or by Ollivier-Ricci
  curvature (Eq. 4).

§3.3 turns that into a plan using only what the attacker knows: "for a
candidate target e, we identify source-destination pairs whose inferred
paths traverse e. The attacker selects up to N_A such pairs". Here
(interpretation I8 in ``docs/decisions.md``):

1. The target is the top-ranked edge e = {u, v} that at least one pair of
   attacker endpoints crosses.
2. "Inferred paths" are shortest paths in Ĝ counted in hops; Ĝ has no link
   weights the attacker could trust. For each ordered endpoint pair (s, d),
   the share of its shortest paths that cross e from u to v is
   sigma_sd(u→v) / sigma_sd, the same term as in Eq. 6.
3. Traffic floods one direction of a link, so each direction of e is scored
   as the oracle scores a link (I3): the attack traffic its top N_A pairs
   would place on it. The better direction is attacked.
4. The budget is split equally over the chosen pairs (Eq. 8).

Attacker endpoints are the configured endpoints (D8: every PoP) that appear
in Ĝ. An attacker cannot plan with a node it never observed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import networkx as nx

from ..attack_plans import make_plan
from ..model import AttackConfig, AttackPlan, Pair

Edge = tuple[str, str]
"""An undirected inferred edge, written with the smaller node name first."""


@dataclass(frozen=True)
class ReconResult:
    """What a measured attacker produced: its plan and how it got there.

    ``inferred`` is Ĝ. ``ranking`` lists Ĝ's edges best target first, with
    the score they were ranked by (betweenness, or curvature where lower is
    better). ``details`` holds mechanism-specific numbers for the result
    files (for example ε, or the share of complete traceroute paths).
    """

    plan: AttackPlan
    inferred: nx.Graph
    ranking: tuple[tuple[Edge, float], ...]
    details: Mapping[str, object] = field(default_factory=dict)


def edge_key(u: str, v: str) -> Edge:
    """The undirected edge {u, v} with the smaller name first."""
    return (u, v) if u <= v else (v, u)


@dataclass(frozen=True)
class PathCounts:
    """Hop distances and shortest-path counts between all nodes of a graph.

    ``dist[s][v]`` is the hop distance from s to v; ``sigma[s][v]`` is the
    number of shortest paths from s to v (sigma in Eq. 6). Unreachable nodes are
    absent.
    """

    dist: dict[str, dict[str, int]]
    sigma: dict[str, dict[str, int]]

    @classmethod
    def of(cls, graph: nx.Graph) -> PathCounts:
        """Breadth-first search from every node, counting shortest paths."""
        dist: dict[str, dict[str, int]] = {}
        sigma: dict[str, dict[str, int]] = {}
        for source in graph:
            d = {source: 0}
            s = {source: 1}
            queue = deque([source])
            while queue:
                node = queue.popleft()
                for nbr in graph[node]:
                    if nbr not in d:
                        d[nbr] = d[node] + 1
                        s[nbr] = 0
                        queue.append(nbr)
                    if d[nbr] == d[node] + 1:
                        s[nbr] += s[node]
            dist[source], sigma[source] = d, s
        return cls(dist, sigma)

    def share(self, pair: Pair, u: str, v: str) -> float:
        """Share of the shortest s→d paths that cross the edge from u to v.

        A shortest s→d path uses u→v exactly when
        dist(s, u) + 1 + dist(v, d) = dist(s, d); the number of such paths is
        sigma(s, u) · sigma(v, d).
        """
        s, d = pair
        ds, ss = self.dist[s], self.sigma[s]
        if d not in ds or u not in ds or d not in self.dist[v]:
            return 0.0
        if ds[u] + 1 + self.dist[v][d] != ds[d]:
            return 0.0
        return ss[u] * self.sigma[v][d] / ss[d]


def betweenness(
    graph: nx.Graph, sources: Iterable[str], targets: Iterable[str]
) -> dict[Edge, float]:
    """Edge betweenness over measured pairs, B(e) in Eq. 6.

    Sums sigma_sd(e) / sigma_sd over pairs with s in ``sources`` and d in ``targets``
    (s ≠ d), using Brandes' algorithm as implemented in NetworkX. NetworkX
    scales undirected results by a constant factor; that does not change the
    ranking, which is all the attacker uses.

    Sources and targets are passed in sorted order: the scores are
    floating-point sums, and summing in set order (which follows Python's
    per-process string hashing) could flip near-ties between runs.
    """
    raw = nx.edge_betweenness_centrality_subset(
        graph,
        sources=sorted(set(sources)),
        targets=sorted(set(targets)),
        normalized=False,
    )
    return {edge_key(u, v): float(b) for (u, v), b in raw.items()}


def rank(scores: Mapping[Edge, float], *, ascending: bool) -> list[tuple[Edge, float]]:
    """Edges sorted by score (ties by edge name), best target first."""
    sign = 1.0 if ascending else -1.0
    return sorted(scores.items(), key=lambda item: (sign * item[1], item[0]))


def plan_from_ranking(
    inferred: nx.Graph,
    ranking: Sequence[tuple[Edge, float]],
    attack: AttackConfig,
    *,
    mechanism: str,
    topology_id: str,
) -> AttackPlan:
    """Build the plan of §3.3 from Ĝ and its edge ranking (steps 1 to 4 above)."""
    wanted = attack.endpoints or tuple(inferred.nodes)
    endpoints = sorted(n for n in set(wanted) if n in inferred)
    pairs = [(s, d) for s in endpoints for d in endpoints if s != d]
    counts = PathCounts.of(inferred)

    for edge, _ in ranking:
        best: tuple[float, list[tuple[Pair, float]], Pair] | None = None
        for u, v in (edge, edge[::-1]):
            shares = [(p, counts.share(p, u, v)) for p in pairs]
            crossing = sorted(
                ((p, s) for p, s in shares if s > 0),
                key=lambda item: (-item[1], item[0]),
            )[: attack.n_pairs]
            if not crossing:
                continue
            # Attack traffic these pairs would put on u→v (as the oracle scores
            # links). Equal scores keep the first direction, (small, large).
            score = attack.budget / len(crossing) * sum(s for _, s in crossing)
            if best is None or score > best[0]:
                best = (score, crossing, (u, v))
        if best is not None:
            _, crossing, target = best
            return make_plan(
                [p for p, _ in crossing],
                attack.budget,
                mechanism=mechanism,
                topology_id=topology_id,
                target=target,
            )
    raise ValueError("No ranked edge lies on a path between attacker endpoints")
