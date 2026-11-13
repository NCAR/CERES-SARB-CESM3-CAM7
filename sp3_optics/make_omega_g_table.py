#!/usr/bin/env python
"""Generate SP3 prescribed LW omega/g tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

if not hasattr(np, "trapezoid"):
    np.trapezoid = np.trapz


REPO_ROOT = Path(__file__).resolve().parents[1]
MAM_LFL_ROOT = Path(__file__).resolve().parents[2] / "CERES-SARB-MAM-LFL"
AEROSOL_YAML = MAM_LFL_ROOT / "aerosol.yaml"
CAM_SOURCE_ROOT = Path("/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam")
CAM_RRTMGP_LW_COEFF_PATH = (
    CAM_SOURCE_ROOT / "src/physics/rrtmgp/data/rrtmgp-gas-lw-g128.nc"
)
OPTICS_ROOT = Path("/glade/work/fillmore/Data/Optics/MERRA2")
PHYSPROP_PATHS = {
    "a1": Path(
        "/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/"
        "mam4_mode1_rrtmg_aeronetdust_sig1.6_dgnh.48_c140304.nc"
    ),
    "a2": Path(
        "/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/"
        "mam4_mode2_rrtmg_aitkendust_c141106.nc"
    ),
    "a3": Path(
        "/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/"
        "mam4_mode3_rrtmg_aeronetdust_c141106.nc"
    ),
    "a4": Path(
        "/glade/campaign/cesm/cesmdata/inputdata/atm/cam/physprops/"
        "mam4_mode4_rrtmg_c130628.nc"
    ),
}
MODE_ORDER = ("a1", "a2", "a3", "a4")
N_SIGMA = 5.0

if str(MAM_LFL_ROOT) not in sys.path:
    sys.path.insert(0, str(MAM_LFL_ROOT))

from mie_lognormal import mode_averaged_cross_sections_um2  # noqa: E402
from mode_config import resolved_allocations  # noqa: E402
from mode_physics import mix_mode_state  # noqa: E402


SPECIES_TYPE_ALIASES = {
    "SO4": "SU",
    "BCPHILIC": "BC",
    "BCPHOBIC": "BC",
    "OCPHILIC": "POM",
    "OCPHOBIC": "POM",
}
SPECIES_INFO = {
    "BC": {"density": 1.0, "hygroscopicity": (0.01, 0.0, 0.0)},
    "POM": {"density": 1.8, "hygroscopicity": (0.14, 0.0, 0.0)},
    "SOA": {"density": 1.8, "hygroscopicity": (0.14, 0.0, 0.0)},
    "SU": {"density": 1.7, "hygroscopicity": (2.42848, -3.85261, 1.88159)},
    "DU": {"density": 2.6, "hygroscopicity": (0.14, 0.0, 0.0)},
    "SS": {"density": 2.2, "hygroscopicity": (4.83257, -6.92329, 3.27805)},
}
SPECIES_OPTICS = {
    "BC": OPTICS_ROOT / "optics_BC.v1_3.nc",
    "POM": OPTICS_ROOT / "optics_OC.v1_3.nc",
    "SOA": OPTICS_ROOT / "optics_OC.v1_3.nc",
    "SU": OPTICS_ROOT / "optics_SU.v1_3.nc",
    "DU": OPTICS_ROOT / "optics_DU.v15_3.nc",
    "SS": OPTICS_ROOT / "optics_SS.v3_3.nc",
    "WAT": OPTICS_ROOT / "optics_WAT.nc",
}
REPRESENTATIVE_MODES = {
    "a1": {
        "description": "Accumulation-mode polluted continental wet state",
        "representative_rh": 0.60,
        "temperature_k": 280.0,
        "dry_volume_fraction": {
            "SU": 0.45,
            "SOA": 0.20,
            "POM": 0.15,
            "BC": 0.05,
            "DU": 0.05,
            "SS": 0.10,
        },
    },
    "a2": {
        "description": "Aitken-mode sulfate/organic wet state",
        "representative_rh": 0.60,
        "temperature_k": 280.0,
        "dry_volume_fraction": {
            "SU": 0.60,
            "SOA": 0.30,
            "POM": 0.05,
            "DU": 0.02,
            "SS": 0.03,
        },
    },
    "a3": {
        "description": "Coarse-mode dust/sea-salt wet state",
        "representative_rh": 0.80,
        "temperature_k": 280.0,
        "dry_volume_fraction": {
            "DU": 0.75,
            "SS": 0.20,
            "SU": 0.05,
        },
    },
    "a4": {
        "description": "Primary-carbon wet state",
        "representative_rh": 0.50,
        "temperature_k": 280.0,
        "dry_volume_fraction": {
            "POM": 0.70,
            "BC": 0.30,
        },
    },
}


def _git_value(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return "unavailable"
    return result.stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _species_type(species: str) -> str:
    upper = str(species).upper()
    if upper in SPECIES_TYPE_ALIASES:
        return SPECIES_TYPE_ALIASES[upper]
    if upper.startswith("DU"):
        return "DU"
    if upper.startswith("SS"):
        return "SS"
    return upper


def load_mam_lfl_mode_species(path: Path = AEROSOL_YAML) -> dict[str, tuple[str, ...]]:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    mode_species: dict[str, set[str]] = {
        mode: {str(species) for species in config["MAM4"][mode].get("types", [])}
        for mode in MODE_ORDER
    }
    for species, allocation in resolved_allocations(config, "MAM4").items():
        type_name = _species_type(species)
        for mode, fraction in allocation.items():
            if mode in mode_species and float(fraction) > 0.0:
                mode_species[mode].add(type_name)
    return {
        mode: tuple(sorted(mode_species[mode]))
        for mode in MODE_ORDER
    }


def validate_representative_modes() -> dict[str, tuple[str, ...]]:
    mode_species = load_mam_lfl_mode_species()
    for mode in MODE_ORDER:
        allowed = set(mode_species[mode])
        requested = set(REPRESENTATIVE_MODES[mode]["dry_volume_fraction"])
        extra = requested - allowed
        if extra:
            raise ValueError(
                f"{mode} representative species are not in MAM-LFL mode definition: "
                f"{sorted(extra)}"
            )
    return mode_species


@dataclass(frozen=True)
class ModeSpec:
    name: str
    physprop_path: Path
    sigma_g: float
    dry_radius_um: float


@dataclass(frozen=True)
class TableResult:
    omega: np.ndarray
    g: np.ndarray
    ext_um2: np.ndarray
    sca_um2: np.ndarray
    abs_um2: np.ndarray
    wet_radius_um: np.ndarray
    n_real: np.ndarray
    n_imag: np.ndarray


def load_cam_lw_edges_cm(path: Path = CAM_RRTMGP_LW_COEFF_PATH) -> np.ndarray:
    with xr.open_dataset(path) as ds:
        limits = np.asarray(ds["bnd_limits_wavenumber"].values, dtype=np.float64)
    if limits.shape != (16, 2):
        raise ValueError(
            f"bnd_limits_wavenumber must have shape (16, 2), got {limits.shape}"
        )
    if not np.allclose(limits[:-1, 1], limits[1:, 0], rtol=0.0, atol=1.0e-8):
        raise ValueError("RRTMGP LW band limits must be contiguous")
    edges = np.r_[limits[:, 0], limits[-1, 1]]
    if edges.shape != (17,):
        raise ValueError(f"CAM LW coefficients must define 17 edges, got {edges.shape}")
    if np.any(np.diff(edges) <= 0.0):
        raise ValueError("CAM_LW edges must be strictly increasing")
    return edges


def load_mode_specs() -> dict[str, ModeSpec]:
    specs = {}
    for mode in MODE_ORDER:
        path = PHYSPROP_PATHS[mode]
        with xr.open_dataset(path) as ds:
            sigma_g = float(ds["sigmag"].values)
            dgnumlo = float(ds["dgnumlo"].values)
            dgnumhi = float(ds["dgnumhi"].values)
        radius_um = 0.5 * np.sqrt(dgnumlo * dgnumhi) * 1.0e6
        specs[mode] = ModeSpec(
            name=mode,
            physprop_path=path,
            sigma_g=sigma_g,
            dry_radius_um=float(radius_um),
        )
    return specs


def _nearest_scalar(ds: xr.Dataset, coord_name: str, variable_name: str, target: float) -> float:
    coord = ds[coord_name]
    values = np.asarray(coord.values, dtype=np.float64).squeeze()
    index = int(np.argmin(np.abs(values.ravel() - float(target))))
    dim = coord.dims[-1] if coord.dims else coord_name
    variable = ds[variable_name]
    if dim in variable.dims:
        variable = variable.isel({dim: index})
    elif coord_name in variable.dims:
        variable = variable.isel({coord_name: index})
    selected = np.asarray(variable.values, dtype=np.float64).squeeze()
    return float(selected.reshape(-1)[0])


def refractive_index_for_species(species: str, wavelength_um: float) -> tuple[float, float]:
    species_key = str(species).upper()
    path = SPECIES_OPTICS[species_key]
    with xr.open_dataset(path) as ds:
        if species_key == "WAT":
            n_real = _nearest_scalar(ds, "wavelength1", "watern", wavelength_um)
            n_imag = _nearest_scalar(ds, "wavelength1", "wateri", wavelength_um)
        else:
            wavelength_m = float(wavelength_um) * 1.0e-6
            n_real = _nearest_scalar(ds, "lambda", "refreal", wavelength_m)
            n_imag = _nearest_scalar(ds, "lambda", "refimag", wavelength_m)
    return float(n_real), abs(float(n_imag))


def _representative_q(mode: str) -> dict[str, np.ndarray]:
    fractions = REPRESENTATIVE_MODES[mode]["dry_volume_fraction"]
    total = sum(float(value) for value in fractions.values())
    if not np.isclose(total, 1.0):
        raise ValueError(f"{mode} dry volume fractions must sum to 1, got {total}")
    q = {}
    for species, fraction in fractions.items():
        rho_kg_m3 = float(SPECIES_INFO[species]["density"]) * 1000.0
        q[species] = np.asarray(float(fraction) * rho_kg_m3, dtype=np.float32)
    return q


def representative_mode_state(mode: str, spec: ModeSpec, wavelength_um: float) -> dict[str, float]:
    assumption = REPRESENTATIVE_MODES[mode]
    species = tuple(assumption["dry_volume_fraction"])
    refractive = {
        name: refractive_index_for_species(name, wavelength_um)
        for name in species
    }
    refractive["WAT"] = refractive_index_for_species("WAT", wavelength_um)
    state = mix_mode_state(
        SPECIES_INFO,
        _representative_q(mode),
        refractive,
        np.asarray(float(assumption["representative_rh"]), dtype=np.float32),
        np.asarray(float(assumption["temperature_k"]), dtype=np.float32),
        spec.dry_radius_um,
    )
    return {
        "r_w_um": float(np.asarray(state["r_w_um"])),
        "n_re": float(np.asarray(state["n_re"])),
        "n_im": abs(float(np.asarray(state["n_im"]))),
    }


def build_physical_table(n_quad: int) -> TableResult:
    mode_specs = load_mode_specs()
    omega = np.zeros((16, 4), dtype=np.float32)
    asym = np.zeros((16, 4), dtype=np.float32)
    ext_um2 = np.zeros((16, 4), dtype=np.float64)
    sca_um2 = np.zeros((16, 4), dtype=np.float64)
    abs_um2 = np.zeros((16, 4), dtype=np.float64)
    wet_radius_um = np.zeros((16, 4), dtype=np.float64)
    n_real = np.zeros((16, 4), dtype=np.float64)
    n_imag = np.zeros((16, 4), dtype=np.float64)

    for iband, wavelength_um in enumerate(CAM_LW_MID_UM):
        for imode, mode in enumerate(MODE_ORDER):
            spec = mode_specs[mode]
            state = representative_mode_state(mode, spec, float(wavelength_um))
            mie = mode_averaged_cross_sections_um2(
                state["n_re"],
                state["n_im"],
                state["r_w_um"],
                spec.sigma_g,
                float(wavelength_um),
                n_quad=n_quad,
                n_sigma=N_SIGMA,
            )
            ext = max(float(mie["ext"]), 0.0)
            sca = max(float(mie["sca"]), 0.0)
            absn = max(float(mie["abs"]), 0.0)
            ext_um2[iband, imode] = ext
            sca_um2[iband, imode] = sca
            abs_um2[iband, imode] = absn
            wet_radius_um[iband, imode] = state["r_w_um"]
            n_real[iband, imode] = state["n_re"]
            n_imag[iband, imode] = state["n_im"]
            omega[iband, imode] = np.float32(min(0.9, sca / ext if ext > 0.0 else 0.0))
            asym[iband, imode] = np.float32(np.clip(float(mie["asymmetry"]), -1.0, 1.0))

    return TableResult(
        omega=omega,
        g=asym,
        ext_um2=ext_um2,
        sca_um2=sca_um2,
        abs_um2=abs_um2,
        wet_radius_um=wet_radius_um,
        n_real=n_real,
        n_imag=n_imag,
    )


def physical_table(n_quad: int) -> tuple[np.ndarray, np.ndarray]:
    table = build_physical_table(n_quad)
    return table.omega, table.g


CAM_LW_EDGES_CM = load_cam_lw_edges_cm()
CAM_LW_MID_UM = 1.0e4 / (0.5 * (CAM_LW_EDGES_CM[:-1] + CAM_LW_EDGES_CM[1:]))


def zero_table() -> tuple[np.ndarray, np.ndarray]:
    return np.zeros((16, 4), dtype=np.float32), np.zeros((16, 4), dtype=np.float32)


def write_table(
    path: Path,
    omega: np.ndarray,
    asym: np.ndarray,
    omega_zero: bool,
    n_quad: int,
    extra_attrs: dict[str, str | int | float] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    attrs = common_attrs()
    attrs.update(extra_attrs or {})
    ds = xr.Dataset(
        {
            "omega_lw": (("lw_band", "bin"), omega.astype("f4")),
            "g_lw": (("lw_band", "bin"), asym.astype("f4")),
        },
        coords={
            "lw_band": np.arange(1, 17, dtype=np.int32),
            "bin": np.arange(1, 5, dtype=np.int32),
            "cam_lw_wavenumber_low_cm1": (
                ("lw_band",),
                CAM_LW_EDGES_CM[:-1].astype("f4"),
            ),
            "cam_lw_wavenumber_high_cm1": (
                ("lw_band",),
                CAM_LW_EDGES_CM[1:].astype("f4"),
            ),
            "cam_lw_midpoint_um": (("lw_band",), CAM_LW_MID_UM.astype("f4")),
        },
        attrs={
            "source": "CERES-SARB-CAM7 SP3",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "omega_zero": int(omega_zero),
            "n_quad": int(n_quad),
            **attrs,
        },
    )
    ds.to_netcdf(path)


def common_attrs() -> dict[str, str]:
    return {
        "generator": "sp3_optics.make_omega_g_table",
        "generator_git_commit": _git_value(REPO_ROOT, ["rev-parse", "HEAD"]),
        "generator_git_status_short": _git_value(REPO_ROOT, ["status", "--short"]),
        "mam_lfl_git_commit": _git_value(MAM_LFL_ROOT, ["rev-parse", "HEAD"]),
        "mam_lfl_git_status_short": _git_value(MAM_LFL_ROOT, ["status", "--short"]),
        "cam_source_root": str(CAM_SOURCE_ROOT),
        "cam_lw_coeff_file": str(CAM_RRTMGP_LW_COEFF_PATH),
        "cam_lw_coeff_sha256": _file_sha256(CAM_RRTMGP_LW_COEFF_PATH),
        "cam_lw_edges_source": (
            f"{CAM_RRTMGP_LW_COEFF_PATH}:bnd_limits_wavenumber"
        ),
    }


def physical_attrs() -> dict[str, str | int | float]:
    mode_species = validate_representative_modes()
    return {
        "table_version": "v2_representative_wet_mam_lfl_mie",
        "mode_order": ",".join(MODE_ORDER),
        "wet_state_source": (
            f"{MAM_LFL_ROOT / 'mode_physics.py'}:"
            "mode_physics.mix_mode_state"
        ),
        "mie_source": (
            f"{MAM_LFL_ROOT / 'mie_lognormal.py'}:"
            "mie_lognormal.mode_averaged_cross_sections_um2"
        ),
        "refindex_source": str(OPTICS_ROOT),
        "refindex_imaginary_convention": (
            "MERRA2 aerosol refimag values are stored negative; this generator "
            "uses positive absorption magnitudes for wet mixing and Mie."
        ),
        "representative_modes_source": (
            "documented T2 dry-volume representative states; species membership "
            f"validated against {AEROSOL_YAML}:MAM4 and Schemes:MAM4 allocations"
        ),
        "mam_lfl_mode_species_json": json.dumps(mode_species, sort_keys=True),
        "n_sigma": float(N_SIGMA),
        "physprop_paths_json": json.dumps(
            {mode: str(path) for mode, path in PHYSPROP_PATHS.items()},
            sort_keys=True,
        ),
        "representative_modes_json": json.dumps(
            REPRESENTATIVE_MODES,
            sort_keys=True,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--omega-zero", action="store_true")
    parser.add_argument("--n-quad", type=int, default=80)
    args = parser.parse_args(argv)

    if args.n_quad < 2:
        raise SystemExit("--n-quad must be >= 2")

    extra_attrs = None
    if args.omega_zero:
        omega, asym = zero_table()
    else:
        omega, asym = physical_table(args.n_quad)
        extra_attrs = physical_attrs()

    if not np.all(np.isfinite(omega)) or not np.all(np.isfinite(asym)):
        raise SystemExit("omega_lw and g_lw must be finite")
    if np.any((omega < 0.0) | (omega > 0.9)):
        raise SystemExit("omega_lw outside [0, 0.9]")
    if np.any((asym < -1.0) | (asym > 1.0)):
        raise SystemExit("g_lw outside [-1, 1]")

    write_table(args.output, omega, asym, args.omega_zero, args.n_quad, extra_attrs)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
