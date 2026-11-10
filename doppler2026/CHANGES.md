# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first. Changes up to version zero (2026-11-04) are
in `archive/v0/CHANGES.md`.

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
