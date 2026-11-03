"""Damage D(A, G), transferability τ (Eq. 1), and effectiveness η (Eq. 10).

Damage (paper §2.4, §3.4). To measure what plan A does to topology G:

1. Route benign demand plus the plan's attack traffic together, using the
   network's routing method (interpretation I4). With ECMP the routes do not
   react to traffic; with MCF they do, so the attack-free baseline is routed
   separately.
2. Push all flows through the network hop by hop. An overloaded link divides
   its capacity between the flows crossing it according to
   ``DamageConfig.sharing``: by default every flow loses the same fraction
   (proportional, like tail drop; decision D11, pending confirmation).
3. Read off the four measures in ``model.DamageReport``.

Benign and attack traffic between the same two PoPs are tracked as separate
flows, so benign loss is never confused with attack loss.

Relative damage. ``relative_damage`` divides a plan's damage by the damage
of a fresh oracle plan built on the topology being evaluated, with the same
budget. This one ratio is the paper's τ (Eq. 1) for a stale plan and η
(Eq. 10) for a plan measured on the same topology. The oracle is the one
chosen by decision D15 (by default the one that knows benign traffic); the
ratio against the other oracle is saved too.

Budget to disrupt. ``budget_to_disrupt`` is the fifth §3.4 measure: the
smallest aggregate budget R_A at which a plan's pairs, with the equal split
of Eq. 8, start to cost benign traffic (decision D14).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from itertools import pairwise

import networkx as nx

from .attack_plans import rescale
from .model import (
    ORACLE_KNOWLEDGE,
    AttackConfig,
    AttackPlan,
    Comparison,
    DamageConfig,
    DamageReport,
    Pair,
    RelativeDamage,
    RoutingConfig,
)
from .recon.oracle import fresh_oracle_plan
from .routing import deliver, directed, route
from .topology import topology_id as compute_topology_id


def evaluate_damage(
    topology: nx.Graph,
    benign: Mapping[Pair, float],
    plan: AttackPlan,
    routing: RoutingConfig,
    config: DamageConfig,
) -> DamageReport:
    """Damage of ``plan`` on ``topology`` with ``benign`` traffic present."""
    graph = directed(topology)
    benign = {pair: amount for pair, amount in benign.items() if amount > 0}
    attack = plan.demands()
    combined = dict(benign)
    for pair, amount in attack.items():
        combined[pair] = combined.get(pair, 0.0) + amount

    # Routes with the attack running, and the attack-free baseline.
    routes = route(graph, combined, routing)
    baseline_routes = route(graph, benign, routing) if benign else {}

    flows: dict[object, tuple[Pair, float]] = {
        ("benign", pair): (pair, amount) for pair, amount in benign.items()
    }
    flows.update({("attack", pair): (pair, amount) for pair, amount in attack.items()})
    with_attack = deliver(graph, flows, routes, config.sharing)
    without_attack = deliver(
        graph,
        {("benign", p): (p, a) for p, a in benign.items()},
        baseline_routes,
        config.sharing,
    )

    utilization = {
        edge: load / graph.edges[edge]["capacity"]
        for edge, load in with_attack.expected_loads.items()
    }
    congested = {
        edge for edge, util in utilization.items() if util > config.congestion_threshold
    }

    # Flow labels are ("benign" | "attack", pair).
    benign_offered = sum(benign.values())
    delivered_with = sum(
        v for label, v in with_attack.delivered.items() if label[0] == "benign"
    )
    delivered_without = sum(without_attack.delivered.values())
    attack_delivered = sum(
        v for label, v in with_attack.delivered.items() if label[0] == "attack"
    )

    # Benign traffic routed over at least one congested link (I2): weight each
    # route by its share of the pair's traffic.
    on_congested = 0.0
    for pair, amount in benign.items():
        for path, probability in routes.get(pair, []):
            if any(edge in congested for edge in pairwise(path)):
                on_congested += amount * probability

    return DamageReport(
        max_utilization=max(utilization.values(), default=0.0),
        overloaded_capacity=sum(
            graph.edges[edge]["capacity"]
            for edge, util in utilization.items()
            if util > config.safe_threshold
        ),
        benign_on_congested=on_congested / benign_offered if benign_offered else 0.0,
        benign_loss=(
            (delivered_without - delivered_with) / benign_offered
            if benign_offered
            else 0.0
        ),
        benign_offered=benign_offered,
        benign_delivered_without_attack=delivered_without,
        benign_delivered_with_attack=delivered_with,
        attack_offered=sum(attack.values()),
        attack_delivered=attack_delivered,
    )


def relative_damage(
    plan: AttackPlan,
    topology: nx.Graph,
    benign: Mapping[Pair, float],
    attack: AttackConfig,
    routing: RoutingConfig,
    config: DamageConfig,
    *,
    fresh_plan: AttackPlan | None = None,
    other_fresh_plan: AttackPlan | None = None,
    extra_fresh_plans: Mapping[str, AttackPlan] | None = None,
) -> RelativeDamage:
    """Damage of ``plan`` on ``topology`` relative to a fresh oracle plan.

    The fresh plan A* is built on ``topology`` with ``plan``'s own budget and
    ``attack``'s pair limit and endpoints, so both plans have the same
    resources. It comes from the oracle named by ``attack.oracle_knowledge``
    (decision D15). The same comparison against the other oracle is
    recorded in the ``other_*`` fields, so the choice can be changed later
    from saved results. Pass ``fresh_plan`` and ``other_fresh_plan`` to
    reuse plans already computed, or to compare against plans that are not
    oracle plans: the security filter passes a fresh plan of the stale plan's
    own mechanism (Eq. 1; O3 option e). ``extra_fresh_plans`` adds further
    comparisons, saved as ``<label>_ratio`` columns.

    The ratio is τ (Eq. 1) when ``plan`` was learned on another topology and
    η (Eq. 10) when it was learned on this one. When the fresh plan does no
    damage, the ratio and ``attack_immune`` follow decision D2
    (``config.zero_denominator``).
    """
    evaluated_on = compute_topology_id(topology)
    knowledge = attack.oracle_knowledge
    (other,) = (k for k in ORACLE_KNOWLEDGE if k != knowledge)
    same_budget = replace(attack, budget=plan.budget)

    def fresh(given: AttackPlan | None, which: str) -> AttackPlan:
        if given is not None:
            return given
        return fresh_oracle_plan(
            topology,
            benign,
            same_budget,
            routing,
            config,
            knowledge=which,
            topology_id=evaluated_on,
        )

    plan_damage = evaluate_damage(topology, benign, plan, routing, config)
    numerator = plan_damage.measure(config.tau_measure)
    reference = fresh(fresh_plan, knowledge)
    other_plan = fresh(other_fresh_plan, other)
    fresh_damage = evaluate_damage(topology, benign, reference, routing, config)
    other_damage = evaluate_damage(topology, benign, other_plan, routing, config)
    denominator = fresh_damage.measure(config.tau_measure)
    other_denominator = other_damage.measure(config.tau_measure)
    ratio, immune = _ratio(numerator, denominator, config)
    other_ratio, other_immune = _ratio(numerator, other_denominator, config)
    extra = []
    for label, extra_plan in (extra_fresh_plans or {}).items():
        value = evaluate_damage(topology, benign, extra_plan, routing, config).measure(
            config.tau_measure
        )
        extra.append(Comparison(label, value, *_ratio(numerator, value, config)))

    return RelativeDamage(
        plan_topology_id=plan.topology_id,
        evaluated_on=evaluated_on,
        plan_mechanism=plan.mechanism,
        measure=config.tau_measure,
        numerator=numerator,
        denominator=denominator,
        ratio=ratio,
        attack_immune=immune,
        plan_damage=plan_damage,
        fresh_damage=fresh_damage,
        oracle_knowledge=_knowledge(reference, knowledge),
        other_oracle_knowledge=_knowledge(other_plan, other),
        other_denominator=other_denominator,
        other_ratio=other_ratio,
        other_attack_immune=other_immune,
        other_fresh_damage=other_damage,
        reference=reference.mechanism,
        other_reference=other_plan.mechanism,
        extra=tuple(extra),
    )


def _knowledge(plan: AttackPlan, oracle_default: str) -> str:
    """``oracle_knowledge`` column: the oracle's knowledge, or the mechanism."""
    return {"oracle_benign": "benign", "oracle": "routing"}.get(
        plan.mechanism, plan.mechanism if plan.mechanism else oracle_default
    )


def _ratio(
    numerator: float, denominator: float, config: DamageConfig
) -> tuple[float, bool]:
    """τ or η, and whether the network is attack-immune (D2).

    When the fresh plan does no damage: under ``"zero_or_inf"`` the ratio is
    0 (immune) if the evaluated plan does none either, and infinity (not
    immune) if it still does; ``"zero"`` and ``"nan"`` ignore the numerator.
    """
    if denominator > config.zero_tolerance:
        return numerator / denominator, False
    if config.zero_denominator == "zero_or_inf":
        if numerator > config.zero_tolerance:
            return math.inf, False
        return 0.0, True
    return (0.0 if config.zero_denominator == "zero" else math.nan), True


def budget_to_disrupt(
    topology: nx.Graph,
    benign: Mapping[Pair, float],
    plan: AttackPlan,
    routing: RoutingConfig,
    config: DamageConfig,
    *,
    max_budget: float,
    relative_tolerance: float = 1e-3,
) -> float:
    """Smallest budget at which ``plan``'s pairs cause benign loss (§3.4, D14).

    The pairs of ``plan`` are kept and the budget is split equally over them
    (Eq. 8); only the total changes. Bisection finds the smallest budget
    whose benign loss exceeds ``config.disruption_level``, to within
    ``relative_tolerance``. Returns ``math.inf`` if even ``max_budget`` does
    not reach it.

    Bisection assumes benign loss does not fall as the budget grows, which
    holds for ECMP (routes do not move) with proportional sharing.
    """

    def disrupts(budget: float) -> bool:
        trial = rescale(plan, budget)
        report = evaluate_damage(topology, benign, trial, routing, config)
        return report.benign_loss > config.disruption_level

    if not disrupts(max_budget):
        return math.inf
    low, high = 0.0, max_budget
    while high - low > relative_tolerance * high:
        middle = (low + high) / 2
        if disrupts(middle):
            high = middle
        else:
            low = middle
    return high
