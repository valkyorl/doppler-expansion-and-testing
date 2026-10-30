"""Tests for damage D(A, G) and the τ/η ratio on hand-checkable topologies."""

import math

import pytest
from helpers import dumbbell, line

from doppler2026.attack_plans import make_plan
from doppler2026.damage import evaluate_damage, relative_damage
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import oracle_plan

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
