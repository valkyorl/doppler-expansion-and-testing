"""Regression tests for two preprocessing bugs fixed for the Doppler 2026 work.

1. Demands whose source sorts after their target (as strings) had no tunnel
   edges, so they were silently dropped from the edge-flow MILP.
2. The tunnel cache was keyed only by network name, so a run with one
   candidate set reused tunnels computed for another.

See doppler2026/CHANGES.md for the full description.
"""

import os

import networkx as nx
import numpy as np
import pytest

import onset.preprocessing as preprocessing
from onset.open_doppler import solve_edge_flow_changes_mlu
from onset.preprocessing import build_optimization_problem

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Node names chosen so that string order differs from numeric order:
# "10" < "2" as strings, which is exactly what triggered bug 1.
RING_NODES = ["0", "1", "2", "3", "4", "10"]


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point every on-disk path cache at a temporary directory."""
    monkeypatch.setattr(preprocessing, "SCRIPT_HOME", str(tmp_path))
    return tmp_path


def _ring_graph() -> nx.Graph:
    graph = nx.Graph()
    for i, node in enumerate(RING_NODES):
        graph.add_node(node, Latitude=40.0 + i, Longitude=-100.0 + i)
    for i, node in enumerate(RING_NODES):
        graph.add_edge(node, RING_NODES[(i + 1) % len(RING_NODES)])
    return graph


def _write_demand(path, graph: nx.Graph, demand: dict) -> str:
    """Write a single-row n*n demand matrix in base_graph node order."""
    nodes = list(graph.nodes)
    matrix = np.zeros((len(nodes), len(nodes)))
    for (s, t), value in demand.items():
        matrix[nodes.index(s), nodes.index(t)] = value
    file_path = str(path)
    with open(file_path, "w") as stream:
        stream.write(" ".join(str(v) for v in matrix.flatten()))
    return file_path


def _build(graph, demand_file, candidate_set, use_cache, network="ring"):
    return build_optimization_problem(
        logical_graph=graph,
        base_graph=graph,
        demand_matrix_file=demand_file,
        network_name=network,
        txp_count={n: graph.degree(n) + 1 for n in graph.nodes},
        candidate_set=candidate_set,
        congestion_threshold_upper_bound=1.0,
        top_k=1,
        optimizer_time_limit=30.0,
        link_capacity=100.0,
        use_cache=use_cache,
        parallel_execution=False,
    )


def test_every_positive_demand_has_tunnel_edges(isolated_cache, tmp_path):
    graph = _ring_graph()
    demand = {(s, t): 1.0 for s in graph.nodes for t in graph.nodes if s != t}
    demand_file = _write_demand(tmp_path / "tm.txt", graph, demand)

    problem = _build(graph, demand_file, "max", use_cache=False)

    missing = [
        c
        for c, v in problem.demand.items()
        if v > 0 and c not in problem.tunnel_edge_sets
    ]
    assert missing == []


def test_reverse_order_demand_is_routed(isolated_cache, tmp_path):
    graph = _ring_graph()
    # "2" sorts after "10", so before the fix this demand was dropped and
    # the MILP reported zero load.
    demand_file = _write_demand(tmp_path / "tm.txt", graph, {("2", "10"): 50.0})

    problem = _build(graph, demand_file, "conservative", use_cache=False)
    result = solve_edge_flow_changes_mlu(problem)

    assert result.has_solutions
    # 50 units split evenly over the two directions around the ring, each
    # with capacity 100, gives MLU 0.25. Before the fix this was 0.
    assert result.selected_solution.validated_mlu == pytest.approx(0.25, abs=1e-6)


def test_tunnel_cache_does_not_leak_between_candidate_sets(isolated_cache, tmp_path):
    graph = _ring_graph()
    demand = {(s, t): 1.0 for s in graph.nodes for t in graph.nodes if s != t}
    demand_file = _write_demand(tmp_path / "tm.txt", graph, demand)

    # Fill the cache with conservative tunnels, then ask for max.
    _build(graph, demand_file, "conservative", use_cache=True)
    max_after_conservative = _build(graph, demand_file, "max", use_cache=True)
    max_fresh = _build(graph, demand_file, "max", use_cache=False)

    assert max_after_conservative.tunnel_edge_sets == max_fresh.tunnel_edge_sets


@pytest.mark.skipif(
    not os.path.exists(os.path.join(REPO_ROOT, "data/graphs/gml/ANS.gml")),
    reason="ANS topology not available",
)
def test_ans_coremelt_drops_no_demands(isolated_cache, tmp_path):
    """The audit measured 15 of 24 nonzero demands dropped on this row."""
    graph = nx.relabel_nodes(
        nx.Graph(
            nx.read_gml(os.path.join(REPO_ROOT, "data/graphs/gml/ANS.gml"), label="id")
        ),
        str,
    )
    traffic = os.path.join(
        REPO_ROOT, "data/traffic/ANS_coremelt_links-2_volume-2.00e+11.txt"
    )
    with open(traffic) as stream:
        rows = [line for line in stream.read().splitlines() if line.strip()]
    demand_file = tmp_path / "row.txt"
    # The simulator reads the last row first (index iter - 1 with iter = 0).
    demand_file.write_text(rows[-1])

    problem = _build(
        graph, str(demand_file), "conservative", use_cache=False, network="ANS"
    )

    positive = [c for c, v in problem.demand.items() if v > 0]
    missing = [c for c in positive if c not in problem.tunnel_edge_sets]
    assert len(positive) == 24
    assert missing == []
