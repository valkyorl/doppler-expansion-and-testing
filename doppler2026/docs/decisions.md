# Decisions

Choices that the paper does not settle, or project choices that shape the
implementation. Each entry says what was decided, by whom, and why. Proposed
entries are not used in code until confirmed.

## Decided

| # | Decision | Decided | Why |
|---|---|---|---|
| P1 | All experiment-specific files, including docs and tests, live in `doppler2026/` at the repository root, run as `python -m doppler2026.<module>` from the root | User, 2026-10-30; moved from `scripts/doppler2026/` on 2026-10-30 | Keeps the experiment, its documentation, and its tests together and separate from older campaigns. At `scripts/` the docs and tests would have sat among campaign scripts |
| P2 | Fix the preprocessing demand-direction and tunnel-cache bugs in shared code rather than working around them | User, 2026-10-30 | They are bugs; the experiment reuses this code. Side effect: results of existing `doppler`/`onset*` methods change |
| P3 | Compute Ollivier–Ricci curvature with the GraphRicciCurvature library | User, 2026-10-30 | Matches the tooling prior work likely used. How it is installed on Python 3.13: P8 |
| P4 | Reconnaissance data: only the precomputed regional Ricci reconstruction exists; start with simulated measurements | User, 2026-10-30 | No raw RTT or traceroute data is in hand |
| P5 | Start implementation before the known gaps are closed, with a plug-in point for each | User, 2026-10-30 | None of the gaps blocks Phases 0–3 (see `PLAN.md` §9) |
| P6 | The new controller has its own epoch loop and does not go through `Simulation.perform_sim` | Plan, 2026-10-30 | Adding attack-plan history and attackers to `perform_sim` would mean rewriting shared code the experiment does not otherwise need |
| P7 | The path-based formulations (`onset`, `onset_v2`) keep their own copy of the demand-direction bug | Phase 0, 2026-10-30 | The experiment uses only the edge-flow formulation; per the "change only what is needed" rule, the path-based data builder is left alone. Recorded so it is not mistaken for fixed |
| P8 | Install GraphRicciCurvature 0.6.1 with `--no-deps`, plus its real dependencies (networkit, POT, python-louvain) | User, 2026-10-30 (Phase 2) | The library pins `scipy<=1.13.1`, which exists only for Python ≤ 3.12; moving to 3.14 would not help, and 0.6.1 is the newest release. The library's code never imports SciPy, so the project keeps SciPy 1.18.1. Tests check its curvature against hand-computed values. Rejected: a separate Python 3.12 environment (an older Python was not acceptable); our own implementation (would not be the published tool) |

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
| D12 | How a silent traceroute hop enters Ĝ_tr (§3.1.2, Eq. 5) | It breaks the path: only two consecutive hops that both answered give an edge. No false links; some real links may be missed | `traceroute.observed_graph` (no setting; the alternatives would be new code) | User, 2026-10-30 |
| D13 | How ε is expressed in the sweep (§3.1.1, Eq. 3) | As a quantile of all measured minimum RTTs, so a sweep gives similar graph densities on networks of any size. ε in ms is saved alongside | `ReconEvalConfig.epsilon_quantiles` | User, 2026-10-30 |
| D14 | Disruption level for the fifth §3.4 measure (budget needed to disrupt) | "Any benign loss": the smallest budget at which benign loss exceeds a tiny level (one millionth of benign demand, above numerical noise), with the plan's pairs fixed. Matches §3.3: "measure when the attack begins to affect benign traffic" | `DamageConfig.disruption_level = 1e-6` | User, 2026-10-30 |
| D15 | What the oracle knows (§3.2), resolving open issue O1. **Flagged for review: see "Choices flagged for review" below** | Option (b): the oracle also knows the benign traffic matrix. It is the fresh plan A* in η (Eq. 10) and τ (Eq. 1). How it chooses (approved by the user): each link in the paper oracle's ranking (I3) is a candidate, attacked with the up to N_A pairs that send the most traffic over it; each candidate is simulated against the benign traffic, and the one with the most damage under the τ measure (benign loss, D1) is the target; near-ties keep the ranking order. The paper's oracle (topology and routing only) stays available, and true critical links for P@k (Eq. 9) still come from its ranking (§3.4) | `AttackConfig.oracle_knowledge = "benign"` (`recon/oracle.benign_oracle_plan`); the paper's oracle is `"routing"`. The experiment's copy is `ReconEvalConfig.oracle_knowledge` | User, 2026-11-03 |
| E1 | The link-capacity bug in `onset.te.evaluate()` | **Fixed** (user, 2026-11-03; originally left unfixed on 2026-10-30). `evaluate()` now uses the same loss model as `deliver_flows`, keeping its max-min sharing: every link carries at most its capacity in total. See "Fixed bug in shared code" below | — | User, 2026-11-03 |
| D3 | History length h, threshold τ_max, pool size K | h = 3, τ_max = 0.5, K = 50 (defaults; all swept in experiments) | Named when built in Phase 3 | User, 2026-11-03 |
| D5 | U_max and S_max | U_max = 0.8, S_max = 1.5 | Named when built in Phase 3 | User, 2026-11-03 |
| D6 | Optical reach | No km limit by default (configurable); D16's two-hop rule bounds E* | Named when built in Phase 3 | User, 2026-11-03 |
| D7 | Which attacker the defender assumes when building its history | Traceroute, following §4.8 ("applying the reconnaissance-to-attack procedure from Section 3"); the oracles and RTT/Ricci are experiment axes. Replaces the earlier proposal (oracle) | Named when built in Phase 3 | User, 2026-11-03 |
| D9 | "Acceptable subset" for random selection (§4.11) | Candidates whose secondary score is within 10% of the best; uniform seeded choice among them | Named when built in Phase 3 | User, 2026-11-03 |
| D16 | Fiber graph G_F and feasible links E* (§4.4); no fiber data exists | Each link of the network's original topology is one fiber, as in the existing AlpWolf model. E* = original links plus PoP pairs exactly two fiber hops apart, which is the old Doppler's "max" candidate set (`preprocessing.compute_candidate_links`). An optional km limit (D6). ROADM and spectrum checks stay a pluggable "allowed" hook: no ROADM data exists, and `network_model.py` names ROADMs but never models them | Named when built in Phase 3 | User, 2026-11-03 |
| D17 | Capacity C_e of a newly created link (Eq. 15–16) | One circuit at the network's median link capacity; existing links keep their own capacity. (The old Doppler gave every circuit a fixed 100 Gb/s, which matches the default capacity of our topologies) | Named when built in Phase 3 | User, 2026-11-03 |
| D18 | Transponders txp(v) (§4.5, Eq. 11); no placement data exists | txp(v) = degree of v in the original topology (one per link, as in AlpWolf; no spares, which §4.5 says are not required). Spares are an experiment axis, placed like the old Doppler's `dynamic_doppler` strategy (extra transponders at the highest-betweenness PoPs). The files in `data/txp/` come from the legacy `rank_transponder_alloc.py` and are not used by default | Named when built in Phase 3 | User, 2026-11-03 |
| D19 | Path stretch ℓ(P) (Eq. 17) | ℓ = great-circle km along the path; under ECMP the longest path a demand uses counts; reference P⁰ = the original topology G_0. Hop count as an alternative setting | Named when built in Phase 3 | User, 2026-11-03 |
| D20 | Connectivity and redundancy (§4.7) | Connected, every demand routable. 2-edge-connectivity is a setting, off by default, always reported | Named when built in Phase 3 | User, 2026-11-03 |
| D21 | Attack budget R_A inside the security filter (Eq. 21) | 2× median link capacity; budget sweeps as an experiment axis | Named when built in Phase 3 | User, 2026-11-03 |
| D22 | How the MILP produces K different candidates (§4.11, Eq. 31) | Existing HiGHS enumeration (no-good cuts) plus a new mode that randomizes objective weights per solve, used by default. The old Gurobi overlap objective (Eq. 18) is the structural-churn baseline | Named when built in Phase 3 | User, 2026-11-03 |
| D23 | Local candidate set (§4.10) | Old "conservative" set (top 10% of links by edge betweenness, one endpoint moved to a neighbour) plus links around the targets of plans in the history; "liberal" as a middle option; expanded set = all of E* | Named when built in Phase 3 | User, 2026-11-03 |
| D24 | Secondary objective for selection (§4.11) | MLU (benign demand, ECMP); stretch and number of changes are alternative settings. Works with D9 | Named when built in Phase 3 | User, 2026-11-03 |
| D25 | Solver and time budget T_opt (§4.12) | HiGHS (already used), T_opt = 60 s per epoch, the old simulator's default (old scripts swept 0.5, 1, and 5 minutes, and K from 10 to 100). A Gurobi backend is added only if HiGHS is too slow to fill the pool | Named when built in Phase 3 | User, 2026-11-03 |
| D26 | Measurement settings of the traceroute attacker whose plans fill the history (D7) | The Phase 2 headline settings: every PoP a vantage point, 10% silent routers; measurement seed = epoch number, so each epoch's plan comes from fresh probes | Named when built in Phase 3 | User, 2026-11-03 |
| D27 | The defender's demand estimate D_t (§4.3 input 4) | D_t = the true benign demand (a perfect estimate), the same matrix every epoch. Estimation error is a later experiment axis | Named when built in Phase 3 | User, 2026-11-03 |

### Fixed bug in shared code (E1)

`onset.te.evaluate()` used to drop traffic hop by hop and group flows by
their hop number as well as the link. Flows that reached the same link at
different hop numbers never competed for its capacity, so a link could carry
more than its capacity with no loss. Minimal case: a 100-capacity link b→c
carrying flow a→b→c (second hop) and flow b→c (first hop), 100 each, carried
200 with zero loss.

Fixed 2026-11-03 at the user's request: `evaluate()` now uses the solver of
`deliver_flows` (`_capacity_constrained_delivery`) with max-min sharing, the
sharing rule it already used. Regression test:
`tests/te_engine_test.py::test_flows_at_different_hops_share_link_capacity`.

**Side effect:** loss and throughput of every existing method that uses
`evaluate()` (`doppler`, `onset*`, and the other `Simulation` methods) change
whenever links are overloaded, so results produced before the fix are not
comparable with results after it. On ANS with ECMP and the Phase 1 benign
traffic scaled 3× and 4×, reported loss rose from 3.9% to 8.0% and from 9.6%
to 13.7%, and the most loaded link went from carrying 1.26× and 1.34× its
capacity to 1.0×. Results without overload are unchanged.

### Choices flagged for review

Decisions the user expects may change. Each one lists what a change would
cost, so the cost stays known as the experiment grows.

- **D15, the oracle's knowledge (option b).** It departs from the paper's
  wording in §3.2 ("knows topology and routing"), so the paper text or the
  choice may need to change once results are in.
  - Code: the setting `AttackConfig.oracle_knowledge` (in the
    reconnaissance experiment, `ReconEvalConfig.oracle_knowledge`) keeps
    both oracles, so switching back means changing one value.
  - Phase 2 results: no re-run needed. Every row of `transferability.csv`
    has η against both oracles (`ratio` against the chosen one,
    `other_ratio` against the other, with `oracle_knowledge` naming which is
    which), and both oracles are attackers in their own right
    (`oracle_benign`, `oracle`). Switching means pointing the figure
    scripts at `other_ratio`, or re-running (about 19 minutes) to swap
    the columns. RQ1 and RQ2 do not
    change: they use the oracle's ranking only as ground truth for
    critical links (I3), which is set separately (see below).
  - Phase 3–4 results: τ decides which topologies Doppler accepts, so every
    multi-epoch run must be re-run under the other oracle. To keep this
    affordable, `damage.relative_damage` always records the damage of both
    oracles' fresh plans for every (plan, topology) pair, so τ and η under
    either oracle can be recomputed from saved files for single-step
    comparisons.
  - Caveat: option (b) makes the oracle a much stronger baseline but not a
    proven upper bound. It searches over target links with a fixed rule for
    choosing pairs, so another plan can still, rarely, do more damage.
    η values are stored unclipped, and any η > 1 is reported.
    Observed in the 2026-11-03 run: 0.6% of measured plans at 1× and
    0.4% at 4× have η > 1 (largest 1.21), against 15% at 2× under the
    paper's oracle.
  - Critical links for P@k (Eq. 9) stay defined by topology and routing,
    as in §3.4, unless the user decides otherwise.

- **I3, how the paper's oracle ranks links** (accepted 2026-11-03; no change
  planned). It is in one function, `recon/oracle.rank_links`, but three
  things build on it: the paper's oracle, the true critical links of RQ2
  (P@k, path-level recovery), and the candidate targets the benign-aware
  oracle (D15) tries. A different ranking means rerunning Phase 2 and, from
  Phase 3 on, every Doppler run. The traceroute and RTT attackers share the
  same per-link scoring (I8), which would likely change with it.
- **I4, damage measured with the network's own routing** (accepted
  2026-11-03; no change planned). It sits in `damage.evaluate_damage` and
  `routing.py`. Alternatives (for example routing attack traffic separately,
  or a TE method that reacts to traffic) need new code there, invalidate the
  ECMP route cache's assumption that routes do not depend on traffic, and
  change every damage, η, and τ result, so all experiments would be rerun.

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

I3 and I4 were accepted by the user on 2026-11-03 but remain
interpretations of the paper, not settled paper text: they stay listed here,
with what changing them would involve, so they can be revisited (see
"Choices flagged for review").

The paper's wording leaves these open. Each was implemented as described and
can be changed in one place.

| # | Paper text | Interpretation | Where |
|---|---|---|---|
| I1 | "the amount of physical-link capacity driven above its safe operating threshold" (§3.4) | Total capacity of links whose offered utilization exceeds the safe threshold (default 0.8, `DamageConfig.safe_threshold`) | `damage.py` |
| I2 | "the fraction of benign traffic traversing congested links" (§3.4) | Share of benign demand whose routes cross at least one link with offered utilization above 1, weighted by the share of its traffic on such routes | `damage.py` |
| I3 (accepted, 2026-11-03) | Oracle "ranks physical links according to the amount of traffic that can be concentrated on them using the available attacker endpoints" (§3.2) | For each directed link, take the N_A endpoint pairs that put the largest share of their traffic on it under the network's routing; the link's score is the attack traffic those pairs would place on it with the equal budget split (Eq. 8). Many links can absorb the whole budget, so ties go to the link the routing uses most (sum of all endpoint pairs' shares on it, its centrality), then more pairs, then lower capacity, then link name. Benign load is not used, because the paper's oracle knows topology and routing, not traffic. (The first version broke ties by name alone and picked a lightly used link; changed during Phase 1) | `recon/oracle.py` |
| I4 (accepted, 2026-11-03) | Damage is measured "against topology G" (§2.4) | Benign and attack traffic are routed together with the network's routing method (ECMP by default, which does not react to traffic). Every link then carries at most its capacity, shared between flows by D11 | `damage.py`, `routing.py` |
| I5 | Benign traffic (§4.3 input 4) | Gravity model with exponential PoP masses, scaled so the busiest link's offered utilization is a chosen value (an experiment setting). The repo's `*_base_tm_0.00e+00_gravity.txt` files are all zeros | `traffic.py` |
| I6 | Link capacities (§2.1, c_e) | Topology Zoo files give none, so every link gets 100 Gbps (configurable), as elsewhere in the repo | `topology.py` |

## Interpretations made in Phase 2 (need confirmation)

| # | Paper text | Interpretation | Where |
|---|---|---|---|
| I7 | Vantage points M (§3.1.1) and "the effect of measurement coverage" (§3.7) | By default every PoP is a vantage point; coverage is an experiment axis (share of PoPs, drawn at random with a recorded seed). With full coverage traceroute sees every link directly (the one-hop probe from a to b), so silent routers hide nothing; the coverage axis is what makes non-response matter | `TracerouteConfig.vantage_points`, `RttConfig.vantage_points`, `ReconEvalConfig.vantage_fractions` |
| I8 | "For a candidate target e, we identify source–destination pairs whose inferred paths traverse e. The attacker selects up to N_A such pairs" (§3.3) | The target is the top-ranked inferred edge that some endpoint pair crosses. Inferred paths are hop-count shortest paths in Ĝ; a pair's share is the fraction of its shortest paths crossing e (the term of Eq. 6). Each direction of e is scored like the oracle scores a link (I3) and the better direction is attacked. Endpoints are D8's endpoints that appear in Ĝ | `recon/inferred.plan_from_ranking` |
| I9 | Traceroute collection and alias resolution (§3.1.2, §3.5) | Simulated. Each probe follows one real forwarding path (drawn by its ECMP share, like Paris traceroute). Each router is silent with probability `non_response`, drawn once per router; destinations always answer. Hops are PoPs, which equals perfect alias resolution | `traceroute.simulate` |
| I10 | Ollivier–Ricci curvature of Ĝ_ε (§3.1.1) | Computed on Ĝ_ε without weights (every edge length 1), library defaults otherwise (α = 0.5, exact optimal transport). Eq. 3 defines Ĝ_ε by the threshold alone. Should be checked against the prior method [?] once it is identified | `rtt_ricci.ricci_curvature` |
| I11 | Repeated RTT measurements, minimum kept (Eq. 2) | Simulated. One probe = propagation delay of a forward and a return path (each drawn by its ECMP share; great-circle length × `route_factor` 1.0, at 200 km/ms in fiber) plus exponential queuing delay (mean 1 ms). 10 probes per pair. Each unordered pair is probed once from the smaller name | `rtt_ricci.simulate`, `RttConfig` |
| I12 | Topology recovery only against independently validated ground truth (§3.4) | In simulation the true network is the one the measurements were generated from, so it is ground truth by construction; rows say `ground_truth_source = simulation`. The regional "ground truth" is not validated (audit #8), so RQ1 is refused there; its RQ2 and RQ3 rows are computed but flagged `ground_truth_independent = False` | `recon/metrics.py`, `experiments/recon_eval.py` |
| I13 | Evaluating reconnaissance on operational networks (§3.5, §3.7) | On the regional network only the stored RTT/Ricci reconstruction is evaluated; no traceroute or RTT measurements are simulated there. No real traceroute data exists for it (P4), and its "ground truth" graph has unknown provenance (audit #8) and partly default capacities, so a simulated attacker on it would be one more simulated network, not a check of real measurements. Its RQ2 and RQ3 figures therefore show only the oracles, no-knowledge plans, and RTT/Ricci. **Confirmed by the user, 2026-11-03** | `experiments/recon_eval.attempts` |

## Open issues found in Phase 2

- **O1. The oracle is not an upper bound on damage.** The paper calls the
  oracle "an upper bound on the value of topology reconnaissance" (§3.2) and
  ranks links by the attack traffic it can concentrate on them. It does not
  know benign traffic, so on most networks every link can absorb the whole
  budget and the choice comes down to tie-breaks (I3). Measured attackers
  often pick a link with more benign traffic and cause more benign loss:
  η reached 10.7 on ANS in the Phase 2 smoke run. Values are stored
  unclipped. Options: (a) keep the paper's oracle and report η > 1 as a
  finding; (b) give the oracle benign-traffic knowledge (rank by expected
  benign loss), which makes it a true upper bound but departs from §3.2's
  wording; (c) keep both, using (b) as the denominator of η and τ. This
  affects τ in Phases 3–4 as well, so it needs a decision before Phase 3.
  **Resolved 2026-11-03: option (b), decision D15.**

## Proposed (need confirmation)

| # | Question | Proposed default | Needed by |
|---|---|---|---|
| D10 | Recon lag L versus epoch length T_R (§4.14) | L counted in epochs, swept 0–3 | Phase 4 |
