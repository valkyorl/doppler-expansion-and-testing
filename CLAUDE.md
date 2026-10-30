# Working agreements for this repository

These instructions apply to every Claude Code session in this workspace.
Edit them freely; they are read at the start of each conversation.

## Current focus: the Doppler 2026 experiment

- The active work is a new Doppler experiment that implements the draft paper
  *Doppler-security-26* (Aug 2026). All files specific to this experiment and
  paper live in `scripts/doppler2026/`.
- Read `scripts/doppler2026/PLAN.md` before starting work on it, and
  `scripts/doppler2026/CHANGES.md` to see what has already been done.
- The paper-vs-code audit that motivated this work is
  `docs/knowledge/analysisResults/doppler-paper-vs-code.html`.
- A copy of the paper draft should be kept at
  `scripts/doppler2026/docs/Doppler_security_26.pdf`. If it is missing, ask the
  user for it rather than working from memory of the paper.

## Rules for changes

1. **The paper is the specification.** When the codebase and the paper's
   design disagree, change the implementation to match the paper. Where the
   paper is silent or ambiguous, do not invent behavior quietly: propose a
   choice, ask the user, and record the decision in
   `scripts/doppler2026/docs/decisions.md`.
2. **Change only what the experiment needs.** Code outside
   `scripts/doppler2026/` may be changed only when the experiment requires it.
   Do not refactor, delete, or clean up unrelated code, even if it is broken or
   legacy. Prefer additive changes (new optional parameters, new functions)
   that leave existing behavior unchanged; when an existing behavior must
   change (for example a bug fix), say so explicitly.
3. **Explain every change.** Whenever a file is created or modified, tell the
   user what changed, why, and which issue it fixes (cite the audit item or
   paper section/equation where relevant). Also add an entry to
   `scripts/doppler2026/CHANGES.md`.
4. **Document as you go.** Every module gets a docstring that says what it is
   for and which paper section/equation it implements. Non-obvious code gets
   inline comments. Larger design topics get a markdown file under
   `scripts/doppler2026/docs/`. The user must be able to understand what is
   implemented without reading the paper side by side.
5. **Record every input to the experiment.** Whenever code imports a library,
   uses a named method or algorithm (e.g. Ollivier–Ricci curvature, Yen's
   k-shortest paths, gravity traffic models), or uses a dataset, add it to
   `scripts/doppler2026/docs/references.md` with where it is used and, when one
   exists, the publication to cite. Mark any citation written from memory as
   unverified; never present an unchecked citation as confirmed.
6. **Keep results reproducible for figures.** Experiments write results in the
   schema described in `scripts/doppler2026/PLAN.md` (§10). Figures and tables
   are generated only by scripts in `scripts/doppler2026/figures/` that read
   those result files, never by hand.
7. **Track known gaps instead of hiding them.** Parts of the paper that cannot
   be implemented yet are listed in `scripts/doppler2026/PLAN.md` (§9) with
   how they will plug in later. Do not write code or results that imply a gap
   has been closed.
