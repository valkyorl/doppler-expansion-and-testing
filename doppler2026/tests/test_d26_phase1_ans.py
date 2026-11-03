"""Phase 1 check on a real topology (ANS, Internet Topology Zoo).

PLAN.md Phase 1: on ANS, the oracle plan should cause clearly more benign
loss than random plans with the same budget, and the oracle plan measured
against itself should have ratio 1.
"""

import statistics
from dataclasses import replace

import pytest

from doppler2026.damage import evaluate_damage, relative_damage
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import benign_oracle_plan, oracle_plan
from doppler2026.recon.random_plan import random_plan
from doppler2026.topology import DEFAULT_CAPACITY, GML_DIR, load_topology
from doppler2026.traffic import benign_demand

pytestmark = pytest.mark.skipif(
    not (GML_DIR / "ANS.gml").exists(), reason="ANS topology not available"
)

ROUTING = RoutingConfig(te_method="ecmp")
DAMAGE = DamageConfig()


@pytest.fixture(scope="module")
def ans():
    topology = load_topology("ANS")
    benign = benign_demand(topology, target_utilization=0.5, routing=ROUTING, seed=1)
    # Twice a link's capacity: enough for the oracle to overload its target.
    attack = AttackConfig(budget=2 * DEFAULT_CAPACITY, n_pairs=10)
    return topology, benign, attack


def test_benign_traffic_is_scaled_to_target(ans):
    topology, benign, _ = ans
    plan = oracle_plan(topology, AttackConfig(budget=1.0, n_pairs=1), ROUTING)
    # A 1 bit/s attack barely changes utilization: about the benign target.
    report = evaluate_damage(topology, benign, plan, ROUTING, DAMAGE)
    assert report.max_utilization == pytest.approx(0.5, abs=1e-6)


def test_oracle_beats_random_plans(ans):
    topology, benign, attack = ans
    oracle = evaluate_damage(
        topology, benign, oracle_plan(topology, attack, ROUTING), ROUTING, DAMAGE
    )
    randoms = [
        evaluate_damage(
            topology, benign, random_plan(topology, attack, seed), ROUTING, DAMAGE
        ).benign_loss
        for seed in range(20)
    ]
    assert oracle.benign_loss > 0
    assert oracle.benign_loss > 2 * statistics.mean(randoms)
    assert oracle.benign_loss >= max(randoms)


def test_oracle_against_itself_has_ratio_one(ans):
    """The paper's oracle as the reference (D15 set to ``"routing"``)."""
    topology, benign, attack = ans
    attack = replace(attack, oracle_knowledge="routing")
    plan = oracle_plan(topology, attack, ROUTING)
    result = relative_damage(plan, topology, benign, attack, ROUTING, DAMAGE)
    assert result.ratio == pytest.approx(1.0)


def test_benign_oracle_against_itself_has_ratio_one(ans):
    """The default reference (D15): the oracle that knows benign traffic."""
    topology, benign, attack = ans
    plan = benign_oracle_plan(topology, benign, attack, ROUTING, DAMAGE)
    result = relative_damage(plan, topology, benign, attack, ROUTING, DAMAGE)
    assert result.ratio == pytest.approx(1.0)


def test_benign_oracle_does_at_least_as_much_damage(ans):
    """It tries the paper's oracle's target too, so it can never do less."""
    topology, benign, attack = ans
    paper = evaluate_damage(
        topology, benign, oracle_plan(topology, attack, ROUTING), ROUTING, DAMAGE
    )
    aware = evaluate_damage(
        topology,
        benign,
        benign_oracle_plan(topology, benign, attack, ROUTING, DAMAGE),
        ROUTING,
        DAMAGE,
    )
    assert aware.benign_loss >= paper.benign_loss - DAMAGE.zero_tolerance
