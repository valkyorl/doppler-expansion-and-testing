# Doppler control loop

What happens in one epoch. This is the design in paper §4.3 (Fig. 1, which is
still a placeholder in the draft), with the attacker's side added so the
experiment can measure stale-plan damage. Boxes are labelled with the module
that implements them (planned).

```mermaid
flowchart TD
    subgraph inputs["Inputs at epoch t"]
        GF["Fiber graph G_F<br/>and transponders txp(v)"]
        Gt["Current topology G_t"]
        Dt["Estimated benign demand D_t"]
        H["History: last h pairs (G_i, A_i)"]
    end

    subgraph attacker["Attacker (simulated)"]
        R["Reconnaissance on G_t<br/>oracle / random / traceroute / RTT-Ricci<br/><i>recon/</i>"]
        A["Attack plan A_t = {(s, d, r)}<br/><i>attack_plans.py</i>"]
        R --> A
    end

    subgraph defender["Doppler defender"]
        E["Feasible links E*<br/>fiber path + optical reach<br/><i>feasibility.py</i>"]
        P["Candidate pool<br/>MILP: transponders, flow, capacity, U_max<br/><i>candidates.py</i>"]
        OF{"Operational filter<br/>MLU, stretch, connectivity<br/><i>filters.py</i>"}
        SF{"Security filter<br/>T(G') = max τ(A_i, G') ≤ τ_max<br/><i>security.py</i>"}
        S["Random choice from the<br/>acceptable safe subset<br/><i>selection.py</i>"]
        T["Transition: add, verify, drop<br/><i>transition.py</i>"]
        E --> P --> OF -->|pass| SF -->|pass| S --> T
        OF -->|reject| X1["discarded"]
        SF -->|reject| X2["discarded"]
    end

    GF --> E
    Gt --> P
    Dt --> P
    Dt --> OF
    Gt --> R
    A -->|"append (G_t, A_t)"| H
    H --> SF
    T --> Gn["Next topology G_t+1"]
    Gn -->|"attacker replays stale plan<br/>damage logged"| M["Results<br/><i>controller.py</i>"]
```

Points worth noticing:

- The defender plans with **benign** demand only. Attack traffic reaches the
  defender only through the attack plans in the history.
- The MILP does not know about security. It proposes operationally plausible
  candidates; the two filters decide (paper Eq. 31).
- Randomness enters at exactly one place, the final choice, and its seed is
  recorded with every run.
