# Working agreements for this repository

These instructions apply to every Claude Code session in this workspace.
Edit them freely; they are read at the start of each conversation.

## Current focus: the Doppler 2026 experiment

- The active work is a new Doppler experiment that implements the draft paper
  *Doppler-security-26* (Aug 2026). All files specific to this experiment and
  paper live in `doppler2026/`.
- Read `doppler2026/README.md` before starting work on it, and
  `doppler2026/CHANGES.md` to see what has changed since version zero.
- `doppler2026/archive/` holds superseded documents (the v0 development
  plan). Do not read or search it by default: exclude it from
  searches, and open it only when a task needs history (why something was
  decided, what an earlier run used). Say so when you do. "PLAN §n" in code
  and docs refers to `doppler2026/archive/v0/PLAN.md`.
- The paper-vs-code audit that motivated this work is
  `docs/knowledge/analysisResults/doppler-paper-vs-code.html`.
- A copy of the paper draft should be kept at
  `doppler2026/docs/Doppler_security_26.pdf`. If it is missing, ask the
  user for it rather than working from memory of the paper.

## Research ownership

This is a research project, and the user owns its scientific decisions:
the objective function, the threat model, assumptions, metrics, and
experimental methodology (including networks, parameters, baselines, and
how results are judged).

- You may suggest scientific choices, with options and a recommendation, but
  do not make them. The user must know about each one and has the final say.
  This applies even to choices that look small (a default value, a
  tie-break, what counts as a "move"), and even when a change seems needed
  to make code run.
- The user keeps their own, human-written document of the differences
  between the paper and the code, all assumptions, and recent experimental
  results. Do not edit it. The docs in `doppler2026/docs/` are your records
  and do not replace it.
- Before carrying out a request, say whether it will introduce a new
  assumption, a new departure from the paper, or a change to the
  methodology, and what each one is, so the user can record or reject it.
  When reporting finished work, list any that resulted.

## Versions and experiments

The working tree holds the current version only. Earlier versions live in
git history, tags (e.g. `v0`), and GitHub releases, which the user makes.

- Do not keep copies of old code, old configs, or reproduce scripts for
  earlier versions. A config that only repeats the defaults is not kept.
- Keep: the documentation of differences from the paper, assumptions, and
  decisions; the current, runnable Doppler; the files outside
  `doppler2026/`; and `doppler2026/studies/`.
- Archive (`doppler2026/archive/`) only what is still needed to understand
  the current code, such as a plan that docs cite.
- A proposed change to Doppler that should be compared with the current
  version goes in `doppler2026/variants/` (see its README). Variants are
  ephemeral: each is either promoted into the real modules or deleted. The
  user decides case by case whether to keep one.
- Study scripts are edited in place; each run's `config.json` records the
  git commit, so old results stay traceable.
- Generated figures (`doppler2026/figures/out/`) are not tracked in git.

## Rules for changes

1. **The paper is the specification.** When the codebase and the paper's
   design disagree, change the implementation to match the paper. Where the
   paper is silent or ambiguous, do not invent behavior quietly: propose a
   choice, ask the user, and record the decision in
   `doppler2026/docs/decisions.md`.
2. **Change only what the experiment needs.** Code outside
   `doppler2026/` may be changed only when the experiment requires it.
   Do not refactor, delete, or clean up unrelated code, even if it is broken or
   legacy. Prefer additive changes (new optional parameters, new functions)
   that leave existing behavior unchanged; when an existing behavior must
   change (for example a bug fix), say so explicitly.
3. **Explain every change.** Whenever a file is created or modified, tell the
   user what changed, why, and which issue it fixes (cite the audit item or
   paper section/equation where relevant). Also add an entry to
   `doppler2026/CHANGES.md`.
4. **Document as you go.** Every module gets a docstring that says what it is
   for and which paper section/equation it implements. Non-obvious code gets
   inline comments. Larger design topics get a markdown file under
   `doppler2026/docs/`. The user must be able to understand what is
   implemented without reading the paper side by side.
5. **Record every input to the experiment.** Whenever code imports a library,
   uses a named method or algorithm (e.g. Ollivier–Ricci curvature, Yen's
   k-shortest paths, gravity traffic models), or uses a dataset, add it to
   `doppler2026/docs/references.md` with where it is used and, when one
   exists, the publication to cite. Mark any citation written from memory as
   unverified; never present an unchecked citation as confirmed.
6. **Keep results reproducible for figures.** Experiments write results in the
   schema described in `doppler2026/docs/results_schema.md`. Figures and tables
   are generated only by scripts in `doppler2026/figures/` that read
   those result files, never by hand.
7. **Track known gaps instead of hiding them.** Parts of the paper that cannot
   be implemented yet are listed in `doppler2026/docs/gaps.md` with
   how they will plug in later. Do not write code or results that imply a gap
   has been closed.
