# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first.

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
