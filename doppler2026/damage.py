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
(Eq. 10) for a plan measured on the same topology.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from itertools import pairwise

import networkx as nx

from .model import (
    AttackConfig,
    AttackPlan,
    DamageConfig,
    DamageReport,
    Pair,
    RelativeDamage,
    RoutingConfig,
)
from .recon.oracle import oracle_plan
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
) -> RelativeDamage:
    """Damage of ``plan`` on ``topology`` relative to a fresh oracle plan.

    The fresh plan A* is built on ``topology`` with ``plan``'s own budget and
    ``attack``'s pair limit and endpoints, so both plans have the same
    resources. Pass ``fresh_plan`` to reuse one already computed.

    The ratio is τ (Eq. 1) when ``plan`` was learned on another topology and
    η (Eq. 10) when it was learned on this one. When the fresh plan does no
    damage, the result is flagged ``attack_immune`` and the ratio follows
    decision D2 (``config.zero_denominator``).
    """
    evaluated_on = compute_topology_id(topology)
    if fresh_plan is None:
        fresh_plan = oracle_plan(
            topology,
            replace(attack, budget=plan.budget),
            routing,
            topology_id=evaluated_on,
        )
    plan_damage = evaluate_damage(topology, benign, plan, routing, config)
    fresh_damage = evaluate_damage(topology, benign, fresh_plan, routing, config)

    numerator = plan_damage.measure(config.tau_measure)
    denominator = fresh_damage.measure(config.tau_measure)
    immune = denominator <= config.zero_tolerance
    if immune:
        ratio = 0.0 if config.zero_denominator == "zero" else math.nan
    else:
        ratio = numerator / denominator

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
    )
