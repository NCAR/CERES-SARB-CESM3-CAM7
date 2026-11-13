#!/usr/bin/env python
"""Compatibility entry point for the SP3 LW omega/g table generator."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sp3_optics.make_omega_g_table import CAM_LW_EDGES_CM
from sp3_optics.make_omega_g_table import CAM_LW_MID_UM
from sp3_optics.make_omega_g_table import CAM_RRTMGP_LW_COEFF_PATH
from sp3_optics.make_omega_g_table import MODE_ORDER
from sp3_optics.make_omega_g_table import build_physical_table
from sp3_optics.make_omega_g_table import load_mode_specs
from sp3_optics.make_omega_g_table import main
from sp3_optics.make_omega_g_table import physical_attrs
from sp3_optics.make_omega_g_table import physical_table
from sp3_optics.make_omega_g_table import write_table
from sp3_optics.make_omega_g_table import zero_table


if __name__ == "__main__":
    raise SystemExit(main())
