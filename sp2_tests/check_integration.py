#!/usr/bin/env python3
"""Assert SP2 AOD nudging behavior from a CAM h0 file."""

import argparse
import sys

import numpy as np
from netCDF4 import Dataset


def read_last(ds, name):
    return np.ma.filled(ds.variables[name][-1, ...], np.nan)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--h0", required=True)
    parser.add_argument("--rtol", type=float, default=0.05)
    parser.add_argument("--atol", type=float, default=1.0e-3)
    args = parser.parse_args()

    with Dataset(args.h0) as ds:
        obs = read_last(ds, "AODNDG_OBS")
        pre = read_last(ds, "AODNDG_MODEL_PRE")
        post = read_last(ds, "AODNDG_MODEL_POST")
        mask = read_last(ds, "AODNDG_MASK")

    nudged = mask > 0.5
    free = ~nudged
    ok = True

    if np.any(nudged):
        rel = np.abs(post[nudged] - obs[nudged]) / np.maximum(np.abs(obs[nudged]), args.atol)
        bad = int(np.sum(rel > args.rtol))
        print(f"nudged cells={int(np.sum(nudged))} max_rel_err={np.nanmax(rel):.4f} bad={bad}")
        ok = ok and bad == 0
    else:
        print("WARNING: no nudged cells found")
        ok = False

    if np.any(free):
        delta = np.abs(post[free] - pre[free])
        bad = int(np.sum(delta > args.atol))
        print(f"free cells={int(np.sum(free))} max_abs_change={np.nanmax(delta):.2e} bad={bad}")
        ok = ok and bad == 0
    else:
        print("WARNING: no free cells found")
        ok = False

    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
