# Doppler 2026 change log

Every file created or changed for the Doppler 2026 experiment, inside or
outside this folder, gets an entry here: what changed, why, and which issue it
addresses. Newest entries first. Changes up to version zero (2026-11-04) are
in `archive/v0/CHANGES.md`.

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
