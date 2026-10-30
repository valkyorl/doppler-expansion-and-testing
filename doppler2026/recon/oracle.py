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
"""

from __future__ import annotations

import networkx as nx

from ..attack_plans import make_plan
from ..model import AttackConfig, AttackPlan, Pair, RoutingConfig
from ..routing import all_pair_routes, directed, link_shares
from ..topology import topology_id as compute_topology_id

MECHANISM = "oracle"


def oracle_plan(
    topology: nx.Graph,
    attack: AttackConfig,
    routing: RoutingConfig,
    *,
    topology_id: str | None = None,
) -> AttackPlan:
    """Build the oracle's attack plan for ``topology``.

    ``topology_id`` defaults to the topology's stable hash.
    """
    graph = directed(topology)
    endpoints = attack.endpoints or tuple(sorted(topology.nodes))
    routes = all_pair_routes(graph, endpoints, routing)
    shares = link_shares(routes)

    best_key: tuple[float, int, float] | None = None
    best_link: Pair | None = None
    best_pairs: list[Pair] = []
    # Links are visited in name order and replaced only by a strictly better
    # key, so on a full tie the alphabetically first link wins.
    for link in sorted(shares):
        # Pairs with the largest share on this link; name order breaks ties.
        ranked = sorted(shares[link].items(), key=lambda item: (-item[1], item[0]))
        chosen = ranked[: attack.n_pairs]
        concentrated = attack.budget / len(chosen) * sum(s for _, s in chosen)
        # How much of all endpoint-pair traffic the network routes over this
        # link: its centrality to the routing. Many links can absorb the whole
        # budget, so this decides between them.
        usage = sum(shares[link].values())
        capacity = graph.edges[link]["capacity"]
        # Higher score wins, then higher usage, then more pairs, then lower
        # capacity.
        key = (concentrated, usage, len(chosen), -capacity)
        if best_key is None or key > best_key:
            best_key, best_link = key, link
            best_pairs = [pair for pair, _ in chosen]

    if best_link is None:
        raise ValueError("No link carries traffic between attacker endpoints")
    return make_plan(
        best_pairs,
        attack.budget,
        mechanism=MECHANISM,
        topology_id=topology_id or compute_topology_id(topology),
        target=best_link,
    )
