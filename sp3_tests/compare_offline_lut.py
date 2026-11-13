#!/usr/bin/env python3
"""Offline reconstruction check for SP3 LFL-native LUT aerosol optics."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

from sp3_optics.lfl_bands import LFL_LW_MIDPOINTS_UM
from sp3_optics.lfl_bands import LFL_SW_MIDPOINTS_UM
from sp3_tests.compare_sp3_methods import ASM
from sp3_tests.compare_sp3_methods import COL
from sp3_tests.compare_sp3_methods import EXT
from sp3_tests.compare_sp3_methods import SCA
from sp3_tests.compare_sp3_methods import band_files_by_stamp
from sp3_tests.compare_sp3_methods import column_asymmetry
from sp3_tests.compare_sp3_methods import column_ssa
from sp3_tests.compare_sp3_methods import h0_values_for_stamp
from sp3_tests.compare_sp3_methods import normalize_band

ROOT = Path(__file__).resolve().parents[1]
MAM_LFL_ROOT = ROOT.parent / "CERES-SARB-MAM-LFL"
if MAM_LFL_ROOT.is_dir() and str(MAM_LFL_ROOT) not in sys.path:
    sys.path.insert(0, str(MAM_LFL_ROOT))
try:
    from mode_physics import lookup_mode_optics as mam_lfl_lookup_mode_optics
except ModuleNotFoundError:  # pragma: no cover - only hit when companion repo is absent
    mam_lfl_lookup_mode_optics = None
try:
    from mie_lognormal import mode_averaged_cross_sections_um2 as mam_lfl_mode_averaged_cross_sections_um2
except ModuleNotFoundError:  # pragma: no cover - only hit when companion repo is absent
    mam_lfl_mode_averaged_cross_sections_um2 = None
try:
    from mie_sphere import mie_cross_sections_um2 as mam_lfl_mie_cross_sections_um2
except ModuleNotFoundError:  # pragma: no cover - only hit when companion repo is absent
    mam_lfl_mie_cross_sections_um2 = None

RADMIN_M = 0.01e-6
RADMAX_M = 25.0e-6
XRMIN = np.log(RADMIN_M)
XRMAX = np.log(RADMAX_M)
DIRECT_MIE_X_CAP = 200.0
RHO_H2O_KG_M3 = 1000.0
STANDARD_GRAVITY = 9.80665
DEFAULT_FINE_LUT_DIR = Path("/glade/work/fillmore/Data/Optics/SARB")
DEFAULT_FINE_LUT_SUFFIX = "c000003.v2"
REFERENCE_METHOD_CAM_LUT = "cam-lut"
REFERENCE_METHOD_MAM_LFL_FINE = "mam-lfl-fine-lut"
REFERENCE_METHOD_MAM_LFL_DIRECT_MIE = "mam-lfl-direct-mie-sampled"
REFERENCE_METHODS = (REFERENCE_METHOD_CAM_LUT, REFERENCE_METHOD_MAM_LFL_FINE, REFERENCE_METHOD_MAM_LFL_DIRECT_MIE)
DIRECT_NORMALIZATION_WET_VOLUME = "wet-volume"
DIRECT_NORMALIZATION_NUMBER = "number"
DIRECT_NORMALIZATIONS = (DIRECT_NORMALIZATION_WET_VOLUME, DIRECT_NORMALIZATION_NUMBER)

SPECIES_DENSITY_KG_M3 = {
    "BC": 1700.0,
    "POM": 1000.0,
    "SOA": 1000.0,
    "SU": 1770.0,
    "DU": 2600.0,
    "SS": 1900.0,
}
MODE_SPECIES = {
    "a1": (("so4_a1", "SU"), ("pom_a1", "POM"), ("soa_a1", "SOA"), ("bc_a1", "BC"), ("dst_a1", "DU"), ("ncl_a1", "SS")),
    "a2": (("so4_a2", "SU"), ("soa_a2", "SOA"), ("ncl_a2", "SS"), ("dst_a2", "DU")),
    "a3": (("dst_a3", "DU"), ("ncl_a3", "SS"), ("so4_a3", "SU")),
    "a4": (("pom_a4", "POM"), ("bc_a4", "BC")),
}
DEFAULT_BANDS = tuple(f"SW{i:02d}" for i in range(1, 15)) + tuple(f"LW{i:02d}" for i in range(1, 13))


@dataclass(frozen=True)
class OfflineBandMetric:
    band: str
    stamp: str
    count: int
    offline_column_mean: float
    sp3_column_mean: float
    median_ext_ratio: float
    median_abs_ext_relative_difference: float
    median_abs_ssa_difference: float
    median_abs_asymmetry_difference: float
    max_abs_ssa_difference: float
    max_abs_asymmetry_difference: float
    ssa_count: int
    asymmetry_count: int
    passed: bool
    sample_count: int = 0
    sample_indices_json: str = ""
    direct_normalization: str = ""


def cheb_basis(surface_radius_m: np.ndarray | float, ncoef: int) -> np.ndarray:
    radius = np.asarray(surface_radius_m, dtype=np.float64)
    xrad = np.log(np.maximum(radius, RADMIN_M))
    xrad = np.clip(xrad, XRMIN, XRMAX)
    xrad = (2.0 * xrad - XRMAX - XRMIN) / (XRMAX - XRMIN)
    basis = np.empty(radius.shape + (int(ncoef),), dtype=np.float64)
    if ncoef <= 0:
        return basis
    basis[..., 0] = 1.0
    if ncoef == 1:
        return basis
    basis[..., 1] = xrad
    for icoef in range(2, int(ncoef)):
        basis[..., icoef] = 2.0 * xrad * basis[..., icoef - 1] - basis[..., icoef - 2]
    return basis


def _bracket_axis(axis: np.ndarray, target: np.ndarray | float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(axis, dtype=np.float64)
    wanted = np.asarray(target, dtype=np.float64)
    if values.size == 1:
        zeros = np.zeros_like(wanted, dtype=np.intp)
        return zeros, zeros, np.zeros_like(wanted, dtype=np.float64)
    idx1 = np.searchsorted(values, wanted, side="right")
    idx1 = np.clip(idx1, 1, values.size - 1)
    idx0 = idx1 - 1
    below = wanted <= values[0]
    above = wanted >= values[-1]
    idx0 = np.where(below, 0, np.where(above, values.size - 1, idx0)).astype(np.intp)
    idx1 = np.where(below, 0, np.where(above, values.size - 1, idx1)).astype(np.intp)
    denom = np.maximum(values[idx1] - values[idx0], 1.0e-60)
    weight = np.where(idx0 == idx1, 0.0, (wanted - values[idx0]) / denom)
    return idx0, idx1, weight


def eval_coeff_table(
    table: np.ndarray,
    basis: np.ndarray,
    re_axis: np.ndarray,
    im_axis: np.ndarray,
    ref_re: np.ndarray | float,
    ref_im: np.ndarray | float,
    *,
    log_ext: bool = False,
) -> np.ndarray:
    coeff_table = np.asarray(table, dtype=np.float64)
    if coeff_table.ndim != 3:
        raise ValueError(f"coefficient table must have shape (refindex_im, refindex_real, coef), got {coeff_table.shape}")
    ire0, ire1, wre = _bracket_axis(re_axis, ref_re)
    iim0, iim1, wim = _bracket_axis(im_axis, np.abs(ref_im))
    c00 = coeff_table[iim0, ire0, :]
    c10 = coeff_table[iim0, ire1, :]
    c01 = coeff_table[iim1, ire0, :]
    c11 = coeff_table[iim1, ire1, :]
    coeff = (1.0 - wim)[..., None] * ((1.0 - wre)[..., None] * c00 + wre[..., None] * c10) + wim[
        ..., None
    ] * ((1.0 - wre)[..., None] * c01 + wre[..., None] * c11)
    coeff = coeff.copy()
    coeff[..., 0] *= 0.5
    value = np.sum(coeff * np.asarray(basis, dtype=np.float64), axis=-1)
    return np.exp(value) if log_ext else value


def _lut_mode_names(lut: xr.Dataset) -> list[str]:
    return [str(value) for value in lut["mode"].values.tolist()]


def _h0_field(h0: xr.Dataset, name: str, stamp: str | None) -> np.ndarray:
    if name not in h0:
        raise KeyError(f"h0 file is missing required variable {name}")
    return np.asarray(h0_values_for_stamp(h0, name, stamp), dtype=np.float64)


def _layer_mass_kg_m2(h0: xr.Dataset, stamp: str | None) -> np.ndarray:
    for name in ("rad_pdeldry", "PDELDRY"):
        if name in h0:
            return _h0_field(h0, name, stamp) / STANDARD_GRAVITY
    raise KeyError("h0 file must contain rad_pdeldry or PDELDRY for layer dry mass per unit area")


def _band_parts(band: str) -> tuple[str, int, str, str, str, str, str, str, str]:
    normalized = normalize_band(band)
    index = int(normalized[2:]) - 1
    if normalized.startswith("SW"):
        return normalized, index, "sw_band", "lfl_sw_band", "extpsw", "abspsw", "asmpsw", "sw", "sw"
    return normalized, index, "lw_band", "lfl_lw_band", "extplw", "absplw", "asmplw", "lw", "lw"


def _fine_lut_path(fine_lut_dir: Path, mode: str, band: str, *, suffix: str = DEFAULT_FINE_LUT_SUFFIX) -> Path:
    normalized = normalize_band(band)
    mode_number = int(mode[1:])
    band_token = f"{normalized[:2].lower()}{int(normalized[2:])}"
    return Path(fine_lut_dir) / f"mam4_mode{mode_number}_{band_token}_larc_{suffix}.nc"


def _band_wavelength_um(band: str, band_index: int) -> float:
    normalized = normalize_band(band)
    if normalized.startswith("SW"):
        return float(LFL_SW_MIDPOINTS_UM[band_index])
    return float(LFL_LW_MIDPOINTS_UM[band_index])


def _mean_wet_volume_m3(surface_radius_um: float, sigma_g: float) -> float:
    log_sigma = np.log(float(sigma_g))
    number_median_um = float(surface_radius_um) / np.exp(2.0 * log_sigma**2)
    return float(
        (4.0 / 3.0)
        * np.pi
        * (number_median_um * 1.0e-6) ** 3
        * np.exp(4.5 * log_sigma**2)
    )


def _select_sample_columns(sp3: xr.Dataset, *, sample_columns: int, min_tau: float) -> list[tuple[int, int]]:
    if sample_columns <= 0:
        raise ValueError("direct_sample_columns must be positive for direct-Mie sampled comparison")
    if COL not in sp3:
        raise KeyError(f"SP3 file is missing required variable {COL}")
    column = sp3[COL]
    if column.ndim != 2:
        raise ValueError(f"{COL} must be two-dimensional for sampled direct-Mie comparison, got {column.dims}")
    values = np.asarray(column, dtype=np.float64)
    valid = np.isfinite(values) & (values > float(min_tau))
    if not np.any(valid):
        raise ValueError(f"no finite SP3 column optical depth cells > {min_tau} for direct-Mie sampling")
    flat_indices = np.flatnonzero(valid.ravel())
    order = np.argsort(values.ravel()[flat_indices], kind="mergesort")
    flat_indices = flat_indices[order]
    if sample_columns < flat_indices.size:
        positions = np.floor(np.linspace(0, flat_indices.size - 1, int(sample_columns))).astype(np.intp)
        flat_indices = flat_indices[positions]
    rows, cols = np.unravel_index(flat_indices, values.shape)
    return [(int(row), int(col)) for row, col in zip(rows, cols)]


def _sample_layer_array(values: np.ndarray, samples: list[tuple[int, int]], *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 3:
        raise ValueError(f"{name} must have shape (lev, lat, lon), got {array.shape}")
    rows = np.asarray([sample[0] for sample in samples], dtype=np.intp)
    cols = np.asarray([sample[1] for sample in samples], dtype=np.intp)
    return array[:, rows, cols]


def _sample_sp3_columns(sp3: xr.Dataset, samples: list[tuple[int, int]]) -> xr.Dataset:
    column = sp3[COL]
    dim0, dim1 = column.dims
    rows = xr.DataArray(np.asarray([sample[0] for sample in samples], dtype=np.intp), dims="sample")
    cols = xr.DataArray(np.asarray([sample[1] for sample in samples], dtype=np.intp), dims="sample")
    data_vars = {}
    for name in (EXT, SCA, ASM, COL, "DELP"):
        if name not in sp3:
            continue
        data = sp3[name]
        if dim0 not in data.dims or dim1 not in data.dims:
            continue
        data_vars[name] = data.isel({dim0: rows, dim1: cols}).load()
    sampled = xr.Dataset(data_vars, attrs=dict(sp3.attrs))
    sampled = sampled.assign_coords(sample=np.arange(len(samples), dtype=np.int32))
    for dim, indexer in ((dim0, rows), (dim1, cols)):
        if dim in sp3.coords:
            sampled = sampled.assign_coords({dim: ("sample", np.asarray(sp3[dim].isel({dim: indexer}), dtype=np.float64))})
    sampled.attrs["sample_indices"] = json.dumps(samples)
    return sampled


def _mode_state(h0: xr.Dataset, mode: str, stamp: str | None, template: np.ndarray) -> tuple[np.ndarray, list[tuple[str, np.ndarray]], np.ndarray, np.ndarray]:
    species_volumes: list[tuple[str, np.ndarray]] = []
    dry_volume = np.zeros_like(template, dtype=np.float64)
    mode_species = MODE_SPECIES.get(mode)
    if mode_species is None:
        raise KeyError(f"unsupported aerosol mode {mode!r}")
    missing = [varname for varname, _spectype in mode_species if varname not in h0]
    if missing:
        raise KeyError(f"h0 file is missing required aerosol species for {mode}: {', '.join(missing)}")
    for varname, spectype in mode_species:
        if varname not in h0:
            continue
        volume = _h0_field(h0, varname, stamp) / SPECIES_DENSITY_KG_M3[spectype]
        species_volumes.append((spectype, volume))
        dry_volume += volume
    if not species_volumes:
        return dry_volume, [], np.zeros_like(template), np.zeros_like(template)
    mode_number = int(mode[1:])
    dgnumwet = _h0_field(h0, f"rad_dgnumwet_{mode_number}", stamp)
    qaerwat = _h0_field(h0, f"rad_qaerwat_{mode_number}", stamp)
    return dry_volume, species_volumes, dgnumwet, qaerwat


def _lognormal_quadrature(median_radius_um: float, sigma_g: float, n_quad: int, n_sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    log_sigma = np.log(float(sigma_g))
    lo = np.log(float(median_radius_um)) - float(n_sigma) * log_sigma
    hi = np.log(float(median_radius_um)) + float(n_sigma) * log_sigma
    ln_radius = np.linspace(lo, hi, int(n_quad), dtype=np.float64)
    radius = np.exp(ln_radius)
    weight = np.exp(-((ln_radius - np.log(float(median_radius_um))) ** 2) / (2.0 * log_sigma**2))
    weight /= log_sigma * np.sqrt(2.0 * np.pi)
    return ln_radius, radius, weight


def _mode_averaged_cross_sections_um2_capped(
    n_real: float,
    n_imag: float,
    *,
    median_radius_um: float,
    sigma_g: float,
    wavelength_um: float,
    n_quad: int,
    n_sigma: float,
) -> dict[str, float]:
    if mam_lfl_mie_cross_sections_um2 is None:
        raise RuntimeError(f"MAM-LFL mie_sphere.py not available at {MAM_LFL_ROOT}")
    ln_radius, radius, weight = _lognormal_quadrature(median_radius_um, sigma_g, n_quad, n_sigma)
    ext = np.empty_like(radius)
    sca = np.empty_like(radius)
    absn = np.empty_like(radius)
    gsca = np.empty_like(radius)
    cap: tuple[float, float, float] | None = None
    for index, radius_um in enumerate(radius):
        area = np.pi * float(radius_um) ** 2
        x_size = 2.0 * np.pi * float(radius_um) / float(wavelength_um)
        if x_size <= DIRECT_MIE_X_CAP:
            cross = mam_lfl_mie_cross_sections_um2(n_real, abs(n_imag), float(radius_um), wavelength_um)
            cap = (
                float(cross["ext"]) / area,
                float(cross["sca"]) / area,
                float(cross["asymmetry"]),
            )
        elif cap is None:
            cap_radius = float(wavelength_um) * DIRECT_MIE_X_CAP / (2.0 * np.pi)
            cap_area = np.pi * cap_radius**2
            cross = mam_lfl_mie_cross_sections_um2(n_real, abs(n_imag), cap_radius, wavelength_um)
            cap = (
                float(cross["ext"]) / cap_area,
                float(cross["sca"]) / cap_area,
                float(cross["asymmetry"]),
            )
        q_ext, q_sca, asymmetry = cap
        ext[index] = q_ext * area
        sca[index] = q_sca * area
        absn[index] = max(ext[index] - sca[index], 0.0)
        gsca[index] = asymmetry * sca[index]
    norm = float(np.trapezoid(weight, ln_radius))
    sca_int = float(np.trapezoid(sca * weight, ln_radius))
    return {
        "ext": float(np.trapezoid(ext * weight, ln_radius) / norm),
        "sca": sca_int / norm,
        "abs": float(np.trapezoid(absn * weight, ln_radius) / norm),
        "asymmetry": float(np.trapezoid(gsca * weight, ln_radius) / sca_int) if sca_int > 0.0 else 0.0,
        "number_norm": norm,
        "n_quad": int(n_quad),
    }


def _mixed_refindex_from_lut(
    lut: xr.Dataset,
    species_volumes: list[tuple[str, np.ndarray]],
    watervol: np.ndarray,
    wetvol: np.ndarray,
    *,
    lfl_band_dim: str,
    band_index: int,
    spectype_suffix: str,
) -> tuple[np.ndarray, np.ndarray]:
    ref_re = watervol * float(
        lut[f"refindex_real_spectype_{spectype_suffix}"].sel(spectype="WAT").isel({lfl_band_dim: band_index}).values
    )
    ref_im = watervol * abs(
        float(lut[f"refindex_im_spectype_{spectype_suffix}"].sel(spectype="WAT").isel({lfl_band_dim: band_index}).values)
    )
    for spectype, volume in species_volumes:
        ref_re += volume * float(
            lut[f"refindex_real_spectype_{spectype_suffix}"].sel(spectype=spectype).isel({lfl_band_dim: band_index}).values
        )
        ref_im += volume * abs(
            float(lut[f"refindex_im_spectype_{spectype_suffix}"].sel(spectype=spectype).isel({lfl_band_dim: band_index}).values)
        )
    ref_re = np.divide(ref_re, wetvol, out=np.zeros_like(ref_re), where=wetvol > 0.0)
    ref_im = np.abs(np.divide(ref_im, wetvol, out=np.zeros_like(ref_im), where=wetvol > 0.0))
    return ref_re, ref_im


def reconstruct_band(lut: xr.Dataset, h0: xr.Dataset, band: str, *, stamp: str | None) -> xr.Dataset:
    normalized, band_index, band_dim, lfl_band_dim, ext_name, abs_name, asm_name, axis_suffix, spectype_suffix = _band_parts(band)
    mass = _layer_mass_kg_m2(h0, stamp)
    ext = np.zeros_like(mass, dtype=np.float64)
    sca = np.zeros_like(mass, dtype=np.float64)
    scag = np.zeros_like(mass, dtype=np.float64)
    modes = _lut_mode_names(lut)

    for imode, mode in enumerate(modes):
        dryvol, species_volumes, dgnumwet, qaerwat = _mode_state(h0, mode, stamp, mass)
        if not species_volumes:
            continue
        watervol = np.maximum(qaerwat / RHO_H2O_KG_M3, 0.0)
        wetvol = dryvol + watervol
        active = (wetvol > 0.0) & (mass > 0.0)
        if not np.any(active):
            continue

        sigma_g = float(lut["sigmag"].isel(mode=imode).values)
        surface_radius = 0.5 * dgnumwet * np.exp(2.0 * np.log(sigma_g) ** 2)
        basis = cheb_basis(surface_radius, int(lut.sizes["coef_number"]))
        ref_re, ref_im = _mixed_refindex_from_lut(
            lut,
            species_volumes,
            watervol,
            wetvol,
            lfl_band_dim=lfl_band_dim,
            band_index=band_index,
            spectype_suffix=spectype_suffix,
        )

        re_axis = lut[f"refindex_real_{axis_suffix}"].isel({band_dim: band_index, "mode": imode}).values
        im_axis = lut[f"refindex_im_{axis_suffix}"].isel({band_dim: band_index, "mode": imode}).values
        selector = {band_dim: band_index, "mode": imode}
        raw_ext = eval_coeff_table(
            lut[ext_name].isel(selector).transpose("refindex_im", "refindex_real", "coef_number").values,
            basis,
            re_axis,
            im_axis,
            ref_re,
            ref_im,
            log_ext=True,
        )
        raw_abs = eval_coeff_table(
            lut[abs_name].isel(selector).transpose("refindex_im", "refindex_real", "coef_number").values,
            basis,
            re_axis,
            im_axis,
            ref_re,
            ref_im,
        )
        asym = eval_coeff_table(
            lut[asm_name].isel(selector).transpose("refindex_im", "refindex_real", "coef_number").values,
            basis,
            re_axis,
            im_axis,
            ref_re,
            ref_im,
        )
        layer_ext = raw_ext * wetvol * RHO_H2O_KG_M3 * mass
        layer_abs = raw_abs * wetvol * RHO_H2O_KG_M3 * mass
        ext_out = np.maximum(layer_ext, 0.0)
        abs_out = np.maximum(0.0, np.minimum(layer_abs, ext_out))
        sca_out = np.maximum(0.0, ext_out - abs_out)
        ext += np.where(active, ext_out, 0.0)
        sca += np.where(active, sca_out, 0.0)
        scag += np.where(active, sca_out * np.clip(asym, -1.0, 1.0), 0.0)

    asymmetry = np.divide(scag, sca, out=np.zeros_like(scag), where=sca > 1.0e-12)
    coords = {name: h0[name].values for name in ("lev", "lat", "lon") if name in h0.coords}
    return xr.Dataset(
        {
            EXT: (("lev", "lat", "lon"), ext),
            SCA: (("lev", "lat", "lon"), sca),
            ASM: (("lev", "lat", "lon"), asymmetry),
            COL: (("lat", "lon"), np.nansum(ext, axis=0)),
        },
        coords=coords,
        attrs={"method": "offline_lut", "band": normalized},
    )


def reconstruct_band_mam_lfl_fine(
    lut: xr.Dataset,
    h0: xr.Dataset,
    band: str,
    *,
    stamp: str | None,
    fine_lut_dir: Path = DEFAULT_FINE_LUT_DIR,
    fine_lut_suffix: str = DEFAULT_FINE_LUT_SUFFIX,
) -> xr.Dataset:
    if mam_lfl_lookup_mode_optics is None:
        raise RuntimeError(f"MAM-LFL mode_physics.py not available at {MAM_LFL_ROOT}")
    normalized, band_index, _band_dim, lfl_band_dim, _ext_name, _abs_name, _asm_name, _axis_suffix, spectype_suffix = _band_parts(band)
    mass = _layer_mass_kg_m2(h0, stamp)
    ext = np.zeros_like(mass, dtype=np.float64)
    sca = np.zeros_like(mass, dtype=np.float64)
    scag = np.zeros_like(mass, dtype=np.float64)

    for mode in _lut_mode_names(lut):
        dryvol, species_volumes, dgnumwet, qaerwat = _mode_state(h0, mode, stamp, mass)
        if not species_volumes:
            continue
        mode_number = int(mode[1:])
        number = _h0_field(h0, f"num_{mode}", stamp)
        watervol = np.maximum(qaerwat / RHO_H2O_KG_M3, 0.0)
        wetvol = dryvol + watervol
        active = (wetvol > 0.0) & (number > 0.0) & (mass > 0.0)
        if not np.any(active):
            continue
        ref_re, ref_im = _mixed_refindex_from_lut(
            lut,
            species_volumes,
            watervol,
            wetvol,
            lfl_band_dim=lfl_band_dim,
            band_index=band_index,
            spectype_suffix=spectype_suffix,
        )
        wet_median_radius_um = np.maximum(0.5 * dgnumwet * 1.0e6, 0.0)
        table_path = _fine_lut_path(fine_lut_dir, mode, normalized, suffix=fine_lut_suffix)
        with xr.open_dataset(table_path) as fine_table:
            cross_ext, cross_abs, asym = mam_lfl_lookup_mode_optics(ref_re, ref_im, wet_median_radius_um, fine_table)
        layer_ext = np.maximum(cross_ext, 0.0) * 1.0e-12 * number * mass
        layer_abs = np.maximum(0.0, np.minimum(cross_abs * 1.0e-12 * number * mass, layer_ext))
        sca_out = np.maximum(0.0, layer_ext - layer_abs)
        ext += np.where(active, layer_ext, 0.0)
        sca += np.where(active, sca_out, 0.0)
        scag += np.where(active, sca_out * np.clip(asym, -1.0, 1.0), 0.0)

    asymmetry = np.divide(scag, sca, out=np.zeros_like(scag), where=sca > 1.0e-12)
    coords = {name: h0[name].values for name in ("lev", "lat", "lon") if name in h0.coords}
    return xr.Dataset(
        {
            EXT: (("lev", "lat", "lon"), ext),
            SCA: (("lev", "lat", "lon"), sca),
            ASM: (("lev", "lat", "lon"), asymmetry),
            COL: (("lat", "lon"), np.nansum(ext, axis=0)),
        },
        coords=coords,
        attrs={"method": REFERENCE_METHOD_MAM_LFL_FINE, "band": normalized},
    )


def reconstruct_band_mam_lfl_direct_mie_sampled(
    lut: xr.Dataset,
    h0: xr.Dataset,
    sp3: xr.Dataset,
    band: str,
    *,
    stamp: str | None,
    sample_columns: int,
    min_tau: float,
    n_quad: int = 120,
    n_sigma: float = 5.0,
    normalization: str = DIRECT_NORMALIZATION_WET_VOLUME,
) -> tuple[xr.Dataset, xr.Dataset]:
    if mam_lfl_mie_cross_sections_um2 is None:
        raise RuntimeError(f"MAM-LFL mie_sphere.py not available at {MAM_LFL_ROOT}")
    if normalization not in DIRECT_NORMALIZATIONS:
        raise ValueError(f"direct normalization must be one of {DIRECT_NORMALIZATIONS}, got {normalization!r}")
    samples = _select_sample_columns(sp3, sample_columns=sample_columns, min_tau=min_tau)
    sampled_sp3 = _sample_sp3_columns(sp3, samples)
    normalized, band_index, _band_dim, lfl_band_dim, _ext_name, _abs_name, _asm_name, _axis_suffix, spectype_suffix = _band_parts(band)
    wavelength_um = _band_wavelength_um(normalized, band_index)
    mass_full = _layer_mass_kg_m2(h0, stamp)
    mass = _sample_layer_array(mass_full, samples, name="layer dry mass")
    ext = np.zeros_like(mass, dtype=np.float64)
    sca = np.zeros_like(mass, dtype=np.float64)
    scag = np.zeros_like(mass, dtype=np.float64)

    for imode, mode in enumerate(_lut_mode_names(lut)):
        dryvol, species_volumes, dgnumwet, qaerwat = _mode_state(h0, mode, stamp, mass_full)
        if not species_volumes:
            continue
        number = None
        if normalization == DIRECT_NORMALIZATION_NUMBER:
            number = _sample_layer_array(_h0_field(h0, f"num_{mode}", stamp), samples, name=f"num_{mode}")
        watervol = np.maximum(qaerwat / RHO_H2O_KG_M3, 0.0)
        wetvol = dryvol + watervol
        ref_re_full, ref_im_full = _mixed_refindex_from_lut(
            lut,
            species_volumes,
            watervol,
            wetvol,
            lfl_band_dim=lfl_band_dim,
            band_index=band_index,
            spectype_suffix=spectype_suffix,
        )
        ref_re = _sample_layer_array(ref_re_full, samples, name=f"{mode} mixed refractive-index real")
        ref_im = _sample_layer_array(ref_im_full, samples, name=f"{mode} mixed refractive-index imaginary")
        wet_radius_um = _sample_layer_array(np.maximum(0.5 * dgnumwet * 1.0e6, 0.0), samples, name=f"{mode} wet radius")
        wetvol_sampled = _sample_layer_array(wetvol, samples, name=f"{mode} wet volume")
        sigma_g = float(lut["sigmag"].isel(mode=imode).values)
        active = (
            (wetvol_sampled > 0.0)
            & (mass > 0.0)
            & (wet_radius_um > 0.0)
            & np.isfinite(ref_re)
            & np.isfinite(ref_im)
        )
        if number is not None:
            active &= number > 0.0
        if not np.any(active):
            continue

        for lev_index, sample_index in zip(*np.nonzero(active)):
            cross = _mode_averaged_cross_sections_um2_capped(
                float(ref_re[lev_index, sample_index]),
                float(abs(ref_im[lev_index, sample_index])),
                median_radius_um=float(wet_radius_um[lev_index, sample_index]),
                sigma_g=sigma_g,
                wavelength_um=wavelength_um,
                n_quad=int(n_quad),
                n_sigma=float(n_sigma),
            )
            if normalization == DIRECT_NORMALIZATION_NUMBER:
                if number is None:
                    raise AssertionError("number normalization requires num_a* fields")
                scale = 1.0e-12 * float(number[lev_index, sample_index]) * float(mass[lev_index, sample_index])
                layer_ext = max(float(cross["ext"]), 0.0) * scale
                layer_abs = min(max(float(cross["abs"]), 0.0) * scale, layer_ext)
            else:
                surface_radius_um = float(wet_radius_um[lev_index, sample_index]) * np.exp(2.0 * np.log(sigma_g) ** 2)
                mean_volume = _mean_wet_volume_m3(surface_radius_um, sigma_g)
                scale = (
                    float(wetvol_sampled[lev_index, sample_index])
                    * RHO_H2O_KG_M3
                    * float(mass[lev_index, sample_index])
                )
                layer_ext = max(float(cross["ext"]), 0.0) * 1.0e-12 / (mean_volume * RHO_H2O_KG_M3) * scale
                layer_abs = min(
                    max(float(cross["abs"]), 0.0) * 1.0e-12 / (mean_volume * RHO_H2O_KG_M3) * scale,
                    layer_ext,
                )
            sca_out = max(0.0, layer_ext - layer_abs)
            ext[lev_index, sample_index] += layer_ext
            sca[lev_index, sample_index] += sca_out
            scag[lev_index, sample_index] += sca_out * float(np.clip(cross["asymmetry"], -1.0, 1.0))

    asymmetry = np.divide(scag, sca, out=np.zeros_like(scag), where=sca > 1.0e-12)
    coords: dict[str, np.ndarray | tuple[str, np.ndarray]] = {"sample": np.arange(len(samples), dtype=np.int32)}
    if "lev" in h0.coords:
        coords["lev"] = h0["lev"].values
    else:
        coords["lev"] = np.arange(ext.shape[0], dtype=np.int32)
    for name in sampled_sp3.coords:
        if name != "sample" and sampled_sp3[name].dims == ("sample",):
            coords[name] = ("sample", np.asarray(sampled_sp3[name].values))
    offline = xr.Dataset(
        {
            EXT: (("lev", "sample"), ext),
            SCA: (("lev", "sample"), sca),
            ASM: (("lev", "sample"), asymmetry),
            COL: (("sample",), np.nansum(ext, axis=0)),
        },
        coords=coords,
        attrs={
            "method": REFERENCE_METHOD_MAM_LFL_DIRECT_MIE,
            "band": normalized,
            "sample_count": len(samples),
            "sample_indices": json.dumps(samples),
            "direct_n_quad": int(n_quad),
            "direct_n_sigma": float(n_sigma),
            "direct_x_cap": float(DIRECT_MIE_X_CAP),
            "direct_normalization": normalization,
        },
    )
    return offline, sampled_sp3


def _load_sp3_band(sp3_dir: Path, band: str, stamp: str) -> xr.Dataset:
    files = band_files_by_stamp(sp3_dir, band)
    if stamp not in files:
        raise FileNotFoundError(f"{sp3_dir} has no {band} file for stamp {stamp}")
    return xr.open_dataset(files[stamp]).load()


def _metric_for_band(
    offline: xr.Dataset,
    sp3: xr.Dataset,
    band: str,
    stamp: str,
    *,
    min_tau: float,
    min_scattering_tau: float,
    ext_ratio_tolerance: float,
    ssa_tolerance: float,
    asymmetry_tolerance: float,
) -> OfflineBandMetric:
    offline_col = np.asarray(offline[COL], dtype=np.float64)
    sp3_col = np.asarray(sp3[COL], dtype=np.float64)
    mask = np.isfinite(offline_col) & np.isfinite(sp3_col) & (sp3_col > float(min_tau))
    sample_count = int(offline.attrs.get("sample_count", 0))
    if sample_count and int(np.count_nonzero(mask)) != sample_count:
        raise ValueError(
            f"{band}: sampled direct-MIE columns lost during finite/min_tau filtering "
            f"({int(np.count_nonzero(mask))} of {sample_count})"
        )
    if not np.any(mask):
        raise ValueError(f"{band}: no finite cells with SP3 column optical depth > {min_tau}")
    ratio = offline_col[mask] / sp3_col[mask]
    rel = np.abs(offline_col[mask] - sp3_col[mask]) / np.abs(sp3_col[mask])
    offline_ssa = column_ssa(offline)
    sp3_ssa = column_ssa(sp3)
    offline_g = column_asymmetry(offline)
    sp3_g = column_asymmetry(sp3)
    ssa_diff_all = np.abs(offline_ssa - sp3_ssa)
    offline_sca_col = np.nansum(np.asarray(offline[SCA], dtype=np.float64), axis=0)
    sp3_sca_col = np.nansum(np.asarray(sp3[SCA], dtype=np.float64), axis=0)
    sca_mask = mask & (offline_sca_col > float(min_scattering_tau)) & (sp3_sca_col > float(min_scattering_tau))
    if not np.any(sca_mask):
        raise ValueError(f"{band}: no finite cells with scattering optical depth > {min_scattering_tau}")
    g_diff_all = np.abs(offline_g - sp3_g)
    ssa_diff = ssa_diff_all[sca_mask]
    g_diff = g_diff_all[sca_mask]
    median_ratio = float(np.nanmedian(ratio))
    median_ssa = float(np.nanmedian(ssa_diff))
    median_g = float(np.nanmedian(g_diff))
    max_ssa = float(np.nanmax(ssa_diff))
    max_g = float(np.nanmax(g_diff))
    median_abs_ext_rel = float(np.nanmedian(rel))
    passed = (
        median_abs_ext_rel <= float(ext_ratio_tolerance)
        and max_ssa <= float(ssa_tolerance)
        and max_g <= float(asymmetry_tolerance)
    )
    return OfflineBandMetric(
        band=normalize_band(band),
        stamp=stamp,
        count=int(np.count_nonzero(mask)),
        offline_column_mean=float(np.nanmean(offline_col[mask])),
        sp3_column_mean=float(np.nanmean(sp3_col[mask])),
        median_ext_ratio=median_ratio,
        median_abs_ext_relative_difference=median_abs_ext_rel,
        median_abs_ssa_difference=median_ssa,
        median_abs_asymmetry_difference=median_g,
        max_abs_ssa_difference=max_ssa,
        max_abs_asymmetry_difference=max_g,
        ssa_count=int(np.count_nonzero(sca_mask)),
        asymmetry_count=int(np.count_nonzero(sca_mask)),
        passed=passed,
        sample_count=int(offline.attrs.get("sample_count", 0)),
        sample_indices_json=str(offline.attrs.get("sample_indices", "")),
        direct_normalization=str(offline.attrs.get("direct_normalization", "")),
    )


def compare_offline_to_sp3(
    *,
    lut_file: Path,
    h0_file: Path,
    sp3_dir: Path,
    bands: Iterable[str] = DEFAULT_BANDS,
    stamp: str,
    reference_method: str = REFERENCE_METHOD_CAM_LUT,
    fine_lut_dir: Path = DEFAULT_FINE_LUT_DIR,
    fine_lut_suffix: str = DEFAULT_FINE_LUT_SUFFIX,
    direct_sample_columns: int = 0,
    direct_n_quad: int = 120,
    direct_n_sigma: float = 5.0,
    direct_normalization: str = DIRECT_NORMALIZATION_WET_VOLUME,
    min_tau: float = 1.0e-3,
    min_scattering_tau: float = 1.5e-3,
    ext_ratio_tolerance: float = 0.10,
    ssa_tolerance: float = 0.02,
    asymmetry_tolerance: float = 0.05,
) -> list[OfflineBandMetric]:
    if reference_method not in REFERENCE_METHODS:
        raise ValueError(f"unsupported reference method {reference_method!r}")
    if reference_method == REFERENCE_METHOD_MAM_LFL_DIRECT_MIE and direct_sample_columns <= 0:
        raise ValueError("direct_sample_columns must be positive for direct-Mie sampled comparison")
    if reference_method == REFERENCE_METHOD_MAM_LFL_DIRECT_MIE and direct_n_quad < 2:
        raise ValueError("direct_n_quad must be >= 2 for direct-Mie sampled comparison")
    if reference_method == REFERENCE_METHOD_MAM_LFL_DIRECT_MIE and direct_n_sigma <= 0.0:
        raise ValueError("direct_n_sigma must be positive for direct-Mie sampled comparison")
    if reference_method == REFERENCE_METHOD_MAM_LFL_DIRECT_MIE and direct_normalization not in DIRECT_NORMALIZATIONS:
        raise ValueError(f"direct_normalization must be one of {DIRECT_NORMALIZATIONS}")
    with xr.open_dataset(lut_file) as lut, xr.open_dataset(h0_file, decode_times=False) as h0:
        metrics = []
        for band in bands:
            normalized = normalize_band(band)
            with _load_sp3_band(sp3_dir, normalized, stamp) as sp3:
                sp3_for_metric = sp3
                if reference_method == REFERENCE_METHOD_MAM_LFL_FINE:
                    offline = reconstruct_band_mam_lfl_fine(
                        lut,
                        h0,
                        normalized,
                        stamp=stamp,
                        fine_lut_dir=fine_lut_dir,
                        fine_lut_suffix=fine_lut_suffix,
                    )
                elif reference_method == REFERENCE_METHOD_MAM_LFL_DIRECT_MIE:
                    offline, sp3_for_metric = reconstruct_band_mam_lfl_direct_mie_sampled(
                        lut,
                        h0,
                        sp3,
                        normalized,
                        stamp=stamp,
                        sample_columns=direct_sample_columns,
                        min_tau=min_tau,
                        n_quad=direct_n_quad,
                        n_sigma=direct_n_sigma,
                        normalization=direct_normalization,
                    )
                else:
                    offline = reconstruct_band(lut, h0, normalized, stamp=stamp)
                metrics.append(
                    _metric_for_band(
                        offline,
                        sp3_for_metric,
                        normalized,
                        stamp,
                        min_tau=min_tau,
                        min_scattering_tau=min_scattering_tau,
                        ext_ratio_tolerance=ext_ratio_tolerance,
                        ssa_tolerance=ssa_tolerance,
                        asymmetry_tolerance=asymmetry_tolerance,
                    )
                )
    return metrics


def write_outputs(
    outdir: Path,
    metrics: list[OfflineBandMetric],
    *,
    reference_method: str = REFERENCE_METHOD_CAM_LUT,
) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "sp3v2_offline_lut_comparison_summary.csv"
    json_path = outdir / "sp3v2_offline_lut_comparison_summary.json"
    rows = [asdict(metric) for metric in metrics]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OfflineBandMetric.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps({"reference_method": reference_method, "band_metrics": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lut-file", required=True, type=Path)
    parser.add_argument("--h0-file", required=True, type=Path)
    parser.add_argument("--sp3-dir", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--stamp", required=True, help="SP3 stamp to compare, e.g. 20080701.10800")
    parser.add_argument("--bands", nargs="*", default=list(DEFAULT_BANDS), help="SP3 bands to compare; default all")
    parser.add_argument("--reference-method", choices=REFERENCE_METHODS, default=REFERENCE_METHOD_CAM_LUT)
    parser.add_argument("--fine-lut-dir", default=DEFAULT_FINE_LUT_DIR, type=Path)
    parser.add_argument("--fine-lut-suffix", default=DEFAULT_FINE_LUT_SUFFIX)
    parser.add_argument(
        "--direct-sample-columns",
        type=int,
        default=0,
        help="number of SP3 columns to sample for mam-lfl-direct-mie-sampled; required for that method",
    )
    parser.add_argument("--direct-n-quad", type=int, default=120, help="lognormal quadrature points for sampled direct Mie")
    parser.add_argument("--direct-n-sigma", type=float, default=5.0, help="lognormal integration half-width in sigma")
    parser.add_argument(
        "--direct-normalization",
        choices=DIRECT_NORMALIZATIONS,
        default=DIRECT_NORMALIZATION_WET_VOLUME,
        help="scale direct-Mie cross sections by CAM wet volume or by num_a* particle number",
    )
    parser.add_argument("--min-tau", type=float, default=1.0e-3)
    parser.add_argument(
        "--min-scattering-tau",
        type=float,
        default=1.5e-3,
        help="minimum column scattering optical depth for strict SSA/asymmetry max-difference gates",
    )
    parser.add_argument("--ext-ratio-tolerance", type=float, default=0.10)
    parser.add_argument("--ssa-tolerance", type=float, default=0.02)
    parser.add_argument("--asymmetry-tolerance", type=float, default=0.05)
    args = parser.parse_args(argv)

    bands = DEFAULT_BANDS if args.bands == ["all"] else tuple(normalize_band(band) for band in args.bands)
    metrics = compare_offline_to_sp3(
        lut_file=args.lut_file,
        h0_file=args.h0_file,
        sp3_dir=args.sp3_dir,
        bands=bands,
        stamp=args.stamp,
        reference_method=args.reference_method,
        fine_lut_dir=args.fine_lut_dir,
        fine_lut_suffix=args.fine_lut_suffix,
        direct_sample_columns=args.direct_sample_columns,
        direct_n_quad=args.direct_n_quad,
        direct_n_sigma=args.direct_n_sigma,
        direct_normalization=args.direct_normalization,
        min_tau=args.min_tau,
        min_scattering_tau=args.min_scattering_tau,
        ext_ratio_tolerance=args.ext_ratio_tolerance,
        ssa_tolerance=args.ssa_tolerance,
        asymmetry_tolerance=args.asymmetry_tolerance,
    )
    csv_path, json_path = write_outputs(args.outdir, metrics, reference_method=args.reference_method)
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    failed = [metric for metric in metrics if not metric.passed]
    for metric in metrics:
        status = "PASS" if metric.passed else "FAIL"
        print(
            f"{status} {metric.band}: ratio={metric.median_ext_ratio:.6g} "
            f"median_abs_rel={metric.median_abs_ext_relative_difference:.6g} "
            f"median_abs_ssa={metric.median_abs_ssa_difference:.6g} "
            f"median_abs_g={metric.median_abs_asymmetry_difference:.6g} "
            f"max_abs_ssa={metric.max_abs_ssa_difference:.6g} "
            f"max_abs_g={metric.max_abs_asymmetry_difference:.6g} "
            f"count={metric.count} "
            f"ssa_count={metric.ssa_count} "
            f"g_count={metric.asymmetry_count}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
