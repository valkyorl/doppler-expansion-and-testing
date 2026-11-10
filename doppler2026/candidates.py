"""Candidate topologies: the MILP pool (paper §4.5-4.6, §4.10-4.11).

Doppler enumerates up to K candidate topologies G' that satisfy the optical
and traffic constraints, then filters them (§4.11, Eq. 31). The security
objective T(G') is not linear, so it is not in this model: the security
filter (``security.py``) applies it afterwards (PLAN §2, generate-then-filter).

The model, over a set L of IP links that may be active:

- x_e ∈ {0, 1} for each e ∈ L: link e is active (§4.4).
- Transponders (Eq. 11): for each PoP v, the active links at v are at most
  txp(v).
- Benign flow (Eq. 12-14): the estimated benign demand D_t (D27) must be
  routed. Flow is aggregated per source PoP: f_s(u→v) is the flow from
  source s on directed link u→v. This is exactly equivalent to one flow per
  source-destination pair (any per-source flow splits into per-pair
  flows), and about N times smaller, which is what lets the pool fill within
  the time budget (decision P9).
- Capacity and utilization (Eq. 15-16): on each directed link,
  sum_s f_s(u→v) <= U_max · C_e · x_e. A variable ``mlu`` bounds the
  utilization of every link and is part of the objective.
- At least one change: the current topology is excluded, and each found
  candidate is excluded before the next solve (no-good cuts).
- No net loss of links (``keep_link_count``; O2 option c): at least as
  many active links as the current topology. Off by default since the
  2026-11-10 baseline: without it the change-minimizing objectives mostly
  remove links (the sparsification under study), and each removal made
  attacks more damaging (O7). v0 had it on.

Every ordered PoP pair has positive benign demand (gravity model), so any
feasible solution is connected. The operational filter checks it again.

Objective (decision D22), one of:

- ``"random_weights"`` (default): sum_e w_e · [e changes] + mlu, with fresh
  weights w_e drawn uniformly from ``weight_range`` before every solve. The
  fixed objective below finds near-copies of the same minimal change; random
  weights make each solve prefer different changes.
- ``"security_guided"`` (O5): as ``random_weights``, but each change's
  weight is lowered by ``security_weight`` x g_e, where g_e in [0, 1] is the
  share of the history plans' attack traffic that the change alone would move
  off their target links (``security.attack_guidance``). A stand-in for
  Eq. 25's "minimize T(G')", which is not linear; the security filter still
  checks the true T(G'). A weight can become negative, so the MILP may prefer
  making such a change to making none.
- ``"changes_plus_mlu"``: 2 · (number of changes) + mlu, the objective of the
  existing open Doppler (``onset.open_doppler``).
- ``"min_overlap"``: |E_t ∩ E'| (Eq. 18), the old Gurobi Doppler's objective
  and the structural-churn baseline of PLAN §7.

Which links may change (§4.10, decision D23): every current link may be
dropped; links that may be added come from E* (``feasibility.py``):

- ``"local"`` (default): the old Doppler's "conservative" set. For each of
  the top ``top_fraction`` links of G_t by edge betweenness, and each link
  targeted by a plan in the history, move one endpoint to a neighbour: for
  link (u, v), the links (n, v) for neighbours n of u and (u, n) for
  neighbours n of v.
- ``"liberal"``: the old "liberal" set; for the same links, every pair of a
  neighbour of u and a neighbour of v.
- ``"expanded"``: all of E*.

Transponders (D18): txp(v) is v's degree in the original topology, plus
``spare_transponders`` at the ``spare_fraction`` most central PoPs (like the
old Doppler's ``dynamic_doppler`` allocation). Default since the 2026-11-10
baseline: no spares, so an added link needs a removal at both endpoints
first (v0 had one spare at every PoP). New links get the median link
capacity of the original topology (D17).

Solver (D25): HiGHS with a fixed seed, so runs reproduce.
"""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

import highspy
import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix

from .model import Pair
from .recon.inferred import Edge, edge_key
from .topology import topology_id as compute_topology_id

CANDIDATE_SETS = ("local", "liberal", "expanded")
OBJECTIVES = ("random_weights", "security_guided", "changes_plus_mlu", "min_overlap")


@dataclass(frozen=True)
class CandidateConfig:
    """Settings of the candidate pool (decisions D3, D5, D17, D18, D22, D23, D25)."""

    pool_size: int = 50
    """K, the most candidates enumerated per epoch (D3)."""
    time_limit: float = 60.0
    """T_opt in seconds for the whole pool (D25, §4.12)."""
    u_max: float = 0.8
    """Highest link utilization the MILP allows (Eq. 16, D5)."""
    candidate_set: str = "local"
    top_fraction: float = 0.1
    """Share of G_t's links, by edge betweenness, that the local set works around."""
    objective: str = "random_weights"
    weight_range: tuple[float, float] = (1.0, 3.0)
    """Range of the per-link change weights (mean 2, as in changes_plus_mlu)."""
    keep_link_count: bool = False
    """No net loss of links: a candidate has at least as many links as the
    current topology, so transponders are re-paired rather than released
    (O2 option c; on in v0, off in the 2026-11-10 baseline)."""
    security_weight: float = 4.0
    """Bonus per unit of guidance for ``security_guided`` (twice the mean change weight)."""
    spare_transponders: int = 0
    """Spare transponders per chosen PoP (D18; v0 had 1)."""
    spare_fraction: float = 0.1
    """Share of PoPs, most central first, that get the spares (v0 had 1.0: all)."""
    seed: int = 0

    def __post_init__(self) -> None:
        if self.candidate_set not in CANDIDATE_SETS:
            raise ValueError(f"candidate_set must be one of {CANDIDATE_SETS}")
        if self.objective not in OBJECTIVES:
            raise ValueError(f"objective must be one of {OBJECTIVES}")
        if self.pool_size < 1 or self.time_limit <= 0:
            raise ValueError("pool_size and time_limit must be positive")
        if not 0 < self.u_max <= 1:
            raise ValueError("u_max must be in (0, 1]")
        low, high = self.weight_range
        if not 0 < low <= high:
            raise ValueError("weight_range must satisfy 0 < low <= high")


@dataclass(frozen=True)
class Candidate:
    """One topology G' from the MILP pool."""

    links: frozenset[Edge]
    added: frozenset[Edge]
    dropped: frozenset[Edge]
    milp_mlu: float
    """Highest benign utilization in the MILP's own (multicommodity) routing."""
    objective: float
    solve_index: int
    proven_optimal: bool
    topology_id: str


@dataclass(frozen=True)
class CandidatePool:
    candidates: tuple[Candidate, ...]
    status: str
    """``"pool_full"``, ``"exhausted"`` (no further feasible topology),
    ``"time_limit"``, or ``"infeasible"`` (no candidate at all)."""
    solves: int
    wall_time: float
    variable_links: tuple[Edge, ...]
    """L: the links the MILP could choose from."""


def transponders(original: nx.Graph, config: CandidateConfig) -> dict[str, int]:
    """txp(v) (Eq. 11, D18): degree in the original topology, plus spares."""
    counts = {str(v): original.degree(v) for v in original.nodes}
    if config.spare_transponders:
        centrality = nx.betweenness_centrality(original)
        ranked = sorted(centrality, key=lambda v: (-centrality[v], v))
        for v in ranked[: max(1, math.ceil(config.spare_fraction * len(ranked)))]:
            counts[v] += config.spare_transponders
    return counts


def link_capacities(original: nx.Graph, links: Iterable[Edge]) -> dict[Edge, float]:
    """C_e (Eq. 15, D17): an original link keeps its capacity; a new one gets the median."""
    median = statistics.median(c for _, _, c in original.edges(data="capacity"))
    return {
        e: float(original.edges[e]["capacity"]) if original.has_edge(*e) else median
        for e in links
    }


def build_topology(
    original: nx.Graph, links: Iterable[Edge], capacities: Mapping[Edge, float]
) -> nx.Graph:
    """The topology with ``links`` active: original PoPs (with coordinates), C_e.

    Links are added in sorted order. Edge order matters: ECMP keeps the first
    few equal-cost paths (the path budget), and their order follows the
    order edges were added. Adding them in set order made results depend on
    Python's per-process string hashing.
    """
    graph = nx.Graph()
    graph.add_nodes_from(original.nodes(data=True))
    for e in sorted(links):
        graph.add_edge(*e, capacity=capacities[e])
    graph.graph.update(original.graph)
    return graph


def _moved_endpoint_links(current: nx.Graph, link: Edge, liberal: bool) -> set[Edge]:
    u, v = link
    nu = set(current.neighbors(u)) - {v}
    nv = set(current.neighbors(v)) - {u}
    if liberal:
        return {edge_key(a, b) for a in nu for b in nv if a != b}
    return {edge_key(n, v) for n in nu} | {edge_key(u, n) for n in nv}


def variable_links(
    current: nx.Graph,
    feasible: Iterable[Edge],
    targets: Iterable[Pair],
    config: CandidateConfig,
) -> tuple[Edge, ...]:
    """L (D23): current links plus the links that may be added."""
    feasible = set(feasible)
    links = {edge_key(u, v) for u, v in current.edges}
    if config.candidate_set == "expanded":
        return tuple(sorted(links | feasible))
    centrality = nx.edge_betweenness_centrality(current)
    ranked = sorted(
        (edge_key(u, v) for u, v in centrality),
        key=lambda e: (-centrality.get(e, centrality.get(e[::-1], 0.0)), e),
    )
    around = set(ranked[: max(1, math.ceil(config.top_fraction * len(ranked)))])
    around |= {edge_key(u, v) for u, v in targets if current.has_edge(u, v)}
    liberal = config.candidate_set == "liberal"
    for link in sorted(around):
        links |= _moved_endpoint_links(current, link, liberal) & feasible
    return tuple(sorted(links))


class _Model:
    """The MILP above, built once; the objective and cuts change between solves."""

    def __init__(
        self,
        current: frozenset[Edge],
        links: tuple[Edge, ...],
        capacities: Mapping[Edge, float],
        txp: Mapping[str, int],
        demand: Mapping[Pair, float],
        u_max: float,
        min_links: int = 0,
    ) -> None:
        self.links = links
        self.current = current
        nodes = sorted(txp)
        # Normalize by the median capacity so coefficients stay near 1.
        unit = statistics.median(capacities.values())
        cap = {e: capacities[e] / unit for e in links}
        arcs = list(links) + [(v, u) for u, v in links]
        sources = sorted({s for (s, _), d in demand.items() if d > 0})

        n_x = len(links)
        flow_col: dict[tuple[str, Pair], int] = {}
        for s in sources:
            for arc in arcs:
                flow_col[(s, arc)] = n_x + len(flow_col)
        self.mlu_col = n_x + len(flow_col)
        n_cols = self.mlu_col + 1

        rows: list[dict[int, float]] = []
        lower: list[float] = []
        upper: list[float] = []

        def add(entries: dict[int, float], lo: float, hi: float) -> None:
            rows.append(entries)
            lower.append(lo)
            upper.append(hi)

        # Eq. 11: transponders.
        for v in nodes:
            entries = {i: 1.0 for i, e in enumerate(links) if v in e}
            if entries:
                add(entries, -math.inf, float(txp[v]))
        # No net loss of links (O2 option c, O7): at least min_links active.
        if min_links:
            add({i: 1.0 for i in range(len(links))}, float(min_links), math.inf)
        # Eq. 12-14: flow conservation, per source s and node v:
        # inflow - outflow = demand(s, v), and -sum of demand at s.
        for s in sources:
            out_total = sum(d for (a, _), d in demand.items() if a == s and d > 0)
            for v in nodes:
                entries: dict[int, float] = {}
                for arc in arcs:
                    if arc[1] == v:
                        entries[flow_col[(s, arc)]] = 1.0
                    if arc[0] == v:
                        entries[flow_col[(s, arc)]] = -1.0
                net = -out_total / unit if v == s else demand.get((s, v), 0.0) / unit
                add(entries, net, net)
        # Eq. 15-16: capacity on active links, and the utilization bound.
        for i, (u, v) in enumerate(links):
            for arc in ((u, v), (v, u)):
                total = {flow_col[(s, arc)]: 1.0 for s in sources}
                add({**total, i: -u_max * cap[(u, v)]}, -math.inf, 0.0)
                add({**total, self.mlu_col: -cap[(u, v)]}, -math.inf, 0.0)

        matrix = csr_matrix(
            (
                [c for r in rows for c in r.values()],
                (
                    [i for i, r in enumerate(rows) for _ in r],
                    [j for r in rows for j in r],
                ),
            ),
            shape=(len(rows), n_cols),
        )
        lp = highspy.HighsLp()
        lp.num_col_ = n_cols
        lp.num_row_ = len(rows)
        lp.col_cost_ = np.zeros(n_cols)
        lp.col_lower_ = np.zeros(n_cols)
        upper_bounds = np.full(n_cols, math.inf)
        upper_bounds[:n_x] = 1.0
        upper_bounds[self.mlu_col] = u_max
        lp.col_upper_ = upper_bounds
        lp.row_lower_ = np.array(lower)
        lp.row_upper_ = np.array(upper)
        lp.integrality_ = [highspy.HighsVarType.kInteger] * n_x + [
            highspy.HighsVarType.kContinuous
        ] * (n_cols - n_x)
        lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
        lp.a_matrix_.start_ = matrix.indptr.astype(np.int32)
        lp.a_matrix_.index_ = matrix.indices.astype(np.int32)
        lp.a_matrix_.value_ = matrix.data.astype(np.float64)
        self.lp = lp
        self.n_cols = n_cols

    def change_costs(self, weights: Mapping[Edge, float]) -> tuple[np.ndarray, float]:
        """Costs of sum_e w_e · [e changes] + mlu, and its constant term.

        A current link changes when x_e = 0 (cost w_e · (1 - x_e)); another
        link changes when x_e = 1 (cost w_e · x_e).
        """
        cost = np.zeros(self.n_cols)
        offset = 0.0
        for i, e in enumerate(self.links):
            if e in self.current:
                cost[i] = -weights[e]
                offset += weights[e]
            else:
                cost[i] = weights[e]
        cost[self.mlu_col] = 1.0
        return cost, offset

    def overlap_costs(self) -> tuple[np.ndarray, float]:
        """Costs of |E_t ∩ E'| (Eq. 18)."""
        cost = np.zeros(self.n_cols)
        for i, e in enumerate(self.links):
            cost[i] = 1.0 if e in self.current else 0.0
        return cost, 0.0

    def no_good_cut(self, selected: frozenset[Edge]) -> tuple[np.ndarray, float]:
        """sum_{e not in S} x_e - sum_{e in S} x_e >= 1 - |S|: exclude exactly S."""
        coeffs = np.array([-1.0 if e in selected else 1.0 for e in self.links])
        return coeffs, 1.0 - len(selected & set(self.links))


def generate(
    current: nx.Graph,
    original: nx.Graph,
    feasible: Iterable[Edge],
    demand: Mapping[Pair, float],
    config: CandidateConfig,
    *,
    targets: Iterable[Pair] = (),
    guidance: Callable[[tuple[Edge, ...]], Mapping[Edge, float]] | None = None,
) -> CandidatePool:
    """Enumerate up to K candidate topologies around ``current`` (§4.11, Eq. 31).

    ``original`` is the network's original topology (fiber graph, transponder
    counts, link capacities); ``feasible`` is E*; ``demand`` is the benign
    estimate D_t; ``targets`` are the links attacked by plans in the history
    (they widen the local candidate set, D23). ``guidance`` maps the
    variable links to their security guidance g_e; it is required by the
    ``security_guided`` objective.
    """
    started = time.perf_counter()
    links = variable_links(current, feasible, targets, config)
    capacities = link_capacities(original, links)
    current_links = frozenset(edge_key(u, v) for u, v in current.edges)
    model = _Model(
        current_links,
        links,
        capacities,
        transponders(original, config),
        demand,
        config.u_max,
        min_links=len(current_links) if config.keep_link_count else 0,
    )
    highs = highspy.Highs()
    highs.setOptionValue("output_flag", False)
    # HiGHS's MIP solver gives the same answer whatever its thread count, so
    # runs reproduce with a fixed seed. "threads" is not set: HiGHS shares
    # one thread pool per process and refuses to run a solver that asks for
    # a different size once the pool exists.
    highs.setOptionValue("random_seed", config.seed)
    highs.passModel(model.lp)
    rng = np.random.default_rng(config.seed)
    x_cols = np.arange(len(links), dtype=np.int32)
    bonus = np.zeros(len(links))
    if config.objective == "security_guided":
        if guidance is None:
            raise ValueError("The security_guided objective needs guidance")
        scores = guidance(links)
        bonus = config.security_weight * np.array([scores.get(e, 0.0) for e in links])

    def exclude(selected: frozenset[Edge]) -> None:
        coeffs, low = model.no_good_cut(selected)
        nonzero = np.nonzero(coeffs)[0].astype(np.int32)
        highs.addRow(low, math.inf, nonzero.size, x_cols[nonzero], coeffs[nonzero])

    exclude(current_links)  # at least one change
    found: list[Candidate] = []
    status = "time_limit"
    solves = 0
    while len(found) < config.pool_size:
        remaining = config.time_limit - (time.perf_counter() - started)
        if remaining <= 0:
            break
        if config.objective in ("random_weights", "security_guided"):
            draws = rng.uniform(*config.weight_range, size=len(links)) - bonus
            cost, offset = model.change_costs(dict(zip(links, draws, strict=True)))
        elif config.objective == "changes_plus_mlu":
            cost, offset = model.change_costs(dict.fromkeys(links, 2.0))
        else:
            cost, offset = model.overlap_costs()
        highs.changeColsCost(
            model.n_cols, np.arange(model.n_cols, dtype=np.int32), cost
        )
        highs.setOptionValue("time_limit", max(remaining, 0.01))
        if highs.run() == highspy.HighsStatus.kError:
            raise RuntimeError(
                f"HiGHS refused to solve: {highs.modelStatusToString(highs.getModelStatus())}"
            )
        solves += 1
        state = highs.getModelStatus()
        values = np.array(highs.getSolution().col_value)
        if state == highspy.HighsModelStatus.kInfeasible:
            status = "exhausted" if found else "infeasible"
            break
        if values.size == 0 or not highs.getInfo().primal_solution_status:
            break  # time limit with no solution
        selected = frozenset(e for e, x in zip(links, values, strict=False) if x > 0.5)
        graph = build_topology(original, selected, capacities)
        found.append(
            Candidate(
                links=selected,
                added=selected - current_links,
                dropped=current_links - selected,
                milp_mlu=float(values[model.mlu_col]),
                objective=float(cost @ values + offset),
                solve_index=solves,
                proven_optimal=state == highspy.HighsModelStatus.kOptimal,
                topology_id=compute_topology_id(graph),
            )
        )
        exclude(selected)
    else:
        status = "pool_full"
    return CandidatePool(
        candidates=tuple(found),
        status=status,
        solves=solves,
        wall_time=time.perf_counter() - started,
        variable_links=links,
    )
