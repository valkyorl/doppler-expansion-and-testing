# Decisions

Choices that the paper does not settle, or project choices that shape the
implementation. Each entry says what was decided, by whom, and why. Proposed
entries are not used in code until confirmed.

## Decided

| # | Decision | Decided | Why |
|---|---|---|---|
| P1 | All experiment-specific files, including docs and tests, live in `doppler2026/` at the repository root, run as `python -m doppler2026.<module>` from the root | User, 2026-10-30; moved from `scripts/doppler2026/` on 2026-10-30 | Keeps the experiment, its documentation, and its tests together and separate from older campaigns. At `scripts/` the docs and tests would have sat among campaign scripts |
| P2 | Fix the preprocessing demand-direction and tunnel-cache bugs in shared code rather than working around them | User, 2026-10-30 | They are bugs; the experiment reuses this code. Side effect: results of existing `doppler`/`onset*` methods change |
| P3 | Compute Ollivier–Ricci curvature with the GraphRicciCurvature library | User, 2026-10-30 | Matches the tooling prior work likely used. Install on Python 3.13 is checked first in Phase 2 |
| P4 | Reconnaissance data: only the precomputed regional Ricci reconstruction exists; start with simulated measurements | User, 2026-10-30 | No raw RTT or traceroute data is in hand |
| P5 | Start implementation before the known gaps are closed, with a plug-in point for each | User, 2026-10-30 | None of the gaps blocks Phases 0–3 (see `PLAN.md` §9) |
| P6 | The new controller has its own epoch loop and does not go through `Simulation.perform_sim` | Plan, 2026-10-30 | Adding attack-plan history and attackers to `perform_sim` would mean rewriting shared code the experiment does not otherwise need |
| P7 | The path-based formulations (`onset`, `onset_v2`) keep their own copy of the demand-direction bug | Phase 0, 2026-10-30 | The experiment uses only the edge-flow formulation; per the "change only what is needed" rule, the path-based data builder is left alone. Recorded so it is not mistaken for fixed |

## Accepted parameter choices

Every accepted choice is a named setting in the experiment config, never a
hard-coded assumption, and every run saves its full config. Changing one
later means editing a config value and re-running the affected experiments
(see "Changing a decision later" below).

| # | Question | Accepted | Config setting | Accepted |
|---|---|---|---|---|
| D1 | Which damage measure defines τ (paper §2.4 lists several) | Benign traffic lost because of the attack (reduction in delivered benign traffic, as a fraction of benign demand). The other §3.4 measures are computed and saved alongside | `DamageConfig.tau_measure = "benign_loss"` | User, 2026-10-30 |
| D2 | τ when the fresh plan does no damage (D(A*, G′) = 0) | τ = 0, and the result is flagged "attack-immune at this budget" | `DamageConfig.zero_denominator = "zero"` | User, 2026-10-30 |
| D4 | Attack budget R_A and number of pairs N_A | R_A swept as a multiple of link capacity; N_A = 10 | `AttackConfig.budget`, `AttackConfig.n_pairs` | User, 2026-10-30 |
| D8 | Attacker endpoints | Every PoP can send and receive attack traffic | `AttackConfig.endpoints = None` (None means all PoPs) | User, 2026-10-30 |
| D11 | How an overloaded link divides capacity when measuring damage | Proportional: every flow on an overloaded link loses the same fraction (tail drop). Under the alternative, max-min fairness, each attack flow is larger than each benign aggregate, so attacks absorb all loss: on ANS no oracle attack caused any benign loss at 0.5×, 1×, or 2× link capacity | `DamageConfig.sharing = "proportional"` | User, 2026-10-30 |
| E1 | Correct the link-capacity model only in the new in-memory path | The experiment uses `onset.te.deliver_flows`, where every link carries at most its capacity in total. `onset.te.evaluate()` keeps its older model unchanged (see "Known issue in shared code" below) | — | User, 2026-10-30 |

### Known issue in shared code (not fixed, by decision E1)

`onset.te.evaluate()` drops traffic hop by hop and groups flows by their hop
number as well as the link. Flows that reach the same link at different hop
numbers never compete for its capacity, so a link can carry more than its
capacity with no loss. Minimal case: a 100-capacity link b→c carrying flow
a→b→c (second hop) and flow b→c (first hop), 100 each, carries 200 with zero
loss (reproduced in `tests/test_te_in_memory.py`, which checks that the new
path shares the link 50/50 instead). This affects the loss and throughput
results of every existing method that uses `evaluate()`. It was left
unchanged so past results stay reproducible; whether to fix it is open.

### Changing a decision later

- Code: change the config value. No logic is written around a specific value.
- Results: τ's numerator and denominator and every damage measure are saved
  per (plan, topology) pair, so τ under a different D1 or D2 can be
  recomputed from saved files. Multi-epoch Doppler runs must still be re-run,
  because τ decided which topologies were chosen.
- Exception: the fifth §3.4 measure (attack budget needed for a given level
  of disruption) needs a search over budgets. It is computed only in the
  reconnaissance experiments, so using it inside the security filter would
  need new code.

## Interpretations made in Phase 1 (need confirmation)

The paper's wording leaves these open. Each was implemented as described and
can be changed in one place.

| # | Paper text | Interpretation | Where |
|---|---|---|---|
| I1 | "the amount of physical-link capacity driven above its safe operating threshold" (§3.4) | Total capacity of links whose offered utilization exceeds the safe threshold (default 0.8, `DamageConfig.safe_threshold`) | `damage.py` |
| I2 | "the fraction of benign traffic traversing congested links" (§3.4) | Share of benign demand whose routes cross at least one link with offered utilization above 1, weighted by the share of its traffic on such routes | `damage.py` |
| I3 | Oracle "ranks physical links according to the amount of traffic that can be concentrated on them using the available attacker endpoints" (§3.2) | For each directed link, take the N_A endpoint pairs that put the largest share of their traffic on it under the network's routing; the link's score is the attack traffic those pairs would place on it with the equal budget split (Eq. 8). Many links can absorb the whole budget, so ties go to the link the routing uses most (sum of all endpoint pairs' shares on it, its centrality), then more pairs, then lower capacity, then link name. Benign load is not used, because the paper's oracle knows topology and routing, not traffic. (The first version broke ties by name alone and picked a lightly used link; changed during Phase 1) | `recon/oracle.py` |
| I4 | Damage is measured "against topology G" (§2.4) | Benign and attack traffic are routed together with the network's routing method (ECMP by default, which does not react to traffic). Every link then carries at most its capacity, shared between flows by D11 | `damage.py`, `routing.py` |
| I5 | Benign traffic (§4.3 input 4) | Gravity model with exponential PoP masses, scaled so the busiest link's offered utilization is a chosen value (an experiment setting). The repo's `*_base_tm_0.00e+00_gravity.txt` files are all zeros | `traffic.py` |
| I6 | Link capacities (§2.1, c_e) | Topology Zoo files give none, so every link gets 100 Gbps (configurable), as elsewhere in the repo | `topology.py` |

## Proposed (need confirmation)

| # | Question | Proposed default | Needed by |
|---|---|---|---|
| D3 | History length h, threshold τ_max, pool size K | h = 3, τ_max = 0.5, K = 50; all swept in experiments | Phase 3 |
| D5 | U_max and S_max | U_max = 0.8, S_max = 1.5 | Phase 3 |
| D6 | Optical reach | Configurable km limit; unlimited until real data exists | Phase 3 |
| D7 | Which attacker the defender assumes when building its history | Oracle (worst case); other mechanisms as an experiment axis | Phase 3 |
| D9 | "Acceptable subset" for random selection (§4.11) | Candidates whose secondary score is within 10% of the best | Phase 3 |
| D10 | Recon lag L versus epoch length T_R (§4.14) | L counted in epochs, swept 0–3 | Phase 4 |
