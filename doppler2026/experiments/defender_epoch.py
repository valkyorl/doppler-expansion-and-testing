"""One Doppler defender epoch (paper §4.3-4.11): the Phase 3 check of PLAN §6.

For each network, starting from its original topology G_0:

1. The attacker measures G_0 by traceroute and learns plan A_0 (D7, D26).
   The history is [(G_0, A_0)].
2. Feasible links E* from the fiber graph (§4.4, D16).
3. The MILP enumerates up to K candidates around G_0 (§4.10-4.11, D22, D23).
4. Operational filter with the network's routing (§4.6-4.7, D5, D19, D20).
5. Security filter: T(G') = max τ(A_i, G') <= τ_max (Eq. 21-22) on the
   candidates that passed step 4. τ's fresh plan is the same attacker
   re-measuring G' (O3 option e), with the next epoch's seed: the attacker
   measures again after the change.
6. Selection: rank the safe pool by the secondary objective and pick at
   random from the acceptable subset (§4.11, D9, D24).
7. Pairwise τ(A_i, G_j) over the safe pool (§4.9, Eq. 24).

The defender uses the true benign demand as its estimate D_t (D27).

The check PLAN §6 asks for: the selected topology satisfies every
operational constraint and has T(G') <= τ_max, and the pool's pairwise τ
matrix is produced. ``run`` raises if the first part fails.

Run from the repository root::

    python -m doppler2026.experiments.defender_epoch --networks ANS

Output (PLAN §10): ``data/results/doppler2026/defender_epoch/<run_id>/`` with
``config.json``; ``candidates.csv`` (one row per candidate: filter outcomes
and reasons, T(G'), secondary scores, whether selected);
``transferability.csv`` (one row per (plan, topology) pair: the security
filter's τ(A_0, G') with ``role = security``, and the pool's pairwise
τ(A_i, G_j) with ``role = pairwise``); ``epochs.csv`` (one row per network).
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .. import candidates as cand
from ..feasibility import FeasibilityConfig, feasible_links
from ..filters import OperationalConfig, operational_check, reference_lengths
from ..model import DamageConfig, RoutingConfig
from ..results import new_run_dir, write_config, write_csv
from ..security import (
    HistoryEntry,
    SecurityConfig,
    attack_config,
    history_plan,
    pairwise_transferability,
    security_check,
)
from ..selection import SelectionConfig, select
from ..topology import load_topology, topology_id
from ..traffic import benign_demand

EXPERIMENT = "defender_epoch"


@dataclass(frozen=True)
class DefenderEpochConfig:
    """All settings of one run; saved in ``config.json``."""

    networks: tuple[str, ...] = ("ANS",)
    benign_utilization: float = 0.5
    benign_seed: int = 1
    epoch: int = 0
    """Epoch number; the history attacker's measurement seed (D26)."""
    seed: int = 0
    """Seed of the random selection (the MILP weights use ``candidates.seed``)."""
    feasibility: FeasibilityConfig = field(default_factory=FeasibilityConfig)
    candidates: cand.CandidateConfig = field(default_factory=cand.CandidateConfig)
    operational: OperationalConfig = field(default_factory=OperationalConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    damage: DamageConfig = field(default_factory=DamageConfig)
    pairwise: bool = True


def secondary_score(objective: str, operational, candidate: cand.Candidate) -> float:
    if objective == "mlu":
        return operational.mlu
    if objective == "stretch":
        return operational.max_stretch
    return float(len(candidate.added) + len(candidate.dropped))


def run_network(name: str, config: DefenderEpochConfig) -> tuple[dict, list, list]:
    """One epoch on one network: (epoch row, candidate rows, transferability rows)."""
    started = time.perf_counter()
    routing, damage = config.routing, config.damage
    original = load_topology(name)
    benign = benign_demand(
        original, config.benign_utilization, routing, seed=config.benign_seed
    )
    attack = attack_config(original, config.security)

    # 1. The attacker's plan on the current (original) topology.
    plan = history_plan(original, attack, routing, config.security, seed=config.epoch)
    history = [HistoryEntry(topology_id(original), plan)]

    # 2-3. E* and the candidate pool.
    feasible = feasible_links(original, config.feasibility)
    pool = cand.generate(
        original,
        original,
        feasible,
        benign,
        config.candidates,
        targets=[e.plan.target for e in history if e.plan.target],
    )
    capacities = cand.link_capacities(original, pool.variable_links)
    reference = reference_lengths(
        original, benign, routing, config.operational.stretch_metric
    )

    # 4-5. Filters.
    rows: list[dict] = []
    transfer_rows: list[dict] = []
    safe: dict[str, tuple] = {}
    for candidate in pool.candidates:
        graph = cand.build_topology(original, candidate.links, capacities)
        operational = operational_check(
            graph, benign, reference, routing, config.operational
        )
        row = {
            "network": name,
            "epoch": config.epoch,
            "topology_id": candidate.topology_id,
            "solve_index": candidate.solve_index,
            "links": len(candidate.links),
            "added": len(candidate.added),
            "dropped": len(candidate.dropped),
            "added_links": ";".join(f"{u}-{v}" for u, v in sorted(candidate.added)),
            "dropped_links": ";".join(f"{u}-{v}" for u, v in sorted(candidate.dropped)),
            "milp_mlu": candidate.milp_mlu,
            "milp_objective": candidate.objective,
            "proven_optimal": candidate.proven_optimal,
            "operational_passed": operational.passed,
            "operational_reasons": ";".join(operational.reasons),
            "mlu": operational.mlu,
            "max_stretch": operational.max_stretch,
            "mean_stretch": operational.mean_stretch,
            "two_edge_connected": operational.two_edge_connected,
            "transferability": float("nan"),
            "security_passed": False,
            "attack_immune": False,
            "safe": False,
            "selected": False,
            "acceptable": False,
        }
        if operational.passed:
            security = security_check(
                graph,
                history,
                benign,
                attack,
                routing,
                damage,
                config.security,
                seed=config.epoch + 1,
            )
            row.update(
                transferability=security.transferability,
                security_passed=security.passed,
                attack_immune=security.attack_immune,
                safe=security.passed,
            )
            for entry, comparison in zip(history, security.comparisons, strict=True):
                transfer_rows.append(
                    {
                        "network": name,
                        "epoch": config.epoch,
                        "role": "security",
                        "plan_learned_on": entry.topology_id,
                        **comparison.as_row(),
                    }
                )
            if security.passed:
                score = secondary_score(
                    config.selection.objective, operational, candidate
                )
                safe[candidate.topology_id] = (graph, operational, score)
        row["secondary_score"] = (
            safe[candidate.topology_id][2] if candidate.topology_id in safe else None
        )
        rows.append(row)

    # 6. Selection.
    rng = np.random.default_rng(config.seed)
    chosen = None
    if safe:
        choice = select({t: s for t, (_, _, s) in safe.items()}, config.selection, rng)
        chosen = choice.chosen
        for row in rows:
            row["acceptable"] = row["topology_id"] in choice.acceptable
            row["selected"] = row["topology_id"] == chosen

    # 7. Pairwise τ over the safe pool (Eq. 24).
    if config.pairwise and len(safe) > 1:
        ids = sorted(safe)
        members = [
            (
                safe[t][0],
                history_plan(
                    safe[t][0], attack, routing, config.security, seed=config.epoch
                ),
            )
            for t in ids
        ]
        for i, j, comparison in pairwise_transferability(
            members,
            benign,
            attack,
            routing,
            damage,
            config.security,
            seed=config.epoch + 1,
        ):
            transfer_rows.append(
                {
                    "network": name,
                    "epoch": config.epoch,
                    "role": "pairwise",
                    "plan_learned_on": ids[i],
                    "member_i": i,
                    "member_j": j,
                    **comparison.as_row(),
                }
            )

    selected = next((r for r in rows if r["selected"]), None)
    epoch_row = {
        "network": name,
        "epoch": config.epoch,
        "current_topology_id": topology_id(original),
        "history_plan_target": plan.target,
        "feasible_links": len(feasible),
        "variable_links": len(pool.variable_links),
        "pool_status": pool.status,
        "solves": pool.solves,
        "solver_time": pool.wall_time,
        "candidates": len(pool.candidates),
        "operational_passed": sum(r["operational_passed"] for r in rows),
        "safe": len(safe),
        "attack_immune": sum(r["attack_immune"] for r in rows),
        "acceptable": sum(r["acceptable"] for r in rows),
        "selected_topology_id": chosen,
        "selected_transferability": selected["transferability"] if selected else None,
        "selected_mlu": selected["mlu"] if selected else None,
        "selected_max_stretch": selected["max_stretch"] if selected else None,
        "selected_added": selected["added_links"] if selected else None,
        "selected_dropped": selected["dropped_links"] if selected else None,
        "wall_time": time.perf_counter() - started,
    }
    return epoch_row, rows, transfer_rows


def check(epoch_row: dict, rows: list[dict], config: DefenderEpochConfig) -> None:
    """PLAN §6 Phase 3 check: the selected topology meets every constraint."""
    selected = [r for r in rows if r["selected"]]
    if len(selected) != 1:
        raise AssertionError(f"{epoch_row['network']}: no topology selected")
    chosen = selected[0]
    if not chosen["operational_passed"]:
        raise AssertionError("selected topology fails the operational filter")
    if chosen["mlu"] > config.operational.u_max + 1e-9:
        raise AssertionError("selected topology exceeds U_max")
    if (
        config.operational.s_max is not None
        and chosen["max_stretch"] > config.operational.s_max + 1e-9
    ):
        raise AssertionError("selected topology exceeds S_max")
    if not chosen["transferability"] <= config.security.tau_max + 1e-9:
        raise AssertionError("selected topology has T(G') > tau_max")


def run(config: DefenderEpochConfig, run_id: str | None = None) -> str:
    """Run the epoch on every network and write its result files."""
    run_dir = new_run_dir(EXPERIMENT, run_id)
    write_config(run_dir, asdict(config))
    epochs: list[dict] = []
    candidate_rows: list[dict] = []
    transfer_rows: list[dict] = []
    for name in config.networks:
        epoch_row, rows, transfers = run_network(name, config)
        epochs.append(epoch_row)
        candidate_rows += rows
        transfer_rows += transfers
        write_csv(run_dir, "epochs.csv", epochs)
        write_csv(run_dir, "candidates.csv", candidate_rows)
        write_csv(run_dir, "transferability.csv", transfer_rows)
        print(
            f"{name}: {epoch_row['candidates']} candidates, "
            f"{epoch_row['operational_passed']} operational, {epoch_row['safe']} safe, "
            f"selected T = {epoch_row['selected_transferability']}, "
            f"{epoch_row['wall_time']:.0f} s"
        )
        if epoch_row["safe"]:
            check(epoch_row, rows, config)
    return str(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--networks", nargs="+", default=["ANS"])
    parser.add_argument("--run-id")
    parser.add_argument("--no-pairwise", action="store_true")
    args = parser.parse_args()
    config = DefenderEpochConfig(
        networks=tuple(args.networks), pairwise=not args.no_pairwise
    )
    print(run(config, args.run_id))


if __name__ == "__main__":
    main()
