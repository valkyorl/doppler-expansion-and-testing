# Doppler 2026: implementation plan

This plan turns the draft paper *Doppler-security-26* (Aug 2026) into a
runnable experiment in this repository. It is written for the people building
and checking the experiment. Paper references use § and Eq. numbers. Audit
references ("audit #n") point to items in
`docs/knowledge/analysisResults/doppler-paper-vs-code.html`.

Status: **Phase 4 built (2026-11-03):** transitions, the multi-epoch
controller with static and churn baselines, `run.py`, and configs. After
open issues O5-O7 the defaults are: no net loss of links, one spare
transponder per PoP, and a security filter with three conditions (τ, stale
damage, vulnerability). Departures from the paper are listed in
`docs/code_paper_discrepancies.md`. Next: Phase 5 (paper evaluations). See
`CHANGES.md`.

---

## 1. What the experiment must show

The paper promises three evaluations (§1, §3.7, §4.12–4.14):

1. **Reconnaissance works.** RTT/Ricci and traceroute reconnaissance produce
   attack plans that beat a no-knowledge attacker and approach an oracle
   (RQ1–RQ3, §3.7).
2. **Doppler expires reconnaissance.** After Doppler reconfigures, attack plans
   learned on earlier topologies have low transferability τ (Eq. 1) while
   benign traffic is still carried within the operator's limits (§4.2 G1–G4).
3. **The cost is acceptable.** Utilization, path stretch, transition
   disruption, solver time, and the dependence on optical resources (§4.12–4.14,
   §2.5 deployment envelope).

The current `doppler` method cannot show any of these (audit #1–#5, #10). The
new experiment is therefore a new controller, not a modification of the old
method. The old `doppler` method and `scripts/Doppler/` are left untouched.

## 2. Design in one picture

One epoch of the Doppler 2026 control loop (paper Fig. 1, §4.3):

```
inputs: fiber graph G_F, current topology G_t, transponders txp(v),
        estimated BENIGN demand D_t, history H = [(G_i, A_i)] of last h states

1. attacker   : recon on G_t  ->  attack plan A_t          (§3, recon/)
                append (G_t, A_t) to history H
2. feasible   : E* = links the optical layer can realize   (§4.4, feasibility.py)
3. generate   : pool of candidate topologies G' ⊆ E*       (§4.10–4.11, candidates.py)
                MILP with txp, flow, capacity, U_max constraints
4. op. filter : route D_t on G' with the real TE method;   (§4.6–4.7, filters.py)
                reject if MLU > U_max, stretch > S_max, disconnected
5. sec. filter: T(G') = max_{A_i in H} τ(A_i, G')          (Eq. 21–22, security.py)
                reject if T(G') > τ_max
6. select     : rank safe pool by secondary objective,     (§4.11, selection.py)
                pick at random (seeded) from acceptable subset
7. transition : E_add / E_remove, make-before-break order, (§4.13, transition.py)
                measure intermediate states
8. advance    : G_{t+1}; attacker's stale plan is replayed on it and
                damage is logged                           (§4.14, controller.py)
```

Two points carry most of the design:

- **Generate-then-filter.** T(G′) depends on routing attack traffic and on a
  fresh plan for G′ (the attacker re-measuring; O3 option e), so it is not
  linear and cannot sit inside the
  MILP. The paper allows this: it enumerates up to K candidates satisfying the
  constraints (Eq. 31) and filters them (§4.3). The MILP only produces
  operationally plausible candidates; the security filter decides.
  The fresh plan is built by the same mechanism as the stale plan, from
  fresh measurements of G′ (Eq. 1: "constructed with current knowledge of
  topology G_j"). Until 2026-11-03 this plan said "a fresh oracle plan",
  which the paper does not say; see O3 in `docs/decisions.md`. The oracle
  comparisons the filter saves alongside are its costly part.
- **The defender never sees attack traffic.** The MILP uses the estimated
  benign demand D_t (§4.3 input 4). Attack plans enter only through the
  security filter. This fixes audit #16.

## 3. Folder layout

Everything specific to this experiment, including its documentation and
tests, lives in `doppler2026/` at the repository root. It is a regular Python
package and runs from the repo root as `python -m doppler2026.run <config>`;
Python puts the current directory on the import path for `-m`, so no
`sys.path` edits are needed. It is not installed with the `onset` package,
so it must be run from the repo root.

```
doppler2026/
  PLAN.md               this file
  CHANGES.md            log of every file created or changed, and why
  README.md             how to install and run (written in Phase 0)
  __init__.py
  docs/
    Doppler_security_26.pdf   copy of the draft (add manually)
    decisions.md              choices the paper leaves open (§8 below)
    paper_map.md              paper equation -> function index
  model.py              dataclasses: AttackPlan, Candidate, EpochRecord, configs
  topology.py           loading topologies with capacities; stable topology IDs
  attack_plans.py       A = {(s_i, d_i, r_i)} (Eq. 7), budget split (Eq. 8)
  recon/
    oracle.py           oracle attackers: the paper's (§3.2) and the one that
                        also knows benign traffic (D15)
    random_plan.py      no-knowledge attacker (§3.2)
    inferred.py         inferred graph + edge ranking -> plan (§3.3), shared
    traceroute.py       simulated traceroute + betweenness ranking (§3.1.2, Eq. 5–6)
    rtt_ricci.py        min-RTT graphs, ε sweep, Ollivier–Ricci ranking (§3.1.1, Eq. 2–4)
    metrics.py          precision/recall/F1, P@k, path-level recovery (§3.4, Eq. 9)
  routing.py            in-memory TE wrapper around onset.te.engine
  damage.py             D(A, G), τ (Eq. 1), T(G′) (Eq. 21)
  feasibility.py        E* with fiber path + optical reach checks (§4.4)
  candidates.py         MILP pool generation, local/expanded sets, Candidate
                        (§4.10–4.11)
  filters.py            operational filter (Eq. 15–17, connectivity)
  security.py           security filter, pairwise τ matrix (Eq. 22–24)
  selection.py          secondary ranking + seeded random choice (§4.11)
  transition.py         E_add/E_remove, make-before-break model (§4.13, Eq. 32–33)
  controller.py         epoch loop, history h, attacker lag vs T_R (§4.14)
  traffic.py            benign gravity TMs for networks without them
  run.py                experiment entry point; writes CSV/JSON results
  results.py            result folders, config.json with provenance, tidy CSVs (§10)
  experiments/          one script per paper evaluation (§7 below)
  figures/              one script per paper figure/table, reading result files (§10)
  configs/              JSON configs per network/mode (ANS_doppler, ANS_static,
                        ANS_churn, smoke)
  tests/                unit + regression tests (with a conftest.py that
                        lets pytest import doppler2026)
```

## 4. Components, mapped to the paper

Each row names the paper requirement, what is built, what is reused, and which
audit item it closes.

| Component | Paper | Approach | Reuses | Closes |
|---|---|---|---|---|
| Attack plan | §2.1, Eq. 7–8 | Plan = list of (s, d, r); equal split of budget R_A over ≤ N_A pairs | — | — |
| Oracle attacker | §3.2 | Route on the true topology; rank physical links by attack traffic the attacker's endpoints can put on them; take pairs crossing the top target | `routing.py` | #9 |
| No-knowledge attacker | §3.2 | N_A random pairs, same budget | — | #9 |
| Traceroute attacker | §3.1.2, Eq. 5–6 | Simulate probes from vantage points along true routes, with a configurable non-response rate; build Ĝ_tr; rank edges by betweenness; pick pairs whose inferred paths cross the target | `routing.py` | #7 |
| RTT/Ricci attacker | §3.1.1, Eq. 2–4 | Simulated RTT = min over noisy samples of propagation delay along true routes; Ĝ_ε for an ε sweep; Ollivier–Ricci curvature via **GraphRicciCurvature**; rank by most negative κ. Also a loader for the existing reconstruction `data/graphs/json/regional/reconstruction_regional.json` | GraphRicciCurvature | #6 |
| Recon metrics | §3.4, Eq. 9–10 | Edge precision/recall/F1 (only when ground truth is independent), P@k, path-level critical-link recovery, η | `routing.py` | #6 |
| Damage D | §2.4, §3.4 | Route benign D_t plus attack plan together with the network's TE; report all five §3.4 measures. Primary measure for τ: benign traffic lost (decision D1) | `onset.te.engine` | #2 |
| τ, T(G′) | Eq. 1, 21 | τ = D(A_i, G′) / D(A*_{G′}, G′), where A*_{G′} is a fresh plan of A_i's mechanism on G′ with the same budget (O3 option e; was "a fresh oracle plan" until 2026-11-03) | the attacker's mechanism | #2, #3 |
| Feasible links E* | §4.4 | A pair (u, v) is feasible when a fiber path exists whose length is within optical reach; ROADM/spectrum hook defaults to "allowed" and is documented as an assumption (no data in repo) | fiber graph coordinates | #11 |
| Per-link capacity C_e | Eq. 15–16 | Capacities come from the topology instead of a fixed 100 Gbps; a new link gets the median (D17) | `candidates.py` (P9) | #15 |
| Candidate pool | §4.10–4.11 | Edge-flow MILP with flow aggregated per source, built in `candidates.py` (P9), with its own enumeration loop: benign demand, U_max, at least one change, configurable secondary objective. **Local** set: candidate links near high-betweenness links of the *current* topology and near links targeted by plans in the history. **Expanded** set: all of E* | HiGHS (not `open_doppler`, P9) | #1, #5, #12 |
| Operational filter | §4.6–4.7, Eq. 15–17 | Re-route D_t on G′ with the real TE method (ECMP by default). Reject on MLU > U_max, any unroutable demand, latency stretch > S_max against the initial topology, or broken connectivity/redundancy requirements | `routing.py` | #13, #14, routing mismatch |
| Security filter | Eq. 21–22 | Compute T(G′) over the last h plans; keep G′ if T(G′) ≤ τ_max | `damage.py` | #2, #3 |
| Diversity | §4.9, Eq. 23–24 | Pairwise τ(A_i, G_j) matrix over the safe pool; report clusters | `damage.py` | #4 |
| Selection | §4.11, G4 | Rank by secondary objective (MLU, stretch, changes); keep the acceptable subset; choose uniformly at random with a recorded seed | — | #4 |
| Transition | §4.13, Eq. 32–33 | Order adds before drops when transponders allow; otherwise label the transition break-before-make. Evaluate the network after each intermediate step (MLU, benign loss) | transponder counts from `candidates.transponders` (not AlpWolf, P10) | #18, #19 |
| Control loop | §4.14 | Epochs of length T_R. The attacker needs L epochs to finish recon, so the attack at epoch t uses the plan learned at t − L. History of the last h (G_i, A_i). Logs solver time vs T_opt | all of the above | #20, #10 |

## 5. Changes outside `doppler2026/`

These are the only changes planned elsewhere, each because the experiment
cannot work correctly without it. All are listed in `CHANGES.md` when made.

1. **`src/onset/preprocessing.py`: fix two bugs** (you chose to fix them in
   shared code).
   - Demands with source > target get no tunnels and are dropped from the
     MILP. Fix: build tunnel edge sets for both directions of each pair.
   - The tunnel cache key ignores the candidate set, so runs poison each
     other. Fix: include the candidate set (and a hash of the candidate links)
     in the cache key.
   - **Side effect:** results of the existing `doppler`, `onset`, `onset_v2`
     and `onset_v3` methods will change, because they were affected by the
     same bugs. Regression tests will pin the corrected behavior.
2. **`src/onset/te/engine.py`: add public in-memory functions** (done in
   Phase 1). `route_demands()` routes without files; `deliver_flows()` pushes
   labelled flows (benign and attack separately) through the network so that
   every link carries at most its capacity, with proportional or max-min
   sharing (D11). `evaluate()` now uses the same loss model with max-min
   sharing: its older hop-by-hop model let a link carry more than its
   capacity, and was fixed on 2026-11-03 (decision E1 in `docs/decisions.md`;
   results of existing methods change when links are overloaded).
3. ~~`src/onset/base_types.py` and `src/onset/open_doppler.py`: optional
   per-edge capacity.~~ **Not needed** (decision P9, 2026-11-03): the
   candidate MILP is built in `doppler2026/candidates.py`, with per-link
   capacity, so shared code is unchanged.
4. **`pyproject.toml`: an optional extra** (done in Phase 2). It lists
   GraphRicciCurvature's real dependencies (networkit, POT, python-louvain);
   the library itself is installed with `--no-deps` because its SciPy pin
   cannot be met on Python 3.13 (decision P8). Base dependencies are
   unchanged.

Not changed: `simulator.py`, `method_registry.py`, `handlers.py`,
`attacker.py`, `scripts/Doppler/`, legacy Gurobi modules. The new controller
does not use AlpWolf (P10: transponder counts come from `candidates.py`) and has its own epoch
loop. Fitting history and attackers into `Simulation.perform_sim` would mean
rewriting it.

## 6. Phases

Each phase ends with something runnable and a check you can verify.

**Phase 0: Foundations**
- Folder skeleton, README, `docs/decisions.md`, `docs/paper_map.md`, test
  harness.
- Shared-code fixes 1 and 2 from §5, with regression tests. The ANS coremelt
  case must drop 0 demands, down from the 15 of 24 measured in the audit.
- Check: existing test suite still passes; new regression tests pass.

**Phase 1: Attack plans and damage**
- `model.py`, `attack_plans.py`, `routing.py`, `recon/oracle.py`,
  `recon/random_plan.py`, `damage.py` (D, τ, η).
- Benign gravity TMs for ANS and the other geo-tagged topologies (the repo's
  `*_base_tm_0.00e+00_gravity.txt` files are all zeros).
- Check: on ANS, the oracle plan causes clearly more benign loss than random
  plans at the same budget; τ of a plan on its own topology is 1.

**Phase 2: Reconnaissance (paper §3)**
- `recon/traceroute.py`, `recon/rtt_ricci.py` (with ε sweep and the regional
  reconstruction loader), `recon/metrics.py`.
- `experiments/recon_eval.py`: RQ1–RQ3 tables and attack-budget curves.
- Check: metrics run on simulated measurements for every geo-tagged topology,
  and on the regional reconstruction.

**Phase 3: Defender (paper §4.4–4.11)**
- Shared-code changes 3 and 4 from §5.
- `feasibility.py`, `candidates.py`, `filters.py`, `security.py`,
  `selection.py`.
- Check: for one epoch on ANS, the selected topology satisfies every
  operational constraint and has T(G′) ≤ τ_max. The pool's pairwise τ matrix
  is produced.

**Phase 4: Control loop and transitions (paper §4.12–4.14)**
- `transition.py`, `controller.py`, `run.py`, configs.
- Check: a multi-epoch run logs per-epoch stale-plan damage, T(G′), pool
  size, solver time, and transition states. Repeating a run with the same
  seed reproduces it exactly.

**Phase 5: Paper evaluations (§7 below).**

## 7. Experiments that produce the paper's results

| Script | Paper | Produces |
|---|---|---|
| `experiments/recon_eval.py` | §3.7 RQ1–RQ3 | Topology recovery, P@k, attack impact vs budget for oracle / random / traceroute / RTT-Ricci, ε sensitivity, coverage. Built in Phase 2. Not yet included: the §3.3 sensitivity experiment with an oracle rate allocation (minimum budget to overload a target with capacity knowledge) |
| `experiments/transferability.py` | §1, §4.2 G1 | τ of stale plans across Doppler epochs vs a static network and vs a structural-churn baseline (Eq. 18) |
| `experiments/diversity.py` | §4.9 | Safe-pool size and pairwise τ clustering per network |
| `experiments/cost.py` | §4.7, §4.13 | MLU, stretch, benign loss in steady state and during transitions |
| `experiments/solver_budget.py` | §4.12 | Time to first safe topology, safe configurations found, best T(G′) vs T_opt |
| `experiments/envelope.py` | §2.5, §4.5 | Effect of fallow transponders, reach, and candidate set size on safe diversity |

The structural-churn baseline (minimize |E_t ∩ E′|, Eq. 18) is the paper's own
point of comparison. It is also what the legacy Gurobi Doppler did, so it is
worth including.

## 8. Choices the paper leaves open

These go into `docs/decisions.md` with a proposed default, and get confirmed
with you before the phase that needs them.

Status 2026-11-03: every choice needed by Phase 3 is accepted, including the
later additions D16–D25 (see `docs/decisions.md`). Only D10 (Phase 4) is open.

| # | Question | Proposed default |
|---|---|---|
| D1 | Which damage measure defines τ? | Benign traffic lost; the other §3.4 measures are reported alongside |
| D2 | τ when the fresh plan does no damage (D(A*, G′) = 0) | Define τ = 0 and flag the candidate as "attack-immune at this budget" |
| D3 | History length h, threshold τ_max, pool size K | h = 3, τ_max = 0.5, K = 50; swept in experiments |
| D4 | Attack budget R_A and pairs N_A | Sweep R_A as a multiple of the target link's capacity; N_A = 10 |
| D5 | U_max and S_max | U_max = 0.8, S_max = 3 (revised 2026-11-03 from 1.5; O4) |
| D6 | Optical reach | Configurable km limit; default unlimited until real data exists |
| D7 | Which attacker the defender assumes when building the history | Accepted 2026-11-03: traceroute (§4.8); oracles and RTT/Ricci as experiment axes |
| D8 | Attacker endpoints | Every PoP can source and sink attack traffic |
| D9 | "Acceptable subset" for random selection | Candidates whose secondary score is within 10% of the best |
| D10 | Recon lag L vs epoch length T_R | L in epochs, swept from 0 to 3 |

## 9. Known gaps: deferred, with a plug-in point

The work proceeds without these. Each gap gets an interface now, so the
missing piece can be added later without reworking the code around it. None of
them blocks Phases 0–3.

| Gap | Paper | What is built now | How it is closed later | Blocks |
|---|---|---|---|---|
| Packet-level transition effects (convergence, packet loss) | §1, §4.13 | `transition.py` writes an explicit, ordered, timestamped list of circuit and IP-link actions per transition, plus flow-level metrics for each intermediate state | An emulation testbed replays the action list and reports convergence and loss into the same result schema | The paper's transient-effects claims only |
| Real RTT / traceroute measurements | §3.5 | Recon modules read measurements through one loader interface; a simulator implements it. The existing regional Ricci reconstruction gets its own loader | Add a loader per real dataset; collection must follow §3.6 authorization rules | RQ1–RQ3 on operational networks |
| Independent ground truth | §3.4 | RQ1 metrics refuse to run unless the ground-truth source is marked as independently validated in the config | Confirm provenance of the regional ground truth (audit #8) or obtain operator-validated topologies | RQ1 numbers only |
| Optical data (ROADM, spectrum, transponder placement) | §4.4 | Feasibility = fiber path + reach, with a pluggable check for the rest (default: allowed, recorded as an assumption) | Add checks when optical data exists | Strength of G3 claims |
| ~~GraphRicciCurvature on Python 3.13~~ | §3.1.1 | Closed in Phase 2: installed with `--no-deps` (decision P8) | — | — |
| Comcast in the reconnaissance evaluation | §3.5 | Excluded from the default network list: its origin is unknown (`docs/references.md`) and at 149 nodes a full run is much slower | Confirm its origin; run it on its own with `--networks Comcast` | Coverage of one more network |
| Open parameter choices D1–D10 | various | Defaults proposed in §8 | Confirmed with you before the phase that needs each one | One phase each |

**Paper-level risk.** The draft promises packet-level transition results. If
no testbed is available before submission, the paper text must be scoped
down. This is a decision for the authors, tracked here so it is not forgotten.

## 10. Results, figures, and tables

**Planned now: the result schema.** Every run writes into
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

**Added as phases finish: paper figures** in `doppler2026/figures/`.
One script per figure or table, reading only result files and writing to
`figures/out/` as PDF (for the paper) and PNG (for review).

| Figure / table | Paper | From | Phase |
|---|---|---|---|
| Doppler control loop diagram | Fig. 1 | hand-drawn source in `docs/diagrams/` | 0 |
| Network summary table | Table 1 | configs + data inventory | 2 |
| Topology recovery (P/R/F1) and ε sensitivity | §3.7 RQ1 | `recon.csv` | 2 |
| Critical-link P@k | §3.7 RQ2 | `recon.csv` | 2 |
| Attack impact vs budget, per attacker | §3.7 RQ3 | `transferability.csv` | 2 |
| τ of stale plans over epochs: Doppler vs static vs structural churn | §4.2 G1 | `transferability.csv` | 4 |
| Pairwise τ heatmap of a safe pool | §4.9 | `transferability.csv` | 3 |
| MLU / stretch / benign loss, steady state and transitions | §4.7, §4.13 | `epochs.csv` | 4 |
| Solver budget trade-off | §4.12 | `epochs.csv`, `candidates.csv` | 5 |
| Deployment envelope | §2.5 | `epochs.csv` | 5 |

## 11. References and inputs

Every library, named method, and dataset the experiment uses is listed in
`docs/references.md`, with where it is used and the publication to cite. The
list grows with each phase (rule 5 in `CLAUDE.md`).
