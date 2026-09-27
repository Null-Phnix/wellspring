"""Real AER regressions plus explicitly synthetic corrupt/edge-case reports."""
import hashlib
from collections import Counter
from pathlib import Path
import zipfile

import pytest

from wellspring.ingest.models import EventType, ReportError
from wellspring.ingest.parser import MAX_REPORT_BYTES, parse_dls, parse_report

FIXTURES = Path(__file__).parents[1] / "fixtures"
REAL = (FIXTURES / "WELLS0925.TXT").read_bytes()
LINES = REAL.decode().splitlines()
END = "    -------------------- END OF WELL LICENCES DAILY LIST  --------------------"


def synthetic(*content):
    return ("\n".join([*LINES[:17], *content, END]) + "\n").encode()


def month_file(name):
    with zipfile.ZipFile(FIXTURES / "dwll2026-08.zip") as z:
        return z.read(name)


def test_real_september_report_sections_and_occurrence_reconciliation():
    r = parse_report(REAL, expected_date="2026-09-25", source_url="fixture:WELLS0925.TXT")
    assert r.issues == []
    assert r.source_block_count == 84
    assert Counter(e.event_type.value for e in r.events) == {
        "issued": 31, "amended": 1, "cancelled": 3, "updated": 13}
    assert sum(e.occurrence_count for e in r.events) == 84
    assert r.source.sha256 == hashlib.sha256(REAL).hexdigest()
    assert r.raw_bytes == REAL


def test_real_butted_columns_are_not_split_on_whitespace():
    e = parse_report(REAL).events[0]
    assert e.licence_number == "0456133"
    assert e.well_purpose == "RESUMPTION"
    assert e.well_type == "PRODUCTION"
    assert e.mineral_rights == "ALBERTA CROWN"
    assert e.ground_elevation_m == 610.2
    assert e.projected_depth_m == 1677.0
    assert e.surface_coordinates_text == "S  259.8M  W  375.5M"
    assert e.field_centre == "BONNYVILLE"
    assert e.aer_classification == "DEV (NC)"
    assert e.licensee == "IMPERIAL OIL RESOURCES LIMITED"


def test_surface_is_not_bottomhole_or_uwi():
    e = parse_report(REAL).events[0]
    assert "16-11" in e.uwi
    assert e.surface_location == "16-12-066-03W4"
    assert e.dls == dict(lsd=16, section=12, township=66, range=3, meridian=4)
    assert e.latitude is e.longitude is e.location_accuracy is None


def test_real_amendment_is_sparse_and_keeps_old_and_changed_name():
    e = next(e for e in parse_report(REAL).events if e.event_type == EventType.AMENDED)
    assert e.well_name == "SPARTAN DELTA HZ WILLGR 15-27-43-9"
    assert e.occurrences[0].changes == [{"field": "well_name", "label": "WELL NAME", "value": "SPARTAN DELTA 102 WILLGR 15-27-43-9"}]
    assert e.licensee is e.projected_depth_m is None


def test_real_same_day_issue_and_cancel_remain_separate_events():
    es = [e for e in parse_report(REAL).events if e.licence_number == "0525808"]
    assert {e.event_type for e in es} == {EventType.ISSUED, EventType.CANCELLED}
    assert len({e.id for e in es}) == 2
    cancel = next(e for e in es if e.event_type == EventType.CANCELLED)
    assert cancel.uwi == "100/00-00-000-00W0/00"
    assert cancel.surface_location is cancel.dls is None


def test_real_multi_uwi_updates_are_all_preserved_in_one_event():
    e = next(e for e in parse_report(REAL).events if e.licence_number == "0516470")
    assert e.occurrence_count > 1
    assert len({o.uwi for o in e.occurrences}) == e.occurrence_count
    assert e.uwi is None  # ambiguous scalar is not an arbitrarily chosen bore
    assert all([c["field"] for c in o.changes] == ["uwi", "well_name", "bottomhole_location"] for o in e.occurrences)
    assert [o.ordinal for o in e.occurrences] == list(range(e.occurrence_count))


def test_source_lines_point_to_exact_original_text():
    for e in parse_report(REAL).events:
        for o in e.occurrences:
            assert o.raw_text == "\n".join(LINES[o.source_line_start - 1:o.source_line_end])


def test_repeated_import_keeps_stable_ids_despite_retrieval_time():
    a = parse_report(REAL, retrieved_at="2026-09-26T00:00:00Z")
    b = parse_report(REAL, retrieved_at="2026-09-27T00:00:00Z")
    assert [e.id for e in a.events] == [e.id for e in b.events]


def test_exact_duplicate_block_is_idempotent_but_counted():
    r = parse_report(synthetic(*LINES[17:22], "", *LINES[17:22]))
    assert len(r.events) == 1
    assert r.source_block_count == 2
    assert r.duplicate_block_count == 1
    assert r.events[0].occurrence_count == 1


def test_synthetic_reentry_section_has_distinct_event_type():
    r = parse_report(synthetic("RE-ENTRY WELL LICENCES", *LINES[17:22]))
    assert r.events[0].event_type == EventType.REENTRY
    assert not r.issues


def test_real_empty_day_is_not_missing_or_failed():
    r = parse_report(month_file("WELLS0801.TXT"), expected_date="2026-08-01")
    assert r.status == "empty" and r.events == [] and r.issues == []


def test_real_alphanumeric_uwis_and_colonless_change_label():
    r = parse_report(month_file("WELLS0804.TXT"))
    assert any(e.uwi.startswith("1F1/") for e in r.events if e.uwi)
    assert any(e.uwi.startswith("1S0/") for e in r.events if e.uwi)
    r = parse_report(month_file("WELLS0810.TXT"))
    assert any(c["field"] == "aer_classification" and c["value"] == "DEV (C)"
               for e in r.events for o in e.occurrences for c in o.changes)
    assert not r.issues


def test_real_august_all_days_and_blocks_reconcile():
    counts, blocks, zero_days = Counter(), 0, 0
    with zipfile.ZipFile(FIXTURES / "dwll2026-08.zip") as z:
        assert len(z.namelist()) == 31
        for name in z.namelist():
            r = parse_report(z.read(name), expected_date=f"2026-08-{name[7:9]}")
            assert not r.issues, (name, r.issues)
            counts.update(e.event_type.value for e in r.events)
            blocks += r.source_block_count
            zero_days += r.status == "empty"
            assert r.source_block_count == sum(e.occurrence_count for e in r.events) + r.duplicate_block_count
    assert counts == {"issued": 406, "amended": 145, "cancelled": 30, "updated": 549}
    assert blocks == 1455
    assert zero_days == 7


@pytest.mark.parametrize("raw", [b"", b"<html>Unavailable</html>", b"x" * (MAX_REPORT_BYTES + 1),
                                  REAL.replace(b"DATE:", b"DAY :"), REAL.replace(b"September", b"Bogus"),
                                  REAL.replace(b"25 September", b"99 September"),
                                  REAL.replace(END.encode(), b""), REAL + b"\x00", REAL + b"\t", REAL + b"\xff",
                                  REAL.replace(b"ALBERTA ENERGY REGULATOR", b"OTHER ENERGY REGULATOR")])
def test_bad_report_envelopes_are_refused(raw):
    with pytest.raises(ReportError):
        parse_report(raw)


def test_rolling_url_wrong_year_is_refused():
    with pytest.raises(ReportError, match="does not match"):
        parse_report(REAL, expected_date="2025-09-25")


def test_conflicting_report_headers_are_refused():
    with pytest.raises(ReportError, match="conflicting"):
        parse_report(REAL.replace(b"DATE:  25 September 2026", b"DATE:  25 September 2026\nDATE: 24 September 2026"))


def test_truncated_record_is_diagnostic_and_keeps_following_valid_record():
    r = parse_report(synthetic(*LINES[17:21], "", *LINES[23:28]))
    assert r.status == "partial" and len(r.issues) == 1
    assert [e.licence_number for e in r.events] == ["0525807"]


@pytest.mark.parametrize("bad", ["NaNM", "infinityM", "12feet", "1.2.3M"])
def test_invalid_numeric_field_is_not_silently_null(bad):
    first = LINES[17][:72] + bad
    r = parse_report(synthetic(first, *LINES[18:22]))
    assert r.events == [] and r.issues[0].code == "malformed_block"


def test_blank_optional_value_remains_null():
    first = LINES[17][:72]
    r = parse_report(synthetic(first, *LINES[18:22]))
    assert not r.issues and r.events[0].ground_elevation_m is None


def test_unknown_section_is_visible_failure():
    r = parse_report(synthetic("WELL LICENCES MYSTERY", *LINES[17:22]))
    assert r.issues[0].code == "unexpected_line"


def test_trailing_garbage_cannot_be_called_empty():
    r = parse_report(synthetic() + b"foreign content\n")
    assert r.status == "partial" and r.issues[0].code == "trailing_content"


@pytest.mark.parametrize("value", [None, "", "00-00-000-00W0", "17-01-010-01W4", "01-37-010-01W4", "01-01-000-01W4", "01-01-010-00W4", "01-01-010-01W9"])
def test_invalid_dls_has_no_coordinates(value):
    assert parse_dls(value) is None


def test_utf8_bom_and_crlf_are_supported():
    assert len(parse_report(b"\xef\xbb\xbf" + REAL).events) == 48


def test_shifted_real_block_cannot_silently_corrupt_touching_fields():
    r = parse_report(synthetic(*(" " + line for line in LINES[17:22])))
    assert r.status == "partial" and not r.events
    assert "fixed columns" in r.issues[0].message


@pytest.mark.parametrize("row", range(5))
def test_individual_shifted_line_is_not_accepted(row):
    block = LINES[17:22].copy()
    block[row] = " " + block[row]
    r = parse_report(synthetic(*block))
    assert r.status == "partial" and not r.events


def test_unknown_cancellation_metadata_is_flagged_not_silently_dropped():
    identifier = LINES[219][:51].ljust(51) + "REASON: TEST"
    r = parse_report(synthetic("WELL LICENCES CANCELLED", LINES[218], identifier))
    assert r.status == "partial" and not r.events
