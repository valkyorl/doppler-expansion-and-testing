"""Tests for damage D(A, G) and the τ/η ratio on hand-checkable topologies."""

import math
from dataclasses import replace

import networkx as nx
import pytest
from helpers import dumbbell, line

from doppler2026.attack_plans import make_plan
from doppler2026.damage import evaluate_damage, relative_damage
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import benign_oracle_plan, oracle_plan

ROUTING = RoutingConfig()


def test_damage_measures_on_a_single_link():
    """Benign 80 and attack 100 share a 100-capacity link.

    Offered utilization is 180 / 100 = 1.8. With proportional sharing every
    flow keeps 100 / 180 of its traffic, so benign delivers 44.4 of 80 and
    loses 0.444 of its demand.
    """
    plan = make_plan([("x", "y")], 100.0, mechanism="test", topology_id="t")
    report = evaluate_damage(line(), {("x", "y"): 80.0}, plan, ROUTING, DamageConfig())

    assert report.benign_loss == pytest.approx(80 / 180)
    assert report.max_utilization == pytest.approx(1.8)
    assert report.overloaded_capacity == pytest.approx(100.0)  # only x -> y
    assert report.benign_on_congested == pytest.approx(1.0)
    assert report.benign_delivered_without_attack == pytest.approx(80.0)
    assert report.benign_delivered_with_attack == pytest.approx(80 * 100 / 180)
    assert report.attack_delivered == pytest.approx(100 * 100 / 180)


def test_max_min_sharing_protects_the_smaller_flow():
    """Under max-min, 100 is split 50/50 between flows of 80 and 100."""
    plan = make_plan([("x", "y")], 100.0, mechanism="test", topology_id="t")
    report = evaluate_damage(
        line(), {("x", "y"): 80.0}, plan, ROUTING, DamageConfig(sharing="max_min")
    )
    assert report.benign_loss == pytest.approx(0.375)


def test_attack_on_an_unused_direction_does_no_benign_damage():
    plan = make_plan([("y", "x")], 500.0, mechanism="test", topology_id="t")
    report = evaluate_damage(line(), {("x", "y"): 80.0}, plan, ROUTING, DamageConfig())
    assert report.benign_loss == pytest.approx(0.0)
    assert report.benign_on_congested == pytest.approx(0.0)
    assert report.max_utilization == pytest.approx(5.0)


def _uniform(graph, amount):
    return {(s, d): amount for s in graph.nodes for d in graph.nodes if s != d}


def test_oracle_plan_on_its_own_topology_has_ratio_one():
    """τ of the fresh plan against itself is 1 by definition (Phase 1 check)."""
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    plan = oracle_plan(graph, attack, ROUTING)
    result = relative_damage(
        plan, graph, _uniform(graph, 5.0), attack, ROUTING, DamageConfig()
    )
    assert result.denominator > 0
    assert result.ratio == pytest.approx(1.0)
    assert not result.attack_immune


def test_zero_denominator_follows_decision_d2():
    """With huge capacity no plan does damage: τ = 0 and the result is flagged."""
    graph = dumbbell(capacity=1e15)
    attack = AttackConfig(budget=200.0, n_pairs=5)
    plan = oracle_plan(graph, attack, ROUTING)
    benign = _uniform(graph, 5.0)

    zero = relative_damage(plan, graph, benign, attack, ROUTING, DamageConfig())
    assert zero.attack_immune and zero.ratio == 0.0

    undefined = relative_damage(
        plan, graph, benign, attack, ROUTING, DamageConfig(zero_denominator="nan")
    )
    assert undefined.attack_immune and math.isnan(undefined.ratio)


def test_ratio_uses_the_configured_measure():
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    plan = oracle_plan(graph, attack, ROUTING)
    result = relative_damage(
        plan,
        graph,
        _uniform(graph, 5.0),
        attack,
        ROUTING,
        DamageConfig(tau_measure="max_utilization"),
    )
    assert result.measure == "max_utilization"
    assert result.numerator == result.plan_damage.max_utilization


def test_as_row_contains_both_reports():
    graph = dumbbell()
    attack = AttackConfig(budget=200.0, n_pairs=5)
    plan = oracle_plan(graph, attack, ROUTING)
    row = relative_damage(
        plan, graph, _uniform(graph, 5.0), attack, ROUTING, DamageConfig()
    ).as_row()
    assert {"ratio", "plan_benign_loss", "fresh_benign_loss"} <= row.keys()


def _path3():
    """x - y - z, both links 100. Benign traffic flows only z -> y."""
    graph = nx.Graph()
    graph.add_edge("x", "y", capacity=100.0)
    graph.add_edge("y", "z", capacity=100.0)
    return graph, {("z", "y"): 80.0}


def test_benign_oracle_targets_the_link_carrying_benign_traffic():
    """D15. Every link can absorb the whole one-pair attack, so the paper's
    oracle picks by tie-break (x -> y, first by name), where there is no
    benign traffic. The benign-aware oracle picks z -> y: 180 offered on 100,
    so benign keeps 100/180 and loses 80/180 of its demand."""
    graph, benign = _path3()
    attack = AttackConfig(budget=100.0, n_pairs=1)
    assert oracle_plan(graph, attack, ROUTING).target == ("x", "y")
    plan = benign_oracle_plan(graph, benign, attack, ROUTING, DamageConfig())
    assert plan.target == ("z", "y")
    assert plan.mechanism == "oracle_benign"
    report = evaluate_damage(graph, benign, plan, ROUTING, DamageConfig())
    assert report.benign_loss == pytest.approx(80 / 180)


def test_relative_damage_records_both_oracles():
    """The ratio uses the oracle chosen by D15; the other one is saved too."""
    graph, benign = _path3()
    attack = AttackConfig(budget=100.0, n_pairs=1)
    benign_aware = benign_oracle_plan(graph, benign, attack, ROUTING, DamageConfig())

    default = relative_damage(
        benign_aware, graph, benign, attack, ROUTING, DamageConfig()
    )
    assert default.oracle_knowledge == "benign"
    assert default.ratio == pytest.approx(1.0)
    # The paper's oracle does no benign damage here, but this plan does: under
    # D2's "zero_or_inf" rule the ratio is infinite and not attack-immune.
    assert default.other_oracle_knowledge == "routing"
    assert not default.other_attack_immune and default.other_ratio == math.inf
    earlier = relative_damage(
        benign_aware,
        graph,
        benign,
        attack,
        ROUTING,
        DamageConfig(zero_denominator="zero"),
    )
    assert earlier.other_attack_immune and earlier.other_ratio == 0.0

    paper = relative_damage(
        benign_aware,
        graph,
        benign,
        replace(attack, oracle_knowledge="routing"),
        ROUTING,
        DamageConfig(),
    )
    assert paper.ratio == math.inf and paper.other_ratio == pytest.approx(1.0)
    row = default.as_row()
    assert {"other_ratio", "other_denominator", "other_fresh_benign_loss"} <= row.keys()


def test_unknown_oracle_knowledge_is_refused():
    with pytest.raises(ValueError, match="oracle_knowledge"):
        AttackConfig(budget=1.0, oracle_knowledge="traffic")


def test_zero_or_inf_rule_when_fresh_plan_does_nothing():
    """D2 (revised): both plans harmless -> 0 and immune; only the stale one -> inf."""
    graph, benign = _path3()
    attack = AttackConfig(budget=100.0, n_pairs=1)
    harmless = make_plan([("x", "y")], 100.0, mechanism="probe", topology_id="t")
    harmful = make_plan([("z", "y")], 100.0, mechanism="probe", topology_id="t")
    both = relative_damage(
        harmless, graph, benign, attack, ROUTING, DamageConfig(), fresh_plan=harmless
    )
    assert both.ratio == 0.0 and both.attack_immune
    stale_only = relative_damage(
        harmful, graph, benign, attack, ROUTING, DamageConfig(), fresh_plan=harmless
    )
    assert stale_only.ratio == math.inf and not stale_only.attack_immune
    assert stale_only.reference == "probe" and stale_only.oracle_knowledge == "probe"


def test_extra_comparisons_are_saved_as_columns():
    graph, benign = _path3()
    attack = AttackConfig(budget=100.0, n_pairs=1)
    plan = benign_oracle_plan(graph, benign, attack, ROUTING, DamageConfig())
    result = relative_damage(
        plan,
        graph,
        benign,
        attack,
        ROUTING,
        DamageConfig(),
        extra_fresh_plans={"vs_self": plan},
    )
    row = result.as_row()
    assert row["vs_self_ratio"] == pytest.approx(1.0)
    assert row["reference"] == "oracle_benign" and row["other_reference"] == "oracle"
