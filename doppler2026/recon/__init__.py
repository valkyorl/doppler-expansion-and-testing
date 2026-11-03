"""Reconnaissance mechanisms (paper §3): each one produces an attack plan.

- ``oracle``: knows the true topology and routing; the reference for η
  (§3.2). Its link ranking is also the true critical-link list C_k.
- ``random_plan``: knows nothing; picks random pairs (§3.2).
- ``traceroute``: observed traceroute graph, betweenness ranking (§3.1.2).
- ``rtt_ricci``: minimum-RTT threshold graphs, Ollivier-Ricci ranking
  (§3.1.1); also loads the stored regional reconstruction.
- ``inferred``: what both measured attackers share: turning an inferred
  graph and its edge ranking into a plan (§3.3).
- ``metrics``: topology recovery, P@k, path-level recovery (§3.4).
"""
