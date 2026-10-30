# Inputs to the Doppler 2026 experiment

Every library, named method or algorithm, and dataset the experiment uses,
with where it is used and what to cite. Keep this up to date whenever code is
added (rule 5 in `CLAUDE.md`).

**Verification status.** The citations below were written from memory while
planning. None has been checked against the publication yet. Before citing
one in the paper, confirm authors, title, venue, and year, then change its
status to "verified" and add the DOI.

Status values: `unverified` (from memory), `verified` (checked against the
source), `to identify` (the right source is not yet known).

## Methods and algorithms

| Input | Used for | Where (planned) | Cite | Status |
|---|---|---|---|---|
| Ollivier–Ricci curvature | Ranking inferred edges for the RTT attacker (Eq. 4) | `recon/rtt_ricci.py` | Y. Ollivier, "Ricci curvature of Markov chains on metric spaces", *Journal of Functional Analysis*, 2009 | unverified |
| RTT-based topology inference with Ricci curvature | The RTT attacker's overall method (§3.1.1); the paper cites it as "prior work [?]" | `recon/rtt_ricci.py` | Ask the authors which work the draft's [?] refers to. One candidate: L. Salamatian et al., "Curvature-based analysis of network connectivity in private backbone infrastructures", ACM SIGMETRICS 2022 | to identify |
| Shortest-path (edge) betweenness | Traceroute attacker ranking (Eq. 6); local candidate set | `recon/traceroute.py`, `candidates.py` | L. C. Freeman, "A set of measures of centrality based on betweenness", *Sociometry*, 1977. Algorithm used by NetworkX: U. Brandes, "A faster algorithm for betweenness centrality", *Journal of Mathematical Sociology*, 2001 | unverified |
| k-shortest simple paths (Yen's algorithm) | Tunnel computation in preprocessing (`nx.shortest_simple_paths`) | `src/onset/preprocessing.py` (reused) | J. Y. Yen, "Finding the k shortest loopless paths in a network", *Management Science*, 1971 | unverified |
| Multi-commodity flow MILP for topology selection | Candidate pool generation (Eq. 11–16) | `candidates.py` via `src/onset/open_doppler.py` | Standard formulation; cite the authors' own earlier Doppler/ONSET papers for the lineage (to identify) | to identify |
| No-good (canonical) cuts | Enumerating distinct candidate topologies | `candidates.py` | E. Balas and R. Jeroslow, "Canonical cuts on the unit hypercube", *SIAM Journal on Applied Mathematics*, 1972 | unverified |
| Single-commodity flow connectivity constraint | Keeping candidate topologies connected | `src/onset/open_doppler.py` (reused) | Commonly attributed to B. Gavish and S. C. Graves (1978) | to identify |
| Gravity traffic model (exponential PoP masses) | Benign traffic matrices | `traffic.gravity_matrix` (in use) | M. Roughan, "Simplifying the synthesis of Internet traffic matrices", *ACM SIGCOMM CCR*, 2005 | unverified |
| ECMP routing | Default TE for damage (and later filters) | `routing.route` via `onset.te.route_demands` (in use) | C. Hopps, "Analysis of an Equal-Cost Multi-Path Algorithm", RFC 2992, 2000 | unverified |
| Proportional (tail-drop) loss at overloaded links, fluid model | How an overloaded link divides capacity when measuring damage (D11) | `onset.te.deliver_flows` → `_capacity_constrained_delivery` (in use) | A fluid FIFO/tail-drop model; a standard reference for fluid network models still to be chosen | to identify |
| Max-min fair sharing (water-filling) | Alternative loss model, kept as a setting (`DamageConfig.sharing = "max_min"`) | `onset.te.engine._link_rule` (in use when selected) | D. Bertsekas and R. Gallager, *Data Networks*, Prentice Hall, 1992 (max-min fairness chapter) | unverified |
| Damped fixed-point iteration | Solving per-link drop rules and flow rates together | `onset.te.engine._capacity_constrained_delivery` (in use) | Standard numerical method; no citation needed | — |
| Oracle target ranking (concentrable attack traffic, then link usage) | Oracle attacker (§3.2, interpretation I3) | `recon/oracle.py` (in use) | The paper's own definition; link usage is edge betweenness over attacker endpoints under the network's routing (see the betweenness row) | — |
| SMORE semi-oblivious TE | Optional TE method | `routing.py` via `src/onset/te/engine.py` | P. Kumar et al., "Semi-oblivious traffic engineering: the road not taken", USENIX NSDI 2018 | unverified |
| Räcke oblivious routing / FRT tree embedding | Inside SMORE | `src/onset/te/engine.py` (reused) | H. Räcke, "Optimal hierarchical decompositions for congestion minimization in networks", ACM STOC 2008; J. Fakcharoenphol, S. Rao, K. Talwar, "A tight bound on approximating arbitrary metrics by tree metrics", ACM STOC 2003 | unverified |
| YATES-compatible hop-by-hop loss model | Not used by the experiment (it uses `deliver_flows`); listed because `evaluate()` claims YATES parity | `onset.te.evaluate` | P. Kumar et al., "YATES: Rapid prototyping for traffic engineering systems", ACM SOSR 2018 | unverified |
| Haversine great-circle distance | Optical reach, propagation delay for simulated RTT, latency stretch | `feasibility.py`, `recon/rtt_ricci.py`, `filters.py` | Standard formula; no citation needed | — |
| Coremelt link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | A. Studer and A. Perrig, "The Coremelt attack", ESORICS 2009 | unverified |
| Crossfire link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | M. S. Kang, S. B. Lee, V. D. Gligor, "The Crossfire attack", IEEE S&P 2013 | unverified |

## Software

| Software | Used for | Cite | Status |
|---|---|---|---|
| GraphRicciCurvature 0.6.1 | Ollivier–Ricci computation | C.-C. Ni et al., "Community detection on networks with Ricci flow", *Scientific Reports*, 2019 (the library's recommended citation; confirm in its README) | unverified |
| HiGHS / highspy | Solving the MILP and LPs | Q. Huangfu and J. A. J. Hall, "Parallelizing the dual revised simplex method", *Mathematical Programming Computation*, 2018 | unverified |
| NetworkX | Graphs, shortest paths (ECMP via `all_shortest_paths`), GML loading | A. Hagberg, D. Schult, P. Swart, "Exploring network structure, dynamics, and function using NetworkX", SciPy Conference 2008 | unverified |
| SciPy | Sparse matrices, MCF LP in the TE engine | P. Virtanen et al., "SciPy 1.0: fundamental algorithms for scientific computing in Python", *Nature Methods*, 2020 | unverified |
| NumPy | Seeded random draws (gravity masses, random attacker) | C. R. Harris et al., "Array programming with NumPy", *Nature*, 2020 | unverified |
| TMgen (vendored, `vendor/TMgen`) | Optional gravity TM generation | Software repository; cite by URL and version | to identify |

## Datasets

| Dataset | Used for | Source / cite | Status |
|---|---|---|---|
| ANS, CRL, bellCanada, sprint, surfNet topologies (`data/graphs/gml/`) | Simulated experiments; ANS in the Phase 1 check (`topology.load_topology`) | Internet Topology Zoo: each file's `Creator` field reads "Topology Zoo Toolset" (origin checked 2026-10-30). Cite S. Knight et al., "The Internet Topology Zoo", *IEEE JSAC*, 2011 | origin verified; citation unverified |
| Comcast topology (`data/graphs/gml/Comcast.gml`) | Not used yet | No `Creator` field; origin unknown | to identify |
| Regional ground truth and Ricci reconstruction (`data/graphs/json/regional/`) | RTT attacker, RQ1–RQ2 | Provenance unknown; possibly router-proxy derived (audit #8). Must be confirmed before use as ground truth (§3.4) | to identify |
| GRNOC router-proxy output (`data/NOC/`) | Not used as ground truth | GlobalNOC router proxy; collected under the authorization rules of §3.6 (to confirm) | to identify |
