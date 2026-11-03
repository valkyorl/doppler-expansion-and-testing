"""Shared pieces of the figure scripts: finding a run, colors, and style.

Every figure script reads only result files of a run (rule 6 in
``CLAUDE.md``) and writes PDF (for the paper) and PNG (for review) to
``figures/out/``. Pass ``--run <folder>`` to choose a run; the default is the
newest run of the experiment.

Colors follow the entity, never its rank: each attacker keeps one color and
one marker in every figure (the first five slots of the validated reference
palette of the dataviz guidelines; the benign-aware oracle of decision D15
was added last, so it takes slot 5 and no other attacker changes color). Markers and line styles repeat the
identity, so no figure depends on color alone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")  # files only, no display
import matplotlib.pyplot as plt
import pandas as pd

from ..results import RESULTS_ROOT

OUT_DIR = Path(__file__).resolve().parent / "out"

MECHANISMS = ("oracle_benign", "oracle", "random", "traceroute", "rtt_ricci")
LABELS = {
    "oracle_benign": "Oracle (benign)",
    "oracle": "Oracle (paper)",
    "random": "No knowledge",
    "traceroute": "Traceroute",
    "rtt_ricci": "RTT / Ricci",
}
COLORS = {
    "oracle_benign": "#e87ba4",
    "oracle": "#2a78d6",
    "random": "#eb6834",
    "traceroute": "#1baf7a",
    "rtt_ricci": "#eda100",
}
MARKERS = {
    "oracle_benign": "v",
    "oracle": "o",
    "random": "s",
    "traceroute": "^",
    "rtt_ricci": "D",
}
LINESTYLES = {
    "oracle_benign": (0, (5, 1, 1, 1)),
    "oracle": "-",
    "random": ":",
    "traceroute": "--",
    "rtt_ricci": "-.",
}

# Coverage is a magnitude, so it gets one hue from light to dark.
COVERAGE_COLORS = {0.25: "#9ec5f4", 0.5: "#5598e7", 1.0: "#1c5cab"}

INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"

HEADLINE = {"vantage_fraction": 1.0, "non_response": 0.1, "epsilon_quantile": 0.2}
"""Settings shown where a figure cannot show every sweep value. A display
choice only: every setting is in the result files."""

NETWORK_ORDER = ("sprint", "ANS", "CRL", "bellCanada", "surfNet", "Comcast", "regional")


def style() -> None:
    """Thin marks, recessive grid and axes, text in ink colors."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 8,
            "axes.titlesize": 8,
            "axes.labelsize": 8,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK_SECONDARY,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.5,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_SECONDARY,
            "ytick.labelcolor": INK_SECONDARY,
            "lines.linewidth": 1.5,
            "lines.markersize": 5,
            "legend.frameon": False,
            "legend.fontsize": 7,
            "text.color": INK,
            "pdf.fonttype": 42,  # embed TrueType, as publishers ask
        }
    )


def parse_run(experiment: str, description: str) -> Path:
    """Command-line ``--run``; defaults to the newest run of ``experiment``."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run", type=Path, help="run folder (default: newest)")
    args = parser.parse_args()
    if args.run:
        return args.run
    runs = sorted(
        (RESULTS_ROOT / experiment).glob("*/"), key=lambda p: p.stat().st_mtime
    )
    if not runs:
        raise SystemExit(f"No runs of {experiment!r} under {RESULTS_ROOT}")
    return runs[-1]


def networks_in(frame: pd.DataFrame) -> list[str]:
    present = set(frame["network"])
    return [n for n in NETWORK_ORDER if n in present] + sorted(
        present - set(NETWORK_ORDER)
    )


def headline(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows at the headline settings (rows without a setting are kept)."""
    keep = pd.Series(True, index=frame.index)
    for column, value in HEADLINE.items():
        if column in frame:
            keep &= frame[column].isna() | (frame[column] == value)
    return frame[keep]


def save(fig: plt.Figure, name: str, run_dir: Path) -> None:
    """Write ``out/<name>.pdf`` and ``.png``, noting the source run in the PDF metadata."""
    OUT_DIR.mkdir(exist_ok=True)
    fig.savefig(
        OUT_DIR / f"{name}.pdf", bbox_inches="tight", metadata={"Subject": str(run_dir)}
    )
    fig.savefig(OUT_DIR / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(OUT_DIR / f"{name}.pdf")


def save_table(frame: pd.DataFrame, name: str, caption: str) -> None:
    """Write a table as Markdown (for review) and a LaTeX tabular (for the paper)."""
    OUT_DIR.mkdir(exist_ok=True)
    cells = frame.astype(str)
    header = list(cells.columns)
    markdown = [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(row) + " |" for row in cells.itertuples(index=False)),
    ]
    (OUT_DIR / f"{name}.md").write_text(f"{caption}\n\n" + "\n".join(markdown) + "\n")

    def tex(text: str) -> str:
        return (
            text.replace("\\", r"\textbackslash{}")
            .replace("_", r"\_")
            .replace("%", r"\%")
            .replace("&", r"\&")
            .replace("#", r"\#")
        )

    latex = [
        f"% {caption}",
        r"\begin{tabular}{" + "l" * len(header) + "}",
        r"\toprule",
        " & ".join(tex(h) for h in header) + r" \\",
        r"\midrule",
        *(
            " & ".join(tex(c) for c in row) + r" \\"
            for row in cells.itertuples(index=False)
        ),
        r"\bottomrule",
        r"\end{tabular}",
    ]
    (OUT_DIR / f"{name}.tex").write_text("\n".join(latex) + "\n")
    print(OUT_DIR / f"{name}.md")


def legend_above(fig: plt.Figure, ax: plt.Axes, title: str | None = None) -> None:
    """Lay out the panels, then put one legend in a band above them.

    Leaves room for the legend so it never covers panel titles.
    """
    handles, labels = ax.get_legend_handles_labels()
    band = 0.16 if title else 0.11
    height = fig.get_figheight()
    fig.tight_layout(rect=(0, 0, 1, 1 - band * 2.0 / height))
    fig.legend(
        handles,
        labels,
        title=title,
        loc="upper center",
        ncol=len(labels),
        bbox_to_anchor=(0.5, 1.0),
    )
