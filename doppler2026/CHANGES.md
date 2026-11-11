# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first. Changes up to version zero (2026-11-04) are
in the v0 change log, `doppler2026/archive/v0/CHANGES.md` in the git tag `v0`.

## 2026-11-10: Paper lines in the discrepancies document checked against the draft

At the user's request, every **Paper** line in `docs/code_paper_discrepancies.md`
was checked against the draft. Quoted text was verbatim (equations written in
plain text); three paraphrases said more than the paper and were corrected:

- A5: the paper does not define a structural-churn baseline; Eq. 18 is only
  a contrast ("one could choose ..."). Now quoted, with the baseline marked
  as our methodology.
- A7: "nothing keeps the number of links" is now labelled as our
  observation, not the paper's statement.
- B6: deriving capacity from circuits is now quoted as the paper's extension
  case; the basic model does not say how a new link's capacity is set.

Added a note at the top: only quoted text is verbatim, everything else is
paraphrase, and our own observations are labelled. No code changed.

## 2026-11-10: What K counts, as an option (D33, discrepancy A3)

The user chose option (c): keep the default, and add Eq. 31 read verbatim
as an option for the solver-budget experiment (§4.12).

- `candidates.py`: `CandidateConfig.pool_counts`, `"generated"` (default,
  unchanged) or `"accepted"`; `generate()` takes an optional `accept`
  callback, called on each candidate as it is found, and in `"accepted"`
  mode stops after K accepted candidates. `CandidatePool.accepted` records
  the count. T_opt is measured on the wall clock from the start, so in
  that mode it covers filtering too.
- `controller.py`: `defender_step`'s per-candidate filtering moved into a
  local `evaluate()`, called after generation (default) or from inside it
  (`"accepted"`). The variable links' capacities are now computed before
  generation (the same values `generate()` computes). Default behaviour
  unchanged: a rerun of `sparsification_synthetic4` matched
  `lag2-2026-11-10` exactly in `summary.csv`, `epochs.csv`,
  `candidates.csv`, and `transferability.csv` (timings aside).
- Docs: `code_paper_discrepancies.md` A3 (the "Why" now says it is a
  choice and why; the option; the paper's own §4.11/§4.12 ambiguity),
  `decisions.md` D33, `paper_map.md` (§4.12). The option's two differences
  from the default mode (T_opt also covers filtering; churn counts
  operationally feasible candidates) are recorded in A3 and D33 as known
  differences of a comparison option, at the user's request, not changed.
- Tests: two pool tests (`test_d26_defender.py`), one controller test on a
  4-PoP network (`test_d26_controller.py`), the documented default.
  On `synthetic4` epoch 1, `"accepted"` with K = 1 stops after 13
  candidates (the first safe one) instead of exhausting all 37.

## 2026-11-10: History as Eq. 19, recon lag at least 2 (D10, D30, D32)

Decided by the user. **Changes existing behaviour:** results of every
Doppler and churn run differ from before.

- `controller.py`: the defender's history is now G_{t-1} ... G_{t-h} as in
  Eq. 19 (it was G_t ... G_{t-h+1}, former discrepancy A2). The new history
  entry is added after the epoch's decision. `recon_lag` defaults to 2 (was
  1), the assumption that makes Eq. 19 sufficient: the topology chosen at
  epoch t is attacked with the plan from G_{t+1-L}, which is then in the
  history. Doppler runs refuse L < 2 with an explanation; static and churn
  accept any L >= 0 (the L = 0 reference stays). At epoch 0 the history is
  empty and Doppler stays on G_0 (new D32); churn still moves. New
  `epochs.csv` column `history_states`; `no_safe_topology` is now false
  when the defender did not run.
- Churn uses the same history, so its candidate pool's attacked-link targets
  (D23) now lag one epoch too.
- `experiments/defender_epoch.py`: behaviour unchanged (still checks
  against the plan on G_0); its docstring now says so.
- Docs: `decisions.md` (D10, D30 revised; D32 new; BL1's reproduction check
  dated), `code_paper_discrepancies.md` (A2 withdrawn as a departure: now
  the lag assumption; sections B and C untouched), `paper_map.md`,
  `results_schema.md`, `studies/README.md`.
- Tests: the lag test rewritten for L = 2; new tests for the Eq. 19 history
  and epoch 0, and for refusing L < 2 in Doppler mode; the documented
  default of `recon_lag` is 2.
- Rerun: `studies/sparsification_synthetic4/lag2-2026-11-10`. Doppler
  behaves as before, one epoch later (moves at epochs 1 and 2, ends on the
  same 4-link topology, stale damage 47% from epoch 5). Churn alternates
  between two 3-link topologies; with L = 2 the stale plan was learned on
  the topology now running, so its τ is 1.0 and damage alternates between
  54.7% and 11.7%.

## 2026-11-10: Current version only; the 4-PoP study; variants

Working style (user, 2026-11-10): the tree holds the current version; older
versions live in git history and the `v0` tag/release. Rule added to
`CLAUDE.md` ("Versions and experiments").

Removed (all in the git tag `v0`):

- `configs/v0/` (15 per-network configs pinning the v0 settings) and
  `reproduce_v0.sh`.
- `configs/ANS_{doppler,static,churn}.json`: they only repeated the
  defaults. `configs/smoke.json` stays; README and `run.py` show a config
  inline instead.
- `archive/v0/CHANGES.md` (the v0 change log). `archive/v0/PLAN.md` stays,
  because code and docs cite it as "PLAN §n".
- `docs/v0_summary.md`. Its still-current content moved: the Phase 5
  figures and the defender-model mismatch (I18) are new rows in
  `docs/gaps.md`; run time, one seed, and the HiGHS quirk are "Practical
  notes" in `README.md`; the build table, issues, and departures were
  already in `README.md`, `decisions.md`, and
  `code_paper_discrepancies.md`. The v0 results table is in the tag.
- `figures/out/` is no longer tracked; `.gitignore` (outside this folder)
  gains `doppler2026/figures/out/`. The files stay on disk.

New:

- `variants/` (`README.md`, `__init__.py` with `applied`): ephemeral
  proposed changes to Doppler, swapped in for one `with` block so a study can
  compare them with the current version; each is promoted or deleted. No
  variants yet. Test: `tests/test_d26_variants.py`.
- `studies/common.py`: the runner shared by the studies (moved out of
  `sparsification_synthetic15.py`, whose behaviour and output are
  unchanged; its `config.json` now records the study name without the
  `studies/` prefix).
- `studies/sparsification_synthetic4.py` and `topologies/synthetic4.gml`
  (user's choice: 4 PoPs, all 6 pairs linked, defaults otherwise). First
  run `studies/sparsification_synthetic4/baseline-2026-11-10` (30 s):
  Doppler removes 2 links at epoch 0, swaps 2 at epoch 1, then has no safe
  candidate and stays on a triangle plus one PoP on a single link; the
  stale attack's damage rises from 5.8% (static) to 47%. Churn drops to 3
  links at epoch 0. Test: `test_four_pop_study_network_links_every_pair`.

Updated: `CLAUDE.md` (start reading `README.md`; the versions rule),
`README.md` (status, versions, run examples, studies), `archive/README.md`,
`__init__.py` and `run.py` docstrings, `studies/README.md` (edit in place,
`common.py`, variants, index row), `docs/decisions.md` (BL1 and O7 now
point to the tag; drivers list item 9, an observation: the operational
filter allows bridges; nothing changed), `docs/gaps.md`,
`docs/references.md` (dataset row).

## 2026-11-10: Synthetic network and the sparsification study

New (user's design, 2026-11-10):

- `synthetic.py`: generator for synthetic test networks. PoPs uniformly at
  random in a square (default 1,500 km, centered in the US Midwest), each
  linked to its 2 nearest PoPs, then the closest pairs up to
  nodes x mean degree / 2 links; layouts with a bridge are redrawn. Seeded
  and reproducible; `ensure()` refuses a stored file that differs from what
  the config generates.
- `topologies/synthetic15.gml`: the 15-PoP, 45-link network (seed 0, one
  draw; degrees 2-9; links 22-733 km).
- `studies/` with `README.md` (conventions and index) and
  `sparsification_synthetic15.py`: 30 epochs of static, Doppler, and churn on
  `synthetic15`, printing and saving per epoch the links, additions and
  removals, safe candidates, stale τ, selected T(G'), MLU, and stretch.
  First run: `studies/sparsification_synthetic15/baseline-2026-11-10`.
- `controller.py`: `ControllerConfig.topology_dir` (load a network from
  another folder; default unchanged), and three new `epochs.csv` columns,
  `current_mlu`, `current_max_stretch`, `current_mean_stretch`: the cost of
  the topology in force each epoch, measured as the operational filter does.
  Additive: existing columns and results are unchanged.
- Tests: `test_d26_synthetic.py` (shape, nearest-neighbour rule,
  reproducibility, GML round trip, refusal); a controller test on a
  synthetic network checking the new columns.
- Docs: `references.md` (random geometric and k-nearest-neighbour graphs,
  unverified; the synthetic dataset), `paper_map.md` (research tools),
  `results_schema.md` (studies, new columns), `README.md`.

## 2026-11-10: Baseline BL1: the sparsifying settings are the defaults again

**Behavior change** (user): the defaults return to the Phase 4 settings.

- `candidates.py`: `spare_transponders` 1 -> 0, `spare_fraction` 1.0 -> 0.1,
  `keep_link_count` True -> False.
- `security.py`: `max_stale_damage_ratio` and `max_vulnerability_ratio`
  1.0 -> None (the security filter is Eq. 22's τ condition only).
- Check: the default ANS Doppler config reproduces
  `controller/phase4-ANS-doppler` exactly (every column of `epochs.csv` and
  `candidates.csv` except timings; run `check-baseline-ANS-doppler`).
- v0 stays reproducible: the 15 per-network configs moved to `configs/v0/`
  with the v0 settings pinned; `reproduce_v0.sh` uses them. Check: the pinned
  sprint Doppler config reproduces `v0-sprint-doppler` exactly (run
  `check-v0pinned-sprint-doppler`). `configs/ANS_*.json` were re-created with
  the current defaults.
- Tests: the defaults test, the transponder test, and two tests that relied
  on the old defaults now state their settings.
- Docs: `decisions.md` (new "Baselines" section with BL1 and the analysis of
  what drives sparsification; D18, O2, O7, O8 notes),
  `code_paper_discrepancies.md` (A6, A7 now "available, off since BL1"; B5),
  `paper_map.md`, `README.md`, `v0_summary.md` (note at the top).

## 2026-11-10: Working agreements: research ownership

`CLAUDE.md` (repository root), at the user's request:

- New section "Research ownership": the user owns scientific decisions
  (objective function, threat model, assumptions, metrics, experimental
  methodology); Claude suggests but does not decide; the user's own
  human-written record of differences, assumptions, and results is not to be
  edited; every request gets a statement of any new assumption, departure
  from the paper, or methodology change it would introduce.
- Start-of-work reading is now `docs/v0_summary.md` and this change log; the
  archive is read only when history is needed.
- Rules 6 and 7 point to `docs/results_schema.md` and `docs/gaps.md`.

## 2026-11-10: v0 development documents archived

- Moved `PLAN.md` and `CHANGES.md` to `archive/v0/` (with `git mv`, so their
  history is kept) and added `archive/README.md`. They describe how v0 was
  reached and are no longer maintained.
- The two parts of the plan still in use became their own documents:
  `docs/gaps.md` (PLAN §9, known gaps) and `docs/results_schema.md` (PLAN
  §10, result schema and figures). References to PLAN §9 and §10 in code
  docstrings and docs now point to them; other "PLAN §n" references are
  historical and mean `archive/v0/PLAN.md` (stated in `__init__.py`,
  `README.md`, and `archive/README.md`).
- `README.md`, `__init__.py`, `docs/v0_summary.md`: updated pointers.
- `CLAUDE.md` (repository root): see the entry below.
