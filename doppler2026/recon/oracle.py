"""Oracle attacker: perfect knowledge of topology and routing (paper §3.2).

The oracle is the upper bound on what reconnaissance can give an attacker.
It also supplies the fresh plan A*_j in the transferability ratio τ (Eq. 1):
what an attacker who re-measured the new topology could do.

How it chooses (interpretation I3 in ``docs/decisions.md``):

1. Route every ordered pair of attacker endpoints the way the network would.
2. For each directed link, find the pairs whose traffic crosses it, and the
   share of each pair's traffic that does (below 1 when ECMP splits it).
3. Take the up to N_A pairs with the largest shares. With the budget split
   equally over them (Eq. 8), the attack traffic they put on the link is
   ``R_A / |A| * sum(shares)``. That is the link's score.
4. Target the link with the highest score. Many links can absorb the whole
   budget (any link fully crossed by N_A pairs), so ties go to the link the
   routing uses most: the sum of all endpoint pairs' shares on it. This is
   the link's centrality to the network's traffic, the "critical link"
   notion of §3.4, and needs only topology and routing. Remaining ties go to
   more pairs, then lower capacity, then the link name, so the choice is
   deterministic.

Benign load is not used: the paper's oracle knows topology and routing
state, not the traffic matrix.

The full ranking (``rank_links``) is also the ground truth for critical-link
recovery: its top k links are C_k in P@k (Eq. 9; ``recon/metrics.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from ..attack_plans import make_plan
from ..model import AttackConfig, AttackPlan, Pair, RoutingConfig
from ..routing import all_pair_routes, directed, link_shares
from ..topology import topology_id as compute_topology_id

MECHANISM = "oracle"


@dataclass(frozen=True)
class LinkScore:
    """One directed physical link in the oracle's ranking.

    ``key`` is (concentrated attack traffic, usage, number of pairs,
    -capacity); higher is a better target. ``pairs`` are the pairs the
    oracle would use against this link.
    """

    link: Pair
    key: tuple[float, float, int, float]
    pairs: tuple[Pair, ...]


def rank_links(
    topology: nx.Graph, attack: AttackConfig, routing: RoutingConfig
) -> list[LinkScore]:
    """Every directed link that carries endpoint traffic, best target first.

    Ties on the whole key go to the alphabetically first link, so the
    ranking is deterministic. The order does not depend on the budget
    (the score is proportional to it), only on ``attack.n_pairs`` and
    ``attack.endpoints``.
    """
    graph = directed(topology)
    endpoints = attack.endpoints or tuple(sorted(topology.nodes))
    routes = all_pair_routes(graph, endpoints, routing)
    shares = link_shares(routes)

    scores = []
    for link in shares:
        # Pairs with the largest share on this link; name order breaks ties.
        ranked = sorted(shares[link].items(), key=lambda item: (-item[1], item[0]))
        chosen = ranked[: attack.n_pairs]
        concentrated = attack.budget / len(chosen) * sum(s for _, s in chosen)
        # How much of all endpoint-pair traffic the network routes over this
        # link: its centrality to the routing. Many links can absorb the whole
        # budget, so this decides between them.
        usage = sum(shares[link].values())
        capacity = graph.edges[link]["capacity"]
        key = (concentrated, usage, len(chosen), -capacity)
        scores.append(LinkScore(link, key, tuple(pair for pair, _ in chosen)))
    # Higher score first, then higher usage, more pairs, lower capacity, and
    # finally link name.
    scores.sort(key=lambda s: (tuple(-k for k in s.key), s.link))
    return scores


def oracle_plan(
    topology: nx.Graph,
    attack: AttackConfig,
    routing: RoutingConfig,
    *,
    topology_id: str | None = None,
) -> AttackPlan:
    """Build the oracle's attack plan for ``topology``: attack its top link.

    ``topology_id`` defaults to the topology's stable hash.
    """
    ranking = rank_links(topology, attack, routing)
    if not ranking:
        raise ValueError("No link carries traffic between attacker endpoints")
    best = ranking[0]
    return make_plan(
        best.pairs,
        attack.budget,
        mechanism=MECHANISM,
        topology_id=topology_id or compute_topology_id(topology),
        target=best.link,
    )
