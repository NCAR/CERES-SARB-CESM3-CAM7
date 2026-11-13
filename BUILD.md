# Building CESM3 / CAM7 on derecho

How to clone, configure, and build a **CESM3 (`cesm3_0_beta08`) / CAM7** case on the NCAR **derecho** supercomputer for the CERES-SARB-CAM7 project.

For the verified GNU/OpenMPI build and four-rank smoke run on the Orion Linux
desktop, use [`docs/cesm3-desktop.md`](docs/cesm3-desktop.md). The desktop
recipe is a stock, no-MODIS CERES-MIP baseline and has different environment
rules from the Derecho build below.

**Status: verified working 2026-06-27** — `F2000dev` (CAM7, MAM4) at `f09_f09_mg17` builds to a `cesm.exe` on derecho (login node, conda-free environment; ~8.7 min, `-j16`).

Current live checkout provenance, component revisions, targeted CIME metadata, and a documentation
index are recorded in [docs/cesm3-checkout.md](docs/cesm3-checkout.md). Refresh and verify it with
`python scripts/update_cesm3_reference.py` and
`python scripts/update_cesm3_reference.py --check`.

Companion Claude Code skill (automates this): `.claude/skills/build-cesm-cam7/` → `scripts/clone_cesm.sh`, `scripts/build_case.sh`.

---

## Three rules that will save you hours

1. **Build in a conda-free environment.** Derecho login profiles auto-activate miniforge, which ships `libyaml-cpp.so`. CAM7's TUV-x does `find_package(yaml-cpp)` and will grab the conda copy via the `PATH`→prefix search, skip building its own static `libyaml-cpp.a`, and then `cam.buildlib` fails with *"yaml-cpp library not found at .../bld/lib/lib/libyaml-cpp.a"*. **Remove miniforge from `PATH` and unset `CONDA_PREFIX` before `case.build`**, giving CIME a `python3` via a shim dir. (`build_case.sh` does this for you.)
2. **Build on a login node, not `qcmd`/compute.** TUV-x FetchContent-clones yaml-cpp from GitHub at CMake-configure time, so the build needs **internet** — which compute nodes don't have. (Cloning with `git-fleximod` likewise needs internet.)
3. **Never rebuild a case whose executable is queued or shared.** PBS queues the case run script, and CIME launches the `cesm.exe` in that case's current `EXEROOT`; it does not protect you with a private executable copy at submit time. If `qstat -u $USER` shows a queued/running job for a case, treat that case's `EXEROOT` and `cesm.exe` as read-only until the run is done. This matters for `--keepexe` clones too: the clone may launch the original case's executable.

---

## Layout convention
- **Vanilla CESM checkout** (upstream; managed by `git-fleximod`, not committed here): `/glade/work/fillmore/CESM3/cesm3_0_beta08`.
- **This repo** (`CERES-SARB-CAM7`): our customized code, namelist, scripts, docs, tests.
- **Cases**: `/glade/work/fillmore/CESM3/cases/<case>`.
- **Build/run output** (auto, scratch): `/glade/derecho/scratch/$USER/<case>/{bld,run}`.
- **Development rebuilds**: use a fresh dev case name so it gets a fresh scratch build root, e.g. `/glade/work/fillmore/CESM3/cases/sp2_dev_<topic>` -> `/glade/derecho/scratch/$USER/sp2_dev_<topic>/bld`.

## Prerequisites
- On a derecho **login node** (internet required; see Rule 2).
- Project/account code: **`P19010000`** (`create_newcase` requires it; `PROJECT_REQUIRED=true`).
- `python3` for `git-fleximod` and CIME. Miniforge's python is fine for cloning; for **building** it must be provided *without* putting miniforge on `PATH` (see Rule 1).
- Default `ncarenv/23.09` modules; `case.build` loads its own intel + cray-mpich + netcdf toolchain from `ccs_config/machines/derecho`.

---

## Step 1 — Clone CESM3 and check out components
```bash
export PATH=/glade/work/fillmore/miniforge3/bin:$PATH    # python3 for git-fleximod (clone only)
cd /glade/work/fillmore/CESM3
git clone https://github.com/ESCOMP/CESM.git cesm3_0_beta08
cd cesm3_0_beta08
git checkout cesm3_0_beta08
./bin/git-fleximod update      # CAM7, CTSM, MOM6, CICE6, CISM, RRTMGP, TUV-x, ... (~3.8 GB)
./bin/git-fleximod status      # verify cam @ cam6_4_161, tuv-x @ v0.14.3, etc.
```
Or: `TAG=cesm3_0_beta08 DEST=/glade/work/fillmore/CESM3/cesm3_0_beta08 bash .claude/skills/build-cesm-cam7/scripts/clone_cesm.sh`

To **fork CAM** later (version-controlled source mods): point the `cam` submodule (`url`+`fxtag` in `.gitmodules`) at your fork, then `./bin/git-fleximod update cam`.

## Step 2 — Pick a CAM7 compset
The `cam6_4_161` source contains *both* CAM6 and CAM7 physics; the compset's `CAM60` vs **`CAM70`** token chooses. Plain `FHIST`/`F2000climo` are **CAM6** — don't use them for CAM7.

| Use | Compset | Current-checkout resolution |
|---|---|---|
| Vanilla CAM7 build test (present-day, MAM4) | `F2000dev` | `2000_CAM70_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV` |
| Historical CAM-chem alias audit | `FCHIST` | `HIST_CAM60%CT1S1_...` (**CAM6**, not CAM7) |
| Nudged CAM-chem alias audit | `FCnudged` / `FCts2nudged` | `HIST_CAM60%CT1S1%NUDG_...` / `HIST_CAM60%CT2S1%NUDG_...` (**CAM6**, not CAM7) |

In this beta08 checkout, only `F2000dev` among those aliases resolves to `CAM70`. The project adds
meteorological and AOD nudging through validated namelist/source configuration on that CAM7 base;
do not treat an `FC*` alias as CAM7 without querying and inspecting its current expanded long name.

`-phys cam7` defaults to `chem=ghg_mam4` → prognostic **MAM4**. Chem menu (from `config_cache.xml`) includes `trop_mam4`, **`trop_strat_mam4_vbs`** (CAM7 analog of the prior project's CCTS1), `trop_strat_mam5_t1s1/_t2s1/_t4s2`, `trop_strat_mam5_vbsext`, `waccm_*_mam5`, `geoschem_mam4`. To force one: `./xmlchange --append CAM_CONFIG_OPTS="-chem trop_strat_mam4_vbs"`.

## Step 3 + 4 — Create, set up, build (use the script)
```bash
# run from the repo root (wherever you cloned CERES-SARB-CAM7):
CASE=/glade/work/fillmore/CESM3/cases/myrun_cam7 \
COMPSET=F2000dev RES=f09_f09_mg17 \
bash .claude/skills/build-cesm-cam7/scripts/build_case.sh
```
The script scrubs conda, runs `create_newcase --project P19010000 --run-unsupported`, `case.setup`, and `case.build` on the login node, then verifies `cesm.exe`.

Manual equivalent (note the conda scrub):
```bash
cd /glade/work/fillmore/CESM3/cesm3_0_beta08/cime/scripts
./create_newcase --case /glade/work/fillmore/CESM3/cases/myrun_cam7 \
  --compset F2000dev --res f09_f09_mg17 --machine derecho --compiler intel \
  --project P19010000 --run-unsupported
cd /glade/work/fillmore/CESM3/cases/myrun_cam7
./case.setup
# conda-free build env (else yaml-cpp failure — see Rule 1):
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
./case.build          # login node
```
Success: `MODEL BUILD HAS FINISHED SUCCESSFULLY`; `./xmlquery EXEROOT` has `cesm.exe`; `CaseStatus` shows `case.build success`. Clean rebuild: `./case.build --clean-all && ./case.build`.

## SP2 development rebuilds

While submitted SP2 runs are queued or running, do **not** rebuild either submitted case or any case that shares its executable. On 2026-06-28, the submitted July 2008 pair was:

- `sp2_200807_mam4_modis` / PBS `6581712.desched1`
- `sp2_200807_mam4_free` / PBS `6581729.desched1`

Both resolve `EXEROOT` to:

```bash
/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld
```

The free case was cloned with `--keepexe`, so it shares:

```bash
/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld/cesm.exe
```

Those full-July jobs completed successfully on 2026-06-28. On 2026-06-30, `qstat -u $USER` was empty and both cases had `case.run success`; see `RUN.md` for the output inventory. Treat this pair as provenance-preserved production output. For new SP2 source development, avoid rebuilding these cases unless you explicitly intend to invalidate or replace that run record.

For SP2 source development, create a separate dev case and build there:

```bash
DEVCASE=/glade/work/fillmore/CESM3/cases/sp2_dev_aod

CASE=$DEVCASE COMPSET=F2000dev RES=f09_f09_mg17 \
  bash .claude/skills/build-cesm-cam7/scripts/build_case.sh

bash scripts/sp2_deploy.sh "$DEVCASE"
cd "$DEVCASE"
./case.build
./xmlquery CASE EXEROOT --value
```

Before rebuilding any existing case, check the queue and the executable root:

```bash
qstat -u $USER
cd /glade/work/fillmore/CESM3/cases/<case>
./xmlquery CASE EXEROOT BUILD_COMPLETE --value
```

## Step 5 — (Optional) Run
```bash
./xmlchange STOP_OPTION=ndays,STOP_N=1
./case.submit              # uses PROJECT P19010000
```
See `RUN.md` for run tracking.

---

## Gotchas (observed)
| Symptom | Cause / fix |
|---|---|
| `cam.buildlib failed` → `yaml-cpp library not found at .../bld/lib/lib/libyaml-cpp.a` | conda/miniforge on `PATH` → tuv-x `find_package(yaml-cpp)` grabbed conda's copy, skipped building the static lib. **Scrub conda from the build env** (Rule 1); wipe `bld/atm/obj/tuv-x` and rebuild. |
| Build hangs/fails fetching yaml-cpp | No internet (compute node). **Build on a login node** (Rule 2). |
| `ERROR: PROJECT_REQUIRED ... no project found` | Pass `--project P19010000` (or `export PROJECT=P19010000`). |
| Built CAM6 when you wanted CAM7 | Used a `CAM60` compset. In this checkout, use the live-verified `CAM70` alias `F2000dev`; the queried `FCHIST`/`FCnudged`/`FCts2nudged` aliases resolve to CAM6. |
| `git-fleximod: command not found` | `python3` not found. `export PATH=/glade/work/fillmore/miniforge3/bin:$PATH` (clone step only). |
| Compset rejected as unsupported | Add `--run-unsupported`. |
| No aerosols in run | Confirm `mode_defs`/`aer_drydep_list` in `CaseDocs/atm_in`; use a `*_mam4`/`*_mam5` chem. |

## Reference: components (`git-fleximod status`, `cesm3_0_beta08`)
`cam` @ `cam6_4_161` (CAM7) with `atmos_phys`, `rte-rrtmgp` @ `v1.9.2`, `rrtmgp-data` @ `v1.8`, `pumas`, `clubb`, `carma`, `cosp2`, `mpas`, `fv3`, `geoschem`, **`tuv-x` @ `v0.14.3`** (pulls `jbeder/yaml-cpp@65c1c27`); `clm` @ `ctsm5.4.027`; `cice` (CICE6); `mom` (MOM6); `cism`; `cmeps`/`cdeps`; `cime` @ `cime6.1.169`.
