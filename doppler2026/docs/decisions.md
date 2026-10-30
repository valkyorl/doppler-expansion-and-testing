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

## Proposed (need confirmation)

| # | Question | Proposed default | Needed by |
|---|---|---|---|
| D1 | Which damage measure defines τ (paper §2.4 lists several) | Benign traffic lost; the other §3.4 measures are reported alongside | Phase 1 |
| D2 | τ when the fresh plan does no damage (D(A*, G′) = 0) | τ = 0, and flag the candidate as "attack-immune at this budget" | Phase 1 |
| D3 | History length h, threshold τ_max, pool size K | h = 3, τ_max = 0.5, K = 50; all swept in experiments | Phase 3 |
| D4 | Attack budget R_A and number of pairs N_A | Sweep R_A as a multiple of the target link's capacity; N_A = 10 | Phase 1 |
| D5 | U_max and S_max | U_max = 0.8, S_max = 1.5 | Phase 3 |
| D6 | Optical reach | Configurable km limit; unlimited until real data exists | Phase 3 |
| D7 | Which attacker the defender assumes when building its history | Oracle (worst case); other mechanisms as an experiment axis | Phase 3 |
| D8 | Attacker endpoints | Every PoP can send and receive attack traffic | Phase 1 |
| D9 | "Acceptable subset" for random selection (§4.11) | Candidates whose secondary score is within 10% of the best | Phase 3 |
| D10 | Recon lag L versus epoch length T_R (§4.14) | L counted in epochs, swept 0–3 | Phase 4 |
