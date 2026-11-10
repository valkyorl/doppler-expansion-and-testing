# Doppler 2026 experiment

This folder implements the experiment for the draft paper
*Doppler-security-26* (Aug 2026): a moving-target defense that reconfigures an
optical network so that link-flooding attack plans learned on earlier
topologies stop working, while benign traffic is still carried safely.

**Defaults since 2026-11-10: baseline BL1** (`docs/decisions.md`): the
sparsifying Phase 4 settings (no spare transponders, no link floor, security
filter = τ only), for studying the sparsification on synthetic networks
(`studies/`). v0's settings are pinned in `configs/v0/`.

**Status: version zero (v0), 2026-11-04.** Every part of the paper's design
(§3 reconnaissance, §4 Doppler with its baselines) is built and runs end to
end; the paper's §4 evaluation (Phase 5) is not. Start with
`docs/v0_summary.md`: what exists, what the results show so far, the issues,
and what is not built. Where the implementation departs from the draft paper
is listed in `docs/code_paper_discrepancies.md`.

## What exists so far

| Module | What it does | Paper |
|---|---|---|
| `model.py` | Data types and all experiment settings | §2.1, §3.3, §3.4 |
| `topology.py` | Load a Topology Zoo network with link capacities | — |
| `routing.py` | Route traffic in memory with the existing TE engine | §2.1 |
| `traffic.py` | Benign gravity-model demand at a chosen load | §4.3 |
| `attack_plans.py` | Turn chosen pairs into a plan with an equal budget split | Eq. 7–8 |
| `recon/oracle.py` | Perfect-knowledge attackers: the paper's oracle, and the one that also knows benign traffic (the reference for τ and η, decision D15) | §3.2 |
| `recon/random_plan.py` | No-knowledge attacker | §3.2 |
| `recon/traceroute.py` | Traceroute attacker, with a probe simulator | §3.1.2, Eq. 5–6 |
| `recon/rtt_ricci.py` | RTT/Ricci attacker, with an RTT simulator; regional data loaders | §3.1.1, Eq. 2–4 |
| `recon/inferred.py` | Inferred graph + edge ranking → attack plan (shared by both) | §3.3 |
| `recon/metrics.py` | Topology recovery, P@k, path-level recovery | §3.4, Eq. 9 |
| `damage.py` | Damage of a plan; η against a fresh oracle plan, τ against any supplied fresh plan; budget to disrupt | §2.4, §3.4, Eq. 1, Eq. 10 |
| `results.py` | Result folders, `config.json` with provenance, tidy CSVs | docs/results_schema.md |
| `experiments/recon_eval.py` | The reconnaissance evaluation | §3.7 RQ1–RQ3 |
| `feasibility.py` | Feasible IP links E* from the fiber graph | §4.4 |
| `candidates.py` | MILP candidate pool (transponders, benign flow, capacity, U_max) | §4.5–4.6, §4.10–4.11, Eq. 11–16 |
| `filters.py` | Operational filter: connectivity, MLU, path stretch under the network's routing | §4.6–4.7, Eq. 16–17 |
| `security.py` | Security filter T(G') and pairwise τ of the safe pool; history attacker | §4.8–4.9, Eq. 19–24 |
| `selection.py` | Secondary ranking and seeded random choice | §4.11 |
| `experiments/defender_epoch.py` | One defender epoch per network (the Phase 3 check) | §4.3–4.11 |
| `transition.py` | E_add / E_remove, transition order, intermediate states | §4.13, Eq. 32–33 |
| `controller.py` | The multi-epoch control loop, attacker lag, history; static and churn baselines | §4.3, §4.14 |
| `run.py`, `configs/` | Run the controller from a JSON config | `docs/results_schema.md` |
| `reproduce_v0.sh` | Rerun every v0 experiment and build every figure (controller runs from `configs/v0/`) | `docs/results_schema.md` |
| `synthetic.py`, `topologies/` | Synthetic test networks (random positions, nearest neighbours first) and their GML files | research tool |
| `studies/` | Small research studies, one script each; index in `studies/README.md` | research tool |
| `figures/fig_controller_stale_damage.py` | Stale-plan damage per epoch: static, Doppler, churn | §4.2 G1 |

A minimal example, from the repository root:

```python
from doppler2026.damage import relative_damage
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import benign_oracle_plan, oracle_plan
from doppler2026.topology import DEFAULT_CAPACITY, load_topology
from doppler2026.traffic import benign_demand

routing = RoutingConfig()                       # ECMP
topology = load_topology("ANS")
benign = benign_demand(topology, target_utilization=0.5, routing=routing, seed=1)
attack = AttackConfig(budget=2 * DEFAULT_CAPACITY, n_pairs=10)

damage = DamageConfig()

# The reference oracle (decision D15) knows benign traffic too.
plan = benign_oracle_plan(topology, benign, attack, routing, damage)
result = relative_damage(plan, topology, benign, attack, routing, damage)
print(result.ratio, result.plan_damage.benign_loss)   # 1.0, about 0.154

# The paper's oracle (§3.2) knows only topology and routing.
plan = oracle_plan(topology, attack, routing)
result = relative_damage(plan, topology, benign, attack, routing, damage)
print(result.ratio, result.other_ratio)   # about 0.167 (vs D15), 1.0 (vs itself)
```

## Where to read

| File | What it tells you |
|---|---|
| `docs/v0_summary.md` | **Start here:** the state at version zero, issues, and what is not built |
| `CHANGES.md` | Every file created or changed since v0, and why |
| `docs/gaps.md` | Parts of the paper that cannot be built yet, with their plug-in points |
| `docs/results_schema.md` | The result files every experiment writes, and the figures |
| `archive/v0/` | The development plan and change log that led to v0. Historical: read only when the history is needed. "PLAN §n" in code and docs means `archive/v0/PLAN.md` |
| `docs/paper_map.md` | Which module implements which paper section and equation |
| `docs/decisions.md` | Choices the paper leaves open, and what was decided |
| `docs/code_paper_discrepancies.md` | Where the implementation departs from what the draft spells out, and promises the results do not yet support |
| `docs/references.md` | Libraries, methods, and datasets used, with citations |
| `docs/diagrams/` | Control loop, module map, and data-flow diagrams |
| `docs/Doppler_security_26.pdf` | The paper draft (kept out of git; never commit or publish it) |
| `figures/out/` | Generated figures and tables. The PDFs are deliberately not in git (the repository ignores `*.pdf`); regenerate them from a run with the scripts in `figures/` |

## Running

All commands run from the repository root with the project's virtual
environment active.

### Installing the Ricci dependency

The RTT/Ricci attacker needs GraphRicciCurvature 0.6.1. Its package metadata
pins `scipy<=1.13.1`, which has no Python 3.13 build, but its code never
imports SciPy (decision P8). Install its real dependencies, then the
library without its own dependency list:

```bash
pip install -e ".[doppler2026]"          # networkit, POT, python-louvain
pip install --no-deps GraphRicciCurvature==0.6.1
```

`pip check` will then report the SciPy pin as unmet; that is expected.

### Everything at once (v0)

```bash
bash doppler2026/reproduce_v0.sh            # all steps, about 1.5 hours
bash doppler2026/reproduce_v0.sh figures    # one step: recon, defender, controller, figures
bash doppler2026/reproduce_v0.sh all v1     # rerun under another run name
```

### Reconnaissance experiment (Phase 2)

```bash
python -m doppler2026.experiments.recon_eval --networks ANS CRL bellCanada sprint surfNet
```

Results go to `data/results/doppler2026/recon_eval/<run_id>/` (see
`docs/results_schema.md`). `data/` is git-ignored, so results stay local; `config.json`
in each run is enough to reproduce it.

Run this experiment's tests:

```bash
pytest doppler2026/tests --no-cov
```

Lint and format-check this folder. The repository's ruff config only covers
an explicit list of files that does not include this folder, so the same
rules are passed on the command line:

```bash
ruff check --isolated --target-version py313 --line-length 88 \
  --select E,F,W,I,N,UP,B,C4,SIM,RUF --ignore E501 doppler2026
ruff format --isolated --check doppler2026
```

### One defender epoch (Phase 3)

```bash
python -m doppler2026.experiments.defender_epoch --networks sprint ANS CRL bellCanada surfNet
```

### Multi-epoch Doppler and baselines (Phase 4)

```bash
python -m doppler2026.run doppler2026/configs/ANS_doppler.json   # Doppler
python -m doppler2026.run doppler2026/configs/ANS_static.json    # topology never changes
python -m doppler2026.run doppler2026/configs/ANS_churn.json     # structural churn, Eq. 18
```

`configs/ANS_*.json` use the current defaults (baseline BL1). `configs/v0/`
has one file per network (sprint, ANS, CRL, bellCanada, surfNet) and mode
(`doppler`, `static`, `churn`) with the v0 settings pinned. Compare the modes with
`python -m doppler2026.figures.fig_controller_stale_damage --prefix v0`,
which reads every run named `v0-<network>-<mode>`.

A config lists only the settings it changes; everything else keeps the
defaults in `docs/decisions.md`. Results go to
`data/results/doppler2026/controller/<run_id>/`: `epochs.csv`,
`candidates.csv`, `transferability.csv`, `transitions.jsonl`, and
`config.json` with the fully resolved config. The same config reproduces the
same results exactly (timings aside).

### Studies

```bash
python -m doppler2026.studies.sparsification_synthetic15   # 30 epochs x 3 modes, about 6 minutes
python -m doppler2026.synthetic --nodes 15 --seed 0          # (re)write a synthetic network
```

Each study states its question and setup in its docstring; the index is
`studies/README.md`.

## Layout

The modules are listed in "What exists so far" above; the original layout
plan is §3 of `archive/v0/PLAN.md`.
