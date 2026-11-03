"""RQ2 (§3.7): does reconnaissance find the attack-relevant links?

Figure, per network (columns): top row P@k (Eq. 9), the share of the
attacker's k top-ranked edges that are among the k true critical links;
bottom row path-level recovery, the share whose real route crosses a true
critical link (§3.4). Headline settings, mean over measurement seeds. True
critical links are the oracle's ranking (I3).

The regional network is marked with a dagger: its ground truth is not
independently validated, so its values are indicative only (I12).

    python -m doppler2026.figures.fig_rq2_critical_links [--run <folder>]
"""

import matplotlib.pyplot as plt
import pandas as pd

from .common import (
    COLORS,
    LABELS,
    LINESTYLES,
    MARKERS,
    headline,
    legend_above,
    networks_in,
    parse_run,
    save,
    style,
)

ROWS = (("p_at_k", "P@k"), ("path_at_k", "Path-level recovery@k"))


def main() -> None:
    run_dir = parse_run("recon_eval", __doc__.split("\n")[0])
    recon = pd.read_csv(run_dir / "recon.csv")
    data = headline(recon[recon.metric.isin([m for m, _ in ROWS])])
    networks = networks_in(data)

    style()
    fig, axes = plt.subplots(
        len(ROWS),
        len(networks),
        figsize=(1.6 * len(networks), 3.4),
        sharey=True,
        sharex=True,
        squeeze=False,
    )
    for row, (metric, ylabel) in enumerate(ROWS):
        for col, network in enumerate(networks):
            ax = axes[row][col]
            subset = data[(data.network == network) & (data.metric == metric)]
            for mechanism in ("traceroute", "rtt_ricci"):
                line = (
                    subset[subset.mechanism == mechanism].groupby("k")["value"].mean()
                )
                if line.empty:
                    continue
                ax.plot(
                    line.index,
                    line.values,
                    color=COLORS[mechanism],
                    marker=MARKERS[mechanism],
                    linestyle=LINESTYLES[mechanism],
                    label=LABELS[mechanism],
                )
            ax.set_ylim(0, 1.02)
            if row == 0:
                independent = bool(subset.ground_truth_independent.all())
                ax.set_title(network if independent else f"{network}†")
            if col == 0:
                ax.set_ylabel(ylabel)
            if row == len(ROWS) - 1:
                ax.set_xlabel("k")
    legend_above(fig, axes[0][0])
    save(fig, "rq2_critical_links", run_dir)


if __name__ == "__main__":
    main()
