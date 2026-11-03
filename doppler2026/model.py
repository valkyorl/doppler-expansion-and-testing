"""Shared data types for the Doppler 2026 experiment.

Everything the experiment passes between modules is defined here, so the
meaning of each field is written down once:

- ``AttackPlan``: the attacker's plan A = {(s_i, d_i, r_i)} (paper §2.1, Eq. 7).
- ``AttackConfig``, ``RoutingConfig``, ``DamageConfig``: the experiment
  settings, including the accepted decisions D1, D2, D4, D8
  (``docs/decisions.md``). Every decision is a field here, never a constant
  buried in the logic, so it can be changed in one place.
- ``DamageReport``: the damage D(A, G) one plan causes on one topology,
  measured four ways (paper §3.4).
- ``RelativeDamage``: a stale or measured plan's damage divided by a fresh
  oracle plan's damage. This ratio is τ (Eq. 1) when the plan was learned on
  another topology and η (Eq. 10) when it was learned on the same one.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

Pair = tuple[str, str]
"""An ordered (source, destination) pair of PoPs."""

DAMAGE_MEASURES = (
    "max_utilization",
    "overloaded_capacity",
    "benign_on_congested",
    "benign_loss",
)
"""Damage measures computed for every evaluation (paper §3.4, bullets 1 to 4)."""


@dataclass(frozen=True)
class AttackFlow:
    """One attack flow (s_i, d_i, r_i): ``rate`` in bits per second."""

    source: str
    target: str
    rate: float


@dataclass(frozen=True)
class AttackPlan:
    """An attack plan A = {(s_i, d_i, r_i)} (paper Eq. 7).

    ``topology_id`` names the topology the plan was learned on, so a plan
    replayed on a later topology is recognisably stale. ``target`` is the
    link the attacker meant to flood, if the mechanism chose one.
    """

    flows: tuple[AttackFlow, ...]
    budget: float
    mechanism: str
    topology_id: str
    target: Pair | None = None

    def demands(self) -> dict[Pair, float]:
        """Attack traffic per (source, destination) pair."""
        out: dict[Pair, float] = {}
        for flow in self.flows:
            key = (flow.source, flow.target)
            out[key] = out.get(key, 0.0) + flow.rate
        return out


@dataclass(frozen=True)
class RoutingConfig:
    """How the network routes traffic.

    ``te_method`` is one of the existing engine's methods: ``ecmp`` (default;
    does not react to traffic), ``mcf``, ``semimcfraeke``, ``semimcfraekeft``.
    ``path_budget`` caps ECMP/SMORE paths per pair, as in the existing engine.
    """

    te_method: str = "ecmp"
    path_budget: int = 3
    seed: int | None = None


ORACLE_KNOWLEDGE = ("benign", "routing")
"""What the oracle may know (decision D15; ``AttackConfig.oracle_knowledge``)."""


@dataclass(frozen=True)
class AttackConfig:
    """Attacker settings (paper §3.3; decisions D4 and D8).

    ``budget`` is the aggregate attack rate R_A in bits per second.
    ``n_pairs`` is N_A, the most source-destination pairs a plan may use.
    ``endpoints`` lists the PoPs the attacker can send from and to; ``None``
    means every PoP (D8).
    ``oracle_knowledge`` says which oracle builds the fresh plan A* that η
    (Eq. 10) and τ (Eq. 1) divide by (decision D15, flagged for review):
    ``"benign"`` (default) also knows the benign traffic matrix and targets
    the link where its attack does the most damage; ``"routing"`` is the
    paper's oracle (§3.2), which knows only topology and routing.
    """

    budget: float
    n_pairs: int = 10
    endpoints: tuple[str, ...] | None = None
    oracle_knowledge: str = "benign"

    def __post_init__(self) -> None:
        if not (self.budget > 0 and math.isfinite(self.budget)):
            raise ValueError("budget must be a positive, finite rate")
        if self.n_pairs < 1:
            raise ValueError("n_pairs must be at least 1")
        if self.oracle_knowledge not in ORACLE_KNOWLEDGE:
            raise ValueError(f"oracle_knowledge must be one of {ORACLE_KNOWLEDGE}")


@dataclass(frozen=True)
class DamageConfig:
    """How damage and τ are measured (decisions D1, D2; interpretations I1, I2).

    ``tau_measure``: which damage measure τ and η are computed from (D1).
    ``zero_denominator``: what τ is when the fresh plan does no damage (D2).
    ``"zero"`` sets τ = 0; ``"nan"`` leaves it undefined. Either way the
    result is flagged ``attack_immune``.
    ``safe_threshold``: utilization above which a link counts as driven past
    its safe operating point (I1).
    ``congestion_threshold``: utilization above which a link counts as
    congested (I2). 1.0 means offered load exceeds capacity.
    ``zero_tolerance``: damage at or below this is treated as no damage.
    ``sharing``: how an overloaded link divides its capacity (decision D11,
    pending confirmation). ``"proportional"`` (every flow loses the same
    fraction, like tail drop) or ``"max_min"`` (the existing engine's
    default; small flows are served in full first). Under max-min, attack
    flows larger than benign flows absorb all the loss, so on ANS no attack
    causes any benign loss at all.
    ``disruption_level``: benign loss (share of benign demand) that counts as
    "the attack begins to affect benign traffic" for the fifth §3.4 measure,
    the budget needed to disrupt (decision D14). The default, one millionth,
    is "any loss" while staying above numerical noise in the loss model.
    """

    tau_measure: str = "benign_loss"
    zero_denominator: str = "zero"
    safe_threshold: float = 0.8
    congestion_threshold: float = 1.0
    zero_tolerance: float = 1e-9
    sharing: str = "proportional"
    disruption_level: float = 1e-6

    def __post_init__(self) -> None:
        if self.sharing not in ("proportional", "max_min"):
            raise ValueError("sharing must be 'proportional' or 'max_min'")
        if self.tau_measure not in DAMAGE_MEASURES:
            raise ValueError(
                f"tau_measure must be one of {DAMAGE_MEASURES}, got {self.tau_measure!r}"
            )
        if self.zero_denominator not in ("zero", "nan"):
            raise ValueError("zero_denominator must be 'zero' or 'nan'")


@dataclass(frozen=True)
class DamageReport:
    """Damage D(A, G) of one plan on one topology (paper §2.4, §3.4).

    Measures (see ``docs/decisions.md`` I1, I2 for the interpretations):

    - ``max_utilization``: highest offered load / capacity on any link, with
      the attack running. Can exceed 1.
    - ``overloaded_capacity``: total capacity (bit/s) of links whose offered
      utilization is above ``DamageConfig.safe_threshold``.
    - ``benign_on_congested``: share of benign demand routed over a link
      whose offered utilization is above ``DamageConfig.congestion_threshold``.
    - ``benign_loss``: benign traffic delivered without the attack minus with
      it, as a share of benign demand. This is the measure behind τ (D1).

    The remaining fields are the raw totals the measures were computed from.
    """

    max_utilization: float
    overloaded_capacity: float
    benign_on_congested: float
    benign_loss: float
    benign_offered: float
    benign_delivered_without_attack: float
    benign_delivered_with_attack: float
    attack_offered: float
    attack_delivered: float

    def measure(self, name: str) -> float:
        if name not in DAMAGE_MEASURES:
            raise ValueError(f"Unknown damage measure {name!r}")
        return float(getattr(self, name))


@dataclass(frozen=True)
class RelativeDamage:
    """A plan's damage relative to a fresh oracle plan on the same topology.

    ``ratio = numerator / denominator`` where the numerator is the plan's
    damage and the denominator is the fresh oracle plan's damage, both on
    ``evaluated_on`` and with the same attack budget.

    - If the plan was learned on a different topology, ``ratio`` is the
      transferability τ(A_i, G_j) (paper Eq. 1).
    - If it was learned on the same topology by a non-oracle mechanism,
      ``ratio`` is the normalized effectiveness η(A, G) (paper Eq. 10).

    The denominator comes from the oracle named by ``oracle_knowledge``
    (decision D15). The ``other_*`` fields repeat the comparison against the
    other oracle, so τ and η can be recomputed under either choice from saved
    files.

    ``ratio`` can exceed 1. The paper's oracle ranks links by how much attack
    traffic it can concentrate (§3.2), which ignores benign traffic (open
    issue O1). The benign-aware oracle searches only over target links, with
    a fixed rule for choosing pairs, so it too is not a proven upper bound.
    Values are stored unclipped.

    ``attack_immune`` is True when the fresh plan does no damage (D2).
    """

    plan_topology_id: str
    evaluated_on: str
    plan_mechanism: str
    measure: str
    numerator: float
    denominator: float
    ratio: float
    attack_immune: bool
    plan_damage: DamageReport
    fresh_damage: DamageReport
    oracle_knowledge: str
    other_oracle_knowledge: str
    other_denominator: float
    other_ratio: float
    other_attack_immune: bool
    other_fresh_damage: DamageReport

    def as_row(self) -> dict[str, object]:
        """Flatten to one row of ``transferability.csv`` (PLAN §10)."""
        row: dict[str, object] = {
            "plan_topology_id": self.plan_topology_id,
            "evaluated_on": self.evaluated_on,
            "plan_mechanism": self.plan_mechanism,
            "measure": self.measure,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "ratio": self.ratio,
            "attack_immune": self.attack_immune,
            "oracle_knowledge": self.oracle_knowledge,
            "other_oracle_knowledge": self.other_oracle_knowledge,
            "other_denominator": self.other_denominator,
            "other_ratio": self.other_ratio,
            "other_attack_immune": self.other_attack_immune,
        }
        for prefix, report in (
            ("plan", self.plan_damage),
            ("fresh", self.fresh_damage),
            ("other_fresh", self.other_fresh_damage),
        ):
            for key, value in asdict(report).items():
                row[f"{prefix}_{key}"] = value
        return row
