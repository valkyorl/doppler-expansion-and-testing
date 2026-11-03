"""Loading network topologies for the experiment.

The topologies in ``data/graphs/gml/`` come from the Internet Topology Zoo
(``docs/references.md``). They give PoP locations (latitude/longitude) and
links, but no usable link capacities, so every link gets ``default_capacity``
unless the edge already carries a numeric ``capacity`` attribute. The rest of
the repository uses 100 Gbps the same way.

Graphs returned here are undirected ``networkx.Graph`` objects with string
node names. Routing code converts them to directed graphs when needed
(``routing.py``).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from onset.base_types import compute_stable_topology_id
from onset.utilities.reconfiguration import calc_haversine

REPO_ROOT = Path(__file__).resolve().parents[1]
GML_DIR = REPO_ROOT / "data" / "graphs" / "gml"
DEFAULT_CAPACITY = 100e9
"""Link capacity in bit/s used when a topology file gives none (100 Gbps)."""


def load_topology(
    name: str,
    *,
    default_capacity: float = DEFAULT_CAPACITY,
    gml_dir: Path = GML_DIR,
) -> nx.Graph:
    """Load ``<gml_dir>/<name>.gml`` as an undirected graph with capacities.

    Node names become strings ("0", "1", ...). Parallel links in the file are
    merged into one link. Each node keeps its ``Latitude``/``Longitude``.
    """
    raw = nx.read_gml(gml_dir / f"{name}.gml", label="id")
    graph = nx.relabel_nodes(nx.Graph(raw), str)
    for u, v, attrs in graph.edges(data=True):
        capacity = attrs.get("capacity")
        if not isinstance(capacity, int | float) or capacity <= 0:
            graph.edges[u, v]["capacity"] = float(default_capacity)
    graph.graph["name"] = name
    return graph


def great_circle_km(topology: nx.Graph, u: str, v: str) -> float:
    """Great-circle (haversine) distance between PoPs ``u`` and ``v`` in km.

    Uses the nodes' ``Latitude``/``Longitude``. Real fiber is longer than the
    great circle; callers that need fiber length scale this up.
    """
    a, b = topology.nodes[u], topology.nodes[v]
    return calc_haversine(a["Latitude"], a["Longitude"], b["Latitude"], b["Longitude"])


def topology_id(graph: nx.Graph) -> str:
    """Stable ID of a topology: a hash of its node and link sets.

    Uses the same hash as the existing optimizer
    (``onset.base_types.compute_stable_topology_id``), so IDs match between
    the experiment and the MILP's solutions.
    """
    return compute_stable_topology_id(
        [str(n) for n in graph.nodes], [(str(u), str(v)) for u, v in graph.edges]
    )
