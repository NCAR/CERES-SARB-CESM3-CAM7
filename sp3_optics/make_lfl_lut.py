#!/usr/bin/env python
"""Generate SP3 LFL aerosol optics Chebyshev lookup tables."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from multiprocessing import get_context
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

if not hasattr(np, "trapezoid"):
    np.trapezoid = np.trapz


from sp3_optics.lfl_bands import LFL_LW_EDGES_UM
from sp3_optics.lfl_bands import LFL_LW_MIDPOINTS_UM
from sp3_optics.lfl_bands import LFL_SW_EDGES_UM
from sp3_optics.lfl_bands import LFL_SW_MIDPOINTS_UM
from sp3_optics.make_omega_g_table import MAM_LFL_ROOT
from sp3_optics.make_omega_g_table import MODE_ORDER
from sp3_optics.make_omega_g_table import PHYSPROP_PATHS
from sp3_optics.make_omega_g_table import _git_value
from sp3_optics.make_omega_g_table import refractive_index_for_species

if str(MAM_LFL_ROOT) not in sys.path:
    sys.path.insert(0, str(MAM_LFL_ROOT))

from mie_sphere import mie_cross_sections_um2  # noqa: E402


BANDS_YAML = MAM_LFL_ROOT / "bands.yaml"
CHEB_RADIUS_MIN_UM = 0.01
CHEB_RADIUS_MAX_UM = 25.0
RHO_H2O_KG_M3 = 1000.0
N_SIGMA = 5.0
X_CAP = 200.0
DEFAULT_CAM_NCOEF = 5
DEFAULT_LFL_NCOEF = 20
DEFAULT_MIE_RADIUS_GRID_SIZE = 700
CAM_VISIBLE_SW_INDEX = 9
SPECTYPES = ("BC", "POM", "SOA", "SU", "DU", "SS", "WAT")
CAM_SPECTYPE_PHYSPROP_PATHS = {
    "BC": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/bcpho_rrtmg_c100508.nc"),
    "POM": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/ocpho_rrtmg_c130709.nc"),
    "SOA": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/ocphi_rrtmg_c100508.nc"),
    "SU": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/sulfate_rrtmg_c080918.nc"),
    "DU": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/dust_aeronet_rrtmg_c141106.nc"),
    "SS": Path("/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/ssam_rrtmg_c100508.nc"),
}
CAM_WATER_REFINDEX_PATH = Path(
    "/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/water_refindex_rrtmg_c080910.nc"
)
STOCK_RRTMG_SW_LOW_CM = np.array(
    [
        2600.0,
        3250.0,
        4000.0,
        4650.0,
        5150.0,
        6150.0,
        7700.0,
        8050.0,
        12850.0,
        16000.0,
        22650.0,
        29000.0,
        38000.0,
        820.0,
    ],
    dtype=np.float64,
)
STOCK_RRTMG_SW_HIGH_CM = np.array(
    [
        3250.0,
        4000.0,
        4650.0,
        5150.0,
        6150.0,
        7700.0,
        8050.0,
        12850.0,
        16000.0,
        22650.0,
        29000.0,
        38000.0,
        50000.0,
        2600.0,
    ],
    dtype=np.float64,
)
STOCK_RRTMG_LW_EDGES_CM = np.array(
    [
        10.0,
        350.0,
        500.0,
        630.0,
        700.0,
        820.0,
        980.0,
        1080.0,
        1180.0,
        1390.0,
        1480.0,
        1800.0,
        2080.0,
        2250.0,
        2390.0,
        2600.0,
        3250.0,
    ],
    dtype=np.float64,
)


def _load_cam_sw_edges_cm(path: Path = BANDS_YAML) -> np.ndarray:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    edges = np.asarray(config["CAM_SW"], dtype=np.float64)
    if edges.shape != (15,):
        raise ValueError(f"CAM_SW must define 15 edges, got {edges.shape}")
    return edges


def _wavenumber_midpoints_um(edges_cm: np.ndarray) -> np.ndarray:
    return 1.0e4 / (0.5 * (edges_cm[:-1] + edges_cm[1:]))


def _wavenumber_pair_midpoints_um(low_cm: np.ndarray, high_cm: np.ndarray) -> np.ndarray:
    return 1.0e4 / (0.5 * (np.asarray(low_cm, dtype=np.float64) + np.asarray(high_cm, dtype=np.float64)))


def _normalize_log_surface_radius(surface_radius_um: np.ndarray | float) -> np.ndarray:
    radius = np.asarray(surface_radius_um, dtype=np.float64)
    log_radius = np.log(np.clip(radius, CHEB_RADIUS_MIN_UM, CHEB_RADIUS_MAX_UM) * 1.0e-6)
    xmin = np.log(CHEB_RADIUS_MIN_UM * 1.0e-6)
    xmax = np.log(CHEB_RADIUS_MAX_UM * 1.0e-6)
    return (2.0 * log_radius - xmax - xmin) / (xmax - xmin)


def _surface_radius_from_normalized_x(x_radius: np.ndarray) -> np.ndarray:
    x = np.asarray(x_radius, dtype=np.float64)
    xmin = np.log(CHEB_RADIUS_MIN_UM * 1.0e-6)
    xmax = np.log(CHEB_RADIUS_MAX_UM * 1.0e-6)
    log_radius = 0.5 * (x * (xmax - xmin) + xmax + xmin)
    return np.exp(log_radius) / 1.0e-6


def cheb_surface_radii_um(n_radius: int) -> np.ndarray:
    """Sampling radii from first-kind Chebyshev nodes on CAM's log-radius domain."""
    if n_radius < 2:
        raise ValueError("n_radius must be >= 2")
    index = np.arange(int(n_radius), dtype=np.float64)
    x_radius = np.cos(np.pi * (index + 0.5) / float(n_radius))
    return np.sort(_surface_radius_from_normalized_x(x_radius)).astype(np.float64)


def default_ncoef(band_set: str, stock_ncoef: int = DEFAULT_CAM_NCOEF) -> int:
    if band_set == "lfl":
        return DEFAULT_LFL_NCOEF
    if band_set == "cam":
        return int(stock_ncoef)
    raise ValueError(f"unsupported band_set {band_set!r}")


def cam_cheb_fit(x: np.ndarray, values: np.ndarray, ncoef: int) -> np.ndarray:
    coeff = np.polynomial.chebyshev.chebfit(
        np.asarray(x, dtype=np.float64),
        np.asarray(values, dtype=np.float64),
        deg=int(ncoef) - 1,
    )
    coeff[0] *= 2.0
    return coeff.astype(np.float64)


def cam_cheb_eval(x: np.ndarray, coeff: np.ndarray) -> np.ndarray:
    coeff = np.asarray(coeff, dtype=np.float64)
    standard = coeff.copy()
    standard[0] *= 0.5
    return np.polynomial.chebyshev.chebval(np.asarray(x, dtype=np.float64), standard)


def surface_radius_to_number_median_um(surface_radius_um: float, sigma_g: float) -> float:
    log_sigma = np.log(float(sigma_g))
    return float(surface_radius_um) / np.exp(2.0 * log_sigma**2)


def _mean_wet_volume_m3(surface_radius_um: float, sigma_g: float) -> float:
    number_median_um = surface_radius_to_number_median_um(surface_radius_um, sigma_g)
    log_sigma = np.log(float(sigma_g))
    return float(
        (4.0 / 3.0)
        * np.pi
        * (number_median_um * 1.0e-6) ** 3
        * np.exp(4.5 * log_sigma**2)
    )


def _mean_wet_volume_m3_array(surface_radius_um: np.ndarray, sigma_g: float) -> np.ndarray:
    radius = np.asarray(surface_radius_um, dtype=np.float64)
    number_median_um = radius / np.exp(2.0 * np.log(float(sigma_g)) ** 2)
    log_sigma = np.log(float(sigma_g))
    return (
        (4.0 / 3.0)
        * np.pi
        * (number_median_um * 1.0e-6) ** 3
        * np.exp(4.5 * log_sigma**2)
    )


def raw_specific_optics(
    cross_sections_um2: dict[str, float],
    surface_radius_um: float,
    sigma_g: float,
) -> dict[str, np.float64]:
    mean_volume_m3 = _mean_wet_volume_m3(surface_radius_um, sigma_g)
    denominator = mean_volume_m3 * RHO_H2O_KG_M3
    return {
        "ext": np.float64(float(cross_sections_um2["ext"]) * 1.0e-12 / denominator),
        "sca": np.float64(float(cross_sections_um2["sca"]) * 1.0e-12 / denominator),
        "abs": np.float64(float(cross_sections_um2["abs"]) * 1.0e-12 / denominator),
        "asm": np.float64(np.clip(float(cross_sections_um2["asymmetry"]), -1.0, 1.0)),
    }


def _mie_radius_grid_um(surface_radii_um: np.ndarray, sigma_g: float, n_grid: int) -> np.ndarray:
    if n_grid < 3:
        raise ValueError("mie_radius_grid_size must be >= 3")
    median_radii = np.asarray(
        [surface_radius_to_number_median_um(float(radius), sigma_g) for radius in surface_radii_um],
        dtype=np.float64,
    )
    span = np.exp(N_SIGMA * np.log(float(sigma_g)))
    return np.geomspace(
        float(median_radii.min()) / span,
        float(median_radii.max()) * span,
        int(n_grid),
    )


def _mie_curve_um2(
    wavelength_um: float,
    n_real: float,
    n_imag: float,
    radius_grid_um: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    radius = np.asarray(radius_grid_um, dtype=np.float64)
    x_size = 2.0 * np.pi * radius / float(wavelength_um)
    ext = np.empty_like(radius)
    sca = np.empty_like(radius)
    gsca = np.empty_like(radius)
    cap: tuple[float, float, float] | None = None
    for index, radius_um in enumerate(radius):
        area = np.pi * float(radius_um) ** 2
        if x_size[index] <= X_CAP:
            cross = mie_cross_sections_um2(n_real, abs(n_imag), float(radius_um), wavelength_um)
            cap = (
                float(cross["ext"]) / area,
                float(cross["sca"]) / area,
                float(cross["asymmetry"]),
            )
        elif cap is None:
            cap_radius = float(wavelength_um) * X_CAP / (2.0 * np.pi)
            cap_cross = mie_cross_sections_um2(n_real, abs(n_imag), cap_radius, wavelength_um)
            cap_area = np.pi * cap_radius**2
            cap = (
                float(cap_cross["ext"]) / cap_area,
                float(cap_cross["sca"]) / cap_area,
                float(cap_cross["asymmetry"]),
            )
        q_ext, q_sca, asymmetry = cap
        ext[index] = q_ext * area
        sca[index] = q_sca * area
        gsca[index] = asymmetry * q_sca * area
    return ext, sca, gsca


def _integrate_curve_specific_optics(
    radius_grid_um: np.ndarray,
    ext_um2: np.ndarray,
    sca_um2: np.ndarray,
    gsca_um2: np.ndarray,
    surface_radii_um: np.ndarray,
    sigma_g: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lnr = np.log(np.asarray(radius_grid_um, dtype=np.float64))
    log_sigma = np.log(float(sigma_g))
    surface_radii = np.asarray(surface_radii_um, dtype=np.float64)
    median_radii = surface_radii / np.exp(2.0 * log_sigma**2)
    mean_volume = _mean_wet_volume_m3_array(surface_radii, sigma_g)
    ext = np.empty_like(surface_radii)
    absn = np.empty_like(surface_radii)
    asm = np.empty_like(surface_radii)
    for index, median_radius in enumerate(median_radii):
        weight = np.exp(-((lnr - np.log(float(median_radius))) ** 2) / (2.0 * log_sigma**2))
        weight /= log_sigma * np.sqrt(2.0 * np.pi)
        norm = float(np.trapezoid(weight, lnr))
        ext_avg = float(np.trapezoid(ext_um2 * weight, lnr) / norm)
        sca_avg = float(np.trapezoid(sca_um2 * weight, lnr) / norm)
        gsca_avg = float(np.trapezoid(gsca_um2 * weight, lnr) / norm)
        denominator = mean_volume[index] * RHO_H2O_KG_M3
        ext[index] = max(ext_avg, 0.0) * 1.0e-12 / denominator
        absn[index] = max(ext_avg - sca_avg, 0.0) * 1.0e-12 / denominator
        asm[index] = gsca_avg / sca_avg if sca_avg > 0.0 else 0.0
    return ext, absn, np.clip(asm, -1.0, 1.0)


def _source_band_indices(source_mid_um: np.ndarray, target_mid_um: tuple[float, ...]) -> np.ndarray:
    source = np.asarray(source_mid_um, dtype=np.float64)
    return np.asarray(
        [int(np.argmin(np.abs(source - float(mid)))) for mid in target_mid_um],
        dtype=np.int32,
    )


def _limited(values: np.ndarray, limit: int | None) -> np.ndarray:
    if limit is None:
        return values
    return values[: int(limit)]


def _densify_axis(values: np.ndarray, subdivisions: int) -> np.ndarray:
    if subdivisions < 1:
        raise ValueError("refindex_subdivisions must be >= 1")
    axis = np.asarray(values, dtype=np.float64)
    if axis.size <= 1 or subdivisions == 1:
        return axis.astype(np.float64)
    pieces = [
        np.linspace(float(left), float(right), int(subdivisions) + 1, dtype=np.float64)[:-1]
        for left, right in zip(axis[:-1], axis[1:])
    ]
    return np.concatenate([*pieces, axis[-1:].astype(np.float64)])


def _mode_index(mode: str) -> int:
    try:
        return MODE_ORDER.index(mode)
    except ValueError as exc:
        raise ValueError(f"unsupported mode {mode!r}") from exc


def fit_optics_node(
    wavelength_um: float,
    n_real: float,
    n_imag: float,
    sigma_g: float,
    surface_radii_um: np.ndarray,
    x_radius: np.ndarray,
    ncoef: int,
    mie_radius_grid_size: int = DEFAULT_MIE_RADIUS_GRID_SIZE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    radius_grid = _mie_radius_grid_um(surface_radii_um, sigma_g, int(mie_radius_grid_size))
    ext_curve, sca_curve, gsca_curve = _mie_curve_um2(
        float(wavelength_um),
        float(n_real),
        abs(float(n_imag)),
        radius_grid,
    )
    ext, absn, asm = _integrate_curve_specific_optics(
        radius_grid,
        ext_curve,
        sca_curve,
        gsca_curve,
        surface_radii_um,
        sigma_g,
    )
    ext = np.maximum(ext, 1.0e-300)
    absn = np.maximum(absn, 0.0)
    return (
        cam_cheb_fit(x_radius, np.log(ext), ncoef),
        cam_cheb_fit(x_radius, absn, ncoef),
        cam_cheb_fit(x_radius, asm, ncoef),
    )


def _fit_one_node(
    wavelength_um: float,
    n_real: float,
    n_imag: float,
    sigma_g: float,
    surface_radii_um: np.ndarray,
    x_radius: np.ndarray,
    ncoef: int,
    n_quad: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return fit_optics_node(
        wavelength_um,
        n_real,
        n_imag,
        sigma_g,
        surface_radii_um,
        x_radius,
        ncoef,
        mie_radius_grid_size=n_quad,
    )


def _fit_lut_task(
    task: tuple[
        str,
        int,
        int,
        int,
        int,
        float,
        float,
        float,
        float,
        np.ndarray,
        np.ndarray,
        int,
        int,
    ],
) -> tuple[str, int, int, int, int, np.ndarray, np.ndarray, np.ndarray]:
    (
        band_kind,
        iband,
        imode,
        iim,
        ire,
        wavelength_um,
        n_real,
        n_imag,
        sigma_g,
        surface_radii_um,
        x_radius,
        ncoef,
        n_quad,
    ) = task
    ext, absn, asm = _fit_one_node(
        wavelength_um,
        n_real,
        n_imag,
        sigma_g,
        surface_radii_um,
        x_radius,
        ncoef,
        n_quad,
    )
    return band_kind, iband, imode, iim, ire, ext, absn, asm


def _spectype_refindices() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sw_real = np.zeros((len(SPECTYPES), len(LFL_SW_MIDPOINTS_UM)), dtype=np.float64)
    sw_imag = np.zeros_like(sw_real)
    lw_real = np.zeros((len(SPECTYPES), len(LFL_LW_MIDPOINTS_UM)), dtype=np.float64)
    lw_imag = np.zeros_like(lw_real)
    for ispec, species in enumerate(SPECTYPES):
        for iband, wavelength in enumerate(LFL_SW_MIDPOINTS_UM):
            sw_real[ispec, iband], sw_imag[ispec, iband] = refractive_index_for_species(
                species,
                float(wavelength),
            )
        for iband, wavelength in enumerate(LFL_LW_MIDPOINTS_UM):
            lw_real[ispec, iband], lw_imag[ispec, iband] = refractive_index_for_species(
                species,
                float(wavelength),
            )
    return sw_real, sw_imag, lw_real, lw_imag


def _cam_spectype_refindices() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sw_real = np.zeros((len(SPECTYPES), len(LFL_SW_MIDPOINTS_UM)), dtype=np.float64)
    sw_imag = np.zeros_like(sw_real)
    lw_real = np.zeros((len(SPECTYPES), len(LFL_LW_MIDPOINTS_UM)), dtype=np.float64)
    lw_imag = np.zeros_like(lw_real)
    sw_source = _source_band_indices(
        _wavenumber_pair_midpoints_um(STOCK_RRTMG_SW_LOW_CM, STOCK_RRTMG_SW_HIGH_CM),
        LFL_SW_MIDPOINTS_UM,
    )
    lw_source = _source_band_indices(_wavenumber_midpoints_um(STOCK_RRTMG_LW_EDGES_CM), LFL_LW_MIDPOINTS_UM)

    for ispec, species in enumerate(SPECTYPES):
        path = CAM_WATER_REFINDEX_PATH if species == "WAT" else CAM_SPECTYPE_PHYSPROP_PATHS[species]
        with xr.open_dataset(path) as ds:
            if species == "WAT":
                sw_real[ispec, :] = ds["refindex_real_water_sw"].values[sw_source]
                sw_imag[ispec, :] = np.abs(ds["refindex_im_water_sw"].values[sw_source])
                lw_real[ispec, :] = ds["refindex_real_water_lw"].values[lw_source]
                lw_imag[ispec, :] = np.abs(ds["refindex_im_water_lw"].values[lw_source])
            else:
                sw_real[ispec, :] = ds["refindex_real_aer_sw"].values[sw_source]
                sw_imag[ispec, :] = np.abs(ds["refindex_im_aer_sw"].values[sw_source])
                lw_real[ispec, :] = ds["refindex_real_aer_lw"].values[lw_source]
                lw_imag[ispec, :] = np.abs(ds["refindex_im_aer_lw"].values[lw_source])
    return sw_real, sw_imag, lw_real, lw_imag


def spectype_refindices(refindex_source: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    if refindex_source == "mam-lfl":
        return (*_spectype_refindices(), "/glade/work/fillmore/Data/Optics/MERRA2")
    if refindex_source == "cam":
        return (*_cam_spectype_refindices(), "cam_physprop")
    raise ValueError(f"unsupported refindex_source {refindex_source!r}")


def _refindex_comparison_rows(
    band_prefix: str,
    midpoints_um: tuple[float, ...],
    mam_real: np.ndarray,
    mam_imag: np.ndarray,
    cam_real: np.ndarray,
    cam_imag: np.ndarray,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for iband, midpoint in enumerate(midpoints_um):
        for ispec, spectype in enumerate(SPECTYPES):
            real_delta = float(mam_real[ispec, iband] - cam_real[ispec, iband])
            imag_delta = float(mam_imag[ispec, iband] - cam_imag[ispec, iband])
            rows.append(
                {
                    "band": f"{band_prefix}{iband + 1:02d}",
                    "midpoint_um": float(midpoint),
                    "spectype": spectype,
                    "mam_lfl_real": float(mam_real[ispec, iband]),
                    "cam_real": float(cam_real[ispec, iband]),
                    "real_delta": real_delta,
                    "real_abs_delta": abs(real_delta),
                    "real_relative_delta": abs(real_delta) / max(abs(float(cam_real[ispec, iband])), 1.0e-30),
                    "mam_lfl_imag": float(mam_imag[ispec, iband]),
                    "cam_imag": float(cam_imag[ispec, iband]),
                    "imag_delta": imag_delta,
                    "imag_abs_delta": abs(imag_delta),
                    "imag_relative_delta": abs(imag_delta) / max(abs(float(cam_imag[ispec, iband])), 1.0e-30),
                }
            )
    return rows


def refindex_comparison_report() -> dict[str, object]:
    mam_sw_real, mam_sw_imag, mam_lw_real, mam_lw_imag = _spectype_refindices()
    cam_sw_real, cam_sw_imag, cam_lw_real, cam_lw_imag = _cam_spectype_refindices()
    sw_rows = _refindex_comparison_rows(
        "SW",
        LFL_SW_MIDPOINTS_UM,
        mam_sw_real,
        mam_sw_imag,
        cam_sw_real,
        cam_sw_imag,
    )
    lw_rows = _refindex_comparison_rows(
        "LW",
        LFL_LW_MIDPOINTS_UM,
        mam_lw_real,
        mam_lw_imag,
        cam_lw_real,
        cam_lw_imag,
    )
    return {
        "mam_lfl_source": "/glade/work/fillmore/Data/Optics/MERRA2",
        "cam_source": "cam_physprop",
        "sw": sw_rows,
        "lw": lw_rows,
        "summary": {
            "sw_real_abs_delta_max": max(row["real_abs_delta"] for row in sw_rows),
            "sw_imag_abs_delta_max": max(row["imag_abs_delta"] for row in sw_rows),
            "lw_real_abs_delta_max": max(row["real_abs_delta"] for row in lw_rows),
            "lw_imag_abs_delta_max": max(row["imag_abs_delta"] for row in lw_rows),
        },
    }


def retarget_lut_refindex(dataset: xr.Dataset, refindex_source: str) -> xr.Dataset:
    """Return a copy of an existing LUT with spectype refractive-index tables replaced."""
    spectype_sw_real, spectype_sw_imag, spectype_lw_real, spectype_lw_imag, source_attr = spectype_refindices(
        refindex_source
    )
    retargeted = dataset.copy(deep=True)
    expected_shapes = {
        "refindex_real_spectype_sw": spectype_sw_real.shape,
        "refindex_im_spectype_sw": spectype_sw_imag.shape,
        "refindex_real_spectype_lw": spectype_lw_real.shape,
        "refindex_im_spectype_lw": spectype_lw_imag.shape,
    }
    for name, expected in expected_shapes.items():
        if tuple(retargeted[name].shape) != tuple(expected):
            raise ValueError(f"{name} has shape {retargeted[name].shape}, expected {expected}")
    retargeted["refindex_real_spectype_sw"].values[...] = spectype_sw_real
    retargeted["refindex_im_spectype_sw"].values[...] = spectype_sw_imag
    retargeted["refindex_real_spectype_lw"].values[...] = spectype_lw_real
    retargeted["refindex_im_spectype_lw"].values[...] = spectype_lw_imag
    previous = retargeted.attrs.get("refindex_source", retargeted.attrs.get("spectype_refindex_source", "unknown"))
    retargeted.attrs["retargeted_refindex_from"] = str(previous)
    retargeted.attrs["refindex_source"] = refindex_source
    retargeted.attrs["spectype_refindex_source"] = source_attr
    retargeted.attrs["created_utc"] = datetime.now(timezone.utc).isoformat()
    return retargeted


def _stock_template(mode: str) -> xr.Dataset:
    return xr.open_dataset(PHYSPROP_PATHS[mode])


def _eval_coefficients(coefficients: np.ndarray, x_radius: np.ndarray, log_ext: bool) -> np.ndarray:
    values = cam_cheb_eval(x_radius, np.asarray(coefficients, dtype=np.float64))
    return np.exp(values) if log_ext else values


def _median_or_nan(values: list[float]) -> float:
    if not values:
        return float("nan")
    finite = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    return float(np.median(finite)) if finite.size else float("nan")


def cam_calibration_report(
    generated: xr.Dataset,
    radius_samples: np.ndarray | None = None,
) -> dict[str, object]:
    """Compare a generated CAM-band table against stock CAM physprop coefficients."""
    if generated.attrs.get("band_set") != "cam":
        raise ValueError("cam_calibration_report requires a dataset generated with band_set='cam'")
    if radius_samples is None:
        radius_samples = np.geomspace(0.012, 20.0, 80)
    x_radius = _normalize_log_surface_radius(np.asarray(radius_samples, dtype=np.float64))
    source_sw = json.loads(generated.attrs["source_sw_band_indices_json"])
    source_lw = json.loads(generated.attrs["source_lw_band_indices_json"])
    mode_names = [str(mode) for mode in generated["mode"].values.tolist()]

    sw_ext_rel: list[float] = []
    sw_abs_rel: list[float] = []
    sw_asm_abs: list[float] = []
    visible_ext_rel: list[float] = []
    lw_abs_rel: list[float] = []
    stock_sources: dict[str, str] = {}
    stock_history: dict[str, str] = {}

    for imode, mode in enumerate(mode_names):
        with _stock_template(mode) as stock:
            stock_sources[mode] = str(stock.attrs.get("source", ""))
            stock_history[mode] = str(stock.attrs.get("history", ""))
            n_re = min(generated.sizes["refindex_real"], stock.sizes["refindex_real"])
            n_im = min(generated.sizes["refindex_im"], stock.sizes["refindex_im"])
            for iband, source_iband in enumerate(source_sw):
                if iband >= generated.sizes["sw_band"]:
                    continue
                for iim in range(n_im):
                    for ire in range(n_re):
                        gen_ext = _eval_coefficients(
                            generated["extpsw"]
                            .isel(sw_band=iband, mode=imode, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=True,
                        )
                        stock_ext = _eval_coefficients(
                            stock["extpsw"]
                            .isel(sw_band=source_iband, mode=0, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=True,
                        )
                        sw_ext_rel.extend(
                            np.abs(gen_ext - stock_ext)
                            / np.maximum(np.abs(stock_ext), 1.0e-30)
                        )
                        if int(source_iband) == CAM_VISIBLE_SW_INDEX:
                            visible_ext_rel.extend(
                                np.abs(gen_ext - stock_ext)
                                / np.maximum(np.abs(stock_ext), 1.0e-30)
                            )
                        gen_abs = _eval_coefficients(
                            generated["abspsw"]
                            .isel(sw_band=iband, mode=imode, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        stock_abs = _eval_coefficients(
                            stock["abspsw"]
                            .isel(sw_band=source_iband, mode=0, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        mask = np.abs(stock_abs) > 1.0e-20
                        if np.any(mask):
                            sw_abs_rel.extend(
                                np.abs(gen_abs[mask] - stock_abs[mask])
                                / np.maximum(np.abs(stock_abs[mask]), 1.0e-30)
                            )
                        gen_asm = _eval_coefficients(
                            generated["asmpsw"]
                            .isel(sw_band=iband, mode=imode, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        stock_asm = _eval_coefficients(
                            stock["asmpsw"]
                            .isel(sw_band=source_iband, mode=0, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        sw_asm_abs.extend(np.abs(gen_asm - stock_asm))
            for iband, source_iband in enumerate(source_lw):
                if iband >= generated.sizes["lw_band"]:
                    continue
                for iim in range(n_im):
                    for ire in range(n_re):
                        gen_abs = _eval_coefficients(
                            generated["absplw"]
                            .isel(lw_band=iband, mode=imode, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        stock_abs = _eval_coefficients(
                            stock["absplw"]
                            .isel(lw_band=source_iband, mode=0, refindex_im=iim, refindex_real=ire)
                            .values,
                            x_radius,
                            log_ext=False,
                        )
                        mask = np.abs(stock_abs) > 1.0e-20
                        if np.any(mask):
                            lw_abs_rel.extend(
                                np.abs(gen_abs[mask] - stock_abs[mask])
                                / np.maximum(np.abs(stock_abs[mask]), 1.0e-30)
                            )

    metrics = {
        "sw_ext_relative_median": _median_or_nan(sw_ext_rel),
        "sw_abs_relative_median": _median_or_nan(sw_abs_rel),
        "sw_asm_absolute_median": _median_or_nan(sw_asm_abs),
        "visible_ext_relative_median": _median_or_nan(visible_ext_rel),
        "lw_abs_relative_median": _median_or_nan(lw_abs_rel),
    }
    gates = {
        "ext_median_le_10pct": bool(metrics["sw_ext_relative_median"] <= 0.10),
        "visible_ext_median_le_5pct": bool(metrics["visible_ext_relative_median"] <= 0.05),
        "asm_median_le_0p05": bool(metrics["sw_asm_absolute_median"] <= 0.05),
    }
    return {
        "band_set": "cam",
        "modes": mode_names,
        "radius_samples_um": [float(value) for value in np.asarray(radius_samples, dtype=np.float64)],
        "metrics": metrics,
        "gates": gates,
        "stock_sources": stock_sources,
        "stock_history": stock_history,
        "note": "Generated MAM-LFL Mie coefficients are compared against stock CAM OPAC/miev0 physprop coefficients.",
    }


def _band_definition(
    band_set: str,
) -> tuple[tuple[float, ...], tuple[float, ...], np.ndarray, np.ndarray]:
    stock_sw_mid = _wavenumber_pair_midpoints_um(STOCK_RRTMG_SW_LOW_CM, STOCK_RRTMG_SW_HIGH_CM)
    stock_lw_mid = _wavenumber_midpoints_um(STOCK_RRTMG_LW_EDGES_CM)
    if band_set == "lfl":
        return LFL_SW_MIDPOINTS_UM, LFL_LW_MIDPOINTS_UM, stock_sw_mid, stock_lw_mid
    if band_set == "cam":
        return tuple(stock_sw_mid), tuple(stock_lw_mid), stock_sw_mid, stock_lw_mid
    raise ValueError(f"unsupported band_set {band_set!r}")


def build_lut_dataset(
    modes: tuple[str, ...] = MODE_ORDER,
    band_set: str = "lfl",
    refindex_source: str = "mam-lfl",
    n_radius: int | None = None,
    n_quad: int = DEFAULT_MIE_RADIUS_GRID_SIZE,
    ncoef: int | None = None,
    max_sw_bands: int | None = None,
    max_lw_bands: int | None = None,
    max_re: int | None = None,
    max_im: int | None = None,
    workers: int = 1,
    refindex_subdivisions: int = 1,
) -> xr.Dataset:
    if n_quad < 2:
        raise ValueError("n_quad must be >= 2")
    if workers < 1:
        raise ValueError("workers must be >= 1")
    if refindex_subdivisions < 1:
        raise ValueError("refindex_subdivisions must be >= 1")

    sw_mid, lw_mid, source_sw_mid, source_lw_mid = _band_definition(band_set)
    sw_mid_values = np.asarray(sw_mid[:max_sw_bands], dtype=np.float64)
    lw_mid_values = np.asarray(lw_mid[:max_lw_bands], dtype=np.float64)
    source_sw_indices = _source_band_indices(source_sw_mid, tuple(sw_mid_values))
    source_lw_indices = _source_band_indices(source_lw_mid, tuple(lw_mid_values))
    mode_names = tuple(modes)

    with _stock_template(mode_names[0]) as first:
        stock_ncoef = int(first.sizes["coef_number"])
        ncoef = default_ncoef(band_set, stock_ncoef) if ncoef is None else int(ncoef)
        re_count = len(_densify_axis(_limited(first["refindex_real_sw"].values[0], max_re), refindex_subdivisions))
        im_count = len(_densify_axis(_limited(first["refindex_im_sw"].values[0], max_im), refindex_subdivisions))
    if ncoef < 2:
        raise ValueError("ncoef must be >= 2")
    if n_radius is None:
        n_radius = max(5 * ncoef, 50)
    if n_radius < ncoef:
        raise ValueError("n_radius must be >= ncoef")

    shape_sw = (len(sw_mid_values), len(mode_names), im_count, re_count, ncoef)
    shape_lw = (len(lw_mid_values), len(mode_names), im_count, re_count, ncoef)
    extpsw = np.zeros(shape_sw, dtype=np.float64)
    abspsw = np.zeros(shape_sw, dtype=np.float64)
    asmpsw = np.zeros(shape_sw, dtype=np.float64)
    extplw = np.zeros(shape_lw, dtype=np.float64)
    absplw = np.zeros(shape_lw, dtype=np.float64)
    asmplw = np.zeros(shape_lw, dtype=np.float64)
    refr_sw = np.zeros((len(sw_mid_values), len(mode_names), re_count), dtype=np.float64)
    refi_sw = np.zeros((len(sw_mid_values), len(mode_names), im_count), dtype=np.float64)
    refr_lw = np.zeros((len(lw_mid_values), len(mode_names), re_count), dtype=np.float64)
    refi_lw = np.zeros((len(lw_mid_values), len(mode_names), im_count), dtype=np.float64)
    sigmag = np.zeros(len(mode_names), dtype=np.float64)

    surface_radii = cheb_surface_radii_um(int(n_radius))
    x_radius = _normalize_log_surface_radius(surface_radii)
    fit_tasks: list[
        tuple[str, int, int, int, int, float, float, float, float, np.ndarray, np.ndarray, int, int]
    ] = []

    def store_fit(
        band_kind: str,
        iband: int,
        imode: int,
        iim: int,
        ire: int,
        ext: np.ndarray,
        absn: np.ndarray,
        asm: np.ndarray,
    ) -> None:
        if band_kind == "sw":
            extpsw[iband, imode, iim, ire, :] = ext
            abspsw[iband, imode, iim, ire, :] = absn
            asmpsw[iband, imode, iim, ire, :] = asm
        else:
            extplw[iband, imode, iim, ire, :] = ext
            absplw[iband, imode, iim, ire, :] = absn
            asmplw[iband, imode, iim, ire, :] = asm

    for imode, mode in enumerate(mode_names):
        with _stock_template(mode) as template:
            sigmag[imode] = float(template["sigmag"].values)
            for iband, source_iband in enumerate(source_sw_indices):
                re_axis = _densify_axis(_limited(template["refindex_real_sw"].values[source_iband], max_re), refindex_subdivisions)
                im_axis = _densify_axis(_limited(template["refindex_im_sw"].values[source_iband], max_im), refindex_subdivisions)
                refr_sw[iband, imode, :] = re_axis
                refi_sw[iband, imode, :] = im_axis
                for iim, n_imag in enumerate(im_axis):
                    for ire, n_real in enumerate(re_axis):
                        task = (
                            "sw",
                            iband,
                            imode,
                            iim,
                            ire,
                            float(sw_mid_values[iband]),
                            float(n_real),
                            float(n_imag),
                            sigmag[imode],
                            surface_radii,
                            x_radius,
                            ncoef,
                            n_quad,
                        )
                        if workers == 1:
                            store_fit(*_fit_lut_task(task))
                        else:
                            fit_tasks.append(task)
            for iband, source_iband in enumerate(source_lw_indices):
                re_axis = _densify_axis(_limited(template["refindex_real_lw"].values[source_iband], max_re), refindex_subdivisions)
                im_axis = _densify_axis(_limited(template["refindex_im_lw"].values[source_iband], max_im), refindex_subdivisions)
                refr_lw[iband, imode, :] = re_axis
                refi_lw[iband, imode, :] = im_axis
                for iim, n_imag in enumerate(im_axis):
                    for ire, n_real in enumerate(re_axis):
                        task = (
                            "lw",
                            iband,
                            imode,
                            iim,
                            ire,
                            float(lw_mid_values[iband]),
                            float(n_real),
                            float(n_imag),
                            sigmag[imode],
                            surface_radii,
                            x_radius,
                            ncoef,
                            n_quad,
                        )
                        if workers == 1:
                            store_fit(*_fit_lut_task(task))
                        else:
                            fit_tasks.append(task)

    if workers > 1:
        with ProcessPoolExecutor(max_workers=int(workers), mp_context=get_context("forkserver")) as executor:
            for result in executor.map(_fit_lut_task, fit_tasks):
                store_fit(*result)

    spectype_sw_real, spectype_sw_imag, spectype_lw_real, spectype_lw_imag, spectype_source_attr = (
        spectype_refindices(refindex_source)
    )
    dims_sw = ("sw_band", "mode", "refindex_im", "refindex_real", "coef_number")
    dims_lw = ("lw_band", "mode", "refindex_im", "refindex_real", "coef_number")
    ds = xr.Dataset(
        {
            "extpsw": (dims_sw, extpsw.astype("f8")),
            "abspsw": (dims_sw, abspsw.astype("f8")),
            "asmpsw": (dims_sw, asmpsw.astype("f8")),
            "extplw": (dims_lw, extplw.astype("f8")),
            "absplw": (dims_lw, absplw.astype("f8")),
            "asmplw": (dims_lw, asmplw.astype("f8")),
            "refindex_real_sw": (
                ("sw_band", "mode", "refindex_real"),
                refr_sw.astype("f8"),
            ),
            "refindex_im_sw": (
                ("sw_band", "mode", "refindex_im"),
                refi_sw.astype("f8"),
            ),
            "refindex_real_lw": (
                ("lw_band", "mode", "refindex_real"),
                refr_lw.astype("f8"),
            ),
            "refindex_im_lw": (
                ("lw_band", "mode", "refindex_im"),
                refi_lw.astype("f8"),
            ),
            "sigmag": (("mode",), sigmag.astype("f8")),
            "lfl_sw_edges_um": (
                ("lfl_sw_edge",),
                np.asarray(LFL_SW_EDGES_UM, dtype=np.float64),
            ),
            "lfl_lw_edges_um": (
                ("lfl_lw_edge",),
                np.asarray(LFL_LW_EDGES_UM, dtype=np.float64),
            ),
            "cheb_surface_radius_um": (("radius_sample",), surface_radii.astype("f8")),
            "refindex_real_spectype_sw": (
                ("spectype", "lfl_sw_band"),
                spectype_sw_real.astype("f8"),
            ),
            "refindex_im_spectype_sw": (
                ("spectype", "lfl_sw_band"),
                spectype_sw_imag.astype("f8"),
            ),
            "refindex_real_spectype_lw": (
                ("spectype", "lfl_lw_band"),
                spectype_lw_real.astype("f8"),
            ),
            "refindex_im_spectype_lw": (
                ("spectype", "lfl_lw_band"),
                spectype_lw_imag.astype("f8"),
            ),
        },
        coords={
            "sw_band": np.arange(1, len(sw_mid_values) + 1, dtype=np.int32),
            "lw_band": np.arange(1, len(lw_mid_values) + 1, dtype=np.int32),
            "mode": list(mode_names),
            "refindex_im": np.arange(1, im_count + 1, dtype=np.int32),
            "refindex_real": np.arange(1, re_count + 1, dtype=np.int32),
            "coef_number": np.arange(1, ncoef + 1, dtype=np.int32),
            "spectype": list(SPECTYPES),
            "lfl_sw_band": np.arange(1, len(LFL_SW_MIDPOINTS_UM) + 1, dtype=np.int32),
            "lfl_lw_band": np.arange(1, len(LFL_LW_MIDPOINTS_UM) + 1, dtype=np.int32),
            "sw_midpoint_um": (("sw_band",), sw_mid_values.astype("f8")),
            "lw_midpoint_um": (("lw_band",), lw_mid_values.astype("f8")),
        },
        attrs={
            "source": "CERES-SARB-CAM7 SP3 LFL LUT",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "table_version": "sp3v2_lfl_chebyshev_mie",
            "band_set": band_set,
            "mode_order": ",".join(mode_names),
            "cheb_radius_min_um": float(CHEB_RADIUS_MIN_UM),
            "cheb_radius_max_um": float(CHEB_RADIUS_MAX_UM),
            "cheb_radius_domain": "wet surface mode radius matching CAM modal_size_parameters",
            "cheb_radius_sampling": "first-kind Chebyshev nodes on normalized log surface radius",
            "cheb_first_coefficient": "stored double; CAM evaluates 0.5*c1 + sum(c_i*T_i)",
            "normalization": "raw specific optics = per-particle cross section / (mean wet volume * rhoh2o)",
            "rhoh2o_kg_m3": float(RHO_H2O_KG_M3),
            "mie_source": (
                f"{Path(__file__).name}:_mie_curve_um2/_integrate_curve_specific_optics "
                f"using {MAM_LFL_ROOT / 'mie_sphere.py'}:mie_cross_sections_um2"
            ),
            "spectype_refindex_source": spectype_source_attr,
            "mam_lfl_git_commit": _git_value(MAM_LFL_ROOT, ["rev-parse", "HEAD"]),
            "physprop_paths_json": json.dumps(
                {mode: str(PHYSPROP_PATHS[mode]) for mode in mode_names},
                sort_keys=True,
            ),
            "source_sw_band_indices_json": json.dumps(source_sw_indices.tolist()),
            "source_lw_band_indices_json": json.dumps(source_lw_indices.tolist()),
            "refindex_source": refindex_source,
            "n_radius": int(n_radius),
            "ncoef": int(ncoef),
            "mie_radius_grid_size": int(n_quad),
            "workers": int(workers),
            "refindex_axis_subdivisions": int(refindex_subdivisions),
            "x_cap": float(X_CAP),
            "n_sigma": float(N_SIGMA),
        },
    )
    return ds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--bands", choices=("lfl", "cam"), default="lfl")
    parser.add_argument("--refindex-source", choices=("mam-lfl", "cam"), default="mam-lfl")
    parser.add_argument("--retarget-from", type=Path, help="reuse an existing LUT and replace only spectype refindices")
    parser.add_argument("--modes", nargs="+", default=list(MODE_ORDER))
    parser.add_argument("--n-radius", type=int)
    parser.add_argument("--n-quad", type=int, default=DEFAULT_MIE_RADIUS_GRID_SIZE)
    parser.add_argument("--n-coef", type=int)
    parser.add_argument("--max-sw-bands", type=int)
    parser.add_argument("--max-lw-bands", type=int)
    parser.add_argument("--max-re", type=int)
    parser.add_argument("--max-im", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--refindex-subdivisions",
        type=int,
        default=1,
        help="split each stock refractive-index axis interval into this many linear subintervals",
    )
    parser.add_argument("--calibration-report", type=Path)
    parser.add_argument("--refindex-report", type=Path)
    args = parser.parse_args(argv)

    if args.retarget_from is not None:
        with xr.open_dataset(args.retarget_from) as base:
            ds = retarget_lut_refindex(base.load(), args.refindex_source)
    else:
        ds = build_lut_dataset(
            modes=tuple(args.modes),
            band_set=args.bands,
            refindex_source=args.refindex_source,
            n_radius=args.n_radius,
            n_quad=args.n_quad,
            ncoef=args.n_coef,
            max_sw_bands=args.max_sw_bands,
            max_lw_bands=args.max_lw_bands,
            max_re=args.max_re,
            max_im=args.max_im,
            workers=args.workers,
            refindex_subdivisions=args.refindex_subdivisions,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(args.output)
    print(f"wrote {args.output}")
    if args.calibration_report is not None:
        if args.bands != "cam":
            raise ValueError("--calibration-report requires --bands cam")
        report = cam_calibration_report(ds)
        args.calibration_report.parent.mkdir(parents=True, exist_ok=True)
        with args.calibration_report.open("w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
        print(f"wrote {args.calibration_report}")
    if args.refindex_report is not None:
        report = refindex_comparison_report()
        args.refindex_report.parent.mkdir(parents=True, exist_ok=True)
        with args.refindex_report.open("w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
        print(f"wrote {args.refindex_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
