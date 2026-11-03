"""Phase 2 checks on real data: the regional reconstruction loads, and the
reconnaissance experiment produces every metric on a small network.

PLAN.md Phase 2: metrics run on simulated measurements for every geo-tagged
topology (here one small one, for speed; the full run is
``python -m doppler2026.experiments.recon_eval``) and on the regional
reconstruction.
"""

import math

import pytest

from doppler2026.experiments import recon_eval
from doppler2026.recon import rtt_ricci
from doppler2026.results import new_run_dir, write_csv
from doppler2026.topology import GML_DIR

needs_regional = pytest.mark.skipif(
    not (rtt_ricci.REGIONAL_DIR / "reconstruction_regional.json").exists(),
    reason="regional data not available",
)


@needs_regional
def test_regional_files_load():
    recon = rtt_ricci.load_regional_reconstruction()
    truth = rtt_ricci.load_regional_ground_truth()
    assert (recon.number_of_nodes(), recon.number_of_edges()) == (12, 53)
    assert (truth.number_of_nodes(), truth.number_of_edges()) == (12, 18)


SMALL = recon_eval.ReconEvalConfig(
    networks=("sprint",),
    budget_multiples=(2.0,),
    random_seeds=2,
    measurement_seeds=(0,),
    vantage_fractions=(1.0, 0.5),
    non_response=(0.1,),
    epsilon_quantiles=(0.3,),
    k_values=(1, 3),
)


@pytest.mark.skipif(
    not (GML_DIR / "sprint.gml").exists(), reason="sprint not available"
)
def test_experiment_rows_for_a_geo_topology():
    network = next(recon_eval.load_networks(SMALL))
    recon_rows, transfer_rows = recon_eval.evaluate_network(network, SMALL)
    # oracle + 2 random + 2 coverages x (1 traceroute + 1 rtt) plans, 1 budget.
    assert len(transfer_rows) == 7
    assert {r["mechanism"] for r in transfer_rows} == {
        "oracle",
        "random",
        "traceroute",
        "rtt_ricci",
    }
    oracle = next(r for r in transfer_rows if r["mechanism"] == "oracle")
    assert oracle["ratio"] == pytest.approx(1.0)
    metrics = {(r["mechanism"], r["metric"]) for r in recon_rows}
    for mechanism in ("traceroute", "rtt_ricci"):
        for name in (
            "precision",
            "recall",
            "f1",
            "p_at_k",
            "path_at_k",
            "budget_to_disrupt",
        ):
            assert (mechanism, name) in metrics
    assert all(r["ground_truth_independent"] for r in recon_rows)


@needs_regional
def test_regional_refuses_topology_recovery():
    config = recon_eval.ReconEvalConfig(
        networks=(), budget_multiples=(2.0,), random_seeds=1, k_values=(1,)
    )
    network = next(recon_eval.load_networks(config))
    assert network.name == "regional"
    recon_rows, _ = recon_eval.evaluate_network(network, config)
    precision = [r for r in recon_rows if r["metric"] == "precision"]
    assert len(precision) == 1 and math.isnan(precision[0]["value"])
    assert "not independently validated" in precision[0]["note"]
    assert not any(r["ground_truth_independent"] for r in recon_rows)


def test_results_writer(tmp_path):
    run_dir = new_run_dir("demo", "r1", root=tmp_path)
    path = write_csv(run_dir, "x.csv", [{"a": 1}, {"a": 2, "b": 3}])
    assert path.read_text().splitlines() == ["a,b", "1,", "2,3"]
    with pytest.raises(FileExistsError):
        new_run_dir("demo", "r1", root=tmp_path)
