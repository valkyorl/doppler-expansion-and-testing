"""From a selected topology to a network transition (paper §4.13, Eq. 32-33).

The controller computes E_add = E_{t+1} \\ E_t (Eq. 32) and
E_remove = E_t \\ E_{t+1} (Eq. 33) and orders the changes. Where transponders
allow, it follows make-before-break: establish the new circuits, let routing
use them, then remove the obsolete links. When a new circuit needs a
transponder that an old link still holds, a strict make-before-break is not
possible; such transitions are labelled and evaluated separately (§4.13).

Order (decision D31, "mixed"):

1. add every new link whose two endpoints have a free transponder (repeated
   while any fits);
2. remove only the old links whose transponders the remaining additions
   need (for each blocked addition in name order, at each endpoint without
   a free transponder, the first old link there by name);
3. add the links that now fit; steps 2 and 3 repeat until every addition is
   made;
4. remove the remaining old links.

A transition is make-before-break when step 2 removed nothing. The network
is evaluated after every step with the benign demand only (connectivity,
MLU, benign loss including unroutable demand): flow-level metrics, not
packet-level effects, which are a gap (docs/gaps.md). The ordered list of actions
is what a testbed would replay; steps are numbered, not timed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import networkx as nx

from .candidates import build_topology
from .model import DamageConfig, Pair, RoutingConfig
from .recon.inferred import Edge, edge_key
from .routing import deliver, directed, route


@dataclass(frozen=True)
class Action:
    step: int
    """1-4, as in the module docstring (2 and 3 repeat as 2, 3, 2, 3 ...)."""
    kind: str
    """``"add"`` or ``"remove"``."""
    link: Edge


@dataclass(frozen=True)
class State:
    """The network after one step of the transition."""

    after_step: int
    """0 is the starting topology."""
    links: int
    connected: bool
    mlu: float
    """Highest offered benign utilization (0 when nothing is routed)."""
    benign_loss: float
    """Share of benign demand not delivered, unroutable demand included."""


@dataclass(frozen=True)
class Transition:
    added: frozenset[Edge]
    removed: frozenset[Edge]
    make_before_break: bool
    actions: tuple[Action, ...]
    states: tuple[State, ...] = field(default=())

    @property
    def kind(self) -> str:
        if not self.added and not self.removed:
            return "none"
        return "make_before_break" if self.make_before_break else "break_before_make"

    def as_record(self) -> dict:
        """One line of ``transitions.jsonl`` (docs/results_schema.md)."""
        return {
            "kind": self.kind,
            "added": sorted("-".join(e) for e in self.added),
            "removed": sorted("-".join(e) for e in self.removed),
            "actions": [
                {"order": i, "step": a.step, "kind": a.kind, "link": "-".join(a.link)}
                for i, a in enumerate(self.actions)
            ],
            "states": [s.__dict__ for s in self.states],
        }


def order_changes(
    current: Iterable[Edge], target: Iterable[Edge], txp: Mapping[str, int]
) -> Transition:
    """Eq. 32-33 and the ordering of D31 (without evaluating the states)."""
    current = {edge_key(*e) for e in current}
    target = {edge_key(*e) for e in target}
    to_add = sorted(target - current)
    to_remove = sorted(current - target)
    used = Counter(v for e in current for v in e)

    def free(v: str) -> int:
        return txp[v] - used[v]

    actions: list[Action] = []
    pending = list(to_add)
    remaining = list(to_remove)
    broke = False
    step = 1
    while pending:
        progress = True
        while progress:  # add whatever fits
            progress = False
            for e in list(pending):
                if free(e[0]) > 0 and free(e[1]) > 0:
                    actions.append(Action(step, "add", e))
                    used.update(e)
                    pending.remove(e)
                    progress = True
        if not pending:
            break
        # Free the transponders the blocked additions need.
        step = 2
        for e in pending:
            for v in e:
                if free(v) > 0:
                    continue
                old = next((r for r in remaining if v in r), None)
                if old is None:
                    raise ValueError(f"No old link frees a transponder at {v}")
                actions.append(Action(2, "remove", old))
                used.subtract(old)
                remaining.remove(old)
                broke = True
        step = 3
    for e in remaining:
        actions.append(Action(4, "remove", e))
    return Transition(
        added=frozenset(to_add),
        removed=frozenset(to_remove),
        make_before_break=not broke,
        actions=tuple(actions),
    )


def _state(
    after_step: int,
    graph: nx.Graph,
    benign: Mapping[Pair, float],
    routing: RoutingConfig,
    damage: DamageConfig,
) -> State:
    demands = {p: a for p, a in benign.items() if a > 0}
    offered = sum(demands.values())
    directed_graph = directed(graph)
    routes = route(directed_graph, demands, routing)
    flows = {p: (p, a) for p, a in demands.items()}
    delivery = deliver(directed_graph, flows, routes, damage.sharing)
    mlu = max(
        (
            load / directed_graph.edges[e]["capacity"]
            for e, load in delivery.expected_loads.items()
        ),
        default=0.0,
    )
    delivered = sum(delivery.delivered.values())
    return State(
        after_step=after_step,
        links=graph.number_of_edges(),
        connected=nx.is_connected(graph),
        mlu=mlu,
        benign_loss=1 - delivered / offered if offered else 0.0,
    )


def evaluate_transition(
    original: nx.Graph,
    current: Iterable[Edge],
    target: Iterable[Edge],
    capacities: Mapping[Edge, float],
    txp: Mapping[str, int],
    benign: Mapping[Pair, float],
    routing: RoutingConfig,
    damage: DamageConfig,
) -> Transition:
    """Order the changes and measure the network after every step."""
    plan = order_changes(current, target, txp)
    links = {edge_key(*e) for e in current}
    states = [
        _state(0, build_topology(original, links, capacities), benign, routing, damage)
    ]
    for i, action in enumerate(plan.actions):
        if action.kind == "add":
            links.add(action.link)
        else:
            links.discard(action.link)
        last_of_step = (
            i + 1 == len(plan.actions) or plan.actions[i + 1].step != action.step
        )
        if last_of_step:
            graph = build_topology(original, links, capacities)
            states.append(_state(action.step, graph, benign, routing, damage))
    return Transition(
        added=plan.added,
        removed=plan.removed,
        make_before_break=plan.make_before_break,
        actions=plan.actions,
        states=tuple(states),
    )
