# Doppler 2026: state at version zero (v0)

Date: 2026-11-04. Written for anyone picking up the experiment after the
initial implementation: what exists, what it shows so far, what goes wrong,
and what the paper promises that is not built yet. It replaces reading
the v0 plan and change log end to end; those record how v0 was reached and
are archived in `archive/v0/`.

v0 is a line drawn under the first implementation attempt, not a finished
experiment. Every module of the paper's design (§3 reconnaissance, §4
Doppler) exists and runs end to end; the paper's §4 evaluation (Phase 5) is
not built, and several of the paper's claims are not supported by the
results so far.

## 1. Reproducing v0

From the repository root:

```bash
bash doppler2026/reproduce_v0.sh            # everything, about 1.5 hours
bash doppler2026/reproduce_v0.sh controller # one step: recon, defender, controller, figures
```

| Step | Writes | Contents |
|---|---|---|
| `recon` | `data/results/doppler2026/recon_eval/v0/` | §3.7 RQ1-RQ3 on five simulated networks and the regional reconstruction |
| `defender` | `data/results/doppler2026/defender_epoch/v0/` | One defender epoch per network with the pairwise τ matrix (the Phase 3 check) |
| `controller` | `data/results/doppler2026/controller/v0-<network>-<mode>/` | 10 epochs per network for `static`, `doppler`, and `churn` |
| `figures` | `doppler2026/figures/out/` | Table 1, RQ1-RQ3 figures and tables, stale-plan damage per epoch |

Results are exactly reproducible: the same config and seed give identical
files (checked across Python hash seeds). Each run's `config.json` holds
the full settings, the git commit, and package versions. Results are not in
git (`data/` is ignored); neither are figure PDFs. The tests:
`pytest tests doppler2026/tests --no-cov`.

## 2. What is built

| Paper | What | Where |
|---|---|---|
| §2, Eq. 1, 7-8, 10 | Attack plans, damage under ECMP with capacity-limited links, τ and η | `model.py`, `attack_plans.py`, `routing.py`, `damage.py` |
| §3.1-3.3 | Attackers: two oracles, no-knowledge, traceroute (simulated probes), RTT/Ricci (simulated RTTs, plus the stored regional reconstruction) | `recon/` |
| §3.4, §3.7 | Topology recovery, P@k, attack impact vs budget (RQ1-RQ3) | `recon/metrics.py`, `experiments/recon_eval.py`, `figures/fig_rq*.py` |
| §4.4-4.7 | Feasible links, MILP candidate pool, operational filter (U_max, stretch, connectivity) | `feasibility.py`, `candidates.py`, `filters.py` |
| §4.8-4.9 | History of attack plans, security filter T(G') ≤ τ_max, pairwise τ | `security.py` |
| §4.10-4.12 | Candidate sets, enumeration, seeded random selection, time budget | `candidates.py`, `selection.py` |
| §4.13 | E_add / E_remove, transition order, intermediate states (flow level) | `transition.py` |
| §4.14 | Multi-epoch controller with attacker lag; static and structural-churn baselines | `controller.py`, `run.py`, `configs/` |

The full paper-to-code map is `docs/paper_map.md`.

## 3. Results at v0

**Reconnaissance (§3.7, run `recon_eval/v0`).** Tables and figures are in
`figures/out/` (`table1_networks`, `rq1_*`, `rq2_*`, `rq3_*`). They are
identical to the Phase 2 results, so the reproducibility fix made after
Phase 2 changed nothing there. Headline (median η at twice link capacity,
`rq3_attack_effectiveness.md`): with full coverage, the traceroute attacker
matches the paper's oracle on four of five networks (η = 1.0 against it)
and reaches 0.17-0.60 of the benign-aware reference oracle; RTT/Ricci
reaches 0.03-0.53; no-knowledge plans do no damage at that budget. The
benign-aware oracle does 1.6-6 times the damage of the paper's oracle
(O1). All measurements are simulated (B1).

**One defender epoch (§4.4-4.11, run `defender_epoch/v0`).** Pools fill (50
candidates in 3-100 s); 14-43 pass the operational filter; **none is safe
on any network** in the first epoch. Why differs by network (O8, section 4).

**Ten epochs, Doppler against the baselines (§4.2 G1, runs
`controller/v0-<network>-<mode>`).** Mean benign loss caused by the stale
attack (L = 1), figure `figures/out/controller_stale_damage.png`:

| Network | Mode | Epochs that moved | Mean stale loss (%) | Mean stale τ | Links (first -> last) |
|---|---|---|---|---|---|
| sprint | Static | 0 | 2.3 | 1.0 | 18 -> 18 |
| sprint | Doppler | 6 | 0.9 | 0.57 | 18 -> 22 |
| sprint | Structural churn | 10 | 3.4 | 0.79 | 18 -> 18 |
| ANS | Static | 0 | 2.6 | 1.0 | 25 -> 25 |
| ANS | Doppler | 2 | 2.4 | 0.93 | 25 -> 25 |
| ANS | Structural churn | 10 | 3.7 | 0.94 | 25 -> 25 |
| CRL | Static | 0 | 9.8 | 1.0 | 38 -> 38 |
| CRL | Doppler | 0 | 9.8 | 1.0 | 38 -> 38 |
| CRL | Structural churn | 10 | 7.4 | 0.96 | 38 -> 38 |
| bellCanada | Static | 0 | 5.6 | 1.0 | 64 -> 64 |
| bellCanada | Doppler | 0 | 5.6 | 1.0 | 64 -> 64 |
| bellCanada | Structural churn | 10 | 5.1 | 0.91 | 64 -> 64 |
| surfNet | Static | 0 | 6.1 | 1.0 | 68 -> 68 |
| surfNet | Doppler | 0 | 6.1 | 1.0 | 68 -> 68 |
| surfNet | Structural churn | 10 | 7.2 | 1.01 | 68 -> 69 |

What this says:

- **sprint is the one network where Doppler works as the paper describes.**
  It moves in 6 of 10 epochs, the stale plan keeps 57% of a fresh plan's
  effect on average, and the stale attack's damage falls from 2.3% to
  0.9%.
- **ANS moves twice** and stays just under the static network.
- **On CRL, bellCanada, and surfNet Doppler never moves**, so it equals the
  static network. On CRL and bellCanada the structural-churn baseline does
  better than both.
- **Doppler never does more damage than the static network**, in any epoch
  on any network. This is the effect of the damage conditions added to the
  security filter (A6). Without them it did much worse (O7).
- Churn moves every epoch on every network, but is worse than static on
  sprint, ANS, and surfNet.

One seed per run; differences of a few tenths of a percent are within what
another seed could change.

## 4. Issues we are running into

Open issues are numbered O1-O8 in `docs/decisions.md`; O1-O7 are decided,
O8 is open.

- **Doppler rarely finds a safe topology (O5, O8).** This is the main
  problem at v0. In the first epoch no network has a safe candidate. Two
  different causes:
  - On CRL and surfNet no feasible candidate reaches τ <= 0.5: the changes
    the filters allow are too small to move the attacked traffic. On CRL
    the stretch limit (S_max = 3, a ratio of path lengths in km) rejects
    most candidates and the rest add one link; on surfNet most pass the
    stretch limit, but τ stays at 0.93 or more.
  - On sprint, ANS, and bellCanada some candidates do reach τ <= 0.5, but
    a fresh attacker would do more damage on them than on the original
    topology, so the vulnerability limit rejects them.
- **τ alone does not protect the network (O7).** τ is a ratio against a
  fresh attacker on the same topology, so a topology that is weaker overall
  can still have low τ. Without the added damage conditions, Doppler on ANS
  raised the stale attack's damage from 2.6% to 13.3%. The conditions fix
  that, at the cost of most of Doppler's moves. The paper's Eq. 22 needs a
  damage condition, or G1 needs restating (discrepancy A6, C3).
- **Change-minimizing generation (O2, O5, A4).** The MILP minimizes a
  weighted count of changes, so candidates stay close to the current
  topology. T(G') cannot be put in the MILP; a security-guided objective
  was tried (O5) and did not help, because the guidance score does not
  predict τ.
- **The oracle is not an upper bound (O1, A1).** The paper's oracle does
  not know benign traffic, and measured attackers did more damage than it
  in 15% of plans at 2x link capacity. The reference oracle for η now
  knows benign traffic; even it is beaten in 0.4-0.6% of plans.
- **Run time.** A Doppler epoch takes 3-30 s on sprint and ANS, 35-40 s on
  CRL, and 75-150 s on bellCanada and surfNet, mostly in the security
  filter (one re-measured attacker plus damage simulations per candidate).
  A 10-epoch run on the large networks takes 15-20 minutes. Sweeps in
  Phase 5 will need parallel runs.
- **One seed.** Every v0 number comes from one seed per run. They are
  exactly reproducible, but there is no measure of spread yet.
- **Solver quirk.** HiGHS refuses to run when its thread count is set after
  another HiGHS model has run in the same process; the code does not set
  it, and stops with an error if a solve fails, instead of returning a
  short pool.

## 5. Where the code departs from the paper

Listed in full in `docs/code_paper_discrepancies.md`. In short:

- **Departures from the specification (A1-A7):**
  - the reference oracle for η knows benign traffic (A1);
  - the history includes the current topology (A2);
  - K counts candidates before the security filter, and the MILP does not
    minimize T(G'), which is applied as a filter instead (A3, A4);
  - the churn baseline selects from Doppler's pool (A5);
  - the security filter has two damage conditions beyond Eq. 22 (A6);
  - candidates keep at least the current number of links (A7).
- **Missing data or infrastructure (B1-B8):** simulated measurements, no
  validated ground truth, the fiber graph is the IP topology, incomplete
  optical feasibility, assumed transponders and new-link capacity,
  flow-level transitions only, abstract epochs.
- **Promises not supported yet (C1-C3):** sustained expiry of
  reconnaissance, Doppler against structural churn, and damage under
  reconfiguration. Their current status is in section 3 above.

Interpretations of the paper's wording (I1-I21) are in `docs/decisions.md`.
At v0 all of them are accepted **provisionally**: the code and results
depend on them, but only I3, I4, and I13 were reviewed one by one.

## 6. Planned but not built

From §7 of the v0 plan and `docs/gaps.md` (gaps with their plug-in points):

- **Phase 5 experiment scripts.** None exists. Each would sweep configs and
  write the same result schema:
  - `experiments/transferability.py` (§4.2 G1): stale-plan τ across epochs
    for Doppler, static, and churn, swept over recon lag L, τ_max, h, and
    attack budget, with several seeds. At v0 there is one run per mode and
    network and one figure comparing them.
  - `experiments/diversity.py` (§4.9): safe-pool size and pairwise τ
    clustering. The pairwise τ matrix is computed for one epoch
    (`defender_epoch.py`) but not plotted.
  - `experiments/cost.py` (§4.7, §4.13): MLU, stretch, benign loss in steady
    state and during transitions. The values are logged per epoch and per
    transition step; no figure.
  - `experiments/solver_budget.py` (§4.12): time to the first safe topology
    and best T(G') against T_opt.
  - `experiments/envelope.py` (§2.5, §4.5): spare transponders, reach,
    candidate set size. The O7 variants were run by hand from configs.
- **Figures** for the pairwise τ heatmap (§4.9) and the cost metrics.
- **§3.3 oracle rate allocation:** the minimum budget to overload a target
  with capacity knowledge (a sensitivity experiment).
- **Repetitions:** every v0 number comes from one seed; no spread or
  confidence intervals.
- **Needs data or a testbed:** real RTT and traceroute campaigns (§3.5),
  operator-validated ground truth (§3.4), optical data (ROADMs, spectrum,
  transponder placement; §4.4), packet-level transition effects and real
  timings (§4.13-4.14), and Comcast (unknown origin).
- **Defender model mismatch:** the defender assumes exactly the attacker
  that attacks (I18); an attacker using another mechanism is a later axis.

## 7. Documents

| Document | What it is |
|---|---|
| `docs/v0_summary.md` | This summary |
| `docs/code_paper_discrepancies.md` | Every departure from the paper and every unsupported promise |
| `docs/decisions.md` | Every decision, interpretation, and open issue (O1-O8), with dates and reasons |
| `docs/paper_map.md` | Paper section to module |
| `docs/references.md` | Libraries, methods, datasets, citations (unverified ones marked) |
| `README.md` | Install and run |
| `docs/gaps.md`, `docs/results_schema.md` | Known gaps; the result schema and figures (from the v0 plan) |
| `archive/v0/PLAN.md`, `archive/v0/CHANGES.md` | The development plan and log that led to v0 (archived 2026-11-10) |
