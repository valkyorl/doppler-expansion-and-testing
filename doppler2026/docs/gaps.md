# Known gaps

Parts of the paper that cannot be implemented yet, each with what exists now
and how it plugs in later (rule 7 in `CLAUDE.md`). Moved here from §9 of
the v0 plan (`archive/v0/PLAN.md`) on 2026-11-10; keep it current.

The work proceeds without these. Each gap gets an interface now, so the
missing piece can be added later without reworking the code around it.

| Gap | Paper | What is built now | How it is closed later | Blocks |
|---|---|---|---|---|
| Packet-level transition effects (convergence, packet loss) | §1, §4.13 | `transition.py` writes an explicit, ordered (numbered, not timed) list of IP-link actions per transition, plus flow-level metrics for each intermediate state | An emulation testbed replays the action list and reports convergence and loss into the same result schema | The paper's transient-effects claims only |
| Real RTT / traceroute measurements | §3.5 | Recon modules read measurements through one loader interface; a simulator implements it. The existing regional Ricci reconstruction gets its own loader | Add a loader per real dataset; collection must follow §3.6 authorization rules | RQ1–RQ3 on operational networks |
| Independent ground truth | §3.4 | RQ1 metrics refuse to run unless the ground-truth source is marked as independently validated in the config | Confirm provenance of the regional ground truth (audit #8) or obtain operator-validated topologies | RQ1 numbers only |
| Optical data (ROADM, spectrum, transponder placement) | §4.4 | Feasibility = fiber path + reach, with a pluggable check for the rest (default: allowed, recorded as an assumption) | Add checks when optical data exists | Strength of G3 claims |
| ~~GraphRicciCurvature on Python 3.13~~ | §3.1.1 | Closed in Phase 2: installed with `--no-deps` (decision P8) | — | — |
| Comcast in the reconnaissance evaluation | §3.5 | Excluded from the default network list: its origin is unknown (`docs/references.md`) and at 149 nodes a full run is much slower | Confirm its origin; run it on its own with `--networks Comcast` | Coverage of one more network |
| ~~Open parameter choices D1–D10~~ | various | Closed at v0: all decided (`docs/decisions.md`) | — | — |
| Phase 5 experiment scripts (`transferability.py`, `diversity.py`, `cost.py`, `solver_budget.py`, `envelope.py`) | §4.2, §4.7, §4.9, §4.12, §2.5 | Every quantity they need is written by `run.py` and `experiments/defender_epoch.py`; one figure (`fig_controller_stale_damage.py`) compares the modes | One script per row of §7, each a sweep over configs writing the §10 schema | The paper's §4 evaluation |
| §3.3 oracle rate allocation (minimum budget to overload a target with capacity knowledge) | §3.3 | — | A new attacker in `recon/oracle.py` and a sweep in `recon_eval.py` | The §3.3 sensitivity experiment only |
| Sustained reconfiguration on most networks (O5, O8) | §1, §4.2 G1 | At v0's settings (git tag `v0`), Doppler moved on sprint and ANS; on CRL, bellCanada, and surfNet no candidate passed the operational and security filters (open issue O8). Under BL1 it is studied on synthetic networks (`studies/`) | Tuning (S_max, Eq. 17 latency allowance, larger changes, τ_max) measured with the envelope experiment | Claims C1-C3 in `docs/code_paper_discrepancies.md` |
| Figures for the pairwise τ heatmap (§4.9) and the cost metrics (§4.7, §4.13) | §4.7, §4.9, §4.13 | The values are written per epoch and per transition step (`defender_epoch.py`, `run.py`) | One script each in `figures/` reading those result files | The paper's diversity and cost figures |
| Defender model mismatch | §4.8 | The defender's history attacker is exactly the attacker that attacks (I18) | Run the security filter with one mechanism and attack with another, as a sweep axis | Claims about an attacker the defender did not model |
| Seeds and repetitions | §5 | Every run is exactly reproducible from its seed; each v0 run uses one seed | Repeat runs over seeds in the Phase 5 scripts and report spread | Confidence intervals in every figure |

**Paper-level risk.** The draft promises packet-level transition results. If
no testbed is available before submission, the paper text must be scoped
down. This is a decision for the authors, tracked here so it is not forgotten.
