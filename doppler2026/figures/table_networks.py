"""Paper Table 1: networks used in the reconnaissance evaluation (§3.5).

Reads ``networks.csv`` of a ``recon_eval`` run. "Ground truth" is marked
independent only where the paper's definition holds; for simulated networks
the truth is the simulated topology itself (interpretation I12).

    python -m doppler2026.figures.table_networks [--run <folder>]
"""

import pandas as pd

from .common import networks_in, parse_run, save_table


def main() -> None:
    run_dir = parse_run("recon_eval", __doc__.split("\n")[0])
    frame = pd.read_csv(run_dir / "networks.csv")
    frame = frame.set_index("network").loc[networks_in(frame)].reset_index()
    truth = frame.apply(
        lambda r: "simulated (by construction)"
        if r.ground_truth_source == "simulation"
        else ("validated" if r.ground_truth_independent else "not validated"),
        axis=1,
    )
    table = pd.DataFrame(
        {
            "Network": frame.network,
            "Nodes": frame.nodes,
            "Links": frame.links,
            "RTT VPs": frame.rtt_vantage_points,
            "Traceroute VPs": frame.traceroute_vantage_points,
            "Measurements": frame.measurements,
            "Ground truth": truth,
            "Optical data": frame.optical_data,
        }
    )
    save_table(
        table,
        "table1_networks",
        "Table 1. Networks in the reconnaissance evaluation. VP counts are the "
        "simulated coverages swept (100/50/25% of PoPs).",
    )


if __name__ == "__main__":
    main()
