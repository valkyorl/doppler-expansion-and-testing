"""RQ1 (§3.7): how accurately the attacker reconstructs the network.

Figure: edge F1 of the inferred graph, per network (columns). Top row:
traceroute against the share of silent routers; bottom row: RTT/Ricci
against ε (as an RTT quantile, D13). One line per measurement coverage
(share of PoPs used as vantage points), mean over measurement seeds.
Table: precision, recall, and F1 at the headline settings.

Only networks with ground truth usable for RQ1 appear: here the simulated
ones (I12). The regional network is left out because its ground truth is not
independently validated (§3.4).

    python -m doppler2026.figures.fig_rq1_recovery [--run <folder>]
"""

import matplotlib.pyplot as plt
import pandas as pd

from .common import (
    COVERAGE_COLORS,
    LABELS,
    headline,
    legend_above,
    networks_in,
    parse_run,
    save,
    save_table,
    style,
)

SWEEPS = (
    ("traceroute", "non_response", "Silent routers (share)"),
    ("rtt_ricci", "epsilon_quantile", "ε (quantile of min RTT)"),
)


def main() -> None:
    run_dir = parse_run("recon_eval", __doc__.split("\n")[0])
    recon = pd.read_csv(run_dir / "recon.csv")
    rq1 = recon[
        recon.ground_truth_independent
        & recon.metric.isin(["precision", "recall", "f1"])
    ]
    networks = networks_in(rq1)

    style()
    fig, axes = plt.subplots(
        len(SWEEPS),
        len(networks),
        figsize=(1.6 * len(networks), 3.4),
        sharey=True,
        squeeze=False,
    )
    for row, (mechanism, column, xlabel) in enumerate(SWEEPS):
        data = rq1[(rq1.mechanism == mechanism) & (rq1.metric == "f1")]
        for col, network in enumerate(networks):
            ax = axes[row][col]
            for fraction, color in COVERAGE_COLORS.items():
                line = (
                    data[
                        (data.network == network) & (data.vantage_fraction == fraction)
                    ]
                    .groupby(column)["value"]
                    .mean()
                )
                ax.plot(
                    line.index,
                    line.values,
                    color=color,
                    marker="o",
                    label=f"{fraction:.0%} of PoPs",
                )
            ax.set_ylim(0, 1.02)
            if row == 0:
                ax.set_title(network)
            if col == 0:
                ax.set_ylabel(f"{LABELS[mechanism]}\nedge F1")
            ax.set_xlabel(xlabel if col == len(networks) // 2 else "")
    legend_above(fig, axes[0][0], title="Vantage points")
    save(fig, "rq1_topology_recovery", run_dir)

    # Table at the headline settings, mean over measurement seeds.
    table = (
        headline(rq1)
        .groupby(["network", "mechanism", "metric"])["value"]
        .mean()
        .unstack("metric")
        .reindex(columns=["precision", "recall", "f1"])
        .round(2)
        .reset_index()
    )
    table["mechanism"] = table.mechanism.map(LABELS)
    table["network"] = pd.Categorical(table.network, networks, ordered=True)
    save_table(
        table.sort_values(["network", "mechanism"]),
        "rq1_topology_recovery",
        "RQ1. Edge precision, recall, and F1 at full coverage, 10% silent routers "
        "(traceroute), ε at the 0.2 quantile (RTT); mean over measurement seeds. "
        "Simulated measurements; ground truth is the simulated network.",
    )


if __name__ == "__main__":
    main()
