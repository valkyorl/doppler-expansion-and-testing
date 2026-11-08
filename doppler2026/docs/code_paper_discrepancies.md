# Code–paper discrepancies

Every place where the implementation does something other than what the draft
(*Doppler-security-26*, August 2026) spells out, and every promise the
current results do not support. Choices the paper leaves open
(interpretations, parameter values) are not listed here; they are in
`decisions.md`.

Each entry gives what the paper says, what the code does, why, and what the
paper would need to say to match. References in brackets point to
`decisions.md`.

Status: **in effect** (the code does this now), **in progress** (decided,
not yet built), or **open** (a promise the results do not yet support).

## A. Departures from the paper's specification

### A1. The reference oracle for η also knows benign traffic [D15, O1] — in effect

- **Paper (§3.2):** the oracle "has access to the true network topology and
  routing state" and "therefore represents an upper bound on the value of
  topology reconnaissance".
- **Code:** η (Eq. 10) is measured against an oracle that also knows the
  benign traffic matrix and targets the link where its attack does the most
  benign damage. The paper's oracle is kept and reported alongside.
- **Why:** the paper's oracle is not an upper bound. It cannot tell which
  link carries benign traffic, and measured attackers did more damage than it
  in 15% of plans at 2x link capacity (η up to 4.75).
- **Paper change:** §3.2 must say the oracle knows benign traffic, or drop
  "upper bound". Even the benign-aware oracle is not a proven upper bound
  (η > 1 in 0.4-0.6% of plans).

### A2. The history includes the current topology [D30] — in effect

- **Paper (Eq. 19-20):** the history is G_{t-1}, ..., G_{t-h} and their plans.
- **Code:** the last h states including the current one, G_t ... G_{t-h+1}.
- **Why:** the attacker most likely holds a plan for the running topology, so
  a candidate must invalidate it too.
- **Paper change:** Eq. 19 indexed from G_t.

### A3. K counts candidates before the security filter [PLAN §2] — in effect

- **Paper (§4.11, Eq. 31):** Doppler "enumerates up to K candidate
  configurations satisfying T(G') <= τ_max and all operational constraints".
- **Code:** the MILP enumerates up to K candidates that satisfy the optical,
  flow, and utilization constraints (Eq. 11-16); the operational filter
  (ECMP routing, stretch, connectivity) and the security filter (Eq. 22) run
  afterwards, so the safe pool is usually much smaller than K.
- **Why:** T(G') is not linear (it routes attack traffic and builds a fresh
  attacker plan per candidate), so it cannot be a MILP constraint.
- **Paper change:** describe the enumeration as generate-then-filter and
  report pool sizes after each filter.

### A4. The MILP does not minimize T(G') [O5] — in effect

- **Paper (§4.11, Eq. 25):** "minimize T(G')" subject to the constraints.
- **Code:** the MILP minimizes a weighted count of changes plus utilization
  (D22); T(G') is only checked afterwards (A3). A security heuristic
  (`security_guided`: favour changes that move the history plans' attack
  traffic off their targets) was built for O5 but did not help (its score
  does not predict τ), so it is not the default.
- **Why:** T(G') cannot be in a MILP.
- **Paper change:** Eq. 25 is the conceptual problem; the paper should say
  how candidates are actually generated and that T(G') is applied as a
  filter.

### A5. The structural-churn baseline selects from Doppler's pool [O6] — in effect

- **Paper (§4.8, Eq. 18):** structural churn chooses "min |E_t ∩ E'|".
- **Code:** Eq. 18 is applied as the selection rule over the
  operationally feasible candidates of a pool generated without security
  guidance, with no security filter.
- **Why:** optimizing Eq. 18 directly gave only large rewirings (8 links
  added, 16 removed) that all failed the stretch limit, so the baseline never
  changed the network and was not a fair comparison.
- **Paper change:** define the baseline as Eq. 18 over the same feasible
  candidates and operational constraints as Doppler.

### A6. The security filter also limits stale damage and vulnerability [O7] — in effect

- **Paper (§4.8, Eq. 22):** a candidate is safe when T(G') <= τ_max.
- **Code:** two further conditions, both on by default:
  - stale damage: every history plan's damage is at most what that plan did
    on its own topology, D(A_i, G') <= D(A_i, G_i)
    (`max_stale_damage_ratio = 1.0`);
  - vulnerability: a fresh attacker's damage on G' is at most its damage on
    the original topology G_0 (`max_vulnerability_ratio = 1.0`), so
    reconfiguring never makes the network more vulnerable.
- **Why:** τ is a ratio against a fresh attacker on G'. Reconfiguration that
  weakened the network kept τ low while every attack did more damage
  (Doppler on ANS: stale attacks caused 13.3% benign loss against 2.6% on
  the static network). The stale-damage limit alone still allowed swaps that
  created a new weak point (6.6% with one spare per PoP); only the
  vulnerability limit kept Doppler at or below the static network (2.4%).
  G1's own wording ("produce substantially less damage") and G2 are about
  damage, not the ratio.
- **Paper change:** Eq. 22 gains both damage conditions, or G1 is restated
  in terms of the ratio only and the paper says Doppler may increase
  vulnerability.

### A7. Candidates may not have fewer links than the current topology [O2, O7] — in effect

- **Paper (§4.5, Eq. 11):** transponders bound the active links at each PoP
  from above; nothing keeps the number of links.
- **Code:** at least as many links as the current topology
  (`keep_link_count`), so transponders are re-paired rather than released.
- **Why:** without it, change-minimizing generation only removed links,
  and each removal made the network more vulnerable (O7).
- **Paper change:** §4.5 should state the constraint, or say that circuits
  freed by a reconfiguration are reused ("Doppler may deactivate one existing
  circuit and reuse its endpoint transponders", §4.5, already suggests it).

## B. Paper requirements not met for lack of data or infrastructure

### B1. Simulated measurements, not operational networks — in effect

- **Paper (§3.5, Table 1):** reconnaissance on "the four operational
  networks used in our original study", with real RTT and traceroute
  campaigns (vantage points, probe counts, intervals, alias resolution).
- **Code:** RTT and traceroute measurements are simulated on five Internet
  Topology Zoo networks. The only real data is the stored Ricci
  reconstruction of the regional network; no raw measurements exist.
- **Paper change:** label results as simulated, or obtain the measurement
  campaigns.

### B2. No independently validated ground truth — in effect

- **Paper (§3.4, Table 1):** topology recovery is measured only against
  ground truth "independently validated by the network operator".
- **Code:** for simulated networks the simulated topology is the ground
  truth. The regional network's ground truth has unknown provenance (audit
  #8), so topology recovery is refused there.

### B3. The fiber graph is the IP topology [D16] — in effect

- **Paper (§4.1):** a fiber graph G_F distinct from the IP topology;
  optical circuits route over it.
- **Code:** each link of the original IP topology is taken to be one fiber.
  A new IP link may ride a path of at most two such fibers.

### B4. Feasibility checks are incomplete [D16, D6] — in effect

- **Paper (§4.4):** the feasibility test "at minimum" incorporates fiber
  connectivity, ROADM placement and switching, transponder availability,
  optical reach, and wavelength or spectrum constraints.
- **Code:** fiber hops and an optional reach limit (off by default).
  ROADM and spectrum checks are a hook that allows every link. Transponder
  availability is enforced in the MILP (Eq. 11).

### B5. Transponder counts are assumed [D18] — in effect

- **Paper (§4.3 input 3, §4.5):** "the number and placement of available
  transponders" is an input.
- **Code:** each PoP has one transponder per original link plus one spare
  (default since 2026-11-03, after O7); the number and placement of spares
  are experiment settings.

### B6. New-link capacity is assumed [D17] — in effect

- **Paper (Eq. 15, §4.5):** C_e is the link's realizable capacity, derived
  from the circuits assigned to it.
- **Code:** a new link gets the network's median link capacity.

### B7. Transitions are evaluated at flow level only [I20; PLAN §9] — in effect

- **Paper (§1, §4.13):** measures "routing convergence, packet loss, and
  latency during topology transitions" and separately times circuit
  reconfiguration and link establishment.
- **Code:** utilization, connectivity, and benign loss after each step of the
  transition; actions are ordered but not timed. Packet-level effects need a
  testbed.

### B8. Epochs are abstract, not timed [D10] — in effect

- **Paper (§4.14, §5):** compares the observed cost of reconnaissance with
  the end-to-end time to compute and install a topology.
- **Code:** time is counted in epochs; the attacker's lag L is a number of
  epochs. Only solver time is real.

## C. Promises the current results do not support

Results with the v0 defaults (10 epochs, one seed, runs
`controller/v0-<network>-<mode>`; table `figures/out/controller_stale_damage.md`).
"Stale loss" is the mean share of benign traffic lost to the attack running
in each epoch, which uses the plan learned one epoch earlier (L = 1).

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

### C1. Sustained expiry of reconnaissance — open (O5, O8)

- **Paper (§1, contributions, §4.2 G1):** Doppler "periodically selects a new
  feasible optical topology such that attack plans derived from previous
  network states have low effectiveness", "forcing an attacker to repeat
  reconnaissance".
- **Results at v0:** only on sprint does Doppler keep moving (6 of 10
  epochs), and there the stale plan's τ averages 0.57 and its damage falls
  from 2.3% to 0.9%. On ANS it moves twice (2.4% against 2.6%). On CRL,
  bellCanada, and surfNet it never moves: no candidate passes both the
  operational and the security filter (O8), so the stale attack is fully
  effective (τ = 1.0), as on a static network.
- **Paper change if it persists:** "reconfigures while safe moves exist",
  the controller's behavior when none exists (stays put, D29), and a measured
  per-network budget of safe moves.

### C2. Doppler versus structural churn — open (O6)

- **Paper (§1, §4.8):** "Rather than merely maximizing structural
  differences..."; two topologies with small edge overlap can still route
  attack traffic through the same cut.
- **Results at v0:** the churn baseline (A5) changes the topology in every
  epoch on every network. Against the static network its stale loss is
  higher on sprint (3.4% against 2.3%), ANS (3.7% against 2.6%), and
  surfNet (7.2% against 6.1%), and lower on CRL (7.4% against 9.8%) and
  bellCanada (5.1% against 5.6%). Doppler is below churn on sprint and ANS,
  but above it on CRL and bellCanada, where Doppler never moves. So the
  paper's claim holds on two networks, and on two others plain structural
  change does better than Doppler at v0.

### C3. Reconfiguring must not increase the damage attacks do — met by an added condition (O7, A6)

- **Paper (§4.2 G1, G2):** after a transition, a stale plan "should produce
  substantially less damage"; "a topology is not a valid defense if it
  protects the network by degrading its users".
- **Results:** under Eq. 22 alone (τ only) Doppler made ANS more vulnerable
  (stale loss 13.3% against 2.6% static, before the v0 defaults). τ is a
  ratio against a fresh attacker on the same topology, so a weaker topology
  can still have low τ. With the stale-damage and vulnerability limits of A6
  and the no-net-loss rule of A7, Doppler's stale loss is at or below the
  static network's in every epoch on every network at v0. The cost is fewer moves: on bellCanada, sprint,
  and ANS, candidates that pass τ are rejected only by the vulnerability
  limit (O8).
- **Paper change:** G1 measured as a ratio (Eq. 1) does not guarantee less
  damage; the paper needs an absolute damage bound in the security filter
  (as A6) or a statement that τ alone is insufficient.
