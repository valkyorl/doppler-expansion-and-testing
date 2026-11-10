"""Ephemeral variants of Doppler, compared against the current version.

Not part of the paper; a research tool. Each variant module proposes one
change and lists it in ``REPLACEMENTS`` as ``{module: {name: replacement}}``.
``applied`` swaps those functions in for one ``with`` block, so a study can
run the current and the proposed version side by side without editing the
real modules. Conventions, promotion, and deletion: ``variants/README.md``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from types import ModuleType


@contextmanager
def applied(replacements: Mapping[ModuleType, Mapping[str, object]]) -> Iterator[None]:
    """Replace module attributes inside the block; restore them on exit."""
    saved = []
    try:
        for module, names in replacements.items():
            for name, value in names.items():
                # Only replace what exists, so a typo cannot silently add a
                # new attribute that nothing reads.
                saved.append((module, name, getattr(module, name)))
                setattr(module, name, value)
        yield
    finally:
        for module, name, value in reversed(saved):
            setattr(module, name, value)
