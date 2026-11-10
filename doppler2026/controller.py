"""The Doppler control loop over many epochs (paper §4.3, §4.13-4.14, Fig. 1).

One epoch t, with the network in topology G_t (PLAN §2):

1. Attacker: learns plan A_t on G_t by traceroute (D7, D26; measurement
   seed t). The attack that runs during epoch t uses the plan learned L
   epochs earlier, A_{t-L} (recon lag, D10; default L = 1), so the logged
   stale-plan damage is D(A_{t-L}, G_t) and its transferability
   τ(A_{t-L}, G_t) = D(A_{t-L}, G_t) / D(A_t, G_t) (Eq. 1: A_t is the plan
   built "with current knowledge of" G_t). Nothing is logged while t < L.
2. History: the last h states including the current one, with the plans
   learned on them (D30). The defender's model of the attacker is the same
   attacker (I18).
3. Defender (``mode = "doppler"``): feasible links, candidate pool around G_t,
   operational filter, security filter T(G') <= τ_max, and random selection
   from the acceptable subset (§4.4-4.11; ``defender_step``). Without a safe
   topology the network stays on G_t (D29).
4. Transition to G_{t+1}: E_add / E_remove, ordered by D31, each
   intermediate state measured (``transition.py``).

Baselines for the comparisons of §4.2 G1 and PLAN §7 (same loop, same
attacker):

- ``"static"``: the topology never changes.
- ``"churn"``: structural churn, Eq. 18, applied as the selection rule (O6):
  the pool is generated as for Doppler but without security guidance, only
  the operational filter runs, and the candidate with the least overlap
  |E_t ∩ E'| is chosen (ties at random). Optimizing Eq. 18 directly (the
  ``min_overlap`` MILP objective) gave only large rewirings that all failed
  the stretch limit.

Seeds: one run seed drives the selection's random generator; the MILP
weights of epoch t use ``candidates.seed + t``; the attacker's measurement
seed is t, and the fresh reconnaissance of a candidate (for τ) uses t + 1.
Running the same config twice gives the same topologies, plans, and
results (timings aside).

Benign demand is the defender's estimate D_t, the same matrix every epoch
(D27).
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

import networkx as nx
import numpy as np

from . import candidates as cand
from .damage import relative_damage
from .feasibility import FeasibilityConfig, feasible_links
from .filters import OperationalConfig, operational_check, reference_lengths
from .model import AttackConfig, AttackPlan, DamageConfig, Pair, RoutingConfig
from .recon.inferred import Edge, edge_key
from .security import (
    HistoryEntry,
    SecurityConfig,
    attack_config,
    attack_guidance,
    history_entry,
    history_plan,
    pairwise_transferability,
    security_check,
)
from .selection import SelectionConfig, select
from .topology import REPO_ROOT, load_topology, topology_id
from .traffic import benign_demand
from .transition import evaluate_transition

MODES = ("doppler", "static", "churn")


@dataclass(frozen=True)
class DefenderConfig:
    """Everything the defender's epoch uses (Phase 3 modules)."""

    feasibility: FeasibilityConfig = field(default_factory=FeasibilityConfig)
    candidates: cand.CandidateConfig = field(default_factory=cand.CandidateConfig)
    operational: OperationalConfig = field(default_factory=OperationalConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    damage: DamageConfig = field(default_factory=DamageConfig)


@dataclass(frozen=True)
class ControllerConfig:
    """One multi-epoch run on one network; saved in ``config.json``."""

    network: str = "ANS"
    topology_dir: str | None = None
    """Folder of ``<network>.gml``, relative to the repository root; ``None``
    is the Topology Zoo folder ``data/graphs/gml``. Synthetic networks live
    in ``doppler2026/topologies``."""
    epochs: int = 10
    recon_lag: int = 1
    """L in epochs (D10)."""
    mode: str = "doppler"
    seed: int = 0
    benign_utilization: float = 0.5
    benign_seed: int = 1
    pairwise: bool = False
    """Also compute the safe pool's pairwise τ every epoch (Eq. 24; slow)."""
    defender: DefenderConfig = field(default_factory=DefenderConfig)

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if self.epochs < 1 or self.recon_lag < 0:
            raise ValueError("epochs must be >= 1 and recon_lag >= 0")


@dataclass
class StepResult:
    """What one defender step produced."""

    row: dict
    """Epoch-level fields (pool sizes, selection, solver time)."""
    candidates: list[dict]
    transferability: list[dict]
    selected: cand.Candidate | None
    capacities: Mapping[Edge, float]


def secondary_score(objective: str, operational, candidate: cand.Candidate) -> float:
    if objective == "mlu":
        return operational.mlu
    if objective == "stretch":
        return operational.max_stretch
    if objective == "overlap":  # |E_t ∩ E'| (Eq. 18)
        return float(len(candidate.links) - len(candidate.added))
    return float(len(candidate.added) + len(candidate.dropped))


def defender_step(
    name: str,
    original: nx.Graph,
    current: nx.Graph,
    history: Sequence[HistoryEntry],
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    config: DefenderConfig,
    *,
    epoch: int,
    rng: np.random.Generator,
    security_filter: bool = True,
    pairwise: bool = False,
    vulnerability_reference: float | None = None,
) -> StepResult:
    """Steps 2-6 of PLAN §2 for one epoch: pool, filters, selection.

    With ``security_filter=False`` (the churn baseline) every operational
    candidate counts as safe and no τ is computed.
    """
    routing, damage = config.routing, config.damage
    feasible = feasible_links(original, config.feasibility)
    pool_config = replace(config.candidates, seed=config.candidates.seed + epoch)
    pool = cand.generate(
        current,
        original,
        feasible,
        benign,
        pool_config,
        targets=[e.plan.target for e in history if e.plan.target],
        guidance=lambda links: attack_guidance(
            current, original, links, [e.plan for e in history], routing
        ),
    )
    capacities = cand.link_capacities(original, pool.variable_links)
    reference = reference_lengths(
        original, benign, routing, config.operational.stretch_metric
    )

    rows: list[dict] = []
    transfer_rows: list[dict] = []
    safe: dict[str, tuple] = {}
    by_id = {c.topology_id: c for c in pool.candidates}
    for candidate in pool.candidates:
        graph = cand.build_topology(original, candidate.links, capacities)
        operational = operational_check(
            graph, benign, reference, routing, config.operational
        )
        row = {
            "network": name,
            "epoch": epoch,
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
        passed = operational.passed
        if passed and security_filter:
            security = security_check(
                graph,
                history,
                benign,
                attack,
                routing,
                damage,
                config.security,
                seed=epoch + 1,
                vulnerability_reference=vulnerability_reference,
            )
            row.update(
                transferability=security.transferability,
                stale_damage_ratio=security.damage_ratio,
                vulnerability=security.vulnerability,
                security_reasons=";".join(security.reasons),
                security_passed=security.passed,
                attack_immune=security.attack_immune,
            )
            passed = security.passed
            for entry, comparison in zip(
                list(history)[-config.security.history_length :],
                security.comparisons,
                strict=True,
            ):
                transfer_rows.append(
                    {
                        "network": name,
                        "epoch": epoch,
                        "role": "security",
                        "plan_learned_on": entry.topology_id,
                        **comparison.as_row(),
                    }
                )
        if passed:
            row["safe"] = True
            safe[candidate.topology_id] = (
                graph,
                secondary_score(config.selection.objective, operational, candidate),
            )
        row["secondary_score"] = safe.get(candidate.topology_id, (None, None))[1]
        rows.append(row)

    chosen = None
    acceptable: tuple[str, ...] = ()
    if safe:
        choice = select({t: s for t, (_, s) in safe.items()}, config.selection, rng)
        chosen, acceptable = choice.chosen, choice.acceptable
        for row in rows:
            row["acceptable"] = row["topology_id"] in acceptable
            row["selected"] = row["topology_id"] == chosen

    if pairwise and len(safe) > 1:
        ids = sorted(safe)
        members = [
            (
                safe[t][0],
                history_plan(safe[t][0], attack, routing, config.security, seed=epoch),
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
            seed=epoch + 1,
        ):
            transfer_rows.append(
                {
                    "network": name,
                    "epoch": epoch,
                    "role": "pairwise",
                    "plan_learned_on": ids[i],
                    "member_i": i,
                    "member_j": j,
                    **comparison.as_row(),
                }
            )

    selected_row = next((r for r in rows if r["selected"]), None)
    row = {
        "feasible_links": len(feasible),
        "variable_links": len(pool.variable_links),
        "pool_status": pool.status,
        "solves": pool.solves,
        "solver_time": pool.wall_time,
        "candidates": len(pool.candidates),
        "operational_passed": sum(r["operational_passed"] for r in rows),
        "safe": len(safe),
        "attack_immune": sum(r["attack_immune"] for r in rows),
        "acceptable": len(acceptable),
        "selected_topology_id": chosen,
        "selected_transferability": (
            selected_row["transferability"] if selected_row else None
        ),
        "selected_mlu": selected_row["mlu"] if selected_row else None,
        "selected_max_stretch": selected_row["max_stretch"] if selected_row else None,
        "selected_added": selected_row["added_links"] if selected_row else None,
        "selected_dropped": selected_row["dropped_links"] if selected_row else None,
    }
    return StepResult(
        row=row,
        candidates=rows,
        transferability=transfer_rows,
        selected=by_id.get(chosen) if chosen else None,
        capacities=capacities,
    )


@dataclass
class RunResult:
    epochs: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    transferability: list[dict] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)


def _links(graph: nx.Graph) -> frozenset[Edge]:
    return frozenset(edge_key(u, v) for u, v in graph.edges)


def run(config: ControllerConfig, *, progress=None) -> RunResult:
    """Run ``config.epochs`` epochs from the original topology (see the module docstring)."""
    defender = config.defender
    routing, damage = defender.routing, defender.damage
    if config.topology_dir is None:
        original = load_topology(config.network)
    else:
        original = load_topology(
            config.network, gml_dir=REPO_ROOT / config.topology_dir
        )
    benign = benign_demand(
        original, config.benign_utilization, routing, seed=config.benign_seed
    )
    # Steady-state cost of the topology in force each epoch (§4.7): MLU and
    # stretch against G_0, as the operational filter measures them.
    reference = reference_lengths(
        original, benign, routing, defender.operational.stretch_metric
    )
    attack = attack_config(original, defender.security)
    txp = cand.transponders(original, defender.candidates)
    rng = np.random.default_rng(config.seed)
    if config.mode == "churn":
        # O6: Eq. 18 as the selection rule over the operationally feasible
        # pool, with a pool generated without security guidance.
        objective = defender.candidates.objective
        defender = replace(
            defender,
            candidates=replace(
                defender.candidates,
                objective="random_weights"
                if objective == "security_guided"
                else objective,
            ),
            selection=replace(defender.selection, objective="overlap", tolerance=0.0),
        )

    result = RunResult()
    current = original
    plans: list[AttackPlan] = []
    history: list[HistoryEntry] = []
    for epoch in range(config.epochs):
        started = time.perf_counter()
        current_id = topology_id(current)
        # 1. The attacker learns a plan on the running topology.
        plan = history_plan(current, attack, routing, defender.security, seed=epoch)
        plans.append(plan)
        history.append(history_entry(current, plan, benign, routing, damage))
        if epoch == 0:
            # The attacker's damage on the original topology: the reference
            # of the optional vulnerability limit.
            reference_damage = history[-1].own_damage
        history = history[-defender.security.history_length :]

        row = {
            "network": config.network,
            "mode": config.mode,
            "epoch": epoch,
            "current_topology_id": current_id,
            "links": current.number_of_edges(),
            "plan_target": plan.target,
        }
        steady = operational_check(
            current, benign, reference, routing, defender.operational
        )
        row.update(
            current_mlu=steady.mlu,
            current_max_stretch=steady.max_stretch,
            current_mean_stretch=steady.mean_stretch,
        )
        # The attack running now uses the plan learned L epochs ago (D10).
        if epoch >= config.recon_lag:
            stale = plans[epoch - config.recon_lag]
            hit = relative_damage(
                stale,
                current,
                benign,
                attack,
                routing,
                damage,
                fresh_plan=plan,
                other_fresh_plan=plan,
            )
            row.update(
                attack_plan_learned_at=epoch - config.recon_lag,
                attack_target=stale.target,
                stale_benign_loss=hit.plan_damage.benign_loss,
                fresh_benign_loss=hit.fresh_damage.benign_loss,
                stale_transferability=hit.ratio,
                attack_immune=hit.attack_immune,
                benign_loss_no_attack=1
                - hit.plan_damage.benign_delivered_without_attack
                / hit.plan_damage.benign_offered,
            )
            result.transferability.append(
                {
                    "network": config.network,
                    "mode": config.mode,
                    "epoch": epoch,
                    "role": "stale_attack",
                    "plan_learned_on": stale.topology_id,
                    "plan_learned_at": epoch - config.recon_lag,
                    **hit.as_row(),
                }
            )

        # 2-6. The defender chooses the next topology.
        target = current
        step = None
        if config.mode != "static":
            step = defender_step(
                config.network,
                original,
                current,
                history,
                benign,
                attack,
                defender,
                epoch=epoch,
                rng=rng,
                security_filter=config.mode == "doppler",
                pairwise=config.pairwise,
                vulnerability_reference=reference_damage,
            )
            row.update(step.row)
            for r in step.candidates:
                r["mode"] = config.mode
            result.candidates += step.candidates
            result.transferability += [
                {**r, "mode": config.mode} for r in step.transferability
            ]
            if step.selected is not None:
                target = cand.build_topology(
                    original, step.selected.links, step.capacities
                )
        row["no_safe_topology"] = config.mode != "static" and target is current

        # 7. The transition to G_{t+1} (D31).
        capacities = cand.link_capacities(original, _links(current) | _links(target))
        transition = evaluate_transition(
            original,
            _links(current),
            _links(target),
            capacities,
            txp,
            benign,
            routing,
            damage,
        )
        worst = max(transition.states, key=lambda s: s.benign_loss)
        row.update(
            transition=transition.kind,
            transition_added=len(transition.added),
            transition_removed=len(transition.removed),
            transition_worst_benign_loss=worst.benign_loss,
            transition_worst_mlu=max(s.mlu for s in transition.states),
            transition_always_connected=all(s.connected for s in transition.states),
            wall_time=time.perf_counter() - started,
        )
        result.transitions.append(
            {
                "network": config.network,
                "mode": config.mode,
                "epoch": epoch,
                "from": current_id,
                "to": topology_id(target),
                **transition.as_record(),
            }
        )
        result.epochs.append(row)
        if progress:
            progress(row)
        current = target
    return result
