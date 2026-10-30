# Paper-to-code map

Where each part of *Doppler-security-26* is implemented. Status is one of
**planned**, **implemented**, or **gap** (cannot be implemented yet; see
`PLAN.md` §9). Update this table whenever a module is added or changed.

## §2 Threat model

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §2.1, Eq. 7 | Attack plan A = {(s_i, d_i, r_i)} | `attack_plans.py` | planned |
| §2.1 | Attack success: L_e + Σ r_i > c_e | `damage.py` | planned |
| §2.4, Eq. 1 | Transferability τ(A_i, G_j) | `damage.py` | planned |

## §3 Reconnaissance

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §3.1.1, Eq. 2 | Minimum RTT per vantage-point pair | `recon/rtt_ricci.py` | planned (simulated RTTs) |
| §3.1.1, Eq. 3 | Threshold graphs Ĝ_ε and ε sweep | `recon/rtt_ricci.py` | planned |
| §3.1.1, Eq. 4 | Ollivier–Ricci ranking | `recon/rtt_ricci.py` | planned |
| §3.1.2, Eq. 5 | Observed traceroute graph Ĝ_tr | `recon/traceroute.py` | planned (simulated probes) |
| §3.1.2, Eq. 6 | Betweenness ranking B(e) | `recon/traceroute.py` | planned |
| §3.2 | Oracle attacker | `recon/oracle.py` | planned |
| §3.2 | No-knowledge attacker | `recon/random_plan.py` | planned |
| §3.3, Eq. 8 | Equal split of budget R_A | `attack_plans.py` | planned |
| §3.4 | Precision, recall, F1 | `recon/metrics.py` | planned |
| §3.4, Eq. 9 | P@k, path-level critical-link recovery | `recon/metrics.py` | planned |
| §3.4, Eq. 10 | Normalized effectiveness η | `damage.py` | planned |
| §3.5 | Real measurements on operational networks | loader interface in `recon/` | gap (no raw data) |

## §4 Doppler

| Paper | Concept | Module / function | Status |
|---|---|---|---|
| §4.3 | Control loop (Fig. 1) | `controller.py`; diagram in `docs/diagrams/control-loop.md` | planned (diagram done) |
| §4.3 input 4 | Estimated benign demand D_t | `traffic.py` | planned |
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
