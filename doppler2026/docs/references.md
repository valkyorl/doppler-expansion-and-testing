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
| Ollivier–Ricci curvature | Ranking inferred edges for the RTT attacker (Eq. 4) | `recon/rtt_ricci.ricci_curvature` (in use) | Y. Ollivier, "Ricci curvature of Markov chains on metric spaces", *Journal of Functional Analysis*, 2009 | unverified |
| RTT-based topology inference with Ricci curvature | The RTT attacker's overall method (§3.1.1); the paper cites it as "prior work [?]". Our ε-as-quantile (D13) and unweighted curvature (I10) should be checked against it once identified | `recon/rtt_ricci.py` (in use) | Ask the authors which work the draft's [?] refers to. One candidate: L. Salamatian et al., "Curvature-based analysis of network connectivity in private backbone infrastructures", ACM SIGMETRICS 2022 | to identify |
| Shortest-path (edge) betweenness | Traceroute attacker ranking (Eq. 6), via `nx.edge_betweenness_centrality_subset`; local candidate set (Phase 3) | `recon/inferred.betweenness` (in use), `candidates.py` | L. C. Freeman, "A set of measures of centrality based on betweenness", *Sociometry*, 1977. Algorithm used by NetworkX: U. Brandes, "A faster algorithm for betweenness centrality", *Journal of Mathematical Sociology*, 2001 | unverified |
| k-shortest simple paths (Yen's algorithm) | Tunnel computation in preprocessing (`nx.shortest_simple_paths`) | `src/onset/preprocessing.py` (reused) | J. Y. Yen, "Finding the k shortest loopless paths in a network", *Management Science*, 1971 | unverified |
| Multi-commodity flow MILP for topology selection | Candidate pool generation (Eq. 11–16) | `candidates.py` via `src/onset/open_doppler.py` | Standard formulation; cite the authors' own earlier Doppler/ONSET papers for the lineage (to identify) | to identify |
| No-good (canonical) cuts | Enumerating distinct candidate topologies | `candidates.py` | E. Balas and R. Jeroslow, "Canonical cuts on the unit hypercube", *SIAM Journal on Applied Mathematics*, 1972 | unverified |
| Single-commodity flow connectivity constraint | Keeping candidate topologies connected | `src/onset/open_doppler.py` (reused) | Commonly attributed to B. Gavish and S. C. Graves (1978) | to identify |
| Gravity traffic model (exponential PoP masses) | Benign traffic matrices | `traffic.gravity_matrix` (in use) | M. Roughan, "Simplifying the synthesis of Internet traffic matrices", *ACM SIGCOMM CCR*, 2005 | unverified |
| ECMP routing | Default TE for damage (and later filters) | `routing.route` via `onset.te.route_demands` (in use) | C. Hopps, "Analysis of an Equal-Cost Multi-Path Algorithm", RFC 2992, 2000 | unverified |
| Proportional (tail-drop) loss at overloaded links, fluid model | How an overloaded link divides capacity when measuring damage (D11) | `onset.te.deliver_flows` → `_capacity_constrained_delivery` (in use) | A fluid FIFO/tail-drop model; a standard reference for fluid network models still to be chosen | to identify |
| Max-min fair sharing (water-filling) | Alternative loss model, kept as a setting (`DamageConfig.sharing = "max_min"`) | `onset.te.engine._link_rule` (in use when selected) | D. Bertsekas and R. Gallager, *Data Networks*, Prentice Hall, 1992 (max-min fairness chapter) | unverified |
| Damped fixed-point iteration | Solving per-link drop rules and flow rates together | `onset.te.engine._capacity_constrained_delivery` (in use) | Standard numerical method; no citation needed | — |
| No-good (canonical) cuts | Excluding each found topology so the next MILP solve returns a different one (§4.11; `candidates.py`) | `candidates._Model.no_good_cut` (in use) | E. Balas and R. Jeroslow, "Canonical cuts on the unit hypercube", *SIAM Journal on Applied Mathematics*, 1972 | unverified |
| Source-aggregated multicommodity flow | Exact, smaller form of Eq. 12-14 (one flow per source PoP; decision P9) | `candidates.py` (in use) | Standard; e.g. R. K. Ahuja, T. L. Magnanti, J. B. Orlin, *Network Flows*, Prentice Hall, 1993 | unverified |
| Edge betweenness for the local candidate set | Ranking G_t's links to pick the region the local set works around (§4.10, D23) | `candidates.variable_links` (in use) | See the betweenness row; the rule itself comes from the old Doppler's "conservative" set (`src/onset/preprocessing.compute_candidate_links`) | — |
| Oracle target ranking (concentrable attack traffic, then link usage) | Oracle attacker (§3.2, interpretation I3) | `recon/oracle.py` (in use) | The paper's own definition; link usage is edge betweenness over attacker endpoints under the network's routing (see the betweenness row) | — |
| SMORE semi-oblivious TE | Optional TE method | `routing.py` via `src/onset/te/engine.py` | P. Kumar et al., "Semi-oblivious traffic engineering: the road not taken", USENIX NSDI 2018 | unverified |
| Räcke oblivious routing / FRT tree embedding | Inside SMORE | `src/onset/te/engine.py` (reused) | H. Räcke, "Optimal hierarchical decompositions for congestion minimization in networks", ACM STOC 2008; J. Fakcharoenphol, S. Rao, K. Talwar, "A tight bound on approximating arbitrary metrics by tree metrics", ACM STOC 2003 | unverified |
| YATES-compatible hop-by-hop loss model | No longer used anywhere: `evaluate()` replaced it on 2026-11-03 (E1), because it let a link carry more than its capacity. Kept here because earlier results of existing methods were produced with it | `onset.te.evaluate` (before 2026-11-03) | P. Kumar et al., "YATES: Rapid prototyping for traffic engineering systems", ACM SOSR 2018 | unverified |
| Haversine great-circle distance | Propagation delay for simulated RTT (in use, `topology.great_circle_km` via `onset.utilities.reconfiguration.calc_haversine`); later optical reach and latency stretch | `topology.py`, `feasibility.py`, `filters.py` | Standard formula; no citation needed | — |
| Paris traceroute (fixed flow identifier, so a probe follows one ECMP path) | How simulated traceroute picks one path per probe (I9) | `recon/traceroute.simulate` (in use) | B. Augustin et al., "Avoiding traceroute anomalies with Paris traceroute", ACM IMC 2006 | unverified |
| Anonymous / non-responding routers in traceroute | Why silent hops exist and why they break paths (D12) | `recon/traceroute.py` (in use) | A standard reference on anonymous routers in topology inference (e.g. B. Yao et al., "Topology inference in the presence of anonymous routers", IEEE INFOCOM 2003) | to identify |
| Speed of light in fiber, about 2/3 c (200 km/ms) | Propagation delay of simulated RTTs (I11) | `recon/rtt_ricci.RttConfig.fiber_km_per_ms` (in use) | Physical constant (refractive index ≈ 1.5); no citation needed | — |
| Exponential queuing delay per probe | Noise in simulated RTTs, removed by the minimum (Eq. 2; I11) | `recon/rtt_ricci.simulate` (in use) | Modelling assumption, not from a source; a measurement study of RTT distributions could justify it | to identify |
| Bisection search | Budget needed to disrupt (§3.4 bullet 5, D14) | `damage.budget_to_disrupt` (in use) | Standard numerical method; no citation needed | — |
| Coremelt link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | A. Studer and A. Perrig, "The Coremelt attack", ESORICS 2009 | unverified |
| Crossfire link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | M. S. Kang, S. B. Lee, V. D. Gligor, "The Crossfire attack", IEEE S&P 2013 | unverified |
| Random geometric graph (nodes placed uniformly at random, nearby pairs linked) | Synthetic test networks: closest pairs are linked after each PoP's nearest neighbours (user's choice, 2026-11-10) | `synthetic.generate` (in use) | M. Penrose, *Random Geometric Graphs*, Oxford University Press, 2003 | unverified |
| k-nearest-neighbour graph | Synthetic networks: each PoP first links to its 2 nearest PoPs, so none is isolated | `synthetic.generate` (in use) | Standard construction; no citation needed unless the paper uses the synthetic networks | — |

## Software

| Software | Used for | Cite | Status |
|---|---|---|---|
| GraphRicciCurvature 0.6.1 (installed with `--no-deps`, P8) | Ollivier–Ricci computation (in use, `recon/rtt_ricci.py`) | C.-C. Ni et al., "Community detection on networks with Ricci flow", *Scientific Reports*, 2019 (the library's recommended citation; confirm in its README) | unverified |
| POT (Python Optimal Transport) 0.9.7 | Exact earth mover's distance inside GraphRicciCurvature | R. Flamary et al., "POT: Python Optimal Transport", *Journal of Machine Learning Research*, 2021 | unverified |
| NetworKit 11.2 | Shortest paths inside GraphRicciCurvature | C. L. Staudt, A. Sazonovs, H. Meyerhenke, "NetworKit: A tool suite for large-scale complex network analysis", *Network Science*, 2016 | unverified |
| python-louvain 0.16 | Required by GraphRicciCurvature's import; its community detection is not used | Not cited (not used) | — |
| HiGHS / highspy | Solving the MILP and LPs; the candidate pool MILP (`candidates.py`) | Q. Huangfu and J. A. J. Hall, "Parallelizing the dual revised simplex method", *Mathematical Programming Computation*, 2018 | unverified |
| NetworkX | Graphs, shortest paths (ECMP via `all_shortest_paths`), GML loading; 2-edge-connectivity (`is_k_edge_connected`, `filters.py`) | A. Hagberg, D. Schult, P. Swart, "Exploring network structure, dynamics, and function using NetworkX", SciPy Conference 2008 | unverified |
| SciPy | Sparse matrices, MCF LP in the TE engine | P. Virtanen et al., "SciPy 1.0: fundamental algorithms for scientific computing in Python", *Nature Methods*, 2020 | unverified |
| NumPy | Seeded random draws (gravity masses, random attacker) | C. R. Harris et al., "Array programming with NumPy", *Nature*, 2020 | unverified |
| TMgen (vendored, `vendor/TMgen`) | Optional gravity TM generation | Software repository; cite by URL and version | to identify |

## Datasets

| Dataset | Used for | Source / cite | Status |
|---|---|---|---|
| ANS, CRL, bellCanada, sprint, surfNet topologies (`data/graphs/gml/`) | Simulated experiments: Phase 1 check (ANS), reconnaissance evaluation (all five) | Internet Topology Zoo: each file's `Creator` field reads "Topology Zoo Toolset" (origin checked 2026-10-30). Cite S. Knight et al., "The Internet Topology Zoo", *IEEE JSAC*, 2011 | origin verified; citation unverified |
| Comcast topology (`data/graphs/gml/Comcast.gml`) | Not used yet | No `Creator` field; origin unknown | to identify |
| Regional ground truth and Ricci reconstruction (`data/graphs/json/regional/`) | RTT attacker on a stored reconstruction (in use, `rtt_ricci.load_regional_*`); RQ2/RQ3 rows flagged not independent; RQ1 refused (I12). Files hold only edge lists (12 nodes; 18 true and 53 inferred edges) and capacities in unknown units | Provenance unknown; possibly router-proxy derived (audit #8). Must be confirmed before use as ground truth (§3.4) | to identify |
| GRNOC router-proxy output (`data/NOC/`) | Not used as ground truth | GlobalNOC router proxy; collected under the authorization rules of §3.6 (to confirm) | to identify |
| Synthetic network `synthetic15` (`doppler2026/topologies/synthetic15.gml`) | Sparsification study (`studies/sparsification_synthetic15.py`) | Generated by `doppler2026.synthetic` (seed 0, defaults recorded in the file); not real data | generated |
| Synthetic network `synthetic4` (`doppler2026/topologies/synthetic4.gml`) | Sparsification study (`studies/sparsification_synthetic4.py`) | Generated by `doppler2026.synthetic` (4 PoPs, every pair linked, seed 0; settings recorded in the file); not real data | generated |
