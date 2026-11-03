"""Phase 2 tests: the traceroute and RTT/Ricci attackers, recon metrics, and
the budget to disrupt. Expected values are worked out by hand in comments."""

import itertools
import math

import networkx as nx
import pytest
from helpers import dumbbell, line

from doppler2026.attack_plans import make_plan, rescale
from doppler2026.damage import budget_to_disrupt
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon import metrics, rtt_ricci, traceroute
from doppler2026.recon.inferred import (
    PathCounts,
    betweenness,
    edge_key,
    plan_from_ranking,
    rank,
)
from doppler2026.recon.oracle import oracle_plan, rank_links

ROUTING = RoutingConfig()
ATTACK = AttackConfig(budget=100.0, n_pairs=10)


def cycle4() -> nx.Graph:
    return nx.cycle_graph(["a", "b", "c", "d"])


# --- shared core: inferred graph -> plan (§3.3) ---------------------------


def test_path_share_splits_over_equal_shortest_paths():
    counts = PathCounts.of(cycle4())
    # a to c has two shortest paths, a-b-c and a-d-c: each edge gets half.
    assert counts.share(("a", "c"), "a", "b") == 0.5
    assert counts.share(("a", "c"), "b", "a") == 0.0  # wrong direction
    assert counts.share(("a", "b"), "a", "b") == 1.0


def test_betweenness_ranks_like_equation_6():
    graph = nx.relabel_nodes(nx.connected_watts_strogatz_graph(12, 4, 0.3, seed=3), str)
    nodes = sorted(graph)
    # Eq. 6 by brute force: sum over ordered pairs of sigma_sd(e) / sigma_sd.
    brute = dict.fromkeys((edge_key(u, v) for u, v in graph.edges), 0.0)
    for s, d in itertools.permutations(nodes, 2):
        paths = list(nx.all_shortest_paths(graph, s, d))
        for path in paths:
            for u, v in itertools.pairwise(path):
                brute[edge_key(u, v)] += 1 / len(paths)
    fast = betweenness(graph, nodes, nodes)
    ratio = {e: fast[e] / brute[e] for e in brute}
    # Same up to one constant factor, so the same ranking.
    assert max(ratio.values()) == pytest.approx(min(ratio.values()))


def test_plan_targets_top_edge_with_crossing_pairs():
    graph = dumbbell()
    ranking = rank({("a1", "b1"): 5.0, ("a1", "a2"): 1.0}, ascending=False)
    plan = plan_from_ranking(graph, ranking, ATTACK, mechanism="t", topology_id="g")
    # The 9 pairs (a_i, b_j) all cross a1->b1; b-to-a pairs cross the other
    # direction and score the same, so the first direction is kept.
    assert plan.target == ("a1", "b1")
    assert sorted((f.source, f.target) for f in plan.flows) == sorted(
        (a, b) for a in ("a1", "a2", "a3") for b in ("b1", "b2", "b3")
    )
    assert all(f.rate == pytest.approx(100 / 9) for f in plan.flows)


def test_plan_ignores_endpoints_missing_from_inferred_graph():
    graph = dumbbell()
    attack = AttackConfig(budget=10.0, endpoints=("a2", "b2", "zz"))
    ranking = rank({("a1", "b1"): 1.0}, ascending=False)
    plan = plan_from_ranking(graph, ranking, attack, mechanism="t", topology_id="g")
    assert [(f.source, f.target) for f in plan.flows] == [("a2", "b2")]


# --- oracle ranking (used for C_k) ------------------------------------------


def test_oracle_plan_attacks_top_of_its_ranking():
    graph = dumbbell()
    ranking = rank_links(graph, ATTACK, ROUTING)
    assert oracle_plan(graph, ATTACK, ROUTING).target == ranking[0].link
    assert edge_key(*ranking[0].link) == ("a1", "b1")


# --- traceroute (§3.1.2) ----------------------------------------------------


def test_full_traceroute_recovers_the_topology():
    graph = dumbbell()
    obs = traceroute.simulate(
        graph, ROUTING, traceroute.TracerouteConfig(non_response=0.0)
    )
    found = traceroute.observed_graph(obs)
    assert {edge_key(*e) for e in found.edges} == {edge_key(*e) for e in graph.edges}
    assert obs.path_stats()["complete"] == 1.0


def test_silent_hop_breaks_the_path():
    graph = nx.path_graph(["a", "b", "c"])
    nx.set_edge_attributes(graph, 100.0, "capacity")
    config = traceroute.TracerouteConfig(
        vantage_points=("a",), destinations=("c",), non_response=1.0
    )
    obs = traceroute.simulate(graph, ROUTING, config)
    assert obs.paths[("a", "c")] == ("a", None, "c")
    found = traceroute.observed_graph(obs)
    assert set(found.nodes) == {"a", "c"} and found.number_of_edges() == 0
    assert obs.path_stats() == {"complete": 0.0, "partial": 1.0, "non_responsive": 0.0}


def test_traceroute_attacker_floods_the_bridge():
    obs = traceroute.simulate(
        dumbbell(), ROUTING, traceroute.TracerouteConfig(non_response=0.0)
    )
    result = traceroute.traceroute_attack(obs, ATTACK, topology_id="g")
    assert edge_key(*result.plan.target) == ("a1", "b1")
    assert result.ranking[0][0] == ("a1", "b1")


# --- RTT / Ricci (§3.1.1) ---------------------------------------------------


def test_curvature_matches_hand_computation():
    graph = dumbbell()
    graph.add_edge("x", "y")  # a separate component
    kappa = rtt_ricci.ricci_curvature(graph)
    # Bridge: W1 = 4/3 between the lazy walks at a1 and b1, so 1 - 4/3.
    assert kappa[("a1", "b1")] == pytest.approx(-1 / 3)
    # Triangle edge away from the bridge: W1 = 1/4.
    assert kappa[("a2", "a3")] == pytest.approx(0.75)
    # Isolated edge: both walks are {x: 1/2, y: 1/2}, W1 = 0.
    assert kappa[("x", "y")] == pytest.approx(1.0)
    # 4-cycle: W1 = 1/2 on every edge.
    assert all(
        k == pytest.approx(0.5) for k in rtt_ricci.ricci_curvature(cycle4()).values()
    )


def test_epsilon_graph_uses_rtt_quantile():
    meas = rtt_ricci.RttMeasurements(
        {("a", "b"): 1.0, ("a", "c"): 2.0, ("b", "c"): 3.0, ("c", "d"): 4.0}, "test"
    )
    graph, eps = rtt_ricci.epsilon_graph(meas, 0.5)
    assert eps == pytest.approx(2.5)
    assert {edge_key(*e) for e in graph.edges} == {("a", "b"), ("a", "c")}
    assert "d" in graph  # kept, without edges


def test_simulated_min_rtt_is_propagation_delay():
    graph = line()
    graph.nodes["x"].update(Latitude=0.0, Longitude=0.0)
    graph.nodes["y"].update(Latitude=0.0, Longitude=1.0)
    meas = rtt_ricci.simulate(graph, ROUTING, rtt_ricci.RttConfig(queue_mean_ms=0.0))
    one_degree_km = 6371 * math.pi / 180
    assert meas.min_rtt_ms[("x", "y")] == pytest.approx(2 * one_degree_km / 200.0)


def test_ricci_attacker_floods_the_bridge():
    # Only neighbouring PoPs measured, all at 1 ms; with epsilon at the
    # largest RTT (quantile 1), the epsilon graph is the dumbbell itself.
    meas = rtt_ricci.RttMeasurements(
        {edge_key(*e): 1.0 for e in dumbbell().edges}, "test"
    )
    result = rtt_ricci.rtt_attack(meas, ATTACK, 1.0, topology_id="g")
    assert result.ranking[0][0] == ("a1", "b1")
    assert edge_key(*result.plan.target) == ("a1", "b1")


# --- metrics (§3.4) --------------------------------------------------------


def test_topology_recovery_counts_edges():
    truth = metrics.GroundTruth(cycle4(), "test", independent=True)
    inferred = nx.Graph([("a", "b"), ("b", "c"), ("a", "c")])
    result = metrics.topology_recovery(inferred, truth)
    # 2 of 3 inferred edges are real; 2 of 4 real edges were found.
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))


def test_topology_recovery_refuses_unvalidated_ground_truth():
    truth = metrics.GroundTruth(cycle4(), "router proxy", independent=False)
    with pytest.raises(metrics.GroundTruthNotIndependentError):
        metrics.topology_recovery(cycle4(), truth)


def test_precision_and_path_level_recovery_at_k():
    graph = dumbbell()
    critical = metrics.critical_links(graph, ATTACK, ROUTING, 1)
    assert critical == [("a1", "b1")]
    # An inferred edge a2-b2 is not a real link, but its real route crosses
    # the bridge: a miss for P@k, a hit for path-level recovery.
    ranking = [(("a2", "b2"), -1.0)]
    assert metrics.precision_at_k(ranking, critical, 1) == 0.0
    assert metrics.path_level_recovery(ranking, critical, 1, graph, ROUTING) == 1.0


# --- budget to disrupt (§3.4, D14) -------------------------------------------


def test_budget_to_disrupt_on_one_link():
    graph = line(capacity=100.0)
    plan = make_plan([("x", "y")], 1.0, mechanism="t", topology_id="g")
    # 50 benign on a 100 link: loss starts once the attack exceeds 50.
    budget = budget_to_disrupt(
        graph, {("x", "y"): 50.0}, plan, ROUTING, DamageConfig(), max_budget=400.0
    )
    assert budget == pytest.approx(50.0, rel=2e-3)
    never = budget_to_disrupt(
        graph, {("x", "y"): 50.0}, plan, ROUTING, DamageConfig(), max_budget=40.0
    )
    assert never == math.inf


def test_rescale_keeps_pairs_and_target():
    plan = make_plan(
        [("a", "b"), ("c", "d")],
        10.0,
        mechanism="m",
        topology_id="g",
        target=("a", "b"),
    )
    bigger = rescale(plan, 30.0)
    assert [(f.source, f.target, f.rate) for f in bigger.flows] == [
        ("a", "b", 15.0),
        ("c", "d", 15.0),
    ]
    assert (bigger.target, bigger.mechanism, bigger.topology_id) == (
        ("a", "b"),
        "m",
        "g",
    )


# --- route cache (routing.py) -----------------------------------------------


def test_cached_ecmp_routes_equal_direct_routes():
    from doppler2026.routing import directed, route
    from onset.te import route_demands

    topology = nx.relabel_nodes(
        nx.connected_watts_strogatz_graph(14, 4, 0.3, seed=5), str
    )
    nx.set_edge_attributes(topology, 100.0, "capacity")
    topology.add_node("island")  # unreachable from everything
    graph = directed(topology)
    demands = {("0", "7"): 3.0, ("2", "9"): 0.0, ("5", "island"): 1.0, ("4", "4"): 1.0}
    for _ in range(2):  # first call fills the cache, second reads it
        assert route(graph, demands, ROUTING) == route_demands(
            graph, demands, "ecmp", 3
        )
        assert list(route(graph, demands, ROUTING)) == sorted(demands)


# The reference run uses the library's own forked pool on purpose; the fork
# warning it triggers is expected here and nowhere else.
@pytest.mark.filterwarnings(
    "ignore:This process .* is multi-threaded:DeprecationWarning"
)
def test_in_process_curvature_equals_library_pool():
    from GraphRicciCurvature.OllivierRicci import OllivierRicci

    graph = nx.relabel_nodes(nx.connected_watts_strogatz_graph(20, 4, 0.3, seed=2), str)
    # Compute other graphs first: results must not depend on what came before.
    rtt_ricci.ricci_curvature(dumbbell())
    rtt_ricci.ricci_curvature(cycle4())
    pooled = OllivierRicci(graph, alpha=0.5, method="OTD", proc=1, verbose="ERROR")
    pooled.compute_ricci_curvature()
    expected = {
        edge_key(u, v): k
        for (u, v), k in nx.get_edge_attributes(pooled.G, "ricciCurvature").items()
    }
    assert rtt_ricci.ricci_curvature(graph) == pytest.approx(expected)


def test_curvature_does_not_fork(monkeypatch):
    import multiprocessing

    def no_fork(*args, **kwargs):
        raise AssertionError("ricci_curvature must not start processes")

    monkeypatch.setattr(multiprocessing.context.ForkContext, "Pool", no_fork)
    assert rtt_ricci.ricci_curvature(dumbbell())[("a1", "b1")] == pytest.approx(-1 / 3)
