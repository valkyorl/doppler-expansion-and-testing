"""Reconnaissance evaluation: RQ1-RQ3 of paper §3.7.

For every network, five attackers build attack plans and are compared:

- oracle_benign (decision D15): true topology, routing, and benign
  traffic; the reference for η by default (``oracle_knowledge``);
- oracle (§3.2): the paper's oracle, true topology and routing only;
- random (§3.2): no knowledge, ``random_seeds`` plans;
- traceroute (§3.1.2): simulated probes, swept over the non-response rate
  and the share of PoPs used as vantage points (measurement coverage);
- rtt_ricci (§3.1.1): simulated minimum RTTs, swept over ε (as a quantile,
  D13) and coverage.

For each plan it records:

- RQ1, topology recovery (precision/recall/F1), only where ground truth is
  independent (``recon/metrics.py``);
- RQ2, P@k and path-level recovery against the oracle's critical links;
- RQ3, damage and η against the oracle at every budget in the sweep, plus
  the budget needed to disrupt benign traffic (§3.4, D14). η against the
  other oracle is saved too (``other_ratio``), so D15 can be revisited
  without re-running.

Both oracles are rebuilt at every budget in the sweep (their plans are the
fresh plans A*), so each oracle's own η is 1 by construction. Every other
plan keeps its pairs and has its budget rescaled.

The regional network is evaluated too: its stored Ricci reconstruction is
ranked by curvature and tested against its "ground truth" graph. That graph
is not independently validated (audit #8), so RQ1 is refused there and every
row carries ``ground_truth_independent = False``.

Run from the repository root::

    python -m doppler2026.experiments.recon_eval                # default networks
    python -m doppler2026.experiments.recon_eval --networks ANS sprint --run-id test

Output (PLAN §10): ``data/results/doppler2026/recon_eval/<run_id>/`` with
``config.json``, ``networks.csv`` (one row per network, for Table 1),
``recon.csv`` (RQ1, RQ2, budget to disrupt; one metric per
row) and ``transferability.csv`` (RQ3; one plan and budget per row, with η in
``ratio``).
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, replace

import networkx as nx
import numpy as np

from ..attack_plans import rescale
from ..damage import budget_to_disrupt, relative_damage
from ..model import AttackConfig, AttackPlan, DamageConfig, RoutingConfig
from ..recon import metrics, rtt_ricci, traceroute
from ..recon.inferred import ReconResult
from ..recon.oracle import BENIGN_MECHANISM, MECHANISM, fresh_oracle_plan
from ..recon.random_plan import random_plan
from ..results import new_run_dir, write_config, write_csv
from ..topology import DEFAULT_CAPACITY, load_topology, topology_id
from ..traffic import benign_demand

EXPERIMENT = "recon_eval"
# Comcast is left out by default: its origin is unknown and, at 149 nodes, it
# is much slower (PLAN.md §9). Run it explicitly with --networks Comcast.
NETWORKS = ("ANS", "CRL", "bellCanada", "sprint", "surfNet")


@dataclass(frozen=True)
class ReconEvalConfig:
    """All settings of one run; saved in ``config.json``."""

    networks: tuple[str, ...] = NETWORKS
    include_regional: bool = True
    benign_utilization: float = 0.5
    benign_seed: int = 1
    budget_multiples: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0)
    """R_A as multiples of the network's median link capacity (D4)."""
    max_budget_multiple: float = 16.0
    """Search limit for the budget to disrupt."""
    n_pairs: int = 10
    random_seeds: int = 20
    measurement_seeds: tuple[int, ...] = (0, 1, 2)
    vantage_fractions: tuple[float, ...] = (1.0, 0.5, 0.25)
    non_response: tuple[float, ...] = (0.0, 0.1, 0.3)
    epsilon_quantiles: tuple[float, ...] = (0.05, 0.1, 0.2, 0.3, 0.5)
    rtt: rtt_ricci.RttConfig = field(default_factory=rtt_ricci.RttConfig)
    k_values: tuple[int, ...] = (1, 3, 5, 10)
    oracle_knowledge: str = "benign"
    """Which oracle is the reference for η (decision D15, flagged for review)."""
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    damage: DamageConfig = field(default_factory=DamageConfig)


@dataclass(frozen=True)
class Network:
    """One network under test, with its benign traffic and ground truth."""

    name: str
    topology: nx.Graph
    truth: metrics.GroundTruth
    benign: dict
    reference_capacity: float


@dataclass(frozen=True)
class Attempt:
    """One attacker run: the plan (at the reference budget) and its settings."""

    mechanism: str
    plan: AttackPlan
    settings: dict
    recon: ReconResult | None = None


def vantage_points(
    nodes: list[str], fraction: float, seed: int
) -> tuple[str, ...] | None:
    """A seeded random share of PoPs as vantage points; ``None`` (all) at 1.0."""
    if fraction >= 1.0:
        return None
    count = max(2, round(fraction * len(nodes)))
    rng = np.random.default_rng(seed)
    # str(): NumPy returns its own string type, which would leak into results.
    return tuple(
        sorted(str(n) for n in rng.choice(sorted(nodes), size=count, replace=False))
    )


def load_networks(config: ReconEvalConfig) -> Iterator[Network]:
    for name in config.networks:
        topology = load_topology(name)
        yield _network(
            name, topology, metrics.GroundTruth(topology, "simulation", True), config
        )
    if config.include_regional:
        topology = rtt_ricci.load_regional_ground_truth()
        for _, _, attrs in topology.edges(data=True):
            attrs.setdefault("capacity", DEFAULT_CAPACITY)
        truth = metrics.GroundTruth(
            topology, "regional (provenance unknown, audit #8)", False
        )
        yield _network("regional", topology, truth, config)


def _network(
    name: str, topology: nx.Graph, truth: metrics.GroundTruth, config: ReconEvalConfig
) -> Network:
    benign = benign_demand(
        topology, config.benign_utilization, config.routing, seed=config.benign_seed
    )
    capacity = statistics.median(c for _, _, c in topology.edges(data="capacity"))
    return Network(name, topology, truth, benign, float(capacity))


def attempts(
    network: Network, attack: AttackConfig, config: ReconEvalConfig
) -> Iterator[Attempt]:
    """Every attacker run for one network, at the reference budget ``attack.budget``."""
    topology, routing = network.topology, config.routing
    tid = topology_id(topology)
    for mechanism, knowledge in ((BENIGN_MECHANISM, "benign"), (MECHANISM, "routing")):
        plan = fresh_oracle_plan(
            topology,
            network.benign,
            attack,
            routing,
            config.damage,
            knowledge=knowledge,
            topology_id=tid,
        )
        yield Attempt(mechanism, plan, {})
    for seed in range(config.random_seeds):
        yield Attempt(
            "random",
            random_plan(topology, attack, seed, topology_id=tid),
            {"seed": seed},
        )

    if network.name == "regional":
        # Only the stored reconstruction exists: no measurements to simulate
        # (interpretation I13).
        recon = rtt_ricci.ricci_attack(
            rtt_ricci.load_regional_reconstruction(),
            attack,
            topology_id=tid,
            details={"source": "regional reconstruction"},
        )
        yield Attempt(
            "rtt_ricci", recon.plan, {"source": "regional reconstruction"}, recon
        )
        return

    nodes = sorted(topology.nodes)
    for seed in config.measurement_seeds:
        for fraction in config.vantage_fractions:
            points = vantage_points(nodes, fraction, seed)
            base = {"measurement_seed": seed, "vantage_fraction": fraction}
            for rate in config.non_response:
                observation = traceroute.simulate(
                    topology,
                    routing,
                    traceroute.TracerouteConfig(
                        vantage_points=points, non_response=rate, seed=seed
                    ),
                )
                recon = traceroute.traceroute_attack(
                    observation, attack, topology_id=tid
                )
                yield Attempt(
                    "traceroute", recon.plan, {**base, "non_response": rate}, recon
                )
            measurements = rtt_ricci.simulate(
                topology, routing, replace(config.rtt, vantage_points=points, seed=seed)
            )
            for quantile in config.epsilon_quantiles:
                recon = rtt_ricci.rtt_attack(
                    measurements, attack, quantile, topology_id=tid
                )
                yield Attempt(
                    "rtt_ricci",
                    recon.plan,
                    {
                        **base,
                        "epsilon_quantile": quantile,
                        "epsilon_ms": recon.details["epsilon_ms"],
                    },
                    recon,
                )


def evaluate_network(
    network: Network, config: ReconEvalConfig
) -> tuple[list[dict], list[dict]]:
    """All recon rows and transferability rows for one network."""
    routing, damage = config.routing, config.damage
    topology = network.topology
    capacity = network.reference_capacity
    attack = AttackConfig(
        budget=capacity,
        n_pairs=config.n_pairs,
        oracle_knowledge=config.oracle_knowledge,
    )
    critical = metrics.critical_links(topology, attack, routing, max(config.k_values))
    tid = topology_id(topology)
    # Both oracles' fresh plans at every budget: {mechanism: {multiple: plan}}.
    fresh = {
        mechanism: {
            m: fresh_oracle_plan(
                topology,
                network.benign,
                replace(attack, budget=m * capacity),
                routing,
                damage,
                knowledge=knowledge,
                topology_id=tid,
            )
            for m in config.budget_multiples
        }
        for mechanism, knowledge in (
            (BENIGN_MECHANISM, "benign"),
            (MECHANISM, "routing"),
        )
    }
    reference = BENIGN_MECHANISM if config.oracle_knowledge == "benign" else MECHANISM
    (other,) = set(fresh) - {reference}
    common = {
        "network": network.name,
        "ground_truth_source": network.truth.source,
        "ground_truth_independent": network.truth.independent,
    }

    recon_rows: list[dict] = []
    transfer_rows: list[dict] = []
    for attempt in attempts(network, attack, config):
        label = {**common, "mechanism": attempt.mechanism, **attempt.settings}

        def metric(
            name: str, value: float, k: int | None = None, note: str = "", label=label
        ) -> None:
            recon_rows.append(
                {**label, "metric": name, "k": k, "value": value, "note": note}
            )

        if attempt.recon is not None:
            recon = attempt.recon
            for key in ("complete", "partial", "non_responsive"):
                if key in recon.details:
                    metric(f"paths_{key}", float(recon.details[key]))
            metric("inferred_nodes", recon.inferred.number_of_nodes())
            try:
                for name, value in metrics.topology_recovery(
                    recon.inferred, network.truth
                ).items():
                    metric(name, value)
            except metrics.GroundTruthNotIndependentError as refused:
                metric("precision", float("nan"), note=str(refused))
            for k in config.k_values:
                metric("p_at_k", metrics.precision_at_k(recon.ranking, critical, k), k)
                metric(
                    "path_at_k",
                    metrics.path_level_recovery(
                        recon.ranking, critical, k, topology, routing
                    ),
                    k,
                )
        target_hit = (
            attempt.plan.target is not None
            and tuple(sorted(attempt.plan.target)) in critical[:1]
        )
        metric("targets_top_critical_link", float(target_hit))
        disrupt = budget_to_disrupt(
            topology,
            network.benign,
            attempt.plan,
            routing,
            damage,
            max_budget=config.max_budget_multiple * capacity,
        )
        metric(
            "budget_to_disrupt",
            disrupt / capacity,
            note="multiple of median link capacity",
        )

        for multiple in config.budget_multiples:
            if attempt.mechanism in fresh:
                # An oracle re-plans at every budget.
                plan = fresh[attempt.mechanism][multiple]
            else:
                plan = rescale(attempt.plan, multiple * capacity)
            result = relative_damage(
                plan,
                topology,
                network.benign,
                replace(attack, budget=plan.budget),
                routing,
                damage,
                fresh_plan=fresh[reference][multiple],
                other_fresh_plan=fresh[other][multiple],
            )
            transfer_rows.append(
                {
                    **label,
                    "budget_multiple": multiple,
                    "plan_target": plan.target,
                    "plan_pairs": len(plan.flows),
                    **result.as_row(),
                }
            )
    return recon_rows, transfer_rows


def network_row(network: Network, config: ReconEvalConfig) -> dict:
    """One row of ``networks.csv``: what paper Table 1 reports for a network.

    Vantage-point counts are the simulated coverages used, not real
    measurement infrastructure. No network has optical data (PLAN §9).
    """
    nodes = network.topology.number_of_nodes()
    simulated = network.name != "regional"
    coverages = sorted(
        {max(2, round(f * nodes)) if f < 1 else nodes for f in config.vantage_fractions}
    )
    return {
        "network": network.name,
        "nodes": nodes,
        "links": network.topology.number_of_edges(),
        "measurements": "simulated" if simulated else "stored reconstruction only",
        "rtt_vantage_points": "/".join(map(str, coverages)) if simulated else "unknown",
        "traceroute_vantage_points": "/".join(map(str, coverages))
        if simulated
        else "none",
        "ground_truth_source": network.truth.source,
        "ground_truth_independent": network.truth.independent,
        "optical_data": "none",
        "median_link_capacity": network.reference_capacity,
    }


def run(config: ReconEvalConfig, run_id: str | None = None) -> str:
    """Run the experiment and write its result files; returns the run folder."""
    run_dir = new_run_dir(EXPERIMENT, run_id)
    write_config(run_dir, asdict(config))
    recon_rows: list[dict] = []
    transfer_rows: list[dict] = []
    inventory: list[dict] = []
    for network in load_networks(config):
        start = time.perf_counter()
        rows, transfers = evaluate_network(network, config)
        recon_rows += rows
        transfer_rows += transfers
        inventory.append(network_row(network, config))
        write_csv(run_dir, "networks.csv", inventory)
        print(
            f"{network.name}: {len(transfers)} evaluations in {time.perf_counter() - start:.0f} s"
        )
        # Rewritten after every network, so a long run leaves usable partial results.
        write_csv(run_dir, "recon.csv", recon_rows)
        write_csv(run_dir, "transferability.csv", transfer_rows)
    return str(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--networks", nargs="+", default=list(NETWORKS))
    parser.add_argument("--no-regional", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    config = ReconEvalConfig(
        networks=tuple(args.networks), include_regional=not args.no_regional
    )
    print(run(config, args.run_id))


if __name__ == "__main__":
    main()
