"""Small hand-checkable topologies shared by the Doppler 2026 tests."""

import networkx as nx


def line(capacity: float = 100.0) -> nx.Graph:
    """Two PoPs, x and y, joined by one link."""
    graph = nx.Graph()
    graph.add_edge("x", "y", capacity=capacity)
    return graph


def dumbbell(capacity: float = 100.0) -> nx.Graph:
    """Two triangles (a1, a2, a3) and (b1, b2, b3) joined by the bridge a1-b1.

    The bridge is the obvious bottleneck: every a-to-b pair crosses it.
    """
    graph = nx.Graph()
    for u, v in [
        ("a1", "a2"),
        ("a2", "a3"),
        ("a1", "a3"),
        ("b1", "b2"),
        ("b2", "b3"),
        ("b1", "b3"),
        ("a1", "b1"),
    ]:
        graph.add_edge(u, v, capacity=capacity)
    return graph
