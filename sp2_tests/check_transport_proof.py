#!/usr/bin/env python3
"""Assert that SP2 aerosol increments persist and move after observations stop."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


def read_field(ds: Dataset, name: str) -> np.ndarray:
    return np.ma.filled(ds.variables[name][:], np.nan)


def pulse_mask_from_obs(path: str | Path) -> np.ndarray:
    with Dataset(path) as ds:
        obs = read_field(ds, "aod_weighted_mean")
    return np.asarray(obs, dtype=float) > -900.0


def _max_abs(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return 0.0
    return float(np.nanmax(np.abs(finite)))


def _abs_sum(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return 0.0
    return float(np.nansum(np.abs(finite)))


def transport_metrics(
    nudged_h0: str | Path,
    free_h0: str | Path,
    pulse_obs: str | Path,
    *,
    nudged_diag_h0: str | Path | None = None,
    post_start_index: int,
) -> dict[str, float]:
    pulse_mask = pulse_mask_from_obs(pulse_obs)

    with Dataset(nudged_h0) as nds:
        nudged_aod = read_field(nds, "AODVIS")
    with Dataset(nudged_diag_h0 or nudged_h0) as nds:
        nudged_mask = read_field(nds, "AODNDG_MASK")
    with Dataset(free_h0) as fds:
        free_aod = read_field(fds, "AODVIS")

    if nudged_aod.shape != free_aod.shape:
        raise ValueError(f"AODVIS shape mismatch: nudged {nudged_aod.shape}, free {free_aod.shape}")
    if nudged_aod.shape[-2:] != pulse_mask.shape:
        raise ValueError(
            f"pulse mask shape {pulse_mask.shape} does not match AODVIS grid {nudged_aod.shape[-2:]}"
        )
    if post_start_index < 0 or post_start_index >= nudged_mask.shape[0]:
        raise ValueError("post_start_index must select at least one output record")

    post_mask = np.asarray(nudged_mask[post_start_index:, ...], dtype=float)
    finite_post_mask = post_mask[np.isfinite(post_mask)]
    post_mask_max = float(np.nanmax(finite_post_mask)) if finite_post_mask.size else 0.0

    final_delta = np.asarray(nudged_aod[-1, ...] - free_aod[-1, ...], dtype=float)
    inside = pulse_mask
    outside = ~pulse_mask
    inside_abs_sum = _abs_sum(final_delta[inside])
    outside_abs_sum = _abs_sum(final_delta[outside])
    total_abs_sum = inside_abs_sum + outside_abs_sum
    outside_frac = outside_abs_sum / total_abs_sum if total_abs_sum > 0.0 else 0.0

    return {
        "post_mask_max": post_mask_max,
        "inside_abs_sum": inside_abs_sum,
        "outside_abs_sum": outside_abs_sum,
        "total_abs_sum": total_abs_sum,
        "outside_frac": float(outside_frac),
        "outside_abs_max": _max_abs(final_delta[outside]),
    }


def proof_passes(metrics: dict[str, float], *, outside_frac_min: float, outside_max_min: float) -> bool:
    return (
        metrics["post_mask_max"] == 0.0
        and metrics["total_abs_sum"] > 0.0
        and metrics["outside_frac"] >= outside_frac_min
        and metrics["outside_abs_max"] >= outside_max_min
    )


def metric_summary(metrics: dict[str, float]) -> str:
    order = (
        "post_mask_max",
        "inside_abs_sum",
        "outside_abs_sum",
        "total_abs_sum",
        "outside_frac",
        "outside_abs_max",
    )
    return " ".join(f"{name}={metrics[name]:.6g}" for name in order)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nudged-h0", required=True)
    parser.add_argument("--free-h0", required=True)
    parser.add_argument("--nudged-diag-h0", default=None)
    parser.add_argument("--pulse-obs", required=True)
    parser.add_argument("--post-start-index", type=int, required=True)
    parser.add_argument("--outside-frac-min", type=float, required=True)
    parser.add_argument("--outside-max-min", type=float, required=True)
    args = parser.parse_args()

    metrics = transport_metrics(
        args.nudged_h0,
        args.free_h0,
        args.pulse_obs,
        nudged_diag_h0=args.nudged_diag_h0,
        post_start_index=args.post_start_index,
    )
    ok = proof_passes(
        metrics,
        outside_frac_min=args.outside_frac_min,
        outside_max_min=args.outside_max_min,
    )
    print(metric_summary(metrics))
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
