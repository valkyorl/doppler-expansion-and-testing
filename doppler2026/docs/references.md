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
| Gravity traffic model | Benign traffic matrices | `traffic.py` | M. Roughan, "Simplifying the synthesis of Internet traffic matrices", *ACM SIGCOMM CCR*, 2005 | unverified |
| ECMP routing | Default TE for filters and damage | `routing.py` via `src/onset/te/engine.py` | C. Hopps, "Analysis of an Equal-Cost Multi-Path Algorithm", RFC 2992, 2000 | unverified |
| SMORE semi-oblivious TE | Optional TE method | `routing.py` via `src/onset/te/engine.py` | P. Kumar et al., "Semi-oblivious traffic engineering: the road not taken", USENIX NSDI 2018 | unverified |
| Räcke oblivious routing / FRT tree embedding | Inside SMORE | `src/onset/te/engine.py` (reused) | H. Räcke, "Optimal hierarchical decompositions for congestion minimization in networks", ACM STOC 2008; J. Fakcharoenphol, S. Rao, K. Talwar, "A tight bound on approximating arbitrary metrics by tree metrics", ACM STOC 2003 | unverified |
| Max-min fair sharing at congested links | Computing delivered vs dropped traffic (damage D) | `src/onset/te/engine.py` (reused) | Behaviour matches YATES: P. Kumar et al., "YATES: Rapid prototyping for traffic engineering systems", ACM SOSR 2018 | unverified |
| Haversine great-circle distance | Optical reach, propagation delay for simulated RTT, latency stretch | `feasibility.py`, `recon/rtt_ricci.py`, `filters.py` | Standard formula; no citation needed | — |
| Coremelt link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | A. Studer and A. Perrig, "The Coremelt attack", ESORICS 2009 | unverified |
| Crossfire link-flooding attack | Attack model background (§2.1) | `attack_plans.py` | M. S. Kang, S. B. Lee, V. D. Gligor, "The Crossfire attack", IEEE S&P 2013 | unverified |

## Software

| Software | Used for | Cite | Status |
|---|---|---|---|
| GraphRicciCurvature 0.6.1 | Ollivier–Ricci computation | C.-C. Ni et al., "Community detection on networks with Ricci flow", *Scientific Reports*, 2019 (the library's recommended citation; confirm in its README) | unverified |
| HiGHS / highspy | Solving the MILP and LPs | Q. Huangfu and J. A. J. Hall, "Parallelizing the dual revised simplex method", *Mathematical Programming Computation*, 2018 | unverified |
| NetworkX | Graphs, paths, betweenness | A. Hagberg, D. Schult, P. Swart, "Exploring network structure, dynamics, and function using NetworkX", SciPy Conference 2008 | unverified |
| SciPy | Sparse matrices, MCF LP in the TE engine | P. Virtanen et al., "SciPy 1.0: fundamental algorithms for scientific computing in Python", *Nature Methods*, 2020 | unverified |
| NumPy | Numerics | C. R. Harris et al., "Array programming with NumPy", *Nature*, 2020 | unverified |
| TMgen (vendored, `vendor/TMgen`) | Optional gravity TM generation | Software repository; cite by URL and version | to identify |

## Datasets

| Dataset | Used for | Source / cite | Status |
|---|---|---|---|
| ANS, CRL, bellCanada, sprint, surfNet, Comcast topologies (`data/graphs/gml/`) | Simulated experiments | Likely the Internet Topology Zoo: S. Knight et al., "The Internet Topology Zoo", *IEEE JSAC*, 2011. Confirm each file's origin | to identify |
| Regional ground truth and Ricci reconstruction (`data/graphs/json/regional/`) | RTT attacker, RQ1–RQ2 | Provenance unknown; possibly router-proxy derived (audit #8). Must be confirmed before use as ground truth (§3.4) | to identify |
| GRNOC router-proxy output (`data/NOC/`) | Not used as ground truth | GlobalNOC router proxy; collected under the authorization rules of §3.6 (to confirm) | to identify |
