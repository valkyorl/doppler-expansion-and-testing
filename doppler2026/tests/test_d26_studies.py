"""The study helpers (``studies/common.py``) and the 10-PoP baseline's setup."""

import pytest

from doppler2026.studies.common import layout_averages, layout_summary
from doppler2026.studies.sparsification_synthetic10 import LAYOUTS
from doppler2026.synthetic import generate


def _epoch(epoch, links, added=0, removed=0, loss=None):
    row = {
        "epoch": epoch,
        "links": links,
        "transition_added": added,
        "transition_removed": removed,
        "current_mlu": 0.5 + epoch / 10,
        "current_max_stretch": 1.0 + epoch,
    }
    if loss is not None:
        row["stale_benign_loss"] = loss
    return row


def test_layout_summary_counts_moves_links_and_damage():
    rows = [
        _epoch(0, 20),
        _epoch(1, 20, removed=2),
        _epoch(2, 18, added=1, loss=0.1),
        _epoch(3, 19, loss=0.3),
    ]
    summary = layout_summary("n", "doppler", rows)
    assert summary["start_links"] == 20 and summary["end_links"] == 19
    assert summary["lowest_links"] == 18 and summary["links_lost"] == 1
    assert summary["moves"] == 2 and summary["last_move"] == 2
    assert summary["added"] == 1 and summary["removed"] == 2
    assert summary["first_stale_loss"] == 0.1
    assert summary["last_stale_loss"] == summary["max_stale_loss"] == 0.3
    assert summary["max_mlu"] == pytest.approx(0.8)


def test_layout_summary_handles_a_run_without_attacks_or_moves():
    summary = layout_summary("n", "static", [_epoch(0, 20)])
    assert summary["moves"] == 0 and summary["last_move"] is None
    assert summary["max_stale_loss"] is None


def test_layout_averages_are_per_mode_and_skip_missing_values():
    rows = [
        layout_summary("a", "doppler", [_epoch(0, 20), _epoch(1, 18, loss=0.2)]),
        layout_summary("b", "doppler", [_epoch(0, 20), _epoch(1, 20)]),
        layout_summary("a", "static", [_epoch(0, 20)]),
    ]
    averages = {row["mode"]: row for row in layout_averages(rows)}
    assert averages["doppler"]["layouts"] == 2
    assert averages["doppler"]["end_links"] == 19
    assert averages["doppler"]["max_stale_loss"] == pytest.approx(0.2)
    assert "last_move" not in averages["doppler"]
    assert averages["static"]["layouts"] == 1


def test_baseline_has_eight_distinct_layouts_of_the_chosen_shape():
    assert [c.seed for c in LAYOUTS] == list(range(8))
    graphs = [generate(c) for c in LAYOUTS]
    assert all(g.number_of_nodes() == 10 for g in graphs)
    assert all(g.number_of_edges() == 20 for g in graphs)
    assert len({frozenset(map(frozenset, g.edges)) for g in graphs}) == 8
