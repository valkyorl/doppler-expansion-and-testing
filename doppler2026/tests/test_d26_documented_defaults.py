"""The defaults the docs quote are the defaults the code uses.

`docs/decisions.md` and `docs/code_paper_discrepancies.md` state the
accepted defaults in prose; this test pins the same values, so changing a
default in code without updating the docs (or the reverse) fails here.
Each entry names the decision that sets it.
"""

import dataclasses
from pathlib import Path

import pytest

from doppler2026.controller import ControllerConfig
from doppler2026.model import AttackConfig
from doppler2026.run import load_config

DOCUMENTED = {
    "recon_lag": (2, "D10"),
    "defender.feasibility.max_fiber_hops": (2, "D16"),
    "defender.feasibility.max_km": (None, "D6"),
    "defender.candidates.pool_size": (50, "D3"),
    "defender.candidates.time_limit": (60.0, "D25"),
    "defender.candidates.u_max": (0.8, "D5"),
    "defender.candidates.candidate_set": ("local", "D23"),
    "defender.candidates.objective": ("random_weights", "D22, O5"),
    "defender.candidates.keep_link_count": (False, "baseline 2026-11-10"),
    "defender.candidates.spare_transponders": (0, "D18, baseline 2026-11-10"),
    "defender.candidates.spare_fraction": (0.1, "D18, baseline 2026-11-10"),
    "defender.operational.u_max": (0.8, "D5"),
    "defender.operational.s_max": (3.0, "D5, O4"),
    "defender.operational.stretch_metric": ("km", "D19"),
    "defender.operational.require_two_edge_connected": (False, "D20"),
    "defender.security.tau_max": (0.5, "D3"),
    "defender.security.history_length": (3, "D3"),
    "defender.security.budget_multiple": (2.0, "D21"),
    "defender.security.n_pairs": (10, "D4"),
    "defender.security.non_response": (0.1, "D26"),
    "defender.security.max_stale_damage_ratio": (None, "A6, baseline 2026-11-10"),
    "defender.security.max_vulnerability_ratio": (None, "A6, baseline 2026-11-10"),
    "defender.security.oracle_comparisons": (False, "D28"),
    "defender.selection.objective": ("mlu", "D24"),
    "defender.selection.tolerance": (0.10, "D9"),
    "defender.routing.te_method": ("ecmp", "I4"),
    "defender.damage.tau_measure": ("benign_loss", "D1"),
    "defender.damage.zero_denominator": ("zero_or_inf", "D2"),
    "defender.damage.sharing": ("proportional", "D11"),
    "defender.damage.disruption_level": (1e-6, "D14"),
}


def _get(config, dotted):
    for name in dotted.split("."):
        config = getattr(config, name)
    return config


@pytest.mark.parametrize("setting", sorted(DOCUMENTED))
def test_default_matches_docs(setting):
    value, decision = DOCUMENTED[setting]
    assert _get(ControllerConfig(), setting) == value, f"see {decision}"


def test_attack_defaults_match_docs():
    attack = AttackConfig(budget=1.0)
    assert attack.n_pairs == 10  # D4
    assert attack.endpoints is None  # D8
    assert attack.oracle_knowledge == "benign"  # D15


CONFIGS = sorted((Path(__file__).parents[1] / "configs").rglob("*.json"))


@pytest.mark.parametrize(
    "path", CONFIGS, ids=[f"{p.parent.name}/{p.stem}" for p in CONFIGS]
)
def test_shipped_configs_load(path):
    config = load_config(path)
    assert dataclasses.is_dataclass(config)
    if path.stem != "smoke":
        network, mode = path.stem.split("_")
        assert (config.network, config.mode) == (network, mode)
