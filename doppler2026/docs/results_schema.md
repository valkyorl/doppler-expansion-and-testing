# Results, figures, and tables

The result schema every experiment writes and the figure scripts read
(rule 6 in `CLAUDE.md`). Moved here from §10 of the v0 plan
(`archive/v0/PLAN.md`) on 2026-11-10; keep it current.

**The result schema.** Every run writes into
`data/results/doppler2026/<experiment>/<run_id>/`:

- `config.json`: the full resolved config, seed, git commit, and package
  versions. This is enough to rerun the experiment exactly.
- `epochs.csv`: one row per epoch (topology ID, pool sizes after each filter,
  T(G′) of the selected topology, MLU, stretch, benign loss, solver time,
  transition type).
- `candidates.csv`: one row per candidate per epoch (filter outcomes and
  reasons, T(G′), secondary scores).
- `transferability.csv`: one row per (plan, topology) pair with every damage
  measure and τ. τ is given against both oracles: `ratio` and `fresh_*`
  against the reference chosen by D15 (named in `oracle_knowledge`),
  `other_ratio` and `other_fresh_*` against the other one.
- `recon.csv`: reconnaissance metrics per mechanism, network, and ε.
- `transitions.jsonl`: the ordered action list per transition (the testbed
  hand-off from §9).

CSV in long ("tidy") form, so any figure can be produced by filtering and
grouping.

**Built early: structure diagrams** in `docs/diagrams/`, as Mermaid source
(renders on GitHub and in most Markdown viewers):

- The Doppler control loop (the paper's Fig. 1 placeholder).
- The module dependency map of `doppler2026/`.
- Data flow from configs to result files to figures.

**Paper figures** in `doppler2026/figures/`.
One script per figure or table, reading only result files and writing to
`figures/out/` as PDF (for the paper) and PNG (for review).

| Figure / table | Paper | From | Phase |
|---|---|---|---|
| Doppler control loop diagram | Fig. 1 | hand-drawn source in `docs/diagrams/` | 0 |
| Network summary table | Table 1 | configs + data inventory | 2 |
| Topology recovery (P/R/F1) and ε sensitivity | §3.7 RQ1 | `recon.csv` | 2 |
| Critical-link P@k | §3.7 RQ2 | `recon.csv` | 2 |
| Attack impact vs budget, per attacker | §3.7 RQ3 | `transferability.csv` | 2 |
| Stale-plan damage over epochs: Doppler vs static vs structural churn (built at v0 as `fig_controller_stale_damage.py`, damage and τ per epoch) | §4.2 G1 | `epochs.csv` | 4 |
| Pairwise τ heatmap of a safe pool (not built at v0) | §4.9 | `transferability.csv` | 3 → 5 |
| MLU / stretch / benign loss, steady state and transitions (not built at v0) | §4.7, §4.13 | `epochs.csv` | 4 → 5 |
| Solver budget trade-off | §4.12 | `epochs.csv`, `candidates.csv` | 5 |
| Deployment envelope | §2.5 | `epochs.csv` | 5 |
