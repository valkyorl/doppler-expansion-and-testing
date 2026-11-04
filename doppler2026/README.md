# Doppler 2026 experiment

This folder implements the experiment for the draft paper
*Doppler-security-26* (Aug 2026): a moving-target defense that reconfigures an
optical network so that link-flooding attack plans learned on earlier
topologies stop working, while benign traffic is still carried safely.

**Status:** Phase 4 built: the multi-epoch controller with transitions and
static and churn baselines, on top of Phase 3's defender (feasible links,
candidate pool, operational and security filters, selection) and Phase 2's
attackers, damage, τ/η, and reconnaissance experiment (RQ1–RQ3). Defaults
after open issues O5-O7: no net loss of links, one spare transponder per
PoP, and a security filter that checks τ, stale damage, and vulnerability.
See `CHANGES.md` for what has been done and `PLAN.md` §6 for what comes
next. Where the implementation departs from the draft paper is listed in
`docs/code_paper_discrepancies.md`.

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
| `results.py` | Result folders, `config.json` with provenance, tidy CSVs | PLAN §10 |
| `experiments/recon_eval.py` | The reconnaissance evaluation | §3.7 RQ1–RQ3 |
| `feasibility.py` | Feasible IP links E* from the fiber graph | §4.4 |
| `candidates.py` | MILP candidate pool (transponders, benign flow, capacity, U_max) | §4.5–4.6, §4.10–4.11, Eq. 11–16 |
| `filters.py` | Operational filter: connectivity, MLU, path stretch under the network's routing | §4.6–4.7, Eq. 16–17 |
| `security.py` | Security filter T(G') and pairwise τ of the safe pool; history attacker | §4.8–4.9, Eq. 19–24 |
| `selection.py` | Secondary ranking and seeded random choice | §4.11 |
| `experiments/defender_epoch.py` | One defender epoch per network (the Phase 3 check) | §4.3–4.11 |
| `transition.py` | E_add / E_remove, transition order, intermediate states | §4.13, Eq. 32–33 |
| `controller.py` | The multi-epoch control loop, attacker lag, history; static and churn baselines | §4.3, §4.14 |
| `run.py`, `configs/` | Run the controller from a JSON config | PLAN §3, §10 |

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
| `PLAN.md` | The full design, phases, experiments, and known gaps |
| `CHANGES.md` | Every file created or changed for this work, and why |
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

### Reconnaissance experiment (Phase 2)

```bash
python -m doppler2026.experiments.recon_eval --networks ANS CRL bellCanada sprint surfNet
```

Results go to `data/results/doppler2026/recon_eval/<run_id>/` (see
`PLAN.md` §10). `data/` is git-ignored, so results stay local; `config.json`
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

A config lists only the settings it changes; everything else keeps the
defaults in `docs/decisions.md`. Results go to
`data/results/doppler2026/controller/<run_id>/`: `epochs.csv`,
`candidates.csv`, `transferability.csv`, `transitions.jsonl`, and
`config.json` with the fully resolved config. The same config reproduces the
same results exactly (timings aside).

## Layout

The layout is described in `PLAN.md` §3. Modules are added as each phase
implements them, so the folder only contains what currently works.
