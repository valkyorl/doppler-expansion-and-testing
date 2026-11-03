# Paper-to-code map

Where each part of *Doppler-security-26* is implemented. Status is one of
**planned**, **implemented**, or **gap** (cannot be implemented yet; see
`PLAN.md` §9). Update this table whenever a module is added or changed.

## §2 Threat model

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §2.1, Eq. 7 | Attack plan A = {(s_i, d_i, r_i)} | `model.AttackPlan`, `attack_plans.make_plan` | implemented |
| §2.1 | Attack success: L_e + Σ r_i > c_e | `damage.evaluate_damage` (links carry at most c_e; loss by D11) | implemented |
| §2.4, Eq. 1 | Transferability τ(A_i, G_j) | `damage.relative_damage` (D1, D2) | implemented |

## §3 Reconnaissance

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §3.1.1, Eq. 2 | Minimum RTT per vantage-point pair | `recon/rtt_ricci.RttMeasurements`; simulated by `rtt_ricci.simulate` (I11) | implemented (simulated RTTs; real data is a gap) |
| §3.1.1, Eq. 3 | Threshold graphs Ĝ_ε and ε sweep | `rtt_ricci.epsilon_graph` (ε as an RTT quantile, D13); sweep in `experiments/recon_eval.py` | implemented |
| §3.1.1, Eq. 4 | Ollivier–Ricci ranking | `rtt_ricci.ricci_curvature` (GraphRicciCurvature, P3/P8; unweighted, I10), `rtt_ricci.ricci_attack` | implemented |
| §3.1.2, Eq. 5 | Observed traceroute graph Ĝ_tr | `traceroute.observed_graph` (silent hops break paths, D12); probes simulated by `traceroute.simulate` (I9) | implemented (simulated probes; real data is a gap) |
| §3.1.2, Eq. 6 | Betweenness ranking B(e) | `recon/inferred.betweenness`, used by `traceroute.traceroute_attack` | implemented |
| §3.2 | Oracle attacker | `recon/oracle.oracle_plan` (I3) | implemented |
| §3.2 (extension, D15) | Oracle that also knows benign traffic; reference A* for τ and η | `recon/oracle.benign_oracle_plan`, chosen by `fresh_oracle_plan` from `AttackConfig.oracle_knowledge` | implemented (departs from §3.2's wording; flagged for review) |
| §3.2 | No-knowledge attacker | `recon/random_plan.random_plan` | implemented |
| §3.3, Eq. 8 | Equal split of budget R_A | `attack_plans.make_plan`; budget as a capacity multiple: `attack_plans.budget_from_capacity` (D4) | implemented |
| §3.3 | Pairs whose inferred paths cross the target | `recon/inferred.plan_from_ranking` (I8) | implemented |
| §3.3 | Oracle rate allocation (minimum budget to overload a target; sensitivity experiment) | — | planned (not in Phase 2; see `PLAN.md` §9) |
| §3.4 | Precision, recall, F1 | `metrics.topology_recovery` (refuses unvalidated ground truth; I12) | implemented |
| §3.4, Eq. 9 | P@k, path-level critical-link recovery | `metrics.precision_at_k`, `metrics.path_level_recovery`; C_k from `oracle.rank_links` | implemented |
| §3.4 | Attack-effectiveness measures (bullets 1 to 4) | `model.DamageReport`, `damage.evaluate_damage` (I1, I2) | implemented |
| §3.4 | Budget needed for a given disruption (bullet 5) | `damage.budget_to_disrupt` (D14) | implemented |
| §3.4, Eq. 10 | Normalized effectiveness η | `damage.relative_damage` (same ratio as τ; against both oracles, D15) | implemented |
| §3.5 | Real measurements on operational networks | loaders return `TracerouteObservation` / `RttMeasurements`; only the regional reconstruction loader exists (`rtt_ricci.load_regional_reconstruction`) | gap (no raw data) |
| §3.7 | RQ1–RQ3 | `experiments/recon_eval.py` → `recon.csv`, `transferability.csv`; figures `figures/fig_rq1_recovery.py`, `fig_rq2_critical_links.py`, `fig_rq3_attack_impact.py` | implemented (simulated measurements) |
| §3.5, Table 1 | Network summary | `figures/table_networks.py` (from `networks.csv`) | implemented |

## §4 Doppler

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §4.3 | Control loop (Fig. 1) | `controller.py`; diagram in `docs/diagrams/control-loop.md` | planned (diagram done) |
| §4.3 input 4 | Estimated benign demand D_t | `traffic.benign_demand` (I5) | implemented |
| §4.4 | Feasible link set E* | `feasibility.py` | planned (reach only; optical data is a gap) |
| §4.5, Eq. 11 | Transponder limit | reused: `src/onset/open_doppler.py` | implemented (shared code) |
| §4.6, Eq. 12–14 | Flow conservation | reused: `src/onset/open_doppler.py` | implemented (shared code; demand-direction bug fixed in Phase 0) |
| §4.6, Eq. 15 | Activation with per-link capacity C_e | `src/onset/open_doppler.py` | planned (per-link capacity is new) |
| §4.7, Eq. 16 | U_max | `src/onset/open_doppler.py`, `filters.py` | planned |
| §4.7, Eq. 17 | Path stretch S_max | `filters.py` | planned |
| §4.7 | Connectivity and redundancy | `filters.py` | planned |
| §4.8, Eq. 18 | Structural-churn baseline | `experiments/transferability.py` | planned |
| §4.8, Eq. 19–21 | History and T(G′) | `security.py`, `controller.py` | planned |
| §4.8, Eq. 22 | Security filter T(G′) ≤ τ_max | `security.py` | planned |
| §4.9, Eq. 23–24 | Safe set and pairwise τ | `security.py` | planned |
| §4.10 | Local and expanded candidate sets | `candidates.py` | planned |
| §4.11, Eq. 25–31 | Pool enumeration and random selection | `candidates.py`, `selection.py` | planned |
| §4.12 | Optimization time budget T_opt | `candidates.py` | planned |
| §4.13, Eq. 32–33 | E_add / E_remove, make-before-break | `transition.py` | planned |
| §4.13 | Packet-level convergence and loss | testbed replay of `transitions.jsonl` | gap |
| §4.14 | Reconfiguration interval T_R vs recon lag | `controller.py` | planned |
