"""Doppler 2026: the experiment for the draft paper *Doppler-security-26*.

Doppler is a moving-target defense against reconnaissance-dependent
link-flooding attacks. It reconfigures an optical network's IP topology so
that attack plans learned on earlier topologies stop working (low
"attack-plan transferability", paper Eq. 1), while benign traffic is still
carried within the operator's limits.

This package holds everything specific to that experiment. It is run from
the repository root, for example ``python -m doppler2026.run``.

Start with ``README.md`` in this folder for the state of the work, then
``docs/paper_map.md`` for which module implements which part of the paper. References to "PLAN §n" in docstrings point to the v0
development plan, archived at ``archive/v0/PLAN.md``.
"""
