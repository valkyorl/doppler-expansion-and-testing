#!/usr/bin/env bash
# Reproduce every version-zero result and figure of the Doppler 2026 experiment.
#
# Run from the repository root:
#
#     bash doppler2026/reproduce_v0.sh [all|recon|defender|controller|figures] [prefix]
#
# Each step writes a new run folder under data/results/doppler2026/ named
# <prefix> (default v0) or <prefix>-<network>-<mode>; a step refuses to start
# if its folder already exists, so pick a new prefix to rerun. Steps
# recon, defender and controller are independent and may run in parallel;
# figures needs all three. Rough times on a 12-core laptop: recon 20 min,
# defender 10 min, controller 60 min.
#
# The controller runs use configs/v0/, which pin the v0 settings that later
# stopped being defaults (2026-11-10 baseline). recon and defender use the
# code's defaults; the 2026-11-10 changes do not affect recon, but the
# defender epoch needs the v0 commit (or tag) to match v0 exactly.
set -euo pipefail

step="${1:-all}"
prefix="${2:-v0}"
networks=(sprint ANS CRL bellCanada surfNet)
results=data/results/doppler2026

recon() {
    python -m doppler2026.experiments.recon_eval --run-id "$prefix"
}

defender() {
    python -m doppler2026.experiments.defender_epoch \
        --networks "${networks[@]}" --run-id "$prefix"
}

controller() {
    for network in "${networks[@]}"; do
        for mode in static doppler churn; do
            echo "== $network $mode"
            python -u -m doppler2026.run "doppler2026/configs/v0/${network}_${mode}.json" \
                --run-id "$prefix-$network-$mode"
        done
    done
}

figures() {
    local run="$results/recon_eval/$prefix"
    python -m doppler2026.figures.table_networks --run "$run"
    python -m doppler2026.figures.fig_rq1_recovery --run "$run"
    python -m doppler2026.figures.fig_rq2_critical_links --run "$run"
    python -m doppler2026.figures.fig_rq3_attack_impact --run "$run"
    python -m doppler2026.figures.fig_controller_stale_damage --prefix "$prefix"
}

case "$step" in
    recon | defender | controller | figures) "$step" ;;
    all) recon && defender && controller && figures ;;
    *) echo "unknown step: $step" >&2; exit 2 ;;
esac
