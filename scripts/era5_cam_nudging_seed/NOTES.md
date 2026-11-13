# ERA5-to-CAM conversion seed

Copied byte-for-byte on 2026-09-08 from the authorized read-only source
`/glade/work/tvmora/Gen_Data_f09_dev/`. The source stack reads GDEX `d633006`
ERA5 T, Q, U, V, surface pressure, and invariant geopotential and writes CAM FV
nudging files.

This is an inactive seed, not a production-ready converter. Before running it:

- replace the hard-coded collaborator scratch output with a `fillmore` path;
- replace the L30 target initial-condition file with the CAM7 case's f09/L32 file;
- align the generated `.cam7.i.` filename with our `.cam2.i.` nudging template;
- parameterize the exact `2007-12-22 00` through `2009-01-01 00` window;
- smoke-test one hour and verify `lat=192`, `lon=288`, `lev=32`, hybrid
  coefficients, U/V/T/Q/PS, timestamps, and the terminal boundary file.

Do not edit or execute files in the collaborator tree. Adapt a copy of this seed
inside the repository and write generated NetCDF files below
`/glade/work/fillmore/Data/CERES-SARB-CAM7/`.

The focused Python translation is now `scripts/generate_era5_cam_nudging.py`.
Its versioned March-gap configuration is
`config/era5/march_2008_gap_v1.yaml`; the neighboring-hour validation config is
`config/era5/smoke_20080308_23_v1.yaml`. The Python converter preserves this
seed for provenance and ports only the ERA5 N320/L137 to CAM f09/L32 path. Run
its `preflight` command before any production conversion and submit multi-day
work with `scripts/submit_era5_cam_nudging_pbs.py`; generated files are refused
outside the project Data tree and existing files are never overwritten.
