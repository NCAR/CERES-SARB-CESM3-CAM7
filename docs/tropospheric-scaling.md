# Tropospheric MODIS scaling

Set the same CAM namelist option in CAM6 and CAM7:

```fortran
aod_nudge_on = .true.
aod_tropo_only = .true.
```

`aod_tropo_only` defaults to `.false.`, which retains the existing whole-column
algorithm. It is broadcast with the other controls in `aod_nudging_nl`.

The tropospheric mode uses CAM's existing tropopause diagnostic: its native
TWMO lapse-rate algorithm with the climatology fallback. This is already the
CAM default in both pinned source versions; see the
[CAM tropopause source documentation](https://docs.cesm.ucar.edu/models/cesm1/browser/html_code/cam/tropopause.F90.html)
for the established algorithm names. CAM6 calls `tropopause_find`; CAM7 calls
`tropopause_find_cam`. No new tropopause algorithm is introduced.

CAM level indices increase downward. Only `k > tropLev(column)` is eligible.
The diagnosed tropopause level and every level above it are excluded. The
boundary is diagnosed once and held fixed across the current update and its
before/after optical probes. An invalid tropopause index produces an empty
eligible mask and skips the tropospheric update.

At 550 nm, the native optics adapter separates the total model AOD into the
eligible layers and the excluded part, including the tropopause level:

```text
fixed_AOD = total_AOD - eligible_AOD
ratio = clamp(max(observed_AOD - fixed_AOD, 0) / eligible_AOD, 0.1, 10)
```

The existing valid-observation guards remain, and `aod_eps` applies to eligible
AOD in tropospheric mode. Targets below the fixed AOD cannot be reached without
changing the excluded atmosphere; those cases reach the lower ratio clamp.
Whole-column mode retains its original observed/total ratio and total-AOD guard.
The partition diagnostics use the same boundary in both modes; the excluded
part is held fixed only in tropospheric mode.

The same mask restricts interstitial species mass, modal/bin number, bulk
species mass, cached bounded number (`NAER`), and aerosol water (`QAERWAT`).
Scaling mass and number together preserves modal size and composition within
eligible layers. Cloud-borne aerosols remain unchanged. Both repositories use
identical compiled kernel code for the ratio, index boundary, and masked state
updates; model-specific adapters retain their native optics interfaces.

## July comparison

`config/tropospheric-july2008.json` records the complete experiment. Each model
has two matched startup cases: June 21 through August 1, 2008, with ten June
spinup days and exactly 248 three-hourly July samples. One newly built executable
per model is shared by the pair; `aod_tropo_only` is the sole scientific namelist
difference. The whole-column rerun adds the instantaneous profile diagnostics
needed for this comparison while retaining the existing scaling algorithm.
Completed historical cases and their outputs are preserved.

The CAM6 pair retains the previous FHIST configuration. The CAM7 pair clones
the existing CERES-MIP historical ERA5/MODIS case, preserving its forcing and
radiation constituent definitions. Both use the checksum-verified MODIS C7
archive owned by fillmore. Cross-model differences still include their different
physics, meteorology, forcing, and initialization; the within-model pairs
isolate the scaling option.

The setup uses isolated case SourceMods and namelist XML. It does not deploy
into or modify either shared CESM checkout. Cloned CAM caches are regenerated
to avoid retaining the original case's SourceMods path. CAM6 uses the develop
queue; CAM7 uses the regular main queue so the two pairs can run independently
of the development queue's per-user CPU limit.

```bash
python scripts/setup_tropospheric_july2008.py --mode tropo
qsub -o /absolute/project-data/logs/tropospheric-july2008-v1/build.log \
  scripts/build_tropospheric_july2008.pbs
# After the build succeeds:
python scripts/setup_tropospheric_july2008.py --mode column
# Use the DAVINCI Python environment for this submission helper:
python scripts/submit_tropospheric_pair.py
```

The setup rejects existing case/build/run paths. Another experiment needs unique
paths in its plan. Submission rejects duplicate recorded attempts, verifies the
shared executable/SourceMods and matched namelists, submits both models through
CIME, and schedules the complete verification/DAVINCI workflow after both succeed.

## Evidence and profiles

Additional instantaneous history fields preserve the eligible mask, native
tropopause level/pressure, model midlevel pressure, eligible/excluded AOD, and
aggregate aerosol mass and number profiles immediately before and after each
sampled update. Mass sums all enumerated interstitial and bulk species; number
sums interstitial modes and bins. Aerosol water and cloud-borne mass are not part
of the dry-aerosol profile sum.

The reader accepts CAM6's `h0` and CAM7's `h0i` first-tape naming.
The July verifier checks every archived July sample for the correct mask,
clamps, residual-target fit, optical partition, and expected profile scaling.
It requires **exactly zero mass and number increment at every protected
profile cell** in the tropospheric case. The whole-column reference must show
nonzero protected-layer increments, establishing the behavior that changed.
Compiled adapter tests additionally exercise each individual excluded tracer,
number field, bulk/bin path, cache, inactive column, and failed diagnosis.

The DAVINCI YAML produces ten PDFs per model: three AOD maps and seven vertical
profiles. Profiles show whole-column and tropospheric analyzed mass, their
state difference, and each method's mass/number analysis increments. The profile
axis is a simple native model-level offset from the diagnosed tropopause:
zero is the excluded tropopause level, positive is above, and negative is below.
Each point is the area-weighted July mean over available columns at that offset.
Each trajectory uses its own contemporaneous tropopause; the columns contributing
at the largest offsets can differ between the two profiles.
Absolute mass profiles display log10(MMR in kg/kg); mass differences/increments
use ng/kg. This avoids interpolating the tropopause or smearing a zero increment
across its boundary.

A zero direct stratospheric increment does **not** imply identical stratospheric
profiles between the two evolving runs. Transport, subsequent physics, and a
moving tropopause can produce later differences. The before/after update check
is the test for unintended stratospheric nudging.

All figures are generated through the complete DAVINCI pipeline under PBS and
are promoted only after numerical, automated, and visual checks pass. Raw runs,
verification JSON, history checksum manifests, and accepted PDFs live under the
model's `Data/CERES-SARB-CAM6` or `Data/CERES-SARB-CAM7` tree. The run-history
records retain job IDs, source hashes, and completion evidence.

## Verified July 2008 results

All four 41-day integrations finished with PBS exit zero. Each pair has exactly
248 consecutive July samples. CAM6 additionally writes the initial June 21
00:00 sample (329 total records); CAM7 starts history at 03:00 (328 records).
Both preserve the August 1 boundary and exclude it from July means.

| Model | Whole-column mean AOD | Tropospheric mean AOD | Change | Protected cells checked, new mode |
| --- | ---: | ---: | ---: | ---: |
| CAM6 | 0.17947168 | 0.17482069 | -2.591% | 198,684,925 |
| CAM7 | 0.18910808 | 0.18856361 | -0.288% | 195,393,712 |

Every protected cell has **exactly zero** direct mass and number increment in
the new mode. The excluded optical depth also remains exactly unchanged. Both
whole-column references have nonzero protected-layer increments. All sampled
guards, clamps, optical partitions, profile scaling, inactive-column checks, and
unclamped MODIS target checks pass.

The whole-column CAM6 rerun reproduces all 248 previously accepted July
analyzed-AOD samples **bit for bit**. The new whole-column CAM7 mean differs
from its archived three-month-spinup reference by only -0.00091054 AOD
(-0.479%); its spatial correlation with that archive is 0.999745. The differing
spinup and sampling make the CAM7 archive a context check rather than an exact
reproduction test.

| CAM6 versus CAM7 | Mean bias | Relative mean difference | Spatial RMSE | Spatial correlation | Area within 0.05 AOD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Whole-column | -0.00963640 | -5.096% | 0.04076279 | 0.971101 | 91.59% |
| Tropospheric | -0.01374293 | -7.288% | 0.04564837 | 0.964758 | 88.72% |

The AOD patterns remain closely correlated between models. Tropospheric
scaling changes CAM6 more than CAM7 in this experiment; these tests do not
isolate why. CAM6 retains FHIST meteorology and CAM7 retains ERA5 nudging, in
addition to their differing physics and forcing.

Both full DAVINCI pipelines passed automated inspection and visual review.
Twenty accepted PDFs (ten per model) are retained under:

- `/glade/work/fillmore/Data/CERES-SARB-CAM6/plots/tropospheric-july2008-v1`
- `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/tropospheric-july2008-v1`

The accepted mass and number increment profiles lie at zero at and above the
excluded tropopause level. Whole-column profiles show increments there; the
new trajectories also have lower analyzed mass aloft. Monthly mean increments
can cancel, so the exact-zero conclusion uses every archived pre/post cell,
supported by compiled individual-field tests.

Validation includes ten CAM6 unit tests, 45 focused CAM7 tests, and both native
model builds. Small numerical summaries are versioned in
[`run_history/results/tropospheric-july2008-v1.json`](../run_history/results/tropospheric-july2008-v1.json)
and the identical cross-model summary in
[`run_history/results/tropospheric-july2008-cross-model.json`](../run_history/results/tropospheric-july2008-cross-model.json).
The paired run records link scheduler evidence, history checksum manifests,
full verification JSON, visual reviews, and accepted-PDF checksums.
