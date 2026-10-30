# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first.

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

- **`__init__.py`**: makes the folder importable as `scripts.doppler2026`
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
  can import `scripts.doppler2026` without changing the repo-wide pytest
  config.
- **`tests/test_d26_package.py`**: smoke test that the package imports.

### Checks

- Full suite: 165 passed (161 before, plus 4 regression tests).
- `pytest scripts/doppler2026/tests`: 1 passed.
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
- **Created `scripts/doppler2026/PLAN.md`.** The implementation plan: control
  loop design, folder layout, paper-to-component map, the four changes needed
  outside this folder, phases with checks, experiments, open decisions, and
  known gaps.
- **Created `scripts/doppler2026/CHANGES.md`** (this file). Gives one place to
  see what has been changed and why.

No code has been changed yet.
