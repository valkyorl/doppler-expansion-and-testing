# Doppler 2026 experiment

This folder implements the experiment for the draft paper
*Doppler-security-26* (Aug 2026): a moving-target defense that reconfigures an
optical network so that link-flooding attack plans learned on earlier
topologies stop working, while benign traffic is still carried safely.

**Status:** Phase 0 (foundations). No experiment code yet. See
`CHANGES.md` for what has been done.

## Where to read

| File | What it tells you |
|---|---|
| `PLAN.md` | The full design, phases, experiments, and known gaps |
| `CHANGES.md` | Every file created or changed for this work, and why |
| `docs/paper_map.md` | Which module implements which paper section and equation |
| `docs/decisions.md` | Choices the paper leaves open, and what was decided |
| `docs/references.md` | Libraries, methods, and datasets used, with citations |
| `docs/diagrams/` | Control loop, module map, and data-flow diagrams |
| `docs/Doppler_security_26.pdf` | The paper draft (add a copy here; not yet present) |

## Running

All commands run from the repository root with the project's virtual
environment active.

Run this experiment's tests:

```bash
pytest scripts/doppler2026/tests --no-cov
```

Lint and format-check this folder. The repository's ruff config only covers
an explicit list of files that does not include this folder, so the same
rules are passed on the command line:

```bash
ruff check --isolated --target-version py313 --line-length 88 \
  --select E,F,W,I,N,UP,B,C4,SIM,RUF --ignore E501 scripts/doppler2026
ruff format --isolated --check scripts/doppler2026
```

The experiment runner (`python -m scripts.doppler2026.run`) arrives in
Phase 4.

## Layout

The layout is described in `PLAN.md` §3. Modules are added as each phase
implements them, so the folder only contains what currently works.
