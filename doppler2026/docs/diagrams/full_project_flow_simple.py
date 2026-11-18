"""Draw the plain-language, per-epoch overview of Doppler.

For explaining the process to other researchers and as a possible paper figure
(the control loop of §4.3, with the attacker of §2-3 beside it). The detailed
version, with equations and code references, is ``full_project_flow.dot``; the
exact procedure is in ``docs/epoch_walkthrough.md``.

Steps side by side happen in the same epoch. The arrows carry the meaning:

- The attacker's new plan goes into storage; the attack uses an older one
  (recon lag, D10).
- No arrow runs from the attacker to Doppler. The defender does not observe the
  attacker: it runs the same reconnaissance procedure itself (§4.8, I18).
- What Doppler remembers is first used in the next epoch (Eq. 19-20, D30).

Run from the repository root::

    python doppler2026/docs/diagrams/full_project_flow_simple.py

Writes ``full_project_flow_simple.png`` and ``.pdf`` next to this file.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

INK = "#27303a"
MUTED = "#59626e"
ATTACKER = ("#f9d5ca", "#c0392b")
DOPPLER = ("#d3e6f3", "#1f6f8b")
NETWORK = ("#fff1c9", "#a97f00")
NEUTRAL = ("#e3e5e9", "#68717d")
MEMORY = "#6a4fb3"

WIDTH, HEIGHT = 10.4, 13.1
BOX_W, BOX_H = 3.35, 0.92
LEFT_X, RIGHT_X = 2.95, 7.25
FIRST_ROW, ROW_STEP = 8.95, 1.22


def row(index: float) -> float:
    return FIRST_ROW - index * ROW_STEP


def box(ax, x, y, title, body="", colors=NEUTRAL, width=BOX_W, height=BOX_H):
    fill, edge = colors
    ax.add_patch(
        FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0,rounding_size=0.07",
            facecolor=fill,
            edgecolor=edge,
            linewidth=1.2,
            zorder=3,
        )
    )
    if body:
        lines = body.count("\n") + 1
        ax.text(x, y + 0.11 * lines, title, ha="center", va="center", color=INK,
                fontsize=10.5, fontweight="bold", zorder=4)
        ax.text(x, y - 0.13, body, ha="center", va="center", color=INK,
                fontsize=9.3, linespacing=1.2, zorder=4)
    else:
        ax.text(x, y, title, ha="center", va="center", color=INK, fontsize=10.5,
                fontweight="bold", zorder=4)


def arrow(ax, start, end, color=MUTED, style="-", width=1.3):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        zorder=2,
        arrowprops={
            "arrowstyle": "-|>",
            "color": color,
            "linewidth": width,
            "linestyle": style,
            "shrinkA": 0,
            "shrinkB": 0,
            "mutation_scale": 13,
        },
    )


def elbow(ax, points, color=MUTED, style="-", head=True, width=1.3):
    """A right-angled line through ``points``, with an optional arrowhead."""
    last = len(points) - 2 if head else len(points) - 1
    xs, ys = zip(*points[: last + 1], strict=True)
    ax.plot(xs, ys, color=color, linestyle=style, linewidth=width, zorder=2,
            solid_capstyle="round")
    if head:
        arrow(ax, points[-2], points[-1], color, style, width)


def draw():
    fig, ax = plt.subplots(figsize=(WIDTH, HEIGHT))
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(-0.3, HEIGHT)
    ax.axis("off")
    middle = (LEFT_X + RIGHT_X) / 2

    # Setup.
    ax.text(middle, 12.78, "Before the first epoch", ha="center", fontsize=13,
            color=INK)
    box(ax, middle, 12.17, "Set up the network",
        "load its links and normal traffic; list the links the optical\n"
        "hardware could build and the equipment at each site",
        width=6.4, height=0.86)
    arrow(ax, (middle, 11.74), (middle, 11.32))

    # The epoch frame.
    frame_bottom = 1.25
    ax.add_patch(Rectangle((0.3, frame_bottom), 9.8, 11.32 - frame_bottom,
                           facecolor="#fbfbfc", edgecolor="#39424e",
                           linewidth=1.4, zorder=0))
    ax.text(middle, 10.98, "For each epoch:", ha="center", fontsize=13, color=INK)

    # Network at the start of the epoch.
    net_y = 10.45
    box(ax, middle, net_y, "Current network", colors=NETWORK, width=7.65, height=0.5)
    ax.text(LEFT_X, 9.6, "Attacker", ha="center", fontsize=12.5, color=ATTACKER[1],
            fontweight="bold")
    ax.text(RIGHT_X, 9.6, "Doppler", ha="center", fontsize=12.5, color=DOPPLER[1],
            fontweight="bold")

    # Attacker column.
    box(ax, LEFT_X, row(0), "1. Probe the network",
        "learn how traffic moves through it", ATTACKER)
    box(ax, LEFT_X, row(1), "2. Build a new attack plan",
        "find a critical link and the\ntraffic pairs that cross it", ATTACKER)
    box(ax, LEFT_X, row(2), "Saved attack plans", colors=("#ffffff", ATTACKER[1]),
        width=2.45, height=0.56)
    box(ax, LEFT_X, row(3), "3. Attack with an older plan",
        "flood its target, even if the\nnetwork has changed since", ATTACKER)

    # Doppler column.
    steps = [
        ("1. Propose new topologies", "using links the optical\nhardware can build"),
        ("2. Protect normal traffic",
         "keep those that stay connected,\nuncongested, without long detours"),
        ("3. Test against old plans",
         "keep those where recent plans\nno longer work well"),
        ("4. Choose unpredictably",
         "pick at random among the best;\nif none is safe, stay as is"),
        ("5. Remember this epoch",
         "save the current network and\nthe attack plan it reveals"),
        ("6. Reconfigure", "change the optical links\nto the chosen topology"),
    ]
    for i, (title, body) in enumerate(steps):
        box(ax, RIGHT_X, row(i), title, body, DOPPLER)
    for i in range(len(steps) - 1):
        arrow(ax, (RIGHT_X, row(i) - BOX_H / 2), (RIGHT_X, row(i + 1) + BOX_H / 2),
              DOPPLER[1])

    # Attacker's vertical flow goes through storage: the new plan is not the
    # one used in this epoch's attack.
    arrow(ax, (LEFT_X, row(0) - BOX_H / 2), (LEFT_X, row(1) + BOX_H / 2), ATTACKER[1])
    arrow(ax, (LEFT_X, row(1) - BOX_H / 2), (LEFT_X, row(2) + 0.28), ATTACKER[1])
    arrow(ax, (LEFT_X, row(2) - 0.28), (LEFT_X, row(3) + BOX_H / 2), ATTACKER[1])
    ax.text(LEFT_X + 0.1, (row(1) - BOX_H / 2 + row(2) + 0.28) / 2, "new plan",
            va="center", fontsize=8.8, color=ATTACKER[1])
    ax.text(LEFT_X + 0.1, (row(2) - 0.28 + row(3) + BOX_H / 2) / 2,
            "older plan", va="center", fontsize=8.8,
            color=ATTACKER[1])

    # The current network feeds both columns; the attack lands on it.
    for x in (LEFT_X, RIGHT_X):
        arrow(ax, (x, net_y - 0.25), (x, 9.86))
    left_edge = LEFT_X - BOX_W / 2
    elbow(ax, [(left_edge, row(3)), (0.72, row(3)), (0.72, net_y),
               (middle - 7.65 / 2, net_y)], ATTACKER[1], width=1.6)
    ax.text(0.59, (row(3) + net_y) / 2, "floods the current network", rotation=90,
            ha="center", va="center", fontsize=9, color=ATTACKER[1])

    # Doppler models the attacker; it does not receive anything from it.
    gap_x = middle + 0.02
    elbow(ax, [(LEFT_X + BOX_W / 2, row(1)), (gap_x, row(1)), (gap_x, row(4)),
               (RIGHT_X - BOX_W / 2, row(4))], MEMORY, "--", head=False)
    box(ax, LEFT_X, row(4) - 0.28, "Dashed line: not a real link",
        "Doppler never sees the attacker or\nits attack. It runs the same procedure\n"
        "and assumes the same plan.",
        ("#f4f1fb", MEMORY), height=1.3)

    # What Doppler remembers is used from the next epoch on.
    right_edge = RIGHT_X + BOX_W / 2
    elbow(ax, [(right_edge, row(4)), (9.42, row(4)), (9.42, row(2)),
               (right_edge, row(2))], MEMORY, width=1.6)
    ax.text(9.58, row(3), "used from the next epoch on", rotation=270, ha="center",
            va="center", fontsize=9, color=MEMORY)

    # Network for the next epoch.
    next_y = 1.72
    arrow(ax, (RIGHT_X, row(5) - BOX_H / 2), (RIGHT_X, next_y + 0.25), DOPPLER[1])
    box(ax, middle, next_y, "Network for the next epoch", colors=NETWORK, width=7.65,
        height=0.5)

    # Evaluation.
    arrow(ax, (middle, frame_bottom), (middle, 0.83))
    ax.text(middle + 0.12, 1.04, "after the last epoch", va="center", fontsize=9,
            color=MUTED)
    box(ax, middle, 0.37, "Evaluate",
        "how much harm did out-of-date plans cause,\n"
        "and what did reconfiguring cost normal traffic?",
        width=6.4, height=0.92)

    here = Path(__file__).resolve().parent
    fig.savefig(here / "full_project_flow_simple.png", dpi=200, bbox_inches="tight",
                facecolor="white")
    fig.savefig(here / "full_project_flow_simple.pdf", bbox_inches="tight",
                facecolor="white")


if __name__ == "__main__":
    draw()
