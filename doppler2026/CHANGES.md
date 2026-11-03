# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first.

## 2026-11-03: Interpretation I13, no simulated attackers on the regional network

- `docs/decisions.md`: added I13, confirmed by the user. On the regional
  network only the stored RTT/Ricci reconstruction is evaluated, so its RQ2
  and RQ3 figures have no traceroute entry. This was already how the code
  behaved but was not recorded.
- `experiments/recon_eval.py`: the comment where regional returns early now
  cites I13. No behavior change.

## 2026-11-03: Decision D15, the oracle knows benign traffic (resolves O1)

- `docs/decisions.md`: added D15 (option (b) for open issue O1, decided by
  the user), marked O1 resolved, and added "Choices flagged for review",
  which lists what changing D15 later would cost.

### Implementation

Behavior change: τ and η now divide by the benign-aware oracle by default,
so every η differs from the 2026-10-30 run. The paper's oracle is unchanged
and still available.

- `model.py`: new setting `AttackConfig.oracle_knowledge` (`"benign"`, the
  default, or `"routing"`, the paper's oracle), validated against
  `ORACLE_KNOWLEDGE`. `RelativeDamage` gained `oracle_knowledge` and the
  comparison against the other oracle (`other_oracle_knowledge`,
  `other_denominator`, `other_ratio`, `other_attack_immune`,
  `other_fresh_damage`), all in `as_row()`. Why: D15, plus keeping the
  choice cheap to change ("Choices flagged for review").
- `recon/oracle.py`: new `benign_oracle_plan` (the selection rule approved
  for D15: every link in the `rank_links` ranking is tried with its pairs and
  simulated against benign traffic; the most damaging under the τ measure
  wins; near-ties keep the ranking order) and `fresh_oracle_plan`, which
  picks the oracle from the setting. `oracle_plan` and `rank_links` are
  unchanged, so critical links for P@k (Eq. 9) are unchanged.
- `damage.py`: `relative_damage` builds the fresh plan A* with
  `fresh_oracle_plan` and always evaluates both oracles (new optional
  `other_fresh_plan` to reuse one). The D2 zero rule moved into a helper
  used for both ratios.
- `experiments/recon_eval.py`: new `ReconEvalConfig.oracle_knowledge`
  (saved in `config.json`). Both oracles are attackers (`oracle_benign`,
  `oracle`) and are rebuilt at every budget, because the benign-aware
  oracle's choice depends on the budget. `plan_target` now records the
  target of the plan actually evaluated at that budget (the same as before
  for every non-oracle plan).
- `figures/common.py`: the benign-aware oracle gets palette slot 5 (magenta),
  marker `v` and its own dash, so no existing attacker changes color.
  Labels: "Oracle (benign)" and "Oracle (paper)".
- `figures/fig_rq3_attack_impact.py`: the table shows η against both oracles.
- Tests:
  - `tests/test_d26_damage.py`: new hand-checked case (path x–y–z, benign
    traffic only on z→y): the paper's oracle picks x→y by tie-break and does
    no benign damage; the benign-aware oracle picks z→y and loses 80/180.
    Also checks both ratios are recorded and an unknown setting is refused.
    The existing ratio-1 test now states `oracle_knowledge="routing"`,
    because it tests the paper's oracle against itself.
  - `tests/test_d26_phase1_ans.py`: same change to the ratio-1 test, plus
    two new tests (the benign-aware oracle has ratio 1 against itself and
    does at least as much damage as the paper's oracle).
  - `tests/test_d26_phase2_networks.py`: expects the fifth attacker and
    checks each oracle's ratio against itself.
- Docs: `README.md` (status, module table, example), `PLAN.md` (status, the
  cost of the fresh plan in the Phase 3 filter, layout, §10 columns),
  `docs/paper_map.md` (new §3.2 extension row), `docs/decisions.md` (D15
  completed with the selection rule and setting names).

### Phase 2 re-run under D15

- Run `data/results/doppler2026/recon_eval/phase2-d15-2026-11-03/` (local),
  all six networks, 19 minutes (was 12; the benign-aware oracle simulates one
  attack per link, and every row now evaluates both oracles). Figures and
  tables in `figures/out/` were regenerated from it. The 2026-10-30 run is
  kept for comparison.
- RQ1 and RQ2 are unchanged (they do not use the oracle's damage).
- RQ3:
  - The benign-aware oracle does much more benign damage than the paper's
    oracle: at R_A = 2× the paper's oracle reaches only 0.17 (ANS) to 0.64
    (sprint) of it.
  - η > 1 is now rare: 0.6% of measured plans at 1× and 0.4% at 4× (largest
    1.21, RTT/Ricci on bellCanada at 1×), none at 2×. Under the paper's
    oracle it was 15% at 2×. As expected, the oracle is a strong baseline,
    not a proven upper bound.
  - Below 1× link capacity neither oracle causes any benign loss, so every
    row at 0.25× and 0.5× is attack-immune and η = 0 there (D2).
  - Budget to disrupt: the benign-aware oracle needs 0.5–0.73× capacity.
    It is not always the lowest (bellCanada: 0.58 against 0.5 for the
    paper's oracle and traceroute), because its pairs are chosen at the
    reference budget (1×) for the most damage there, not for the earliest
    onset of loss.

## 2026-10-30: Phase 2 (reconnaissance) — complete

### Full run and figures

- Run `data/results/doppler2026/recon_eval/phase2-2026-10-30/` (local;
  `data/` is git-ignored): five Topology Zoo networks plus the regional
  network, 12 minutes (bellCanada and surfNet about 5 minutes each).
- Figures and tables are in `figures/out/` (PDF, PNG, Markdown, LaTeX), made
  by `table_networks`, `fig_rq1_recovery`, `fig_rq2_critical_links` and
  `fig_rq3_attack_impact`. After a first look, legends were moved above the
  panels (they covered titles) and budget ticks show 0.25 … 4.
- Results at a glance (headline settings: full coverage, 10% silent
  routers, ε at the 0.2 quantile):
  - **RQ1:** traceroute F1 = 1.0 on every network at full coverage, and
    0.82–0.95 at 25% coverage with 30% silent routers. RTT/Ricci F1 is
    0.38–0.64 and falls sharply with coverage (≤ 0.17 at 25%).
  - **RQ2:** traceroute P@k = 1 on four networks but 0–0.7 on sprint. RTT
    P@k is mostly low (0–0.67); path-level recovery is higher (up to 0.8).
  - **RQ3:** every measured attacker beats no knowledge. The budget needed
    to disrupt is 0.5–0.98× link capacity for traceroute, 0.61–1.89× for
    RTT/Ricci, and 2–3.75× for random plans. Traceroute matches the oracle
    (η = 1) on four of five networks.
  - **O1 confirmed:** 15% of non-oracle plans at R_A = 2× have η > 1 (up to
    4.75), and at 4× the worst random plans exceed the oracle on several
    networks. The oracle as defined in §3.2 is not an upper bound.

### Still open

- **Open issue O1 needs a decision before Phase 3** (`docs/decisions.md`).
- Interpretations I7–I12 need confirmation.
- Comcast is not in the run (PLAN §9). The §3.3 oracle-rate-allocation
  sensitivity experiment is not built (PLAN §7).
- The dataviz palette validator could not be run (Node.js is not
  installed). The four colors are the reference palette's first four slots,
  and every series also has its own marker and line style.
- Later idea (user): whether a Gurobi license speeds up the Phase 3 MILP.

### Decisions

- P8: install GraphRicciCurvature with `--no-deps`. Its `scipy<=1.13.1` pin
  needs Python ≤ 3.12, and the library never imports SciPy.
- D12 silent traceroute hops break the path; D13 ε as an RTT quantile; D14
  budget to disrupt = the smallest budget that causes any benign loss.
- Interpretations I7–I12 and open issue O1 added (need confirmation).

### Changes outside this folder

- **`pyproject.toml`:** new optional extra `doppler2026` (networkit, POT,
  python-louvain), which is PLAN §5 item 4 in a changed form (P8).
  Base dependencies are unchanged.
- **`.venv`:** installed networkit 11.2.2, POT 0.9.7, python-louvain 0.16,
  and GraphRicciCurvature 0.6.1 (no-deps). SciPy stays at 1.18.1.

### New and changed files in this folder

- **`recon/inferred.py` (new):** the shared §3.3 step: inferred graph + edge
  ranking → plan (I8); shortest-path counts; Eq. 6 betweenness.
- **`recon/traceroute.py` (new):** simulated probes (I9), Ĝ_tr (Eq. 5, D12),
  betweenness ranking (Eq. 6), path statistics (§3.5).
- **`recon/rtt_ricci.py` (new):** simulated minimum RTTs (Eq. 2, I11), Ĝ_ε
  (Eq. 3, D13), Ollivier–Ricci ranking (Eq. 4, I10), loaders for the
  regional reconstruction and ground truth. Curvature runs in-process (see
  "Fork fix" below).
- **`recon/metrics.py` (new):** precision/recall/F1 (refused unless ground
  truth is independent, I12), P@k (Eq. 9), path-level recovery.
- **`recon/oracle.py` (changed):** ranking split out as `rank_links` (the true
  critical links C_k). Plan choice is unchanged; the Phase 1 tests pass.
- **`damage.py` (changed):** `budget_to_disrupt` (§3.4 bullet 5, D14).
- **`model.py` (changed):** `DamageConfig.disruption_level`.
- **`attack_plans.py` (changed):** `rescale` (same pairs, new budget).
- **`topology.py` (changed):** `great_circle_km`.
- **`routing.py` (changed):** caches ECMP routes per graph. ECMP was about 2/3
  of running time. Results are identical: checked by a test and by
  comparing two full smoke runs, whose numbers matched exactly.
- **`results.py` (new):** run folders, `config.json` with git commit and
  package versions, tidy CSVs (PLAN §10).
- **`experiments/recon_eval.py` (new):** RQ1–RQ3 on the five Topology Zoo
  networks plus the regional network. It writes `networks.csv`,
  `recon.csv` and `transferability.csv`. Comcast is not in the default list.
- **`figures/` (new):** `common.py` and scripts for Table 1, RQ1, RQ2, RQ3.
- **Tests (new):** `tests/test_d26_recon.py` and
  `tests/test_d26_phase2_networks.py`, 24 tests, including curvature values
  computed by hand (dumbbell bridge κ = −1/3, 4-cycle κ = 1/2).
- **Docs:** README (install steps, experiment), PLAN (status, layout, §5,
  §7, §9), `docs/decisions.md`, `docs/paper_map.md`, `docs/references.md`,
  `docs/diagrams/modules.md`, `recon/__init__.py`.

### Fork fix (found while finishing Phase 2)

- **Problem:** GraphRicciCurvature always forks a process pool, even with
  `proc=1`. The full test suite showed that HiGHS (the TE engine's MCF and
  the MILP) leaves worker threads behind, and Phase 3 will run HiGHS and
  Ricci in one process. Forking a process with threads running can deadlock
  the child. Limiting networkit to one thread, the first workaround, cannot
  stop other libraries' threads.
- **Fix (`recon/rtt_ricci.py`):** while curvature is computed, the
  library's `multiprocessing` is swapped for a stand-in that runs the
  library's own per-edge function in this process. Its algorithm is not
  changed. The library memoizes per-node results by node index, which only
  worked because the memo lived in short-lived children; the memo is now
  cleared before and after every call. Otherwise the second graph would
  reuse the first graph's neighbours: tests crashed with an IndexError until
  this was added, and without a crash it could have given wrong curvature.
- **Tests:** in-process curvature equals the library's pooled run, even after
  other graphs were computed; and no process pool is started. The full suite
  no longer shows the fork warning, except in the one test that runs the
  library's pool on purpose as the reference.

### Checks so far

- `pytest tests doppler2026/tests`: 224 passed. Ruff is clean.
- Smoke run (ANS, sprint, regional): measured attackers beat random. At
  full coverage traceroute recovers the topology exactly (F1 = 1.0); RTT
  F1 is about 0.55. Mean P@5 is 0.68 for traceroute and 0.07 for RTT on
  ANS. The oracle needs 0.86× link capacity to disrupt ANS; random plans
  need about 3×.

## 2026-10-30: Phase 1 (attack plans and damage)

### Decisions

- Recorded D1, D2, D4, D8 as accepted, and the new D11 (proportional loss)
  and E1 (correct the capacity model only in the new path), in
  `docs/decisions.md`. Added interpretations I1 to I6 where the paper's
  wording leaves room; I3 (oracle tie-break) was revised during the phase.

### Changes outside this folder

- **Changed `src/onset/te/engine.py`** (PLAN §5 item 2).
  - *Added `route_demands()`:* routes demands in memory with any TE method.
    The routing dispatch inside `evaluate()` was moved into it unchanged;
    `evaluate()` now calls it and behaves exactly as before.
  - *Added `deliver_flows()` and `FlowDelivery`:* pushes labelled flows
    through routed links and reports delivery per label. Why: damage under
    D1 needs benign loss kept apart from attack loss between the same two
    PoPs, which `evaluate()` merges and only writes to files.
  - *Added a capacity-correct loss model for `deliver_flows()`*
    (`_capacity_constrained_delivery`, `_link_rule`). Why: the older loop in
    `evaluate()` lets a link carry more than its capacity when flows reach
    it at different hop numbers (found while checking Phase 1 on ANS: an
    attack that overloaded its target link to 114% caused zero benign loss).
    The new model makes every link carry at most its capacity, with
    proportional or max-min sharing (D11). `evaluate()` was not changed
    (decision E1); the bug there is documented in `docs/decisions.md`.
- **Changed `src/onset/te/__init__.py`:** exports the new functions.
- **Created `tests/test_te_in_memory.py`:** 18 tests for the new functions,
  including the hop-number case that exposes the old bug and a check on 10
  random networks that no link ever carries more than its capacity.

### New files in this folder

- **`model.py`:** data types and settings (attack plan, routing, attack,
  damage settings, damage report, relative damage). Every decision is a
  setting here.
- **`topology.py`:** loads Topology Zoo networks with a default link
  capacity (I6); stable topology IDs shared with the optimizer.
- **`routing.py`:** thin layer over the engine's in-memory functions, plus
  per-link traffic shares used by the attackers.
- **`traffic.py`:** benign gravity-model demand scaled to a chosen peak
  utilization (I5).
- **`attack_plans.py`:** plans with an equal budget split (Eq. 7–8); budgets
  as a multiple of link capacity (D4).
- **`recon/__init__.py`, `recon/oracle.py`, `recon/random_plan.py`:** the
  oracle (I3) and no-knowledge attackers (§3.2).
- **`damage.py`:** damage D(A, G) with four §3.4 measures, and the ratio
  that is τ (Eq. 1) or η (Eq. 10), with D2 handling.
- **`tests/helpers.py`, `tests/test_d26_attack_plans.py`,
  `tests/test_d26_damage.py`, `tests/test_d26_phase1_ans.py`:** 16 tests,
  including the Phase 1 checks on ANS.
- **Docs updated:** `README.md` (what exists, worked example), `PLAN.md`
  (status, layout, §5 item 2), `docs/paper_map.md` (now 13 rows
  implemented), `docs/references.md` (inputs now in use; Topology Zoo origin
  checked for 5 of 6 files), `docs/diagrams/modules.md` (adds `topology.py`).

### Phase 1 checks

On ANS, benign traffic at 50% peak utilization, ECMP, N_A = 10, 20 random
plans per budget:

| Budget R_A | Oracle benign loss | Random plans: mean | Random plans: worst |
|---|---|---|---|
| 0.5 × link capacity | 0.0000 | 0.0000 | 0.0000 |
| 1 × link capacity | 0.0068 | 0.0000 | 0.0000 |
| 2 × link capacity | 0.0258 | 0.0004 | 0.0077 |

- The oracle beats every random plan at the same budget, and the oracle
  plan measured against itself has ratio 1 (tests in
  `tests/test_d26_phase1_ans.py`).
- Losses are small as a share of all benign traffic because flooding one
  link only hurts the traffic on that link. τ is a ratio of two such
  numbers, so this cancels there.
- Full run: `pytest tests doppler2026/tests` gives 200 passed; ruff clean;
  mypy unchanged (the same 16 pre-existing errors in `open_doppler.py`).

## 2026-10-30: Moved the folder to the repository root

- **Moved `scripts/doppler2026/` to `doppler2026/`.** Why: at `scripts/`,
  the experiment's documentation and tests would sit among campaign scripts;
  at the root they stay together as one self-contained project folder
  (decision P1, updated).
- **Updated every path reference** from `scripts/doppler2026` to
  `doppler2026` and from `scripts.doppler2026` to `doppler2026` in:
  `CLAUDE.md`, `tests/test_preprocessing_regressions.py` (docstring), and
  this folder's `__init__.py`, `README.md`, `PLAN.md`, `CHANGES.md` (earlier
  entries too, so their paths still resolve), `docs/decisions.md`, and
  `docs/diagrams/modules.md` and `data-flow.md`.
- **Changed `tests/conftest.py`:** the repository root is now two folders up
  (`parents[2]`), not three.
- **Reworded `PLAN.md` §3:** the experiment is now a regular top-level
  package run with `python -m doppler2026.<module>` from the repo root,
  instead of relying on `scripts` being a namespace package.
- **Checks:** `pytest doppler2026/tests` passes (also when started from
  another directory); the main suite plus these tests pass together (166);
  ruff clean.

## 2026-10-30: Phase 0 (foundations)

### Changes outside this folder

- **Changed `src/onset/preprocessing.py`: demand-direction bug** (audit
  "Demands are silently dropped depending on direction"; paper §4.6, Eq.
  12–14 require every demand to be routed).
  - *Problem:* tunnels are stored once per unordered node pair, under the key
    (s, t) with s < t as strings. The MILP looks up tunnels by the demand's
    own ordered pair, so every demand with s > t found none, got no flow
    variables, and was silently left out. On ANS coremelt this was 15 of 24
    nonzero demands (about 70% of volume).
  - *Fix:* in `build_optimization_problem`, the edge set stored for (s, t),
    which already contains every path in both directions, is also
    registered for (t, s). The reverse demand now gets exactly the edges the
    forward demand gets; nothing else changes.
  - *Side effect:* results of the existing `doppler`, `onset_v3`, and
    `solve_baseline` paths change, because they were missing these demands.
  - *Not fixed:* the path-based data used by `onset` and `onset_v2` has the
    same problem in a separate builder. The experiment does not use it, so it
    is left alone (decision P7).
- **Changed `src/onset/preprocessing.py`: tunnel-cache key bug** (audit
  "The tunnel cache ignores the candidate set").
  - *Problem:* tunnels were cached under the network name only, so a
    `conservative` run left tunnels that a later `max` run reused.
  - *Fix:* new helper `_tunnel_cache_key` names the cache after the network,
    a hash of the super-graph's edges (fiber plus candidate links), and the
    path mode (serial or parallel, which use different path limits).
  - *Side effect:* old cache files in `data/paths/optimization/` named
    `{network}_tunnel_*.pickle` are no longer read. They are not deleted;
    remove them by hand if you want the disk space back.
- **Created `tests/test_preprocessing_regressions.py`.** Four tests that fail
  without the fixes above and pass with them: every demand has tunnel edges;
  a reverse-order demand is actually routed (MLU 0.25 instead of 0); cached
  tunnels match freshly computed ones across candidate sets; ANS coremelt
  drops 0 of 24 demands. Tests point the cache at a temporary folder so they
  never write into `data/`.

### New files in this folder

- **`__init__.py`**: makes the folder importable as `doppler2026`
  and explains what the package is.
- **`README.md`**: where to start reading, how to run tests and lint.
- **`docs/decisions.md`**: decisions already made (P1–P7) and the open
  parameter choices (D1–D10) with proposed defaults.
- **`docs/paper_map.md`**: every paper section and equation, the module that
  will implement it, and its status.
- **`docs/diagrams/control-loop.md`**, **`modules.md`**, **`data-flow.md`**:
  Mermaid diagrams of one Doppler epoch (a candidate for the paper's Fig. 1),
  module dependencies, and the path from inputs to figures.
- **`tests/conftest.py`**: puts the repository root on `sys.path` so tests
  can import `doppler2026` without changing the repo-wide pytest
  config.
- **`tests/test_d26_package.py`**: smoke test that the package imports.

### Checks

- Full suite: 165 passed (161 before, plus 4 regression tests).
- `pytest doppler2026/tests`: 1 passed.
- ruff (project rules) clean on changed and new files.
- mypy reports 16 errors in `src/onset/open_doppler.py`. They exist without
  these changes too (numpy 2.5 type stubs) and that file was not touched, so
  they are left alone.

## 2026-10-30: Gaps, visualizations, and attribution

- **Updated `CLAUDE.md`.** Added rules 5–7: record every library, method, and
  dataset in `docs/references.md` (citations marked unverified until checked);
  generate figures only from saved result files; track known gaps rather than
  implying they are closed. Why: you asked for attribution suitable for a
  scientific paper and reproducible figures, and these need to persist across
  sessions.
- **Updated `PLAN.md`.** Rewrote §9 as a gap register: each gap that blocks a
  full implementation, what is built now, how it plugs in later, and what it
  blocks. Added §10 (result-file schema, structure diagrams, the list of paper
  figures and tables with their source files and phase) and §11 (pointer to
  the references list). Why: to answer whether work can start before the gaps
  are closed (it can) and to fix the result format now so figures can be
  added later without rerunning anything.
- **Created `docs/references.md`.** The list of inputs to the experiment:
  methods, software, and datasets, with planned usage and suggested
  citations. All citations are from memory and marked unverified or
  "to identify".

## 2026-10-30: Planning

- **Created `CLAUDE.md`** (repo root). Records the working rules for this
  experiment so they persist across Claude Code sessions: the paper is the
  specification, change only what is needed outside this folder, explain and
  log every change, document every module.
- **Created `doppler2026/PLAN.md`.** The implementation plan: control
  loop design, folder layout, paper-to-component map, the four changes needed
  outside this folder, phases with checks, experiments, open decisions, and
  known gaps.
- **Created `doppler2026/CHANGES.md`** (this file). Gives one place to
  see what has been changed and why.

No code has been changed yet.
