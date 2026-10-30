# Doppler: Inputs and Topology-Search Algorithm

This document describes what Doppler takes as input and how it chooses a new
logical topology, as implemented on `main` (commit `aed64a1`). It is written
from the code, not the paper, and it flags places where the two may differ.

Code path, in call order:

| Step | File | Function |
|---|---|---|
| Experiment driver | `scripts/Doppler/exp-v2.py` | `experiment()` |
| Simulation setup | `src/onset/simulator.py` | `Simulation.__init__` |
| Transponder allocation | `src/onset/alpwolf.py` | `AlpWolf._init_transponders` |
| Per-iteration loop | `src/onset/simulator.py` | `Simulation.perform_sim` |
| Method dispatch | `src/onset/method_registry.py`, `src/onset/handlers.py` | `_resolve_method`, `_run_milp_method` |
| Problem construction | `src/onset/preprocessing.py` | `build_optimization_problem`, `preprocess_doppler` |
| MILP build and enumeration | `src/onset/open_doppler.py` | `_build_edge_flow_milp`, `solve_edge_flow_changes_mlu` |
| Solution choice | `src/onset/base_types.py` | `OptimizationResult.selected_solution` |
| Apply and evaluate | `src/onset/simulator.py`, `src/onset/te/engine.py` | `apply_solution`, `evaluate` |
| Reports | `src/onset/reporter.py` | `write_optimization_reports` |

Acronyms: TE = traffic engineering (routing), TP = topology programming
(the defense), MLU = maximum link utilization, MILP = mixed-integer linear
program, ECMP = equal-cost multi-path, MCF = multi-commodity flow,
ftx = fallow (spare) transponder.

---

## 1. Inputs

### 1.1 `Simulation(...)` constructor

| Argument | Default | `exp-v2.py` value | What Doppler does with it |
|---|---|---|---|
| `network_name` | required | `"Gigapop"` / `"CEN"` | Loads `data/graphs/gml/{name}.gml` or `data/graphs/json/{name}.json`. Also the cache key for tunnel paths (see §3.4). Neither Gigapop nor CEN exists in the repo. |
| `num_hosts` | required | `hosts[network]` | Used to create or check the hosts file. Must match the traffic-matrix dimension. |
| `test_name` | required | joined parameter string | Part of the experiment ID and result path only. |
| `iterations` | `0` | `1` | Number of traffic-matrix rows (time steps) to simulate. |
| `te_method` | `"-ecmp"` | `"-mcf"` | Routing used to evaluate the result. **Also changes Doppler's search:** `-mcf` forces `top_k = 1` (§3.8). |
| `traffic_file` | `""` | `data/traffic/{traffic}_{network}-tm` | Flattened traffic matrix, one row per time step, *n×n* values per row. |
| `topology_programming_method` | `""` | `"Doppler"` | Resolved case-insensitively by substring, so `"Doppler"` and `"doppler-v2"` both map to `doppler`. |
| `fallow_transponders` | `0` | `1, 2, 3` | Spare transponders per node, added on top of one per existing link. How they are spread depends on the allocation strategy (§3.1). |
| `fallow_tx_allocation_strategy` | `"static"` | `"dynamic_doppler"` | `static`, `dynamic`, `dynamic_doppler`, `file` or `read_capacity` (§3.1). |
| `fallow_tx_allocation_file` | `""` | — | Per-node `node,count` file, used only with strategy `file`. |
| `candidate_link_choice_method` | `"max"` | `"conservative"`, `"max"` | Which new links the MILP may light: `conservative`, `liberal` or `max` (§3.3). This is the strongest lever on behavior. |
| `congestion_threshold_upper_bound` | `0.8` | `0.99999` | Hard upper bound on MLU inside the MILP. Also, after evaluation, MLU at or above it sets `sig_add_circuits`. |
| `congestion_threshold_lower_bound` | `0.3` | `0.99999` | After evaluation, if MLU is at or below this and links were dropped, the applied solution is reverted. |
| `scale_down_factor` | `1` | `10**7` | Divides both demand and link capacity before building the MILP, for numerical stability. It cancels out in the normalized model. |
| `top_k` | `100` | `0, 10, …, 100` | **Two roles.** (a) Number of distinct topologies to enumerate (ignored under MCF). (b) With `dynamic` / `dynamic_doppler`, the percentage of nodes that receive fallow transponders (§3.1). |
| `optimizer_time_limit_minutes` | `1` | `0.5, 1, 5` | Total wall-clock budget for all enumeration solves combined. |
| `parallel_path_computation` | `True` | default | Chooses the parallel tunnel worker, which uses slightly different path limits than the serial one (§3.4). |
| `te_seed` | `None` | — | Seed for SMORE routing only. Doppler itself is deterministic. |
| `salt` | `""` | — | Only makes temp-file names unique. |
| `start_clean`, `magnitude` | `False`, `1e12` | — | Generate a fresh traffic matrix instead of reading one. |
| `line_code`, `shakeroute`, `net_dir`, `use_heuristic`, `attack_proportion` | various | — | Not used by Doppler's search. They affect naming or other methods. |

### 1.2 `perform_sim(...)` arguments

| Argument | Default | Effect on Doppler |
|---|---|---|
| `demand_factor` | `1` | Multiplies every traffic-matrix entry before Doppler sees it. This is the `scale` axis in `exp-v2.py`. |
| `start_iter`, `end_iter` | `0`, `iterations` | Which traffic rows to run. Row index is `iter - 1`, so a run starting at `0` reads the *last* row first. |
| `repeat` | `False` | Runs every time step twice (used by GreyLambda to show react-then-settle). |
| `dry` | `False` | Returns the result path without running anything. |
| `circuits`, `unit` | `1`, `"Gbps"` | `circuits` is unused by Doppler. `unit` only affects the `.dot` export. |

### 1.3 Fixed values inside the code

These are not exposed as arguments but shape every result.

| Value | Where | Meaning |
|---|---|---|
| `link_capacity = 100e9` | `build_optimization_problem` | Every link in the MILP has 100 Gbps capacity. Capacities in the topology file are ignored. |
| Change weight `2` | `_build_edge_flow_milp` | Objective is `2 × changes + MLU`. |
| MLU upper bound `min(1, threshold)` | `_build_edge_flow_milp` | The MILP cannot return a topology whose MLU exceeds this. |
| `liberal_p = 0.1` | `compute_candidate_links` | Top 10% of links by betweenness seed the `conservative` / `liberal` sets. |
| `max_distance = inf` | `compute_candidate_links` | No geographic limit on `max` candidates. |
| `use_cache = True` | `Simulation._run_topology_optimization` | Tunnel paths are always cached on disk (§3.4). |
| `mip_rel_gap = 0` | `solve_edge_flow_changes_mlu` | Each solve runs to proven optimality unless time runs out. |
| `reconfig_time = 1.0` | `perform_sim` | Fixed reconfiguration time, applied only when the method string is exactly `"doppler"` (lowercase). |

---

## 2. Algorithm at a glance

```
once:   allocate transponders per node                     (§3.1)
per time step t:
   1. demand_t  = traffic row t × demand_factor            (§3.2)
   2. C         = candidate new links                      (§3.3)
   3. S         = fiber graph ∪ C ("super-graph")
   4. tunnels   = allowed paths per demand on S            (§3.4)
   5. solve LP on the current topology (reported only)     (§3.5)
   6. build MILP: choose links x_e ∈ {0,1} on S            (§3.6)
   7. repeat: solve, record topology, forbid it            (§3.7)
      until top_k found, infeasible, or time limit
   8. choose one topology from the list                    (§3.8)
   9. add/drop circuits on the optical model, route traffic
      with ECMP/MCF/SMORE, write metrics                   (§3.9)
  10. maybe revert, based on the congestion thresholds     (§3.10)
```

---

## 3. Step by step

### 3.1 Transponder allocation (once, at `Simulation` construction)

Each node starts with one transponder per existing fiber link (its degree).
Fallow transponders are then added by strategy:

| Strategy | Transponders at node *n* |
|---|---|
| `static` | `degree(n) + fallow_transponders` for every node |
| `dynamic` | Super nodes: `degree + ftx`. Others: `degree + ftx/2`. |
| `dynamic_doppler` | Super nodes: `degree + ftx`. Others: `degree` (no spares). |
| `file` | `degree + count from file` |

Super nodes are the top `ceil(n_nodes × top_k / 100)` nodes by betweenness
centrality, with a minimum of 2 unless that count is 0. With
`dynamic_doppler`, **`top_k` therefore sets how many nodes have spare
transponders.** `top_k = 0` gives none, so Doppler can only rewire existing
ports. `top_k = 100` gives every node spares.

The resulting per-node totals become `txp_count`, the MILP's degree limit.

### 3.2 Demand

The simulator writes row *t* of the traffic file, multiplied by
`demand_factor`, to a temp file. `load_demand_from_file` reads it into a
dict `(source, target) → demand / scale_down_factor`. In the MILP each
demand is then divided by `link_capacity / scale_down_factor`, so the model
works in units of "fraction of one 100 Gbps link".

### 3.3 Candidate links

Computed on the **fiber (base) graph**, not the current logical graph:

| Set | Rule | Size on ANS (25 links) |
|---|---|---|
| `conservative` | Take the top 10% of links by edge betweenness. For each such link *(u, v)*, propose *(neighbor of u, v)* and *(u, neighbor of v)*: links that close a triangle around a busy link. | 8 |
| `liberal` | Same top 10%, but propose *(neighbor of u, neighbor of v)*: links that bypass the busy link one hop out. | — |
| `max` | Every non-adjacent node pair exactly two hops apart, within `max_distance` (unlimited). | 39 |

The **super-graph** is the fiber graph plus every candidate link. The MILP's
edge variables cover all of its edges: existing links can be dropped as well
as candidates added.

### 3.4 Tunnels (allowed paths per demand)

Each demand may only use edges that appear on its precomputed tunnels:

1. **Original tunnels:** up to 6 shortest simple paths on the fiber graph.
2. **Super-graph tunnels:** shortest simple paths on the super-graph, kept
   while path length ≤ `max(len(shortest original path), 4)` nodes. The
   parallel worker also stops after `len(original)²` paths. Each path is
   stored in both directions, and the original tunnels are always included.

The MILP receives, for each demand, the **set of directed edges** on its
tunnels, not the paths. Flow may use any combination of those edges.

Tunnels are cached as pickles in
`data/paths/optimization/{network}_tunnel_*.pickle`, keyed by network name
only (see the problems in §4).

### 3.5 Baseline LP

`solve_baseline` solves a plain LP for the lowest MLU on the *current*
topology with the same tunnels. The result goes into the
`OptimizationResult` but does not affect the search.

### 3.6 The MILP

**Variables**

- `x_e ∈ {0,1}` for every undirected super-graph edge *e*: 1 = link is lit.
- `f_{c,uv} ≥ 0` for every demand *c* and every directed edge *(u,v)* on
  its tunnels: normalized flow.
- `MLU ∈ [0, min(1, congestion_threshold_upper_bound)]`.
- `r_{uv} ≥ 0` for every directed edge: auxiliary "root flow" used only for
  connectivity.

**Constraints**

1. **Transponders:** for each node *n*, `Σ x_e` over edges at *n* ≤
   `txp_count[n]`.
2. **Flow conservation:** for each demand *c = (s,t)* with demand *d*, net
   outflow is *d* at *s*, inflow is *d* at *t*, and zero elsewhere.
3. **Activation:** `f_{c,uv} ≤ x_e` (flow only on lit links).
4. **Utilization:** for each directed edge, `Σ_c f_{c,uv} ≤ MLU`. Every link
   has capacity 1 in normalized units.
5. **Connectivity:** node 0 sends `n−1` units of root flow, every other node
   absorbs 1, and `r_{uv} ≤ (n−1)·x_e`. This keeps the chosen topology
   connected.

**Objective**

```
doppler   : minimize  2 × (links added + links dropped)  +  MLU
onset_v3  : minimize  MLU            (same model, objective_mode="mlu")
```

Since MLU is at most 1 and each change costs 2, **one fewer link change
always beats any MLU improvement.** The solver adds a link only when the
current topology cannot carry the traffic under the MLU cap at all.

### 3.7 Enumerating the top-k topologies

`solve_edge_flow_changes_mlu` builds the model once, then loops:

1. Solve with HiGHS, using whatever remains of the time budget.
2. If optimal, extract the topology (round `x`), compute the links added
   and dropped, recompute MLU from the flows (`validated_mlu`), and hash
   the edge set to a `stable_topology_id`. Keep it if it is new.
3. Add a **no-good cut** that forbids exactly this edge set:
   `Σ_{e∉S} x_e − Σ_{e∈S} x_e ≥ 1 − |S|`.
4. Stop when one of these happens:

| Stop reason | Status |
|---|---|
| `top_k` distinct topologies found | `TOP_K_REACHED` |
| Model becomes infeasible with ≥ 1 solution | `EXHAUSTED` |
| Model infeasible on the first solve | `INFEASIBLE` (no topology) |
| Time limit hit | `TIME_LIMIT_WITH_SOLUTION` / `…WITHOUT_SOLUTION` |

Solutions come back sorted by objective, then change count, then MLU, then
ID. Because of the objective, they arrive roughly in order of how few links
they change.

### 3.8 Choosing one topology

In `handlers._run_milp_method`:

| TE method | `top_k` actually used | Topology applied |
|---|---|---|
| `-mcf` | forced to **1** | The only solution |
| `-ecmp` | `top_k` | `selected_solution`: lowest `validated_mlu`, then fewest changes, then objective, then ID |
| other (SMORE) | `top_k` | same as ECMP |

`validated_mlu` comes from the MILP's own flows, which behave like MCF, so
the ranking never consults the routing method that will actually carry the
traffic. `onset_v3` can re-rank candidates under ECMP
(`uses_ecmp_multisol=True`); the `doppler` registry entry has this off.

The choice is fully deterministic. Nothing in the current code randomizes
which of the top-k topologies is used.

### 3.9 Apply and evaluate

`Simulation.apply_solution` drops and then adds circuits on the `AlpWolf`
optical model. The logical graph is exported to `.gml` and `.dot`, and
`te/engine.py` routes the same traffic row with the chosen TE method. Files
written to each iteration directory:

| File | Contents |
|---|---|
| `MaxExpCongestionVsIterations.dat` | MLU measured by the TE engine |
| `CongestionLossVsIterations.dat` | Fraction of traffic dropped |
| `TotalThroughputVsIterations.dat` | Fraction delivered |
| `TotalSolutions.dat` | Number of topologies enumerated |
| `DopplerMinMLU.dat` | `validated_mlu` of the applied topology, rounded to 3 places |
| `DopplerMLU.dat` | `validated_mlu` of every enumerated topology |
| `OptTime.dat` | Wall time of the whole enumeration |
| `CurrTopoID.dat` | ID of the applied topology |
| `OptimalTopoID.dat` | ID of the best-objective topology |

`exp-v2.py` then writes one CSV row per experiment to `data/reports/`.

### 3.10 After evaluation

- MLU ≥ `congestion_threshold_upper_bound` sets `sig_add_circuits`. Doppler
  ignores this flag and re-optimizes every step anyway.
- MLU ≤ `congestion_threshold_lower_bound` with dropped links present
  reverts the applied solution before the next step.
- Changes otherwise persist, so step *t+1* starts from step *t*'s topology.

---

## 4. Known problems that affect results

Each item was checked on ANS with `ANS_coremelt_links-2_volume-2.00e+11.txt`.

1. **Demands are ignored depending on direction.** Tunnels are stored under
   string-sorted node pairs (`('10','13')`), but demands use every ordered
   pair. Any demand whose source sorts after its target (`'13'→'10'`) has
   no tunnel edges, gets no flow variables, and silently disappears from
   the model. On the coremelt matrix this was 4 of 46 demands (5.1% of
   volume). On gravity background traffic it should be close to half. This
   probably explains why the MILP reports a lower MLU than the routing
   engine (1.000 vs 1.072 at 1.0×).
2. **The tunnel cache ignores the candidate set.** The cache key is only
   the network name, and the simulator always enables it. If `conservative`
   runs first, a later `max` run reuses its tunnels: only 8 of `max`'s 39
   candidate links appear on any tunnel. Results in a mixed grid depend on
   run order. Delete `data/paths/optimization/` between runs until this is
   fixed.
3. **Infeasible under heavy attack.** With MLU capped at ≤ 1, an attack the
   network cannot absorb makes the MILP infeasible and Doppler applies
   nothing.
4. **Changes are almost always avoided.** The 2-per-change weight means
   "change nothing" wins whenever it is feasible.
5. **No randomness.** Selection is deterministic, and under MCF only one
   topology is computed.
6. **ECMP ranking mismatch.** Topologies are ranked by MCF-style MLU but
   evaluated with ECMP, which can raise congestion above the baseline.
7. **Uniform capacities.** The MILP assumes 100 Gbps per link and does not
   model parallel circuits on one link (`x_e` is binary).
8. **`top_k` is overloaded.** In `exp-v2.py` the `top_k` sweep also changes
   how many nodes have fallow transponders, so its effect cannot be read as
   "more alternatives" alone.
