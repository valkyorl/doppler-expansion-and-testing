"""§4.2 G1: does a stale attack plan do less damage under Doppler?

Figure, per network (columns): benign traffic lost to the attack running in
each epoch, the plan learned L epochs earlier (``stale_benign_loss``, D10),
for the static network, Doppler, and the structural-churn baseline (Eq. 18,
O6). Epochs before the attacker holds a plan (t < L) have no point.

Table: per network and mode, the number of epochs that changed the
topology, the mean stale benign loss, the mean stale-plan τ (Eq. 1, against
the attacker's own fresh plan, I19), and the links at the first and last
epoch.

Reads every controller run whose folder name starts with ``<prefix>-``
(default ``v0``), one run per network and mode:

    python -m doppler2026.figures.fig_controller_stale_damage [--prefix v0]
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

from ..results import RESULTS_ROOT
from .common import legend_above, networks_in, save, save_table, style

MODES = ("static", "doppler", "churn")
MODE_LABELS = {"static": "Static", "doppler": "Doppler", "churn": "Structural churn"}
# Modes are their own entities: the first three slots of the reference
# palette, in fixed order, with markers and line styles repeating identity.
MODE_COLORS = {"static": "#2a78d6", "doppler": "#eb6834", "churn": "#1baf7a"}
MODE_MARKERS = {"static": "o", "doppler": "s", "churn": "^"}
MODE_LINESTYLES = {"static": "-", "doppler": "--", "churn": ":"}


def load(prefix: str) -> pd.DataFrame:
    folders = sorted((RESULTS_ROOT / "controller").glob(f"{prefix}-*/epochs.csv"))
    if not folders:
        raise SystemExit(f"No controller runs named {prefix}-* under {RESULTS_ROOT}")
    frames = [pd.read_csv(f).assign(run=f.parent.name) for f in folders]
    epochs = pd.concat(frames, ignore_index=True)
    duplicated = epochs.groupby(["network", "mode"])["run"].nunique()
    if (duplicated > 1).any():
        raise SystemExit(f"More than one run per network and mode:\n{duplicated}")
    return epochs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prefix", default="v0")
    args = parser.parse_args()
    epochs = load(args.prefix)
    networks = networks_in(epochs)
    source = RESULTS_ROOT / "controller" / f"{args.prefix}-*"

    style()
    fig, axes = plt.subplots(
        1, len(networks), figsize=(1.6 * len(networks), 2.1), sharey=True, squeeze=False
    )
    for col, network in enumerate(networks):
        ax = axes[0][col]
        for mode in MODES:
            rows = epochs[(epochs.network == network) & (epochs["mode"] == mode)]
            rows = rows.dropna(subset=["stale_benign_loss"])
            if rows.empty:
                continue
            ax.plot(
                rows.epoch,
                100 * rows.stale_benign_loss,
                color=MODE_COLORS[mode],
                marker=MODE_MARKERS[mode],
                linestyle=MODE_LINESTYLES[mode],
                label=MODE_LABELS[mode],
            )
        ax.set_title(network)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("Epoch" if col == len(networks) // 2 else "")
        if col == 0:
            ax.set_ylabel("Benign traffic lost to stale plan (%)")
    legend_above(fig, axes[0][0])
    save(fig, "controller_stale_damage", source)

    rows = []
    for (network, mode), group in epochs.groupby(["network", "mode"]):
        rows.append(
            {
                "network": network,
                "mode": mode,
                "moves": int((group.transition != "none").sum()),
                "stale_loss_pct": round(100 * group.stale_benign_loss.mean(), 1),
                "stale_tau": round(group.stale_transferability.mean(), 2),
                "links": f"{group.links.iloc[0]} -> {group.links.iloc[-1]}",
            }
        )
    table = pd.DataFrame(rows)
    table["network"] = pd.Categorical(table.network, networks, ordered=True)
    table["mode"] = pd.Categorical(table["mode"], MODES, ordered=True)
    table = table.sort_values(["network", "mode"])
    table["mode"] = table["mode"].map(MODE_LABELS)
    save_table(
        table.rename(
            columns={
                "moves": "Epochs that moved",
                "stale_loss_pct": "Mean stale benign loss (%)",
                "stale_tau": "Mean stale τ",
                "links": "Links (first -> last epoch)",
            }
        ),
        "controller_stale_damage",
        f"§4.2 G1. Stale attack plans (L = recon lag) over the controller runs "
        f"{args.prefix}-*: epochs that changed the topology, mean benign loss "
        "caused by the stale plan, and mean stale τ.",
    )


if __name__ == "__main__":
    main()
