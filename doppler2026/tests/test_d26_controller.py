"""Phase 4 tests: transitions (§4.13), the control loop (§4.14), configs."""

import json

import networkx as nx
import pytest

from doppler2026 import candidates as cand
from doppler2026.controller import ControllerConfig, DefenderConfig, run
from doppler2026.model import DamageConfig, RoutingConfig
from doppler2026.run import load_config
from doppler2026.topology import GML_DIR
from doppler2026.transition import evaluate_transition, order_changes

ROUTING = RoutingConfig()
DAMAGE = DamageConfig()


# Transitions (Eq. 32-33, D31)


def test_additions_with_free_transponders_are_make_before_break():
    plan = order_changes(
        [("a", "b"), ("b", "c")],
        [("a", "c"), ("b", "c")],
        {"a": 2, "b": 2, "c": 2},
    )
    assert plan.added == {("a", "c")} and plan.removed == {("a", "b")}
    assert plan.make_before_break and plan.kind == "make_before_break"
    assert [(a.step, a.kind, a.link) for a in plan.actions] == [
        (1, "add", ("a", "c")),
        (4, "remove", ("a", "b")),
    ]


def test_reused_transponders_force_break_before_make():
    """One transponder per PoP: a-c and b-d need a-b and c-d gone first."""
    plan = order_changes(
        [("a", "b"), ("c", "d")],
        [("a", "c"), ("b", "d")],
        dict.fromkeys("abcd", 1),
    )
    assert not plan.make_before_break and plan.kind == "break_before_make"
    assert [(a.step, a.kind, a.link) for a in plan.actions] == [
        (2, "remove", ("a", "b")),
        (2, "remove", ("c", "d")),
        (3, "add", ("a", "c")),
        (3, "add", ("b", "d")),
    ]


def test_only_needed_links_are_broken_early():
    """a-c needs a free transponder at c only; b-d is removed last."""
    plan = order_changes(
        [("a", "b"), ("c", "d"), ("b", "d")],
        [("a", "b"), ("a", "c")],
        {"a": 2, "b": 2, "c": 1, "d": 2},
    )
    assert [(a.step, a.kind, a.link) for a in plan.actions] == [
        (2, "remove", ("c", "d")),
        (3, "add", ("a", "c")),
        (4, "remove", ("b", "d")),
    ]


def test_no_change_is_no_transition():
    plan = order_changes([("a", "b")], [("a", "b")], {"a": 1, "b": 1})
    assert plan.kind == "none" and not plan.actions


def test_intermediate_states_are_measured():
    """Path a-b-c-d becomes a-c-b-d with tight transponders: d is cut off mid-way.

    a and d have one transponder, b and c two. Adding a-c and b-d first needs
    a-b and c-d removed, which leaves only b-c: a and d are isolated.
    """
    original = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        original.add_edge(u, v, capacity=100.0)
    links = [("a", "b"), ("b", "c"), ("c", "d"), ("a", "c"), ("b", "d")]
    transition = evaluate_transition(
        original,
        [("a", "b"), ("b", "c"), ("c", "d")],
        [("a", "c"), ("b", "c"), ("b", "d")],
        dict.fromkeys(links, 100.0),
        {"a": 1, "b": 2, "c": 2, "d": 1},
        {("a", "d"): 10.0},
        ROUTING,
        DAMAGE,
    )
    assert [s.after_step for s in transition.states] == [0, 2, 3]
    start, broken, done = transition.states
    assert start.connected and start.benign_loss == pytest.approx(0.0)
    assert not broken.connected and broken.benign_loss == pytest.approx(1.0)
    assert done.connected and done.benign_loss == pytest.approx(0.0)
    record = transition.as_record()
    assert record["kind"] == "break_before_make" and len(record["actions"]) == 4


# The control loop (§4.14)

SMALL = DefenderConfig(candidates=cand.CandidateConfig(pool_size=5))
needs_sprint = pytest.mark.skipif(
    not (GML_DIR / "sprint.gml").exists(), reason="sprint missing"
)


def _comparable(rows):
    """Rows without timings; NaN as a string, since NaN != NaN."""
    return [
        {k: ("nan" if v != v else v) for k, v in r.items() if "time" not in k}
        for r in rows
    ]


@needs_sprint
def test_same_config_reproduces_exactly():
    config = ControllerConfig(network="sprint", epochs=3, defender=SMALL)
    first, second = run(config), run(config)
    for a, b in (
        (first.epochs, second.epochs),
        (first.candidates, second.candidates),
        (first.transitions, second.transitions),
    ):
        assert _comparable(a) == _comparable(b)


@needs_sprint
def test_epoch_rows_log_attack_pool_and_transition():
    result = run(ControllerConfig(network="sprint", epochs=3, defender=SMALL))
    first, *later = result.epochs
    assert "stale_transferability" not in first  # t < L: no attack yet (D10)
    for row in later:
        assert {
            "stale_transferability",
            "stale_benign_loss",
            "attack_plan_learned_at",
        } <= row.keys()
        assert row["attack_plan_learned_at"] == row["epoch"] - 1
    for row in result.epochs:
        assert {
            "candidates",
            "safe",
            "solver_time",
            "transition",
            "links",
        } <= row.keys()
    assert len(result.transitions) == 3
    # The stale attack in epoch 1 is the plan from G_0 on the topology selected
    # in epoch 0, so its τ is that topology's T(G') against that plan.
    if first["selected_transferability"] is not None:
        assert later[0]["stale_transferability"] == pytest.approx(
            first["selected_transferability"]
        )


@needs_sprint
def test_static_mode_never_changes_and_lag_zero_is_fresh():
    result = run(
        ControllerConfig(network="sprint", epochs=2, mode="static", recon_lag=0)
    )
    assert {r["current_topology_id"] for r in result.epochs} == {
        result.epochs[0]["current_topology_id"]
    }
    assert all(r["transition"] == "none" for r in result.epochs)
    # L = 0: the attacker uses the plan it just learned: τ = 1.
    assert all(r["stale_transferability"] == pytest.approx(1.0) for r in result.epochs)


@needs_sprint
def test_churn_mode_skips_the_security_filter():
    result = run(
        ControllerConfig(network="sprint", epochs=1, mode="churn", defender=SMALL)
    )
    assert all(
        r["transferability"] != r["transferability"] for r in result.candidates
    )  # NaN
    assert not [t for t in result.transferability if t["role"] == "security"]


# Configs (run.py)


def test_config_loader_builds_nested_settings(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps(
            {
                "_comment": "test",
                "network": "sprint",
                "epochs": 2,
                "defender": {
                    "candidates": {"pool_size": 7, "weight_range": [1.5, 2.5]},
                    "security": {"tau_max": 0.3},
                },
            }
        )
    )
    config = load_config(path)
    assert config.epochs == 2
    assert config.defender.candidates.pool_size == 7
    assert config.defender.candidates.weight_range == (1.5, 2.5)
    assert config.defender.security.tau_max == 0.3
    assert config.defender.operational.s_max == 3.0  # default kept


def test_config_loader_refuses_unknown_settings(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"defender": {"security": {"tau": 0.3}}}))
    with pytest.raises(ValueError, match="Unknown SecurityConfig"):
        load_config(path)


# O5 guidance and the O6 churn baseline


def test_guidance_scores_changes_that_move_attack_off_its_target():
    """Removing the dumbbell's bridge moves all a->b attack traffic off it."""
    from helpers import dumbbell

    from doppler2026.attack_plans import make_plan
    from doppler2026.security import attack_guidance

    graph = dumbbell()
    plan = make_plan(
        [("a2", "b2"), ("a3", "b3")],
        100.0,
        mechanism="traceroute",
        topology_id="g",
        target=("a1", "b1"),
    )
    guidance = attack_guidance(
        graph, graph, [("a1", "b1"), ("a2", "a3"), ("a2", "b2")], [plan], ROUTING
    )
    assert guidance[("a1", "b1")] == pytest.approx(1.0)  # bridge removed
    assert guidance[("a2", "a3")] == pytest.approx(0.0)  # elsewhere
    # A new a2-b2 shortcut carries a2->b2 (50 of 100) directly, and gives
    # a3->b3 a second equal-cost path a3-a2-b2-b3, so ECMP moves half of its
    # 50 too: 75 of 100 leave the bridge.
    assert guidance[("a2", "b2")] == pytest.approx(0.75)


def test_security_guided_objective_needs_guidance():
    from helpers import dumbbell

    from doppler2026.feasibility import feasible_links

    graph = dumbbell()
    with pytest.raises(ValueError, match="guidance"):
        cand.generate(
            graph,
            graph,
            feasible_links(graph),
            {("a1", "b1"): 1.0},
            cand.CandidateConfig(objective="security_guided"),
        )


@needs_sprint
def test_churn_selects_least_overlap_among_operational_candidates():
    result = run(
        ControllerConfig(network="sprint", epochs=1, mode="churn", defender=SMALL)
    )
    rows = [r for r in result.candidates if r["operational_passed"]]
    if rows:
        chosen = next(r for r in rows if r["selected"])
        overlap = lambda r: r["links"] - r["added"]  # noqa: E731
        assert overlap(chosen) == min(overlap(r) for r in rows)


# Synthetic networks and per-epoch cost


def test_controller_runs_on_a_synthetic_network_and_logs_cost(tmp_path):
    from doppler2026.synthetic import SyntheticConfig, generate, write

    write(generate(SyntheticConfig(name="tiny", nodes=6, mean_degree=3.0)), tmp_path)
    result = run(
        ControllerConfig(
            network="tiny", topology_dir=str(tmp_path), epochs=2, mode="static"
        )
    )
    first = result.epochs[0]
    assert first["links"] == 9
    assert 0 < first["current_mlu"] <= 0.5 + 1e-9  # benign scaled to 50% peak
    assert first["current_max_stretch"] == pytest.approx(1.0)  # G_0 itself
