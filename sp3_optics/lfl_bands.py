"""Shared SARB/LFL spectral band constants.

Edges and midpoints are in micrometers.
"""

from __future__ import annotations


LFL_SW_EDGES_UM: tuple[float, ...] = (
    0.1754,
    0.3225,
    0.3575,
    0.4375,
    0.4975,
    0.595,
    0.6896,
    0.794,
    0.889,
    1.042,
    1.41,
    1.9048,
    2.5,
    3.5088,
    4.0,
)

LFL_LW_EDGES_UM: tuple[float, ...] = (
    4.54,
    5.26,
    5.88,
    7.14,
    8.0,
    9.09,
    10.2,
    12.5,
    14.9,
    18.5,
    25.0,
    35.7,
    100.0,
)


def _edge_midpoints(edges: tuple[float, ...]) -> tuple[float, ...]:
    return tuple((left + right) / 2.0 for left, right in zip(edges, edges[1:]))


LFL_SW_MIDPOINTS_UM: tuple[float, ...] = _edge_midpoints(LFL_SW_EDGES_UM)
LFL_LW_MIDPOINTS_UM: tuple[float, ...] = _edge_midpoints(LFL_LW_EDGES_UM)


__all__ = (
    "LFL_SW_EDGES_UM",
    "LFL_LW_EDGES_UM",
    "LFL_SW_MIDPOINTS_UM",
    "LFL_LW_MIDPOINTS_UM",
)
