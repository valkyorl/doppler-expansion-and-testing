"""Tests for attack-plan construction and the two baseline attackers."""

import pytest
from helpers import dumbbell

from doppler2026.attack_plans import budget_from_capacity, make_plan
from doppler2026.model import AttackConfig, RoutingConfig
from doppler2026.recon.oracle import oracle_plan
from doppler2026.recon.random_plan import random_plan


def test_budget_is_split_equally():
    """Eq. 8: r_i = R_A / |A|."""
    plan = make_plan(
        [("a", "b"), ("c", "d"), ("e", "f"), ("g", "h")],
        100.0,
        mechanism="test",
        topology_id="t",
    )
    assert [flow.rate for flow in plan.flows] == [25.0] * 4
    assert sum(plan.demands().values()) == pytest.approx(100.0)


def test_plan_rejects_duplicate_or_empty_pairs():
    with pytest.raises(ValueError):
        make_plan([], 1.0, mechanism="test", topology_id="t")
    with pytest.raises(ValueError):
        make_plan([("a", "b"), ("a", "b")], 1.0, mechanism="test", topology_id="t")


def test_budget_from_capacity():
    assert budget_from_capacity(1.5, 100e9) == pytest.approx(150e9)


def test_oracle_targets_the_bridge():
    """Every a-to-b pair crosses the bridge, so it concentrates the most traffic."""
    plan = oracle_plan(
        dumbbell(), AttackConfig(budget=100.0, n_pairs=5), RoutingConfig()
    )
    assert plan.target in {("a1", "b1"), ("b1", "a1")}
    assert len(plan.flows) == 5
    # Every chosen pair actually crosses the targeted link.
    a_side = {"a1", "a2", "a3"}
    for flow in plan.flows:
        assert (flow.source in a_side) != (flow.target in a_side)


def test_oracle_respects_endpoints():
    endpoints = ("a2", "a3", "b2", "b3")
    plan = oracle_plan(
        dumbbell(),
        AttackConfig(budget=100.0, n_pairs=10, endpoints=endpoints),
        RoutingConfig(),
    )
    for flow in plan.flows:
        assert flow.source in endpoints and flow.target in endpoints


def test_random_plan_is_reproducible_and_seed_dependent():
    config = AttackConfig(budget=100.0, n_pairs=4)
    first = random_plan(dumbbell(), config, seed=7)
    again = random_plan(dumbbell(), config, seed=7)
    other = random_plan(dumbbell(), config, seed=8)
    assert first == again
    assert first.flows != other.flows
    assert len(first.flows) == 4
