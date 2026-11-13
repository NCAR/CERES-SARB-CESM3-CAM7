import numpy as np
import xarray as xr

from sp1_aod_pipeline import f09_grid as g


CAM_GRID = "/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc"


def test_centers_match_cam_fv_file():
    ds = xr.open_dataset(CAM_GRID, decode_times=False)
    assert g.NLAT == 192 and g.NLON == 288
    assert np.allclose(g.f09_lat(), ds["lat"].values, atol=1e-9)
    assert np.allclose(g.f09_lon(), ds["lon"].values, atol=1e-9)


def test_pole_centered_not_legacy():
    lat = g.f09_lat()
    assert lat[0] == -90.0 and lat[-1] == 90.0
    assert abs((lat[1] - lat[0]) - 180.0 / 191.0) < 1e-12
    assert g.f09_lon()[0] == 0.0


def test_bounds_shapes_and_interior_edges_match_slat():
    ds = xr.open_dataset(CAM_GRID, decode_times=False)
    lb = g.f09_lat_bnds()
    assert lb.shape == (192, 2)
    assert lb[0, 0] == -90.0 and lb[-1, 1] == 90.0
    interior = lb[1:, 0]
    assert np.allclose(interior, ds["slat"].values, atol=1e-9)
    lonb = g.f09_lon_bnds()
    assert lonb.shape == (288, 2)
    assert np.allclose(lonb[0], [-0.625, 0.625])


def test_edges_lengths():
    assert g.lat_edges().shape == (193,)
    assert g.lon_edges().shape == (289,)
    assert g.lon_edges()[0] == -0.625 and g.lon_edges()[-1] == 359.375
