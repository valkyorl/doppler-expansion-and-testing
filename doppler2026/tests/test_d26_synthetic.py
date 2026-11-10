"""The synthetic network generator (``synthetic.py``)."""

import networkx as nx
import pytest

from doppler2026.synthetic import SyntheticConfig, ensure, generate, write
from doppler2026.topology import great_circle_km, load_topology


def test_default_network_has_the_chosen_shape():
    config = SyntheticConfig()
    graph = generate(config)
    assert graph.number_of_nodes() == 15
    assert graph.number_of_edges() == 45  # mean degree 6
    assert nx.is_connected(graph) and not nx.has_bridges(graph)
    assert min(d for _, d in graph.degree()) >= 2  # 2 nearest first
    lengths = [great_circle_km(graph, u, v) for u, v in graph.edges]
    assert max(lengths) < 1500 * 2**0.5  # inside the square


def test_every_pop_links_to_its_nearest_neighbours():
    config = SyntheticConfig(nodes=8, mean_degree=3.0, seed=4)
    graph = generate(config)
    for v in graph:
        nearest = sorted(
            (u for u in graph if u != v), key=lambda u: great_circle_km(graph, u, v)
        )[: config.nearest_first]
        assert all(graph.has_edge(u, v) for u in nearest)


def test_generation_is_reproducible_and_seeded():
    a, b = generate(SyntheticConfig()), generate(SyntheticConfig())
    assert set(map(frozenset, a.edges)) == set(map(frozenset, b.edges))
    other = generate(SyntheticConfig(seed=1))
    assert set(map(frozenset, a.edges)) != set(map(frozenset, other.edges))


def test_written_file_loads_like_a_topology_zoo_network(tmp_path):
    config = SyntheticConfig(name="tiny", nodes=6, mean_degree=3.0)
    graph = generate(config)
    write(graph, tmp_path)
    loaded = load_topology("tiny", gml_dir=tmp_path)
    assert set(map(frozenset, loaded.edges)) == set(map(frozenset, graph.edges))
    assert loaded.nodes["0"]["Latitude"] == pytest.approx(graph.nodes["0"]["Latitude"])
    ensure(config, tmp_path)  # matches: no error
    ensure(SyntheticConfig(name="other", nodes=6, mean_degree=3.0), tmp_path)
    with pytest.raises(ValueError, match="differs"):
        ensure(SyntheticConfig(name="tiny", nodes=6, mean_degree=3.0, seed=9), tmp_path)


def test_too_few_links_for_the_nearest_rule_is_refused():
    with pytest.raises(ValueError, match="nearest"):
        generate(SyntheticConfig(nodes=10, mean_degree=1.0))


def test_four_pop_study_network_links_every_pair():
    graph = generate(SyntheticConfig(name="synthetic4", nodes=4, mean_degree=3.0))
    assert graph.number_of_edges() == 6
    assert all(d == 3 for _, d in graph.degree())
