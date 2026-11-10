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
- **Changing a study's setup** means a new script or a new run id, not
  editing a script whose results are already reported, so old runs stay
  explainable.
- **Add a row below** for each study.

| Study | Question | Added | Runs |
|---|---|---|---|
| `sparsification_synthetic15` | Does the baseline Doppler make a dense 15-PoP synthetic network sparser, and how do τ, MLU, and stretch change as it does? | 2026-11-10 | `baseline-2026-11-10` |
