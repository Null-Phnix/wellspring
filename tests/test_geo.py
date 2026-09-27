"""Checks against Government of Alberta ATS polygons, not generated coordinates."""
import json
import math
from pathlib import Path

import pytest

from wellspring.geo import COORDINATE_METHOD, enrich_event


REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "dls-reference.json")
    .read_text(encoding="utf-8")
)["references"]


def _distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    lat_a, lat_b = map(math.radians, (latitude_a, latitude_b))
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    h = (math.sin(delta_lat / 2) ** 2
         + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


@pytest.mark.parametrize("reference", REFERENCE, ids=lambda item: item["descriptor"])
def test_approximation_against_government_lsd_polygon(reference):
    actual = enrich_event({"dls": reference["dls"]})
    assert actual["coordinate_method"] == COORDINATE_METHOD
    assert actual["location_accuracy"] == "approximate"
    assert actual["location_reason"] is None
    assert _distance_km(actual["latitude"], actual["longitude"],
                        reference["latitude"], reference["longitude"]) < 1.5


def test_at_least_five_independent_polygon_checks():
    checks = [item for item in REFERENCE if item["role"] == "verification"]
    assert len(checks) >= 5
    assert len({item["object_id"] for item in checks}) == len(checks)
    assert {item["dls"]["meridian"] for item in checks} == {4, 5, 6}
    assert all(item["url"].startswith("https://geospatial.alberta.ca/") for item in checks)


def test_surface_location_fallback_and_no_input_mutation():
    original = {"surface_location": "16-12-066-03W4", "latitude": 0,
                "longitude": 0, "well_name": "example"}
    actual = enrich_event(original)
    assert original["latitude"] == original["longitude"] == 0
    assert actual["latitude"] is not None and actual["longitude"] is not None
    assert actual["location_reason"] is None


@pytest.mark.parametrize("record,reason", [
    ({}, "missing_surface_location"),
    ({"uwi": "100/16-12-066-03W4/0", "well_name": "16-12-066-03W4"},
     "missing_surface_location"),
    ({"surface_location": "garbled"}, "invalid_surface_dls"),
    ({"dls": {"lsd": True, "section": 1, "township": 1,
              "range": 1, "meridian": 4}}, "invalid_surface_dls"),
    ({"surface_location": "01-01-001-01W6"}, "outside_validated_grid"),
    ({"surface_location": "01-01-121-01W4"}, "outside_validated_grid"),
    ({"surface_location": "01-01-050-27W4"}, "outside_validated_grid"),
    ({"surface_location": "01-01-001-10W5"}, "outside_surveyed_township_grid"),
    ({"surface_location": "01-01-080-15W6"}, "outside_surveyed_township_grid"),
    ({"surface_location": "01-01-120-25W4"}, "outside_surveyed_township_grid"),
])
def test_no_unfounded_coordinates(record, reason):
    actual = enrich_event(record)
    assert actual["latitude"] is actual["longitude"] is None
    assert actual["coordinate_method"] is actual["location_accuracy"] is None
    assert actual["location_reason"] == reason
