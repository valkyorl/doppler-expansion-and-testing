# Doppler 2026 experiment

This folder implements the experiment for the draft paper
*Doppler-security-26* (Aug 2026): a moving-target defense that reconfigures an
optical network so that link-flooding attack plans learned on earlier
topologies stop working, while benign traffic is still carried safely.

**Status:** Phase 1 done: attack plans, the oracle and random attackers,
damage, and τ/η can be computed on any topology. See `CHANGES.md` for what
has been done and `PLAN.md` §6 for what comes next.

## What exists so far

| Module | What it does | Paper |
|---|---|---|
| `model.py` | Data types and all experiment settings | §2.1, §3.3, §3.4 |
| `topology.py` | Load a Topology Zoo network with link capacities | — |
| `routing.py` | Route traffic in memory with the existing TE engine | §2.1 |
| `traffic.py` | Benign gravity-model demand at a chosen load | §4.3 |
| `attack_plans.py` | Turn chosen pairs into a plan with an equal budget split | Eq. 7–8 |
| `recon/oracle.py` | Perfect-knowledge attacker | §3.2 |
| `recon/random_plan.py` | No-knowledge attacker | §3.2 |
| `damage.py` | Damage of a plan; τ and η against a fresh oracle plan | §2.4, Eq. 1, Eq. 10 |

A minimal example, from the repository root:

```python
from doppler2026.damage import relative_damage
from doppler2026.model import AttackConfig, DamageConfig, RoutingConfig
from doppler2026.recon.oracle import oracle_plan
from doppler2026.topology import DEFAULT_CAPACITY, load_topology
from doppler2026.traffic import benign_demand

routing = RoutingConfig()                       # ECMP
topology = load_topology("ANS")
benign = benign_demand(topology, target_utilization=0.5, routing=routing, seed=1)
attack = AttackConfig(budget=2 * DEFAULT_CAPACITY, n_pairs=10)

plan = oracle_plan(topology, attack, routing)   # learned on this topology
result = relative_damage(plan, topology, benign, attack, routing, DamageConfig())
print(result.ratio, result.plan_damage.benign_loss)   # 1.0, about 0.026
```

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

The experiment runner (`python -m doppler2026.run`) arrives in
Phase 4.

## Layout

The layout is described in `PLAN.md` §3. Modules are added as each phase
implements them, so the folder only contains what currently works.
