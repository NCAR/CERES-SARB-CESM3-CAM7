"""Stage SP1 LAADS L2 products via davinci_monet's Earthdata staging core."""

from pathlib import Path

from davinci_monet.io.download.earthdata import CollectionSpec, stage_collection

SP1_COLLECTIONS = {
    "mod04": CollectionSpec("MOD04_L2", Path("modis/terra"), version="6.1"),
    "myd04": CollectionSpec("MYD04_L2", Path("modis/aqua"), version="6.1"),
    "aerdb_noaa20": CollectionSpec(
        "AERDB_L2_VIIRS_NOAA20", Path("viirs/noaa20"), version="2"
    ),
}


def stage_sp1(
    collection,
    start,
    end,
    dest_root,
    *,
    dry_run=False,
    login=None,
    search=None,
    download=None,
):
    try:
        spec = SP1_COLLECTIONS[collection]
    except KeyError:
        known = ", ".join(sorted(SP1_COLLECTIONS))
        raise KeyError(
            f"Unknown SP1 collection {collection!r}. Known: {known}"
        ) from None
    temporal = (start, end) if start is not None and end is not None else None
    dest = Path(dest_root) / spec.subpath
    return stage_collection(
        spec,
        temporal,
        dest,
        dry_run=dry_run,
        login=login,
        search=search,
        download=download,
    )
