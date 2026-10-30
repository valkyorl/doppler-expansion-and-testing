"""Reconnaissance mechanisms (paper §3): each one produces an attack plan.

Implemented:

- ``oracle``: knows the true topology and routing; the upper bound (§3.2).
- ``random_plan``: knows nothing; picks random pairs (§3.2).

Planned for Phase 2: ``traceroute`` (§3.1.2) and ``rtt_ricci`` (§3.1.1).
"""
