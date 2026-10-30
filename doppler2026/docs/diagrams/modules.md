# Module map

How the planned modules in `doppler2026/` depend on each other and on
existing code in `src/onset/`. An arrow means "uses". Dashed boxes are
existing shared code.

```mermaid
flowchart LR
    subgraph d26["doppler2026/"]
        run["run.py"]
        controller["controller.py"]
        transition["transition.py"]
        selection["selection.py"]
        security["security.py"]
        filters["filters.py"]
        candidates["candidates.py"]
        feasibility["feasibility.py"]
        damage["damage.py"]
        plans["attack_plans.py"]
        routing["routing.py"]
        traffic["traffic.py"]
        topo["topology.py"]
        model["model.py"]
        subgraph recon["recon/"]
            oracle["oracle.py"]
            rnd["random_plan.py"]
            tr["traceroute.py"]
            rtt["rtt_ricci.py"]
            metrics["metrics.py"]
        end
    end

    subgraph shared["src/onset/ (existing)"]
        pre["preprocessing.py"]
        od["open_doppler.py"]
        te["te/engine.py"]
        wolf["alpwolf.py"]
    end

    grc[["GraphRicciCurvature"]]

    run --> controller
    controller --> candidates & filters & security & selection & transition & traffic
    controller --> recon
    candidates --> feasibility & pre & od
    filters --> routing
    security --> damage
    damage --> routing & oracle
    transition --> wolf & routing
    recon --> plans & routing
    rtt --> grc
    routing --> te
    traffic --> routing
    oracle & rnd & damage --> topo
    plans --> model

    classDef existing stroke-dasharray: 5 5
    class pre,od,te,wolf existing
```

`model.py` (shared dataclasses) is used by nearly every module; only the
`attack_plans.py` edge is drawn to keep the diagram readable.
