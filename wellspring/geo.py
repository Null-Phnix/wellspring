"""Offline, approximate Alberta DLS surface-location coordinates.

This is a display approximation, not a surveyed wellhead position. See
``docs/DLS.md`` for the calibration, reference checks, and coverage limits.
"""
from __future__ import annotations

import math
from typing import Any

from .ingest.parser import parse_dls

COORDINATE_METHOD = "alberta_dls_grid_approximation_v1"

# Government of Alberta ATS diagrams number sections and LSDs in alternating
# east/west rows. Each inner row is listed from west to east here.
_LSD_ROWS = (
    (4, 3, 2, 1),
    (5, 6, 7, 8),
    (12, 11, 10, 9),
    (13, 14, 15, 16),
)
_MERIDIAN_LONGITUDE = {4: 110.0, 5: 114.0, 6: 118.0}
_MERIDIAN_OFFSET = {4: 0.0050, 5: 0.0016, 6: 0.0005}
_COVERAGE = {4: (1, 120, 1, 26), 5: (1, 120, 1, 25), 6: (60, 120, 1, 15)}
# Maximum surveyed range by township, compressed into runs from the Government
# of Alberta ATS Township polygon layer (MapServer/0, queried 2026-09-27).
# It limits extrapolation into mountain and meridian-edge gaps. A township
# polygon does not establish that every section or LSD within it exists.
_MAX_SURVEYED_RANGE_RUNS = {
    4: ((18, 30), (34, 29), (54, 28), (70, 27), (90, 26),
        (106, 25), (120, 24)),
    5: ((2, 2), (4, 4), (6, 5), (8, 6), (10, 5), (11, 6),
        (12, 5), (15, 6), (17, 7), (19, 10), (20, 11),
        (22, 12), (23, 13), (24, 14), (25, 15), (26, 16),
        (28, 17), (30, 18), (32, 21), (33, 22), (35, 23),
        (36, 26), (39, 27), (54, 28), (70, 27), (90, 26),
        (106, 25), (120, 24)),
    6: ((38, 0), (40, 2), (44, 3), (46, 5), (47, 6),
        (48, 9), (49, 10), (50, 12), (52, 13), (53, 14),
        (54, 13), (74, 14), (106, 13), (120, 12)),
}


def _valid_dls(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    keys = ("lsd", "section", "township", "range", "meridian")
    if any(type(value.get(key)) is not int for key in keys):
        return None
    dls = {key: value[key] for key in keys}
    if not (1 <= dls["lsd"] <= 16 and 1 <= dls["section"] <= 36
            and 1 <= dls["township"] <= 126 and 1 <= dls["range"] <= 30
            and dls["meridian"] in _MERIDIAN_LONGITUDE):
        return None
    return dls


def _approximate(dls: dict[str, int]) -> tuple[float, float]:
    section_row, within_row = divmod(dls["section"] - 1, 6)
    section_col_from_east = within_row if section_row % 2 == 0 else 5 - within_row
    lsd_row, lsd_col_from_west = next(
        (row, col)
        for row, values in enumerate(_LSD_ROWS)
        for col, number in enumerate(values)
        if number == dls["lsd"]
    )
    miles_from_township_east = section_col_from_east + (3.5 - lsd_col_from_west) / 4
    miles_from_township_south = section_row + (lsd_row + 0.5) / 4

    # Empirical township spacing and meridian offsets, calibrated against the
    # Alberta ATS polygon layer. A 9.77 km range includes road allowances.
    northward_townships = dls["township"] - 1
    latitude = (48.99948 + 0.087374 * northward_townships
                - 0.0000007 * northward_townships**2
                + 0.0873 * miles_from_township_south / 6)
    westward_km = ((dls["range"] - 1) * 9.77
                   + miles_from_township_east * 9.77 / 6)
    longitude = (-_MERIDIAN_LONGITUDE[dls["meridian"]]
                 - _MERIDIAN_OFFSET[dls["meridian"]]
                 - westward_km / (111.32 * math.cos(math.radians(latitude))))
    return latitude, longitude


def _max_surveyed_range(meridian: int, township: int) -> int:
    for last_township, max_range in _MAX_SURVEYED_RANGE_RUNS[meridian]:
        if township <= last_township:
            return max_range
    return 0


def enrich_event(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with nullable, display-only coordinates from surface DLS.

    Only ``dls`` or ``surface_location`` may supply the location. UWI, well
    name, and bottomhole descriptions are deliberately ignored.
    """
    enriched = dict(record)
    enriched.update(latitude=None, longitude=None, coordinate_method=None,
                    location_accuracy=None, location_reason=None)

    if record.get("dls") is not None:
        dls = _valid_dls(record["dls"])
        if dls is None:
            enriched["location_reason"] = "invalid_surface_dls"
            return enriched
    else:
        surface = record.get("surface_location")
        if not isinstance(surface, str) or not surface.strip():
            enriched["location_reason"] = "missing_surface_location"
            return enriched
        dls = parse_dls(surface)
        if dls is None:
            enriched["location_reason"] = "invalid_surface_dls"
            return enriched

    min_township, max_township, min_range, max_range = _COVERAGE[dls["meridian"]]
    if not (min_township <= dls["township"] <= max_township
            and min_range <= dls["range"] <= max_range):
        enriched["location_reason"] = "outside_validated_grid"
        return enriched
    if dls["range"] > _max_surveyed_range(dls["meridian"], dls["township"]):
        enriched["location_reason"] = "outside_surveyed_township_grid"
        return enriched

    latitude, longitude = _approximate(dls)
    enriched.update(latitude=round(latitude, 6), longitude=round(longitude, 6),
                    coordinate_method=COORDINATE_METHOD,
                    location_accuracy="approximate")
    return enriched
