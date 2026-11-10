"""The variant switch (``variants.applied``)."""

import types

import pytest

from doppler2026.variants import applied


def _module() -> types.ModuleType:
    module = types.ModuleType("fake")
    module.f = lambda: "current"
    return module


def test_applied_swaps_and_restores():
    module = _module()
    with applied({module: {"f": lambda: "proposed"}}):
        assert module.f() == "proposed"
    assert module.f() == "current"


def test_applied_restores_after_an_error():
    module = _module()
    with pytest.raises(RuntimeError), applied({module: {"f": lambda: "x"}}):
        raise RuntimeError
    assert module.f() == "current"


def test_applied_refuses_a_missing_name():
    module = _module()
    with pytest.raises(AttributeError), applied({module: {"g": lambda: "x"}}):
        pass
    assert not hasattr(module, "g")
