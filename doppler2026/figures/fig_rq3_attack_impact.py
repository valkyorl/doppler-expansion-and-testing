"""RQ3 (§3.7): does the attack plan work against the real network?

Figure, per network (columns): benign traffic lost (share of benign demand,
D1) against the attack budget R_A (multiple of the median link capacity,
D4), for each attacker at the headline settings. No-knowledge plans are
drawn as their mean with a band from the least to the most damaging seed;
measured attackers are means over measurement seeds.

Table: η (Eq. 10) at twice the link capacity, and the budget needed to
disrupt benign traffic (§3.4 bullet 5, D14), median over plans. η can exceed
1 because the paper's oracle does not know benign traffic (open issue O1).

    python -m doppler2026.figures.fig_rq3_attack_impact [--run <folder>]
"""

import matplotlib.pyplot as plt
import pandas as pd

from .common import (
    COLORS,
    LABELS,
    LINESTYLES,
    MARKERS,
    MECHANISMS,
    headline,
    legend_above,
    networks_in,
    parse_run,
    save,
    save_table,
    style,
)

ETA_BUDGET = 2.0


def main() -> None:
    run_dir = parse_run("recon_eval", __doc__.split("\n")[0])
    transfer = headline(pd.read_csv(run_dir / "transferability.csv"))
    recon = headline(pd.read_csv(run_dir / "recon.csv"))
    networks = networks_in(transfer)

    style()
    fig, axes = plt.subplots(
        1, len(networks), figsize=(1.6 * len(networks), 2.1), sharey=True, squeeze=False
    )
    for col, network in enumerate(networks):
        ax = axes[0][col]
        subset = transfer[transfer.network == network]
        for mechanism in MECHANISMS:
            rows = subset[subset.mechanism == mechanism]
            if rows.empty:
                continue
            loss = rows.groupby("budget_multiple")["plan_benign_loss"]
            mean = 100 * loss.mean()
            if mechanism == "random":
                ax.fill_between(
                    mean.index,
                    100 * loss.min(),
                    100 * loss.max(),
                    color=COLORS[mechanism],
                    alpha=0.15,
                    linewidth=0,
                )
            ax.plot(
                mean.index,
                mean.values,
                color=COLORS[mechanism],
                marker=MARKERS[mechanism],
                linestyle=LINESTYLES[mechanism],
                label=LABELS[mechanism],
            )
        ax.set_xscale("log", base=2)
        budgets = sorted(subset.budget_multiple.unique())
        ax.set_xticks(budgets, [f"{b:g}" for b in budgets])
        ax.minorticks_off()
        ax.set_title(
            network if bool(subset.ground_truth_independent.all()) else f"{network}†"
        )
        ax.set_xlabel("R_A (x link capacity)" if col == len(networks) // 2 else "")
        if col == 0:
            ax.set_ylabel("Benign traffic lost (%)")
    legend_above(fig, axes[0][0])
    save(fig, "rq3_attack_impact", run_dir)

    eta = (
        transfer[transfer.budget_multiple == ETA_BUDGET]
        .groupby(["network", "mechanism"])["ratio"]
        .median()
    )
    disrupt = (
        recon[recon.metric == "budget_to_disrupt"]
        .groupby(["network", "mechanism"])["value"]
        .median()
    )
    table = pd.DataFrame(
        {"eta_at_2x": eta.round(2), "budget_to_disrupt": disrupt.round(2)}
    )
    table = table.reset_index()
    table["network"] = pd.Categorical(table.network, networks, ordered=True)
    table["mechanism"] = pd.Categorical(table.mechanism, MECHANISMS, ordered=True)
    table = table.sort_values(["network", "mechanism"])
    table["mechanism"] = table.mechanism.map(LABELS)
    save_table(
        table.rename(
            columns={
                "eta_at_2x": "η at R_A = 2x",
                "budget_to_disrupt": "Budget to disrupt (x capacity)",
            }
        ),
        "rq3_attack_effectiveness",
        "RQ3. Median η at R_A = 2x link capacity, and median budget at which benign "
        "loss begins (inf: not reached by 16x). Headline settings.",
    )


if __name__ == "__main__":
    main()
