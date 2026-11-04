"""Phase 3 tests: feasible links, candidate pool, filters, security, selection."""

import math

import networkx as nx
import numpy as np
import pytest
from helpers import dumbbell, line

from doppler2026 import candidates as cand
from doppler2026.attack_plans import make_plan
from doppler2026.feasibility import FeasibilityConfig, feasible_links
from doppler2026.filters import OperationalConfig, operational_check, reference_lengths
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import oracle_plan
from doppler2026.security import (
    HistoryEntry,
    SecurityConfig,
    history_plan,
    pairwise_transferability,
    security_check,
)
from doppler2026.selection import SelectionConfig, select
from doppler2026.topology import GML_DIR, topology_id

ROUTING = RoutingConfig()
DAMAGE = DamageConfig()


def placed(graph, coordinates):
    for node, (lat, lon) in coordinates.items():
        graph.nodes[node]["Latitude"] = lat
        graph.nodes[node]["Longitude"] = lon
    return graph


def chain():
    """a - b - c - d on the equator, one degree apart (about 111 km each)."""
    graph = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        graph.add_edge(u, v, capacity=100.0)
    return placed(graph, {"a": (0, 0), "b": (0, 1), "c": (0, 2), "d": (0, 3)})


def uniform(graph, amount):
    return {(s, d): amount for s in graph.nodes for d in graph.nodes if s != d}


# Feasible links (§4.4)


def test_feasible_links_are_original_links_plus_two_fiber_hops():
    links = feasible_links(chain())
    assert set(links) == {
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
        ("a", "c"),
        ("b", "d"),
    }
    assert links[("a", "c")] == ("a", "b", "c")


def test_feasible_links_respect_hops_reach_and_optical_check():
    assert set(feasible_links(chain(), FeasibilityConfig(max_fiber_hops=1))) == {
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
    }
    # About 222 km for a two-fiber path: a 200 km reach rejects it.
    assert ("a", "c") not in feasible_links(chain(), FeasibilityConfig(max_km=200))
    assert ("a", "c") in feasible_links(chain(), FeasibilityConfig(max_km=250))
    refused = feasible_links(
        chain(), optical_check=lambda u, v, path: (u, v) != ("a", "c")
    )
    assert ("a", "c") not in refused and ("b", "d") in refused


# Candidate pool (§4.5-4.6, §4.10-4.11)


def test_transponders_and_capacities_follow_d17_d18():
    graph = chain()
    graph.edges["c", "d"]["capacity"] = 300.0
    assert cand.transponders(graph, cand.CandidateConfig(spare_transponders=0)) == {
        "a": 1,
        "b": 2,
        "c": 2,
        "d": 1,
    }
    # Default (D18 revised after O7): one spare at every PoP.
    assert cand.transponders(graph, cand.CandidateConfig()) == {
        "a": 2,
        "b": 3,
        "c": 3,
        "d": 2,
    }
    spares = cand.transponders(
        graph, cand.CandidateConfig(spare_transponders=2, spare_fraction=0.5)
    )
    assert spares == {"a": 1, "b": 4, "c": 4, "d": 1}  # b and c are most central
    capacities = cand.link_capacities(graph, [("a", "b"), ("c", "d"), ("a", "c")])
    assert capacities == {("a", "b"): 100.0, ("c", "d"): 300.0, ("a", "c"): 100.0}


def test_local_set_moves_one_endpoint_of_central_links():
    graph = chain()
    feasible = feasible_links(graph)
    # Top 10% of 3 links = the single most central link, b-c: moving one
    # endpoint gives a-c and b-d.
    local = cand.variable_links(graph, feasible, [], cand.CandidateConfig())
    assert set(local) == set(feasible)
    expanded = cand.variable_links(
        graph, feasible, [], cand.CandidateConfig(candidate_set="expanded")
    )
    assert set(expanded) == set(feasible)


def test_local_set_includes_links_around_history_targets():
    graph = nx.cycle_graph(6)
    graph = nx.relabel_nodes(graph, str)
    nx.set_edge_attributes(graph, 100.0, "capacity")
    feasible = feasible_links(graph, FeasibilityConfig(max_fiber_hops=2))
    config = cand.CandidateConfig(top_fraction=0.01)  # one central link only
    without = set(cand.variable_links(graph, feasible, [], config))
    with_target = set(cand.variable_links(graph, feasible, [("3", "4")], config))
    assert {("2", "4"), ("3", "5")} <= with_target - without


def test_pool_respects_transponders_and_excludes_current():
    graph = dumbbell()
    pool = cand.generate(
        graph,
        graph,
        feasible_links(graph),
        uniform(graph, 1.0),
        cand.CandidateConfig(pool_size=10, candidate_set="expanded"),
    )
    current = {tuple(sorted(e)) for e in graph.edges}
    txp = cand.transponders(graph, cand.CandidateConfig())
    ids = [c.topology_id for c in pool.candidates]
    assert pool.candidates and len(set(ids)) == len(ids)
    for c in pool.candidates:
        assert c.links != current
        assert c.links <= set(pool.variable_links)
        for node, count in txp.items():
            assert sum(node in e for e in c.links) <= count
        assert c.milp_mlu <= 0.8 + 1e-9


def test_pool_with_spares_can_add_links():
    graph = dumbbell()
    pool = cand.generate(
        graph,
        graph,
        feasible_links(graph),
        uniform(graph, 1.0),
        cand.CandidateConfig(
            pool_size=20,
            candidate_set="expanded",
            spare_transponders=1,
            spare_fraction=1.0,
        ),
    )
    assert any(c.added for c in pool.candidates)


def test_pool_is_reproducible():
    graph = dumbbell()
    config = cand.CandidateConfig(pool_size=8, candidate_set="expanded", seed=3)
    feasible = feasible_links(graph)
    first = cand.generate(graph, graph, feasible, uniform(graph, 1.0), config)
    second = cand.generate(graph, graph, feasible, uniform(graph, 1.0), config)
    assert [c.links for c in first.candidates] == [c.links for c in second.candidates]


def test_pool_refuses_demand_beyond_u_max():
    """60 on a 100 link exceeds U_max = 0.5: no topology can carry it."""
    graph = line()
    pool = cand.generate(
        graph,
        graph,
        feasible_links(graph),
        {("x", "y"): 60.0},
        cand.CandidateConfig(u_max=0.5),
    )
    assert pool.status == "infeasible" and not pool.candidates


# Operational filter (§4.6-4.7, Eq. 16-17)


def test_stretch_in_hops_and_km():
    """Dropping b-c from the chain plus a-c and b-d forces b->c over b-d-c."""
    base = chain()
    base.add_edge("a", "c", capacity=100.0)
    base.add_edge("b", "d", capacity=100.0)
    benign = {("b", "c"): 1.0}
    candidate = base.copy()
    candidate.remove_edge("b", "c")
    for metric, expected in (("hops", 2.0), ("km", 3.0)):
        config = OperationalConfig(stretch_metric=metric, s_max=None)
        reference = reference_lengths(base, benign, ROUTING, metric)
        result = operational_check(candidate, benign, reference, ROUTING, config)
        # km: b->d->c is 2 + 1 degrees against 1 degree.
        assert result.max_stretch == pytest.approx(expected, rel=1e-3)
        assert result.passed


def test_operational_filter_reasons():
    base = chain()
    benign = {("a", "d"): 90.0}
    reference = reference_lengths(base, benign, ROUTING, "hops")
    broken = base.copy()
    broken.remove_edge("b", "c")
    hops = OperationalConfig(stretch_metric="hops")
    result = operational_check(broken, benign, reference, ROUTING, hops)
    assert set(result.reasons) >= {"disconnected", "unroutable"}
    hot = operational_check(base, benign, reference, ROUTING, hops)
    assert hot.reasons == ("mlu",) and hot.mlu == pytest.approx(0.9)
    with pytest.raises(ValueError, match="reference lengths"):
        operational_check(base, benign, reference, ROUTING, OperationalConfig())
    strict = OperationalConfig(
        require_two_edge_connected=True, u_max=1.0, stretch_metric="hops"
    )
    assert operational_check(base, benign, reference, ROUTING, strict).reasons == (
        "not_2_edge_connected",
    )


# Security filter and diversity (Eq. 21-24)


# τ-only settings: these tests build history entries without own_damage.
SECURITY = SecurityConfig(max_stale_damage_ratio=None, max_vulnerability_ratio=None)


def traceroute_plan(graph, attack, seed=0):
    return history_plan(graph, attack, ROUTING, SECURITY, seed=seed)


def test_plan_on_its_unchanged_topology_has_tau_one():
    """O3 option e: A* is the same attacker re-measuring, so tau(A, G) = 1."""
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    plan = traceroute_plan(graph, attack)
    assert plan.target in (("a1", "b1"), ("b1", "a1"))  # the bridge
    result = security_check(
        graph,
        [HistoryEntry("g0", plan)],
        uniform(graph, 5.0),
        attack,
        ROUTING,
        DAMAGE,
        SecurityConfig(
            oracle_comparisons=True,
            max_stale_damage_ratio=None,
            max_vulnerability_ratio=None,
        ),
        seed=1,
    )
    (comparison,) = result.comparisons
    assert comparison.reference == "traceroute"
    assert result.transferability == pytest.approx(1.0) and not result.passed
    # Both oracles are saved alongside as extra columns.
    row = comparison.as_row()
    assert {"oracle_benign_ratio", "oracle_ratio"} <= row.keys()


def test_security_check_takes_the_worst_history_plan():
    """A stale plan that attacks inside one triangle misses the bridge; T is the max.

    (A plan learned with the bridge elsewhere would still cross a1-b1 here, so
    it would transfer fully: the paper's point that different graphs can
    share the same cut.)
    """
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    weak = make_plan(
        [("a2", "a3"), ("a3", "a2")],
        attack.budget,
        mechanism="traceroute",
        topology_id="elsewhere",
        target=("a2", "a3"),
    )
    history = [
        HistoryEntry("elsewhere", weak),
        HistoryEntry("here", traceroute_plan(graph, attack)),
    ]
    benign = uniform(graph, 5.0)
    config = SecurityConfig(
        history_length=2, max_stale_damage_ratio=None, max_vulnerability_ratio=None
    )
    result = security_check(
        graph, history, benign, attack, ROUTING, DAMAGE, config, seed=1
    )
    stale, current = (c.ratio for c in result.comparisons)
    assert stale < current == pytest.approx(1.0)
    assert result.transferability == current
    only_last = security_check(
        graph,
        history,
        benign,
        attack,
        ROUTING,
        DAMAGE,
        SecurityConfig(
            history_length=1, max_stale_damage_ratio=None, max_vulnerability_ratio=None
        ),
        seed=1,
    )
    assert len(only_last.comparisons) == 1


def test_security_check_flags_attack_immune_candidates():
    """Nothing overloads: fresh and stale plans both harmless, tau = 0 (D2)."""
    graph = dumbbell(capacity=1e15)
    attack = AttackConfig(budget=200.0, n_pairs=5)
    result = security_check(
        graph,
        [HistoryEntry("g0", traceroute_plan(graph, attack))],
        uniform(graph, 5.0),
        attack,
        ROUTING,
        DAMAGE,
        SECURITY,
        seed=1,
    )
    assert result.attack_immune and result.transferability == 0.0 and result.passed


def test_oracle_comparisons_are_off_by_default():
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    result = security_check(
        graph,
        [HistoryEntry("g0", traceroute_plan(graph, attack))],
        uniform(graph, 5.0),
        attack,
        ROUTING,
        DAMAGE,
        SECURITY,
        seed=1,
    )
    assert "oracle_ratio" not in result.comparisons[0].as_row()


def test_history_of_unknown_mechanism_is_refused():
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    with pytest.raises(NotImplementedError):
        security_check(
            graph,
            [HistoryEntry("g0", oracle_plan(graph, attack, ROUTING))],
            uniform(graph, 5.0),
            attack,
            ROUTING,
            DAMAGE,
            SECURITY,
            seed=1,
        )


def test_stale_damage_limit_rejects_a_plan_that_got_stronger():
    """O7: the stale plan must not do more damage than on its own topology.

    The plan is learned on a dumbbell with a parallel bridge a2-b2; on the
    plain dumbbell its traffic all crosses a1-b1, so it does more damage.
    """
    from doppler2026.security import history_entry

    learned_on = dumbbell()
    learned_on.add_edge("a2", "b2", capacity=100.0)
    candidate = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    benign = uniform(candidate, 5.0)
    entry = history_entry(
        learned_on, traceroute_plan(learned_on, attack), benign, ROUTING, DAMAGE
    )
    result = security_check(
        candidate,
        [entry],
        benign,
        attack,
        ROUTING,
        DAMAGE,
        SecurityConfig(tau_max=10.0, max_vulnerability_ratio=None),
        seed=1,
    )
    assert result.damage_ratio > 1.0
    assert result.reasons == ("stale_damage",) and not result.passed
    looser = security_check(
        candidate,
        [entry],
        benign,
        attack,
        ROUTING,
        DAMAGE,
        SecurityConfig(
            tau_max=10.0, max_stale_damage_ratio=None, max_vulnerability_ratio=None
        ),
        seed=1,
    )
    assert looser.passed


def test_vulnerability_limit_compares_fresh_damage_with_a_reference():
    from doppler2026.security import history_entry

    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    benign = uniform(graph, 5.0)
    entry = history_entry(
        graph, traceroute_plan(graph, attack), benign, ROUTING, DAMAGE
    )
    config = SecurityConfig(tau_max=10.0, max_vulnerability_ratio=1.0)
    same = security_check(
        graph,
        [entry],
        benign,
        attack,
        ROUTING,
        DAMAGE,
        config,
        seed=1,
        vulnerability_reference=entry.own_damage,
    )
    assert same.passed  # as vulnerable as the reference, not more
    stricter = security_check(
        graph,
        [entry],
        benign,
        attack,
        ROUTING,
        DAMAGE,
        config,
        seed=1,
        vulnerability_reference=entry.own_damage / 2,
    )
    assert stricter.reasons == ("vulnerability",)
    with pytest.raises(ValueError, match="reference"):
        security_check(graph, [entry], benign, attack, ROUTING, DAMAGE, config, seed=1)


def test_pool_keeps_the_link_count():
    graph = dumbbell()
    pool = cand.generate(
        graph,
        graph,
        feasible_links(graph),
        uniform(graph, 1.0),
        cand.CandidateConfig(
            pool_size=10,
            candidate_set="expanded",
            spare_transponders=1,
            spare_fraction=1.0,
        ),
    )
    assert pool.candidates
    assert all(len(c.links) >= graph.number_of_edges() for c in pool.candidates)
    removals = cand.generate(
        graph,
        graph,
        feasible_links(graph),
        uniform(graph, 1.0),
        cand.CandidateConfig(
            pool_size=10, candidate_set="expanded", keep_link_count=False
        ),
    )
    assert any(len(c.links) < graph.number_of_edges() for c in removals.candidates)


def test_pairwise_matrix_covers_every_ordered_pair():
    graph = dumbbell()
    other = graph.copy()
    other.add_edge("a2", "b2", capacity=100.0)
    attack = AttackConfig(budget=200.0, n_pairs=5)
    members = [(g, traceroute_plan(g, attack)) for g in (graph, other)]
    rows = pairwise_transferability(
        members, uniform(graph, 5.0), attack, ROUTING, DAMAGE, SECURITY, seed=1
    )
    assert [(i, j) for i, j, _ in rows] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    for i, j, comparison in rows:
        if i == j:
            assert comparison.ratio == pytest.approx(1.0)  # re-measuring G_i
        assert comparison.evaluated_on == topology_id(members[j][0])


# Selection (§4.11)


def test_selection_picks_within_tolerance_reproducibly():
    scores = {"a": 0.50, "b": 0.54, "c": 0.56, "d": 0.90}
    config = SelectionConfig(tolerance=0.10)
    choice = select(scores, config, np.random.default_rng(0))
    assert choice.acceptable == ("a", "b") and choice.chosen in ("a", "b")
    again = select(scores, config, np.random.default_rng(0))
    assert again.chosen == choice.chosen
    picks = {select(scores, config, np.random.default_rng(s)).chosen for s in range(20)}
    assert picks == {"a", "b"}
    with pytest.raises(ValueError):
        select({}, config, np.random.default_rng(0))


# One epoch end to end (PLAN §6 Phase 3 check)


@pytest.mark.skipif(not (GML_DIR / "sprint.gml").exists(), reason="sprint missing")
def test_one_epoch_on_sprint_meets_every_constraint(tmp_path, monkeypatch):
    from doppler2026.experiments import defender_epoch as experiment

    config = experiment.DefenderEpochConfig(
        networks=("sprint",),
        candidates=cand.CandidateConfig(pool_size=10),
    )
    epoch, rows, transfers = experiment.run_network("sprint", config)
    assert epoch["candidates"] == 10
    if epoch["safe"]:
        experiment.check(epoch, rows, config)
        assert sum(r["selected"] for r in rows) == 1
    safe = epoch["safe"]
    pairwise = [t for t in transfers if t["role"] == "pairwise"]
    assert len(pairwise) == (safe * safe if safe > 1 else 0)
    assert all(
        not math.isnan(r["transferability"]) for r in rows if r["operational_passed"]
    )
