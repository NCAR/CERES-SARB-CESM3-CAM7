import numpy as np

from sp1_aod_pipeline.qc import qc_mask


def test_qc_mask_golden():
    aod = np.array([0.30, -999.0, 6.0, 0.10, np.nan, 0.00, 5.00])
    qa = np.array([3, 3, 3, 1, 3, 2, 1])
    sigma = np.array([0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10])
    lat = np.full(7, 10.0)
    lon = np.full(7, 20.0)
    mask = qc_mask(aod, qa, sigma, lat, lon, 2, 0.0, 5.0, 5.0)
    assert mask.tolist() == [True, False, False, False, False, True, False]


def test_qa_threshold_changes_result():
    aod = np.array([0.2, 0.2, 0.2])
    qa = np.array([1, 2, 3])
    sigma = np.full(3, 0.1)
    lat = np.zeros(3)
    lon = np.zeros(3)
    assert qc_mask(aod, qa, sigma, lat, lon, 1, 0.0, 5.0, 5.0).tolist() == [
        True,
        True,
        True,
    ]
    assert qc_mask(aod, qa, sigma, lat, lon, 3, 0.0, 5.0, 5.0).tolist() == [
        False,
        False,
        True,
    ]


def test_cloud_edge_and_uncertainty_screening():
    aod = np.array([0.30, 0.30, 0.30, 0.30])
    qa = np.array([3, 3, 3, 3])
    sigma = np.array([0.10, 999.0, 0.10, -0.10])
    lat = np.array([10.0, 10.0, np.nan, 10.0])
    lon = np.array([20.0, 20.0, 20.0, 20.0])
    mask = qc_mask(aod, qa, sigma, lat, lon, 2, 0.0, 5.0, 5.0)
    assert mask.tolist() == [True, False, False, False]
