# Studies

Small experiments for active research: each answers one question on a
subset of the networks, settings, or results, and runs in minutes. The
paper's full evaluation lives in `experiments/` instead.

Conventions:

- **One script per study**, `studies/<study>.py`, run as
  `python -m doppler2026.studies.<study>`. Its docstring states the
  question, the setup (with who decided it), and what is recorded. Settings
  are constants at the top of the script, so the script itself is the
  record of the study; a JSON config is used only when the same study is
  run with several settings.
- **Results** go to `data/results/doppler2026/studies/<study>/<run_id>/`,
  with `config.json` (every setting, git commit, package versions) and the
  usual CSV files (`docs/results_schema.md`).
- **Shared code** (running the controller in several modes, printing,
  writing results) is in `studies/common.py`; a study script is mostly its
  docstring and settings.
- **Changing a study's setup**: edit the script in place and use a new run
  id. Each run's `config.json` records every setting and the git commit, so
  older results stay explainable from git history.
- **Comparing a proposed change to Doppler** against the current version:
  put the change in `variants/` and switch it on from the study.
- **Add a row below** for each study.

| Study | Question | Added | Runs |
|---|---|---|---|
| `sparsification_synthetic4` | Does the baseline Doppler make a fully linked 4-PoP network sparser, and what happens to τ, MLU, stretch, and the stale attack's damage? | 2026-11-10 | `baseline-2026-11-10` (L = 1, history with G_t); `lag2-2026-11-10` (L = 2, Eq. 19 history) |
| `sparsification_synthetic15` | Does the baseline Doppler make a dense 15-PoP synthetic network sparser, and how do τ, MLU, and stretch change as it does? | 2026-11-10 | `baseline-2026-11-10` (L = 1, history with G_t) |
