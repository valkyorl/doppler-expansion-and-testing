"""Experiment entry point: run the Doppler controller from a JSON config (PLAN §3; results schema).

Run from the repository root::

    python -m doppler2026.run doppler2026/configs/ANS_doppler.json
    python -m doppler2026.run doppler2026/configs/ANS_doppler.json --run-id try1

A config is a JSON object with the fields of ``controller.ControllerConfig``.
``defender`` holds the Phase 3 settings by module (``feasibility``,
``candidates``, ``operational``, ``security``, ``selection``, ``routing``,
``damage``); any field left out keeps its default, so a config lists only
what it changes. ``config.json`` in the run folder records the full
resolved config.

Output: ``data/results/doppler2026/controller/<run_id>/`` with
``config.json``, ``epochs.csv`` (one row per epoch), ``candidates.csv`` (one
row per candidate per epoch), ``transferability.csv`` (the attack running
each epoch, ``role = stale_attack``, and the security filter's τ,
``role = security``), and ``transitions.jsonl`` (the ordered actions and
intermediate states of each transition).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import typing
from pathlib import Path

from .controller import ControllerConfig, DefenderConfig, run
from .results import new_run_dir, write_config, write_csv, write_jsonl

EXPERIMENT = "controller"


def _build(cls, values: dict):
    """A dataclass from a dict, recursing into dataclass fields; unknown keys are refused."""
    hints = typing.get_type_hints(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(values) - names
    if unknown:
        raise ValueError(f"Unknown {cls.__name__} settings: {sorted(unknown)}")
    kwargs = {}
    for name, value in values.items():
        kind = hints[name]
        if dataclasses.is_dataclass(kind) and isinstance(value, dict):
            value = _build(kind, value)
        elif isinstance(value, list):
            value = tuple(value)  # JSON arrays are tuples in the configs
        kwargs[name] = value
    return cls(**kwargs)


def load_config(path: Path) -> ControllerConfig:
    values = json.loads(Path(path).read_text())
    values.pop("_comment", None)
    defender = values.pop("defender", {})
    return ControllerConfig(**values, defender=_build(DefenderConfig, defender))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    config = load_config(args.config)
    run_dir = new_run_dir(EXPERIMENT, args.run_id)
    write_config(run_dir, dataclasses.asdict(config))

    def progress(row: dict) -> None:
        print(
            f"epoch {row['epoch']}: links {row['links']}, "
            f"stale τ {row.get('stale_transferability', '-')}, "
            f"safe {row.get('safe', '-')}, transition {row['transition']}, "
            f"{row['wall_time']:.0f} s",
            flush=True,
        )

    result = run(config, progress=progress)
    write_csv(run_dir, "epochs.csv", result.epochs)
    write_csv(run_dir, "candidates.csv", result.candidates)
    write_csv(run_dir, "transferability.csv", result.transferability)
    write_jsonl(run_dir, "transitions.jsonl", result.transitions)
    print(run_dir)


if __name__ == "__main__":
    main()
