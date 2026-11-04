"""Security filter and attack-distinct diversity (paper §4.8-4.9, Eq. 19-24).

The defender keeps the last h network states and the attack plans an
attacker could have learned on them (Eq. 19-20). For a candidate G' it
computes

    T(G') = max over A_i in the history of τ(A_i, G')            (Eq. 21)

and keeps G' only if T(G') <= τ_max (Eq. 22).

τ is the transferability of Eq. 1, computed by ``damage.relative_damage``:
the stale plan's damage on G' divided by the damage of A*_{G'}, "an attack
plan constructed with current knowledge of topology G'". A*_{G'} is built by
the same mechanism as the stale plan, with the same measurement settings,
from fresh measurements of G' (open issue O3, option e). So a plan on the
unchanged topology it was learned on has τ = 1, and τ_max = 0.5 means "the
stale plan does at most half the damage the attacker would do by measuring
again". τ can exceed 1 (a measured attacker is not optimal, and a stale plan
can beat a fresh one); values are stored unclipped.

When the fresh plan does no damage (D2, rule ``"zero_or_inf"``): τ = 0 and
the candidate is attack-immune if the stale plan does no damage either;
τ = infinity, so the candidate fails, if the stale plan still does damage.

When ``oracle_comparisons`` is on, both oracles' fresh plans are compared
too and saved as extra columns (``oracle_benign_ratio``, ``oracle_ratio``),
so τ against an oracle (the earlier definition) can be recomputed from the
files. It is off by default (D28): the benign-aware oracle simulates one
attack per link, which made it about 97% of the filter's time on bellCanada,
and it does not change which candidates pass.

Which attacker fills the history (D7, D26): the traceroute attacker of
§3.1.2, following §4.8 ("applying the reconnaissance-to-attack procedure
from Section 3 to each network state"), measured with every PoP as a
vantage point and 10% silent routers, with a fresh measurement seed per
network state. Attack budget R_A (D21): 2x the median link capacity of the
original topology, N_A = 10 pairs (D4).

Diversity (§4.9, Eq. 23-24): for the members G_i, G_j of the safe pool S_t,
τ(A_i, G_j) with A_i the plan learned on G_i and A*_j a fresh plan learned on
G_j. Low off-diagonal values mean the pool is attack-distinct; clusters of
high values mean several members expose the same effective plan.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

import networkx as nx

from .candidates import build_topology, link_capacities
from .damage import evaluate_damage, relative_damage
from .model import (
    AttackConfig,
    AttackPlan,
    DamageConfig,
    Pair,
    RelativeDamage,
    RoutingConfig,
)
from .recon import traceroute
from .recon.inferred import Edge, edge_key
from .recon.oracle import BENIGN_MECHANISM, fresh_oracle_plan
from .recon.oracle import MECHANISM as ORACLE_MECHANISM
from .routing import directed, link_shares, route
from .topology import topology_id as compute_topology_id


@dataclass(frozen=True)
class SecurityConfig:
    """Security filter settings (decisions D3, D21, D26; O3 option e)."""

    tau_max: float = 0.5
    history_length: int = 3
    """h: how many past (topology, plan) pairs the filter checks."""
    budget_multiple: float = 2.0
    """R_A as a multiple of the median link capacity (D21)."""
    n_pairs: int = 10
    oracle_knowledge: str = "benign"
    """Which oracle is η's reference (D15); here only labels the attack config."""
    non_response: float = 0.1
    """Silent-router share of the history attacker's traceroute (D26)."""
    max_stale_damage_ratio: float | None = 1.0
    """Stale-damage limit (after O7): every history plan must do at most this
    multiple of the damage it did on its own topology, D(A_i, G') <=
    ratio x D(A_i, G_i) (§4.2 G1: "produce substantially less damage").
    ``None`` turns it off."""
    max_vulnerability_ratio: float | None = 1.0
    """Vulnerability limit (after O7): the fresh attacker's damage on G' may be
    at most this multiple of a reference, the attacker's damage on the
    original topology, so reconfiguring never makes the network more
    vulnerable. ``None`` turns it off."""
    oracle_comparisons: bool = False
    """Also compare every plan against both oracles' fresh plans (extra columns).

    Off by default (D28): it is about 97% of the filter's time and does not
    affect the decision. Turn it on for analysis runs."""

    def __post_init__(self) -> None:
        if self.history_length < 1:
            raise ValueError("history_length must be at least 1")
        if self.tau_max < 0:
            raise ValueError("tau_max must be non-negative")


@dataclass(frozen=True)
class HistoryEntry:
    """One past network state G_i and the plan A_i learned on it (Eq. 19-20)."""

    topology_id: str
    plan: AttackPlan
    own_damage: float | None = None
    """D(A_i, G_i): the plan's damage on the topology it was learned on (the
    τ measure, D1). Needed by the stale-damage limit."""


def history_entry(
    topology: nx.Graph,
    plan: AttackPlan,
    benign: Mapping[Pair, float],
    routing: RoutingConfig,
    damage: DamageConfig,
) -> HistoryEntry:
    """A history entry with the plan's damage on its own topology."""
    report = evaluate_damage(topology, benign, plan, routing, damage)
    return HistoryEntry(
        compute_topology_id(topology), plan, report.measure(damage.tau_measure)
    )


@dataclass(frozen=True)
class SecurityResult:
    transferability: float
    """T(G') (Eq. 21)."""
    passed: bool
    attack_immune: bool
    """Neither the fresh plan nor any stale plan does damage on G' (D2)."""
    comparisons: tuple[RelativeDamage, ...]
    """τ(A_i, G') for each history plan, in history order."""
    damage_ratio: float = math.nan
    """Worst D(A_i, G') / D(A_i, G_i) over the history (the stale-damage limit)."""
    vulnerability: float = math.nan
    """Damage of the fresh plan on G' (what an attacker who re-measures gets)."""
    reasons: tuple[str, ...] = ()
    """Why it failed: any of ``tau``, ``stale_damage``, ``vulnerability``."""


def attack_config(original: nx.Graph, config: SecurityConfig) -> AttackConfig:
    """The attacker's resources: budget relative to the original median capacity."""
    median = statistics.median(c for _, _, c in original.edges(data="capacity"))
    return AttackConfig(
        budget=config.budget_multiple * median,
        n_pairs=config.n_pairs,
        oracle_knowledge=config.oracle_knowledge,
    )


def history_plan(
    topology: nx.Graph,
    attack: AttackConfig,
    routing: RoutingConfig,
    config: SecurityConfig,
    *,
    seed: int,
) -> AttackPlan:
    """The plan the attacker learns on ``topology`` by traceroute (D7, D26)."""
    observation = traceroute.simulate(
        topology,
        routing,
        traceroute.TracerouteConfig(non_response=config.non_response, seed=seed),
    )
    return traceroute.traceroute_attack(
        observation, attack, topology_id=compute_topology_id(topology)
    ).plan


def fresh_plan_like(
    stale: AttackPlan,
    topology: nx.Graph,
    attack: AttackConfig,
    routing: RoutingConfig,
    config: SecurityConfig,
    *,
    seed: int,
) -> AttackPlan:
    """A*: the stale plan's mechanism, run again on fresh measurements of ``topology``.

    Only the traceroute attacker fills the history so far (D7); other
    mechanisms are a Phase 4 experiment axis and are refused until added.
    """
    if stale.mechanism == traceroute.MECHANISM:
        return history_plan(topology, attack, routing, config, seed=seed)
    raise NotImplementedError(
        f"No fresh-reconnaissance rule for mechanism {stale.mechanism!r} yet"
    )


@dataclass(frozen=True)
class FreshPlans:
    """The fresh plans A* on one topology, built once and reused.

    ``by_mechanism`` holds the same-mechanism fresh plan per history
    mechanism (the reference of τ); ``oracles`` the two oracles' plans
    (benign-aware first), empty when oracle comparisons are off.
    """

    by_mechanism: Mapping[str, AttackPlan]
    oracles: tuple[AttackPlan, ...]


def fresh_plans(
    topology: nx.Graph,
    stale_plans: Sequence[AttackPlan],
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    routing: RoutingConfig,
    damage: DamageConfig,
    config: SecurityConfig,
    *,
    seed: int,
) -> FreshPlans:
    by_mechanism: dict[str, AttackPlan] = {}
    for stale in stale_plans:
        if stale.mechanism not in by_mechanism:
            by_mechanism[stale.mechanism] = fresh_plan_like(
                stale, topology, attack, routing, config, seed=seed
            )
    oracles: tuple[AttackPlan, ...] = ()
    if config.oracle_comparisons:
        tid = compute_topology_id(topology)
        oracles = tuple(
            fresh_oracle_plan(
                topology, benign, attack, routing, damage, knowledge=k, topology_id=tid
            )
            for k in ("benign", "routing")
        )
    return FreshPlans(by_mechanism, oracles)


def _compare(
    plan: AttackPlan,
    topology: nx.Graph,
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    routing: RoutingConfig,
    damage: DamageConfig,
    fresh: FreshPlans,
) -> RelativeDamage:
    """τ(plan, topology) against the same-mechanism fresh plan (Eq. 1)."""
    if not math.isclose(plan.budget, attack.budget):
        raise ValueError("History plans must use the filter's attack budget")
    reference = fresh.by_mechanism[plan.mechanism]
    extras = (
        {BENIGN_MECHANISM: fresh.oracles[0], ORACLE_MECHANISM: fresh.oracles[1]}
        if fresh.oracles
        else {}
    )
    return relative_damage(
        plan,
        topology,
        benign,
        replace(attack, budget=plan.budget),
        routing,
        damage,
        fresh_plan=reference,
        # The "other" slot is required; the same-mechanism plan stands in when
        # oracle comparisons are off, so no oracle is built.
        other_fresh_plan=fresh.oracles[0] if fresh.oracles else reference,
        extra_fresh_plans=extras,
    )


def security_check(
    candidate: nx.Graph,
    history: Sequence[HistoryEntry],
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    routing: RoutingConfig,
    damage: DamageConfig,
    config: SecurityConfig,
    *,
    seed: int,
    vulnerability_reference: float | None = None,
) -> SecurityResult:
    """T(G') over the last h history entries, and whether G' passes (Eq. 21-22).

    ``seed`` is the measurement seed of the fresh reconnaissance of G'. Besides
    T(G') <= τ_max, a candidate must meet the stale-damage limit and, when
    set, the vulnerability limit against ``vulnerability_reference``.
    """
    recent = list(history)[-config.history_length :]
    if not recent:
        raise ValueError("The security filter needs at least one history entry")
    fresh = fresh_plans(
        candidate,
        [e.plan for e in recent],
        benign,
        attack,
        routing,
        damage,
        config,
        seed=seed,
    )
    comparisons = tuple(
        _compare(entry.plan, candidate, benign, attack, routing, damage, fresh)
        for entry in recent
    )
    worst = max(c.ratio for c in comparisons)
    tolerance = damage.zero_tolerance

    def grown(now: float, before: float | None) -> float:
        if before is None:
            return math.nan
        if before > tolerance:
            return now / before
        return math.inf if now > tolerance else 0.0

    damage_ratio = max(
        (
            grown(c.numerator, e.own_damage)
            for c, e in zip(comparisons, recent, strict=True)
        ),
        default=math.nan,
    )
    vulnerability = max(c.denominator for c in comparisons)
    reasons = []
    if not worst <= config.tau_max:
        reasons.append("tau")
    if config.max_stale_damage_ratio is not None:
        if any(e.own_damage is None for e in recent):
            raise ValueError(
                "The stale-damage limit needs history entries with own_damage"
            )
        if not damage_ratio <= config.max_stale_damage_ratio:
            reasons.append("stale_damage")
    if config.max_vulnerability_ratio is not None:
        if vulnerability_reference is None:
            raise ValueError("The vulnerability limit needs a reference damage")
        if (
            not grown(vulnerability, vulnerability_reference)
            <= config.max_vulnerability_ratio
        ):
            reasons.append("vulnerability")
    return SecurityResult(
        transferability=worst,
        passed=not reasons,
        attack_immune=all(c.attack_immune for c in comparisons),
        comparisons=comparisons,
        damage_ratio=damage_ratio,
        vulnerability=vulnerability,
        reasons=tuple(reasons),
    )


def pairwise_transferability(
    members: Sequence[tuple[nx.Graph, AttackPlan]],
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    routing: RoutingConfig,
    damage: DamageConfig,
    config: SecurityConfig,
    *,
    seed: int,
) -> list[tuple[int, int, RelativeDamage]]:
    """τ(A_i, G_j) for every ordered pair of pool members, i = j included (Eq. 24).

    ``members`` are (G_i, A_i). A*_j is a fresh plan of A_i's mechanism on
    G_j, measured with ``seed``. Returns (i, j, comparison) triples.
    """
    plans = [plan for _, plan in members]
    fresh = [
        fresh_plans(g, plans, benign, attack, routing, damage, config, seed=seed)
        for g, _ in members
    ]
    return [
        (i, j, _compare(plan, graph_j, benign, attack, routing, damage, fresh[j]))
        for i, (_, plan) in enumerate(members)
        for j, (graph_j, _) in enumerate(members)
    ]


def attack_guidance(
    current: nx.Graph,
    original: nx.Graph,
    links: Sequence[Edge],
    plans: Sequence[AttackPlan],
    routing: RoutingConfig,
) -> dict[Edge, float]:
    """Security guidance g_e for the MILP's ``security_guided`` objective (O5).

    For each link e the MILP may change, the share of the history plans'
    attack traffic that changing e alone (removing it if present, adding it
    if not) would move off each plan's target link, averaged over plans.
    Attack traffic is routed with the network's routing, so an added
    shortcut counts when it pulls the attack pairs' paths away from the
    target. A cheap, additive stand-in for T(G') (Eq. 21, 25): it ignores
    that the attacker re-targets, which the security filter then checks.
    """
    plans = [p for p in plans if p.target is not None]
    if not plans:
        return {}
    current_links = frozenset(edge_key(u, v) for u, v in current.edges)
    capacities = link_capacities(original, current_links | set(links))

    def on_target(graph: nx.Graph) -> list[float]:
        directed_graph = directed(graph)
        loads = []
        for plan in plans:
            demands = plan.demands()
            shares = link_shares(route(directed_graph, demands, routing))
            loads.append(
                sum(demands[p] * s for p, s in shares.get(plan.target, {}).items())
            )
        return loads

    before = on_target(current)
    guidance = {}
    for e in links:
        after = on_target(build_topology(original, current_links ^ {e}, capacities))
        moved = [
            (b - a) / b if b > 0 else 0.0 for b, a in zip(before, after, strict=True)
        ]
        guidance[e] = max(0.0, sum(moved) / len(moved))
    return guidance
