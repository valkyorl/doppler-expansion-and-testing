"""In-memory routing, using the repository's existing TE engine.

The experiment needs to route traffic on many candidate topologies quickly
and to tell benign traffic apart from attack traffic between the same PoPs.
This module is a thin layer over ``onset.te.route_demands`` and
``onset.te.deliver_flows``, which do the actual work (ECMP, MCF, SMORE, and
max-min fair sharing at congested links). Nothing is written to disk.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from itertools import pairwise

import networkx as nx

from onset.te import FlowDelivery, deliver_flows, route_demands

from .model import Pair, RoutingConfig

Route = tuple[tuple[str, ...], float]
"""A path (sequence of nodes) and the share of the pair's traffic it carries."""


def directed(topology: nx.Graph) -> nx.DiGraph:
    """Turn an undirected topology into the directed graph the engine routes on.

    Each undirected link becomes two directed links, each with the link's
    full ``capacity`` (links are full duplex). ``cost`` defaults to 1, so
    ECMP uses hop count, as the existing pipeline does.
    """
    graph: nx.DiGraph = nx.DiGraph()
    graph.add_nodes_from(topology.nodes(data=True))
    for u, v, attrs in topology.edges(data=True):
        capacity = float(attrs["capacity"])
        cost = float(attrs.get("cost", 1.0))
        graph.add_edge(u, v, capacity=capacity, cost=cost)
        graph.add_edge(v, u, capacity=capacity, cost=cost)
    return graph


TRAFFIC_INDEPENDENT = frozenset({"ecmp"})
"""TE methods whose routes depend only on the graph, never on the demands."""

_CACHE_SIZE = 64
_route_cache: OrderedDict[tuple, dict[Pair, list[Route]]] = OrderedDict()


def route(
    graph: nx.DiGraph, demands: Mapping[Pair, float], config: RoutingConfig
) -> dict[Pair, list[Route]]:
    """Route ``demands`` on ``graph`` with the configured TE method.

    For traffic-independent methods (ECMP) the routes of every node pair are
    computed once per graph and reused: an experiment routes the same
    topology hundreds of times, and route computation was most of its
    running time. The result is the same as routing ``demands`` directly
    (``tests/test_d26_recon.py`` checks this).
    """
    if config.te_method not in TRAFFIC_INDEPENDENT:
        return route_demands(
            graph, demands, config.te_method, config.path_budget, seed=config.seed
        )
    # Edge order is part of the key: with more equal-cost paths than the
    # path budget, which paths are kept can depend on it.
    key = (
        config.te_method,
        config.path_budget,
        tuple(graph.nodes),
        tuple((u, v, a.get("cost", 1.0)) for u, v, a in graph.edges(data=True)),
    )
    routes = _route_cache.get(key)
    if routes is None:
        nodes = list(graph.nodes)
        everything = {(s, d): 1.0 for s in nodes for d in nodes if s != d}
        routes = route_demands(
            graph, everything, config.te_method, config.path_budget, seed=config.seed
        )
        _route_cache[key] = routes
        if len(_route_cache) > _CACHE_SIZE:
            _route_cache.popitem(last=False)
    else:
        _route_cache.move_to_end(key)
    # Same keys and order as the engine: every requested pair, sorted. Pairs
    # outside the cache (a node routed to itself) go to the engine directly.
    missing = {pair: amount for pair, amount in demands.items() if pair not in routes}
    extra = (
        route_demands(graph, missing, config.te_method, config.path_budget)
        if missing
        else {}
    )
    return {
        pair: routes[pair] if pair in routes else extra[pair]
        for pair in sorted(demands)
    }


def deliver(
    graph: nx.DiGraph,
    flows: Mapping[object, tuple[Pair, float]],
    routes: Mapping[Pair, list[Route]],
    sharing: str = "proportional",
) -> FlowDelivery:
    """Push labelled flows along ``routes``; see ``onset.te.deliver_flows``.

    ``sharing`` is how overloaded links divide capacity
    (``DamageConfig.sharing``).
    """
    return deliver_flows(graph, flows, routes, sharing=sharing)


def all_pair_routes(
    graph: nx.DiGraph, endpoints: Iterable[str], config: RoutingConfig
) -> dict[Pair, list[Route]]:
    """Routes for every ordered pair of ``endpoints``, as the network would pick them.

    Used by attackers that know the routing. With ECMP the routes do not
    depend on traffic, so a unit demand per pair gives the true routes. With
    traffic-dependent methods (MCF, SMORE) this is the routing for uniform
    demand, which is an approximation of the network's actual state.
    """
    nodes = sorted(set(endpoints))
    demands = {(s, d): 1.0 for s in nodes for d in nodes if s != d}
    return route(graph, demands, config)


def link_shares(routes: Mapping[Pair, list[Route]]) -> dict[Pair, dict[Pair, float]]:
    """For each directed link, the share of each pair's traffic that crosses it.

    ``result[(u, v)][(s, d)]`` is the fraction of (s, d) traffic routed over
    link u -> v (between 0 and 1; below 1 when ECMP splits the pair).
    """
    shares: dict[Pair, dict[Pair, float]] = {}
    for pair, pair_routes in routes.items():
        for path, probability in pair_routes:
            for u, v in pairwise(path):
                link = shares.setdefault((u, v), {})
                link[pair] = link.get(pair, 0.0) + probability
    return shares


def max_utilization(
    graph: nx.DiGraph, demands: Mapping[Pair, float], config: RoutingConfig
) -> float:
    """Highest offered load / capacity on any link when ``demands`` are routed."""
    routes = route(graph, demands, config)
    flows = {pair: (pair, amount) for pair, amount in demands.items() if amount > 0}
    loads = deliver(graph, flows, routes).expected_loads
    return max(
        (load / graph.edges[edge]["capacity"] for edge, load in loads.items()),
        default=0.0,
    )
