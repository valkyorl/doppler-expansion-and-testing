"""Synthetic test networks (not part of the paper; a research tool).

Small, fast networks for studying one behavior at a time, such as the
sparsification of the 2026-11-10 baseline. Each network is generated from a
recorded config and seed and written as a GML file in
``doppler2026/topologies/``, which ``load_topology`` reads like any
Topology Zoo file (``ControllerConfig.topology_dir``).

Generator (chosen by the user, 2026-11-10):

1. Place ``nodes`` PoPs uniformly at random in a square of ``side_km``
   centered on ``center`` (latitude, longitude); kilometres are converted to
   degrees with a flat-earth approximation, fine at this scale.
2. Link every PoP to its ``nearest_first`` nearest PoPs (great-circle
   distance), so no PoP is isolated or hangs on one link.
3. Add the closest remaining pairs until there are
   ``nodes * mean_degree / 2`` links.
4. If the result has a bridge (a single link whose loss disconnects it),
   redraw the positions with the next draw from the same generator. The
   number of draws is recorded in the graph (``draws``).

Every link gets ``capacity`` (bit/s), as for the Topology Zoo networks (I6).

    python -m doppler2026.synthetic            # writes synthetic15.gml
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import networkx as nx
import numpy as np

from onset.utilities.reconfiguration import calc_haversine

from .topology import DEFAULT_CAPACITY

TOPOLOGY_DIR = Path(__file__).resolve().parent / "topologies"
KM_PER_DEGREE = 111.32
"""Length of one degree of latitude in km (and of longitude at the equator)."""
MAX_DRAWS = 1000


@dataclass(frozen=True)
class SyntheticConfig:
    name: str = "synthetic15"
    nodes: int = 15
    mean_degree: float = 6.0
    """Average links per PoP; the network has nodes * mean_degree / 2 links."""
    nearest_first: int = 2
    """Each PoP is first linked to this many nearest PoPs."""
    side_km: float = 1500.0
    """Side of the square the PoPs are placed in (about the US Midwest)."""
    center: tuple[float, float] = (41.5, -90.0)
    """Latitude and longitude of the square's center."""
    capacity: float = DEFAULT_CAPACITY
    seed: int = 0

    @property
    def links(self) -> int:
        return round(self.nodes * self.mean_degree / 2)

    def __post_init__(self) -> None:
        if self.nodes < 3 or self.nearest_first < 1:
            raise ValueError("need at least 3 nodes and nearest_first >= 1")
        if not self.nodes - 1 >= self.nearest_first:
            raise ValueError("nearest_first must be below the number of nodes")
        if self.links > self.nodes * (self.nodes - 1) // 2:
            raise ValueError("mean_degree asks for more links than PoP pairs")


def _positions(config: SyntheticConfig, rng: np.random.Generator) -> dict[str, tuple]:
    lat0, lon0 = config.center
    xy = rng.uniform(-config.side_km / 2, config.side_km / 2, size=(config.nodes, 2))
    km_per_lon = KM_PER_DEGREE * math.cos(math.radians(lat0))
    return {
        str(i): (float(lat0 + y / KM_PER_DEGREE), float(lon0 + x / km_per_lon))
        for i, (x, y) in enumerate(xy)
    }


def _links(config: SyntheticConfig, positions: dict[str, tuple]) -> set[tuple]:
    names = list(positions)
    # Pairs are keyed in sorted name order everywhere, so each link is one key.
    km = {
        tuple(sorted(pair)): calc_haversine(*positions[pair[0]], *positions[pair[1]])
        for pair in itertools.combinations(names, 2)
    }

    def dist(u: str, v: str) -> float:
        return km[tuple(sorted((u, v)))]

    links: set[tuple] = set()
    for v in names:
        nearest = sorted((u for u in names if u != v), key=lambda u: dist(u, v))
        links |= {tuple(sorted((u, v))) for u in nearest[: config.nearest_first]}
    if len(links) > config.links:
        raise ValueError(
            f"linking each PoP to its {config.nearest_first} nearest already "
            f"gives {len(links)} links, more than the {config.links} asked for"
        )
    for pair in sorted(km, key=km.get):
        if len(links) == config.links:
            break
        links.add(pair)
    return links


def generate(config: SyntheticConfig) -> nx.Graph:
    """The network for ``config`` (see the module docstring)."""
    rng = np.random.default_rng(config.seed)
    for draw in range(1, MAX_DRAWS + 1):
        positions = _positions(config, rng)
        graph = nx.Graph()
        for v, (lat, lon) in positions.items():
            graph.add_node(v, Latitude=lat, Longitude=lon)
        graph.add_edges_from(_links(config, positions), capacity=config.capacity)
        if nx.is_connected(graph) and not nx.has_bridges(graph):
            graph.graph.update(
                name=config.name,
                draws=draw,
                **{
                    f"generator_{k}": str(v)
                    for k, v in asdict(config).items()
                    if k != "name"
                },
            )
            return graph
    raise RuntimeError(f"no bridgeless network in {MAX_DRAWS} draws")


def write(graph: nx.Graph, directory: Path = TOPOLOGY_DIR) -> Path:
    """Write ``<directory>/<name>.gml`` in the layout ``load_topology`` reads."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{graph.graph['name']}.gml"
    # load_topology reads ids as names, so name the nodes by integer ids.
    out = nx.relabel_nodes(graph, {v: int(v) for v in graph})
    nx.write_gml(out, path)
    return path


def ensure(config: SyntheticConfig, directory: Path = TOPOLOGY_DIR) -> Path:
    """Write the network if its file is missing; refuse a file that differs."""
    graph = generate(config)
    path = directory / f"{config.name}.gml"
    if not path.exists():
        return write(graph, directory)
    from .topology import load_topology

    stored = load_topology(config.name, gml_dir=directory)
    if set(map(frozenset, stored.edges)) != set(map(frozenset, graph.edges)):
        raise ValueError(f"{path} differs from what {config} generates")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--nodes", type=int, default=SyntheticConfig.nodes)
    parser.add_argument(
        "--mean-degree", type=float, default=SyntheticConfig.mean_degree
    )
    parser.add_argument("--seed", type=int, default=SyntheticConfig.seed)
    parser.add_argument("--name")
    args = parser.parse_args()
    config = SyntheticConfig(
        name=args.name or f"synthetic{args.nodes}",
        nodes=args.nodes,
        mean_degree=args.mean_degree,
        seed=args.seed,
    )
    path = ensure(config)
    graph = generate(config)
    print(
        f"{path}: {graph.number_of_nodes()} PoPs, {graph.number_of_edges()} links, "
        f"degrees {sorted(d for _, d in graph.degree())}, {graph.graph['draws']} draw(s)"
    )


if __name__ == "__main__":
    main()
