#!/usr/bin/env python
"""Stage MODIS L2 aerosol (MOD04/MYD04 C6.1) + AERONET into the project obs root.

Pre-implementation staging for the SP1 obs pipeline. Layout (user-set 2026-06-27):

  $ROOT/MODIS_VIIRS_L2/<DATASET>/<YYYYMMDD>/<native granules>   # MOD04_L2 / MYD04_L2
  $ROOT/AeroNet/AeroNet_<YYYYMMDD>.nc                           # DAVINCI AERONETReader

with $ROOT = /glade/work/fillmore/Data/CERES-SARB-CAM7 (persistent /work).

Default period = JULY 2008 — the test month. It PREDATES VIIRS (SNPP 2011,
NOAA-20 2017), so this is MODIS-only (Terra + Aqua). Global (no bbox), since the
f09 nudging product is global. The preserved two-sensor cache is ~51 GB / ~19k
granules for the month.

CMR notes (verified 2026-06-27): MOD04_L2/MYD04_L2 collection 6.1 has CMR
VersionId **"6.1"** (NOT "61"; the "061" in the filename is a different token),
provider LAADS. AERONET pulled at **Level 2.0 ("AOD20")** since 2008 is finalized.

Run on a derecho login/interactive node (outbound internet). EarthData creds in
~/.netrc. Idempotent: existing granules/day-files are skipped, so re-runs resume.

  python scripts/stage_obs.py --dry-run          # search-only: counts + sizes
  python scripts/stage_obs.py                     # stage MODIS + AERONET, July 2008
  python scripts/stage_obs.py --what aeronet      # AERONET only
"""
import argparse
import datetime as dt
import os
import warnings

ROOT = "/glade/work/fillmore/Data/CERES-SARB-CAM7"

# CMR short_name -> (on-disk dataset label, CMR VersionId)
MODIS_DATASETS = {
    "MOD04_L2": ("MODIS_TERRA_AEROSOL", "6.1"),
    "MYD04_L2": ("MODIS_AQUA_AEROSOL", "6.1"),
}


def _days(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def stage_modis(start, end, root, dry):
    import earthaccess
    warnings.filterwarnings("ignore")
    earthaccess.login(strategy="netrc")
    rows, grand_n, grand_mb = [], 0, 0.0
    for short_name, (label, version) in MODIS_DATASETS.items():
        for day in _days(start, end):
            ymd = day.strftime("%Y%m%d")
            dest = os.path.join(root, "MODIS_VIIRS_L2", label, ymd)
            t0 = day.strftime("%Y-%m-%d")
            t1 = (day + dt.timedelta(days=1)).strftime("%Y-%m-%d")
            res = earthaccess.search_data(short_name=short_name, version=version,
                                          temporal=(t0, t1))
            mb = 0.0
            for g in res:
                try:
                    mb += float(g["size"])
                except Exception:
                    pass
            rows.append((short_name, ymd, len(res), round(mb, 1)))
            grand_n += len(res)
            grand_mb += mb
            print(f"{short_name} {ymd}: {len(res):3d} granules ~{mb:6.0f} MB -> {dest}")
            if dry or not res:
                continue
            os.makedirs(dest, exist_ok=True)
            have = len([f for f in os.listdir(dest) if f.endswith(".hdf")])
            if have >= len(res):
                print(f"  skip (already have {have})")
                continue
            earthaccess.download(res, dest)
    print(f"\nMODIS total: {grand_n} granules ~{grand_mb / 1024:.1f} GB")
    if not dry:
        man = os.path.join(root, "MODIS_VIIRS_L2",
                           f"manifest_{start:%Y%m%d}_{end:%Y%m%d}.tsv")
        with open(man, "w") as f:
            f.write("short_name\tdate\tgranules\tsize_mb\n")
            for r in rows:
                f.write("\t".join(map(str, r)) + "\n")
        print("manifest ->", man)


def stage_aeronet(start, end, root, dry, product="AOD20"):
    from davinci_monet.datasets.surface.aeronet import AERONETReader
    out = os.path.join(root, "AeroNet")
    if not dry:
        os.makedirs(out, exist_ok=True)
    reader = AERONETReader()
    for day in _days(start, end):
        ymd = day.strftime("%Y%m%d")
        fp = os.path.join(out, f"AeroNet_{ymd}.nc")
        if os.path.exists(fp):
            print(f"AERONET {ymd}: have {fp}")
            continue
        print(f"AERONET {ymd}: download ({product}) -> {fp}")
        if dry:
            continue
        # freq="h": hourly-resample (monetio) so the file is the compact (time<=24, site)
        # grid like the existing cache. Raw sub-hourly AERONET pivots to a huge dense
        # time x site array (~0.5 GB/day, mostly NaN) that OOMs the reader.
        # pandas>=2.2 deprecated the "H" alias; pandas 3 removed it (needs lowercase "h").
        ds = reader.open(dates=[day.strftime("%Y-%m-%d"),
                                (day + dt.timedelta(days=1)).strftime("%Y-%m-%d")],
                         product=product, freq="h")
        ds.to_netcdf(fp)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default="2008-07-01")
    p.add_argument("--end", default="2008-07-31")
    p.add_argument("--root", default=ROOT)
    p.add_argument("--what", choices=["modis", "aeronet", "all"], default="all")
    p.add_argument("--aeronet-product", default="AOD20")
    p.add_argument("--dry-run", action="store_true", help="search/report only; no download")
    a = p.parse_args()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end)
    if a.what in ("modis", "all"):
        stage_modis(start, end, a.root, a.dry_run)
    if a.what in ("aeronet", "all"):
        stage_aeronet(start, end, a.root, a.dry_run, a.aeronet_product)


if __name__ == "__main__":
    main()
