"""Physically feasible IP links E* (paper §4.4).

Doppler first lists the IP links the optical layer could establish, and the
optimizer only chooses among them (§4.4: it does not "invent arbitrary edges
and then determine whether those edges could exist").

No fiber, ROADM, or spectrum data exists for any network here, so (decision
D16):

- The fiber graph G_F is the network's original topology: each original
  link is one fiber, as in the existing AlpWolf model.
- A PoP pair (u, v) is feasible when a fiber path joins them in at most
  ``max_fiber_hops`` fibers (default 2, the old Doppler's "max" candidate
  set) and, when ``max_km`` is set, that path's great-circle length is
  within optical reach (D6; no limit by default).
- The other §4.4 checks (ROADM placement and switching, wavelength and
  spectrum) are a pluggable ``optical_check``. The default allows every
  link; this is a recorded assumption (docs/gaps.md, "Optical data").
- Transponder availability, also listed in §4.4, is not checked here: it
  is a constraint of the topology optimizer (Eq. 11, ``candidates.py``),
  because it depends on which other links are active.

The original links are always feasible: they exist.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx

from .recon.inferred import Edge, edge_key
from .topology import great_circle_km

OpticalCheck = Callable[[str, str, tuple[str, ...]], bool]
"""Extra feasibility test for a link (u, v) carried on the given fiber path."""


def allow_all(u: str, v: str, fiber_path: tuple[str, ...]) -> bool:
    """Default optical check: no ROADM or spectrum data, so every link is allowed."""
    return True


@dataclass(frozen=True)
class FeasibilityConfig:
    """Settings for E* (decisions D16 and D6)."""

    max_fiber_hops: int = 2
    """Longest fiber path (in fibers) a new IP link may ride on."""
    max_km: float | None = None
    """Optical reach in km along the fiber path; ``None`` means no limit."""

    def __post_init__(self) -> None:
        if self.max_fiber_hops < 1:
            raise ValueError("max_fiber_hops must be at least 1")
        if self.max_km is not None and self.max_km <= 0:
            raise ValueError("max_km must be positive")


def fiber_length_km(fiber: nx.Graph, path: tuple[str, ...]) -> float:
    """Great-circle length of a fiber path, summed over its fibers."""
    return sum(great_circle_km(fiber, a, b) for a, b in pairwise(path))


def feasible_links(
    fiber: nx.Graph,
    config: FeasibilityConfig | None = None,
    optical_check: OpticalCheck = allow_all,
) -> dict[Edge, tuple[str, ...]]:
    """E*: every feasible IP link, with the fiber path it would ride on.

    The fiber path has the fewest fibers and, among those, the shortest
    great-circle length (ties, or PoPs without coordinates: the first path
    by name). Original links ride on their own fiber.
    """
    config = config or FeasibilityConfig()
    located = all(
        "Latitude" in attrs and "Longitude" in attrs
        for _, attrs in fiber.nodes(data=True)
    )
    if config.max_km is not None and not located:
        raise ValueError("max_km needs Latitude/Longitude on every PoP")

    def length(path: tuple[str, ...]) -> float:
        return fiber_length_km(fiber, path) if located else 0.0

    links: dict[Edge, tuple[str, ...]] = {
        edge_key(u, v): (u, v) for u, v in fiber.edges
    }
    hops = dict(nx.all_pairs_shortest_path_length(fiber, cutoff=config.max_fiber_hops))
    for u in sorted(fiber.nodes):
        for v in sorted(hops[u]):
            edge = edge_key(u, v)
            if u >= v or edge in links:
                continue
            # all_shortest_paths gives the paths with the fewest fibers.
            paths = [tuple(p) for p in nx.all_shortest_paths(fiber, u, v)]
            path = min(paths, key=lambda p: (length(p), p))
            if config.max_km is not None and length(path) > config.max_km:
                continue
            if optical_check(u, v, path):
                links[edge] = path
    return dict(sorted(links.items()))
