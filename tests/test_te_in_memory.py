"""Tests for the in-memory TE functions added for the Doppler 2026 experiment.

``route_demands`` routes without files; ``deliver_flows`` tracks flows that
share a source-destination pair separately (benign vs attack traffic) and
never lets a link carry more than its capacity.
"""

import random

import networkx as nx
import pytest

from onset.te import deliver_flows, route_demands


def _line(capacity=100.0):
    graph = nx.DiGraph()
    graph.add_edge("x", "y", capacity=capacity, cost=1.0)
    graph.add_edge("y", "x", capacity=capacity, cost=1.0)
    return graph


def test_route_demands_matches_shortest_path():
    routes = route_demands(_line(), {("x", "y"): 1.0}, "-ecmp")
    assert routes == {("x", "y"): [(("x", "y"), 1.0)]}


def test_route_demands_rejects_unknown_method():
    with pytest.raises(ValueError, match="Unsupported"):
        route_demands(_line(), {("x", "y"): 1.0}, "-nope")


def test_flows_sharing_a_pair_are_tracked_separately():
    graph = _line()
    routes = route_demands(graph, {("x", "y"): 180.0}, "ecmp")
    result = deliver_flows(
        graph,
        {"benign": (("x", "y"), 80.0), "attack": (("x", "y"), 100.0)},
        routes,
        sharing="max_min",
    )
    # Max-min fair sharing of 100 between flows of 80 and 100: 50 each.
    assert result.delivered["benign"] == pytest.approx(50.0)
    assert result.delivered["attack"] == pytest.approx(50.0)
    assert result.expected_loads[("x", "y")] == pytest.approx(180.0)
    assert result.actual_loads[("x", "y")] == pytest.approx(100.0)


def test_flow_without_route_delivers_nothing():
    graph = _line()
    graph.add_node("z")
    result = deliver_flows(graph, {"f": (("x", "z"), 10.0)}, {})
    assert result.delivered["f"] == 0.0
    assert result.offered["f"] == 10.0


def test_proportional_sharing_scales_every_flow_equally():
    graph = _line()
    routes = route_demands(graph, {("x", "y"): 200.0}, "ecmp")
    result = deliver_flows(
        graph,
        {"benign": (("x", "y"), 80.0), "attack": (("x", "y"), 120.0)},
        routes,
        sharing="proportional",
    )
    # 200 offered on a 100 link: every flow keeps half.
    assert result.delivered["benign"] == pytest.approx(40.0)
    assert result.delivered["attack"] == pytest.approx(60.0)


def test_unknown_sharing_is_rejected():
    with pytest.raises(ValueError, match="sharing"):
        deliver_flows(_line(), {}, {}, sharing="fifo")


@pytest.mark.parametrize("sharing", ["proportional", "max_min"])
def test_flows_compete_regardless_of_hop_number(sharing):
    """a->b->c reaches link b->c on its second hop, b->c on its first.

    The older hop-by-hop loop in evaluate() let both carry 100 on a
    100-capacity link. Here they must share it: 50 each.
    """
    graph = nx.DiGraph()
    graph.add_edge("a", "b", capacity=100.0, cost=1.0)
    graph.add_edge("b", "c", capacity=100.0, cost=1.0)
    routes = {
        ("a", "c"): [(("a", "b", "c"), 1.0)],
        ("b", "c"): [(("b", "c"), 1.0)],
    }
    result = deliver_flows(
        graph,
        {"long": (("a", "c"), 100.0), "short": (("b", "c"), 100.0)},
        routes,
        sharing=sharing,
    )
    assert result.delivered["long"] == pytest.approx(50.0)
    assert result.delivered["short"] == pytest.approx(50.0)
    assert result.actual_loads[("b", "c")] == pytest.approx(100.0)


@pytest.mark.parametrize("sharing", ["proportional", "max_min"])
@pytest.mark.parametrize("seed", range(5))
def test_no_link_carries_more_than_its_capacity(sharing, seed):
    """Heavy random demand on random graphs: carried load stays within capacity."""
    rng = random.Random(seed)
    undirected = nx.connected_watts_strogatz_graph(12, 4, 0.3, seed=seed)
    graph = nx.DiGraph()
    for u, v in undirected.edges:
        capacity = rng.uniform(50.0, 150.0)
        graph.add_edge(str(u), str(v), capacity=capacity, cost=1.0)
        graph.add_edge(str(v), str(u), capacity=capacity, cost=1.0)
    nodes = sorted(graph.nodes)
    demands = {(s, d): rng.uniform(0.0, 40.0) for s in nodes for d in nodes if s != d}
    routes = route_demands(graph, demands, "ecmp")

    result = deliver_flows(
        graph,
        {pair: (pair, amount) for pair, amount in demands.items()},
        routes,
        sharing=sharing,
    )

    for edge, carried in result.actual_loads.items():
        assert carried <= graph.edges[edge]["capacity"] * (1 + 1e-6)
    for pair, amount in demands.items():
        assert -1e-9 <= result.delivered[pair] <= amount + 1e-9
