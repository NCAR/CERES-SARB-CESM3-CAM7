# CESM3/CAM7 Linux desktop baseline

Status: verified on the `Orion` Pop!_OS desktop on 2026-08-13.

This is the stock, no-MODIS baseline for the CERES-MIP setup phase. It proves
that the selected CESM3/CAM7 source builds with a local GNU/OpenMPI toolchain
and that the resulting executable completes a short coupled multi-rank run.
It does not deploy the AOD-nudging or band-optics overlays in this repository,
and the coarse smoke run is not a scientific validation.

The sibling CERES-MIP plan identifies `FHISTC_LTso`/`FHISTC_MTso`,
`ne30pg3_ne30pg3_mt232`, and a 1990-2024 AMIP-style forcing window as the
production direction. The verified baseline uses LT-58L, while the LT-versus-MT
decision and the complete 1990-2024 forcing set remain production gates.

## Verified state

| Item | Verified value |
| --- | --- |
| CESM checkout | `/home/fillmore/EarthSystem/CESM3` |
| CESM tag / root commit | `cesm3_0_beta08` / `8ce857e8ba55bf7aeca11d93562e36abd635e5a0` |
| CAM component | `cam6_4_161` with CAM7 physics selected by the compset |
| Production-shaped build | `FHISTC_LTso`, `ne30pg3_ne30pg3_mt232`, `-phys cam7 -model_top lt`, 16 MPI tasks |
| Executable | `/home/fillmore/EarthSystem/CESM3/output/ceresmip_fhistc_ltso_smoke_orion/bld/cesm.exe` |
| Executable SHA-256 | `668de345f2e07cc53a6a826dee5ceea4cf602249355c167ea7a6e7c4ede0235e` |
| Runtime gate | CAM7 LT-58L, full CLM/CICE/DOCN/MOSART coupling, `ne3pg3_ne3pg3_mt232`, 4 MPI tasks, 6 coupled steps |
| Runtime result | LID `260813-192952`; `case.run success`; CAM end-of-run and CMEPS successful-termination markers |
| CAM compile-definition SHA-256 | `a279ec5f130507bfb53507359072fd2f259110b3949ec32e5d746bbbfe6117ed`, identical in build and runtime cases |

The ne30 executable links entirely against the dedicated conda environment;
`ldd` reports no missing libraries. The ne3 gate stayed below 5 GiB of
resident model memory across four ranks and completed in about 30 seconds. An
eight-rank ne30 startup reached roughly 54 GiB of model RSS and triggered the
Linux OOM killer on this 64 GiB desktop. Do not run ne30 here without
materially more memory; use Orion for builds and coarse gates, then run
production-resolution cases on an appropriately sized system.

## Directory layout

```text
/home/fillmore/EarthSystem/CESM3/
├── cases/
│   ├── ceresmip_fhistc_ltso_smoke_orion/  # authoritative ne30 build case
│   └── ceresmip_f2000_lt_ne3_smoke_orion/ # successful 4-rank runtime gate
├── inputdata/                              # shared CIME input-data cache
└── output/
    ├── ceresmip_fhistc_ltso_smoke_orion/bld/
    └── ceresmip_f2000_lt_ne3_smoke_orion/run/
```

Case definitions are kept separate from generated build/run output, and all
cases share one input-data cache. The CIME machine definition encodes these
paths.

## Recreate the checkout

Use SSH for the root checkout and a command-scoped rewrite so git-fleximod's
GitHub URLs also use SSH:

```bash
cd /home/fillmore/EarthSystem
GIT_SSH_COMMAND='/usr/bin/ssh -o IdentityAgent=none -o IdentitiesOnly=yes -i /home/fillmore/.ssh/id_ed25519' \
  git clone git@github.com:ESCOMP/CESM.git CESM3
git -C CESM3 checkout cesm3_0_beta08

cd /home/fillmore/EarthSystem/CESM3
GIT_SSH_COMMAND='/usr/bin/ssh -o IdentityAgent=none -o IdentitiesOnly=yes -i /home/fillmore/.ssh/id_ed25519' \
GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0='url.git@github.com:.insteadOf' \
GIT_CONFIG_VALUE_0='https://github.com/' \
  ./bin/git-fleximod update
./bin/git-fleximod status
```

The optional FTorch component may remain absent; every required component must
report its pinned tag without an error.

## Recreate the toolchain

The existing MPAS environment established that GNU 15.2/OpenMPI 5.0 is a
workable compiler family, but it does not contain the complete CESM NUOPC
dependency stack. Keep it untouched and create the dedicated environments:

```bash
cd /home/fillmore/EarthSystem/CERES-SARB-CAM7
/home/fillmore/miniforge3/bin/conda env create \
  -f config/cesm/environments/cesm3-build.yml
/home/fillmore/miniforge3/bin/conda env create \
  -f config/cesm/environments/cesm3-tools.yml
```

The machine file expects these exact prefixes:

```text
/home/fillmore/miniforge3/envs/cesm3-build
/home/fillmore/miniforge3/envs/cesm3-tools
```

The first environment supplies GNU, OpenMPI, MPI NetCDF/HDF5/PnetCDF,
ParallelIO, ESMF, CMake, Make, and m4. The second isolates the Perl/XML stack
needed by CTSM's namelist generator.

## Apply the beta08 GNU compatibility patch

Apply the small non-science patch before building:

```bash
export CESM=/home/fillmore/EarthSystem/CESM3
export REPO=/home/fillmore/EarthSystem/CERES-SARB-CAM7

git -C "$CESM/components/cam" apply --unidiff-zero --check \
  "$REPO/config/cesm/patches/cam6_4_161-orion-gnu15.patch"
git -C "$CESM/components/cam" apply --unidiff-zero \
  "$REPO/config/cesm/patches/cam6_4_161-orion-gnu15.patch"
```

One hunk is the same GNU workaround later committed upstream as CAM commit
`9fb9ec445c0716d693a7c75f2b41a5b2e695ad0d`: it stores `thread_id()` before
using the result in an `associate` selector. The other lets CAM find
yaml-cpp's debug archive when TUV-x installs it under `lib/` rather than
`lib64/`. The patch is intentionally zero-context and tag-specific, so apply
it only to `cam6_4_161`. Neither hunk changes model science.

## Recreate the ne30 CAM7 build

```bash
export CESM=/home/fillmore/EarthSystem/CESM3
export REPO=/home/fillmore/EarthSystem/CERES-SARB-CAM7
export MACHINE_DIR="$REPO/config/cesm/machines/orion"
export BUILD_CASE="$CESM/cases/ceresmip_fhistc_ltso_smoke_orion"

"$CESM/cime/scripts/create_newcase" \
  --case "$BUILD_CASE" \
  --compset FHISTC_LTso \
  --res ne30pg3_ne30pg3_mt232 \
  --machine orion \
  --compiler gnu \
  --mpilib openmpi \
  --pecount 16 \
  --extra-machines-dir "$MACHINE_DIR" \
  --run-unsupported

cd "$BUILD_CASE"
./case.setup
GIT_SSH_COMMAND='/usr/bin/ssh -o IdentityAgent=none -o IdentitiesOnly=yes -i /home/fillmore/.ssh/id_ed25519' \
GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0='url.git@github.com:.insteadOf' \
GIT_CONFIG_VALUE_0='https://github.com/' \
  ./case.build
```

The `--run-unsupported` flag reflects beta08 CIME metadata; it is not a claim
of scientific support. Verify `case.build success`, the executable, and its
dynamic libraries:

```bash
tail -n 20 CaseStatus
test -x "$CESM/output/ceresmip_fhistc_ltso_smoke_orion/bld/cesm.exe"
ldd "$CESM/output/ceresmip_fhistc_ltso_smoke_orion/bld/cesm.exe" |
  grep 'not found'
```

The last command should print nothing.

## Recreate the four-rank runtime gate

The runtime gate intentionally changes only the horizontal grid and forcing
mode to keep memory and input volume safe. It retains CAM7 LT-58L and reuses
the ne30 executable only after confirming identical CAM preprocessor
definitions.

```bash
export RUN_CASE="$CESM/cases/ceresmip_f2000_lt_ne3_smoke_orion"

"$CESM/cime/scripts/create_newcase" \
  --case "$RUN_CASE" \
  --compset '2000_CAM70%LT_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV' \
  --res ne3pg3_ne3pg3_mt232 \
  --machine orion \
  --compiler gnu \
  --mpilib openmpi \
  --extra-machines-dir "$MACHINE_DIR" \
  --run-unsupported

cd "$RUN_CASE"
./xmlchange NTASKS=4
./xmlchange STOP_OPTION=nsteps,STOP_N=6,REST_OPTION=never,RESUBMIT=0,DOUT_S=FALSE
./xmlchange \
  EXEROOT="$CESM/output/ceresmip_fhistc_ltso_smoke_orion/bld"
./case.setup
printf '%s\n' 'use_init_interp = .true.' >> user_nl_clm
./xmlchange BUILD_COMPLETE=TRUE
./preview_namelists

cmp Buildconf/camconf/CESM_cppdefs \
  "$BUILD_CASE/Buildconf/camconf/CESM_cppdefs"
./check_input_data --download
./check_input_data
./case.submit
```

Success requires all of the following:

```bash
tail -n 20 CaseStatus
gzip -cd "$CESM/output/ceresmip_f2000_lt_ne3_smoke_orion/run/"\
"atm.log.260813-192952.gz" | grep 'END OF MODEL RUN'
gzip -cd "$CESM/output/ceresmip_f2000_lt_ne3_smoke_orion/run/"\
"med.log.260813-192952.gz" | grep 'SUCCESSFUL TERMINATION OF CMEPS'
```

The verified run had no fatal, abort, segmentation-fault, or OOM markers in
any component log. CAM's history-field inventory includes diagnostic names
containing `qneg3 error`, and the coarse initial state produced nonfatal
clipping warnings; neither caused a run failure. This result is an
executable/MPI/coupling gate, not a climatological test.

## Input-data boundary for CERES-MIP production

The current shared cache is about 40 GiB and is complete for the coarse
climatological gate. The exact historical ne30 case's missing transient
emissions alone are approximately 77 GiB, while the desktop filesystem has
less free space than that. The interrupted large download was removed; no
partial input file is being treated as valid.

Do not run `check_input_data --download` for the full historical case on the
current root filesystem. Put `DIN_LOC_ROOT` on larger storage first. More
importantly, beta08's stock historical inputs are not the final CERES-MIP
1990-2024 forcing contract: the sanctioned SST/SIC, emissions, volcanic, and
2024 extension choices in `../CERES-MIP/fable/09-run-plan.md` remain required.

The next model milestone is therefore a production-system one-year ne30 F-case
with the agreed 1990-2024 forcing family and requested Amon/CFmon/AERmon/COSP
diagnostics. The MODIS/VIIRS constraint overlay remains deliberately deferred
until that stock baseline is established.
