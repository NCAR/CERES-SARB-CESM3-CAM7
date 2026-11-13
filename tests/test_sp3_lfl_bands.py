from __future__ import annotations

import importlib

import pytest


def _load_lfl_bands():
    try:
        return importlib.import_module("sp3_optics.lfl_bands")
    except ModuleNotFoundError as exc:
        pytest.fail(f"sp3_optics.lfl_bands should define shared LFL constants: {exc}")


def _assert_monotone(values: tuple[float, ...]) -> None:
    assert all(left < right for left, right in zip(values, values[1:]))


def _assert_midpoints_are_edge_averages(
    edges: tuple[float, ...], midpoints: tuple[float, ...]
) -> None:
    assert len(midpoints) == len(edges) - 1
    for left, right, midpoint in zip(edges, edges[1:], midpoints):
        assert midpoint == (left + right) / 2.0


def test_lfl_sw_edges_match_documented_bands() -> None:
    bands = _load_lfl_bands()

    assert len(bands.LFL_SW_EDGES_UM) == 15
    _assert_monotone(bands.LFL_SW_EDGES_UM)
    assert bands.LFL_SW_EDGES_UM[0:2] == (0.1754, 0.3225)


def test_lfl_lw_edges_match_documented_bands() -> None:
    bands = _load_lfl_bands()

    assert len(bands.LFL_LW_EDGES_UM) == 13
    _assert_monotone(bands.LFL_LW_EDGES_UM)
    assert bands.LFL_LW_EDGES_UM[5:7] == (9.09, 10.2)


def test_lfl_midpoints_are_arithmetic_edge_averages() -> None:
    bands = _load_lfl_bands()

    _assert_midpoints_are_edge_averages(
        bands.LFL_SW_EDGES_UM, bands.LFL_SW_MIDPOINTS_UM
    )
    _assert_midpoints_are_edge_averages(
        bands.LFL_LW_EDGES_UM, bands.LFL_LW_MIDPOINTS_UM
    )
