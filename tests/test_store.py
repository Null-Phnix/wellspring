from __future__ import annotations

import hashlib
import math
import sqlite3

import pytest

from wellspring.ingest.models import EventType, LicenceEvent, Occurrence, ParseIssue, ParsedReport, Source
from wellspring.ingest.store import connect, events, import_report, record_attempt


def source(
    raw: bytes, *, url: str = "https://example.test/WELLS0101.TXT", parser_version: str = "0.1.0"
) -> Source:
    return Source(url=url, sha256=hashlib.sha256(raw).hexdigest(), retrieved_at="2026-01-02T12:00:00Z",
                  parser_version=parser_version)


def report(
    raw: bytes = b"report one", *, date: str = "2026-01-01", licence: str = "000123",
    event_type: EventType = EventType.ISSUED, issues: list[ParseIssue] | None = None,
    occurrences: list[Occurrence] | None = None, parser_version: str = "0.1.0", **fields: object,
) -> ParsedReport:
    report_source = source(raw, parser_version=parser_version)
    event_data = {
        "id": f"{date}:{event_type.value}:{licence}", "report_date": date, "event_type": event_type,
        "licence_number": licence, "source": report_source, "well_name": "WELL A",
        "uwi": "100/01-02-003-04W5/00", "licensee": "Acme", "substance": "gas",
        "field_centre": "Calgary", "occurrences": occurrences if occurrences is not None else [
            Occurrence(1, "WELL A", "100/01-02-003-04W5/00", [], 1, 5, "block")
        ],
    }
    event = LicenceEvent(**(event_data | fields))
    return ParsedReport(date, report_source, raw, [event], issues or [], source_block_count=1)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "wellspring.sqlite")
    yield connection
    connection.close()


def scalar(conn, sql: str):
    return conn.execute(sql).fetchone()[0]


def test_connect_migrates_schema_enables_foreign_keys_and_refuses_v1_safely(conn, tmp_path):
    assert scalar(conn, "PRAGMA user_version") == 2
    assert scalar(conn, "SELECT value FROM schema_metadata WHERE key = 'schema_version'") == "2"
    assert scalar(conn, "SELECT value FROM schema_metadata WHERE key = 'record_schema_version'") == "1"
    assert scalar(conn, "PRAGMA foreign_keys") == 1
    legacy_path = tmp_path / "legacy-v1.sqlite"
    legacy = sqlite3.connect(legacy_path)
    legacy.execute("CREATE TABLE preserved(value TEXT NOT NULL)")
    legacy.execute("INSERT INTO preserved(value) VALUES ('keep me')")
    legacy.execute("PRAGMA user_version = 1")
    legacy.commit()
    legacy.close()
    with pytest.raises(RuntimeError, match="cannot be migrated safely"):
        connect(legacy_path)
    legacy = sqlite3.connect(legacy_path)
    assert legacy.execute("SELECT value FROM preserved").fetchone()[0] == "keep me"
    assert legacy.execute("PRAGMA user_version").fetchone()[0] == 1
    legacy.close()


def test_import_returns_event_to_dict_shape(conn):
    value = report()
    result = import_report(conn, value)
    assert result["status"] == "imported"
    assert events(conn) == [value.events[0].to_dict()]


def test_same_raw_sha_is_idempotent(conn):
    value = report()
    import_report(conn, value)
    result = import_report(conn, value)
    assert result["status"] == "idempotent"
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 1
    assert scalar(conn, "SELECT count(*) FROM licence_events") == 1
    assert scalar(conn, "SELECT count(*) FROM ingest_attempts WHERE status = 'idempotent'") == 1


def test_distinct_licences_and_event_types_share_a_date(conn):
    first = report(licence="000123")
    second = report(raw=b"report two", licence="000124", event_type=EventType.AMENDED)
    second.events.append(LicenceEvent(
        id="reentry", report_date=second.report_date, event_type=EventType.REENTRY,
        licence_number="000125", source=second.source,
        occurrences=[Occurrence(1, None, None, [], 1, 1, "reentry")],
    ))
    second.source_block_count = 2
    import_report(conn, first)
    import_report(conn, second)
    assert {(item["licence_number"], item["event_type"]) for item in events(conn)} == {
        ("000124", "amended"), ("000125", "reentry")
    }


def test_valid_revision_replaces_date_and_removes_vanished_events(conn):
    first = report(licence="000123")
    extra = LicenceEvent(id="old-extra", report_date=first.report_date, event_type=EventType.UPDATED,
                         licence_number="000124", source=first.source,
                         occurrences=[Occurrence(1, None, None, [], 1, 1, "old")])
    first.events.append(extra)
    first.source_block_count = 2
    import_report(conn, first)
    replacement = report(raw=b"revised report", licence="000125", licensee="Revised")
    result = import_report(conn, replacement)
    assert result["deleted"] == 2
    assert [item["licence_number"] for item in events(conn)] == ["000125"]
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 2


def test_revision_preserves_raw_history(conn):
    first = report(raw=b"first source")
    revised = report(raw=b"second source")
    import_report(conn, first)
    import_report(conn, revised)
    assert conn.execute("SELECT raw_bytes FROM source_reports ORDER BY id").fetchall()[0][0] == b"first source"
    assert scalar(conn, "SELECT count(*) FROM source_reports WHERE report_date = '2026-01-01'") == 2


def test_partial_report_refuses_current_replacement_but_records_raw_and_issue(conn):
    import_report(conn, report())
    partial = report(raw=b"bad report", licence="000999", issues=[ParseIssue("short_block", "missing lines", 5, 6)])
    result = import_report(conn, partial)
    assert result["status"] == "refused_partial"
    assert [item["licence_number"] for item in events(conn)] == ["000123"]
    assert scalar(conn, "SELECT count(*) FROM parse_issues") == 1
    assert scalar(conn, "SELECT import_status FROM source_reports WHERE raw_bytes = x'626164207265706f7274'") == "partial"


def test_occurrences_and_changes_are_persisted_in_order(conn):
    occurrence = Occurrence(ordinal=4, well_name="first", uwi="u1", changes=[{"field": "licensee", "before": "A", "after": "B"}], source_line_start=4, source_line_end=8, raw_text="block")
    import_report(conn, report(occurrences=[occurrence]))
    assert scalar(conn, "SELECT ordinal FROM event_occurrences") == 4
    assert conn.execute("SELECT field_name, before_value, after_value FROM event_changes").fetchone()[:] == ("licensee", "A", "B")


def test_failure_rolls_back_events_and_source_record(conn):
    duplicate = report(raw=b"dup")
    duplicate.events.append(LicenceEvent(id="duplicate", report_date=duplicate.report_date, event_type=EventType.ISSUED,
                                         licence_number=duplicate.events[0].licence_number, source=duplicate.source,
                                         occurrences=[Occurrence(1, None, None, [], 1, 1, "dup")]))
    duplicate.source_block_count = 2
    with pytest.raises(ValueError, match="duplicate event"):
        import_report(conn, duplicate)
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 0
    assert scalar(conn, "SELECT count(*) FROM licence_events") == 0
    assert scalar(conn, "SELECT count(*) FROM ingest_attempts WHERE status = 'failed'") == 1


def test_bad_source_hash_is_refused_and_attempt_recorded(conn):
    value = report()
    value.source = Source(value.source.url, "0" * 64, value.source.retrieved_at)
    value.events[0].source = value.source
    with pytest.raises(ValueError, match="SHA-256"):
        import_report(conn, value)
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 0
    assert scalar(conn, "SELECT count(*) FROM ingest_attempts WHERE status = 'failed'") == 1


def test_invalid_event_schema_and_enum_are_refused(conn):
    value = report()
    value.events[0].schema_version = 99
    with pytest.raises(ValueError, match="schema_version"):
        import_report(conn, value)
    value = report(raw=b"wrong enum")
    value.events[0].event_type = "issued"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="EventType"):
        import_report(conn, value)
    with pytest.raises(ValueError, match="NaN"):
        import_report(conn, report(raw=b"nan", ground_elevation_m=math.nan))


def test_unique_and_foreign_key_constraints(conn):
    import_report(conn, report())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO licence_events(event_key, report_date, event_type, licence_number,
                     source_report_id, event_json) VALUES ('x', '2026-01-01', 'issued', '000123', 1, '{}')""")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO event_occurrences(licence_event_id, ordinal, source_line_start,
                     source_line_end, raw_text) VALUES (999, 0, 0, 0, 'x')""")


def test_record_attempt_and_status_validation(conn):
    record_attempt(conn, "2026-01-01", "https://example.test", "not_found", "404")
    assert scalar(conn, "SELECT error FROM ingest_attempts") == "404"
    with pytest.raises(ValueError, match="unsupported"):
        record_attempt(conn, "2026-01-01", "https://example.test", "invented")


def test_new_parser_version_can_promote_previously_partial_raw_body(conn):
    partial = report(raw=b"same body", parser_version="0.1.0", licence="000111",
                     issues=[ParseIssue("short", "missing line", 1, 2)])
    assert import_report(conn, partial)["status"] == "refused_partial"
    corrected = report(raw=b"same body", parser_version="0.2.0", licence="000111")
    result = import_report(conn, corrected)
    assert result["status"] == "imported"
    assert [item["licence_number"] for item in events(conn)] == ["000111"]
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 2


def test_new_parser_version_rebuilds_valid_same_raw_body(conn):
    original = report(raw=b"same valid body", parser_version="0.1.0", licensee="Old owner")
    import_report(conn, original)
    rebuilt = report(raw=b"same valid body", parser_version="0.2.0", licensee="Corrected owner")
    result = import_report(conn, rebuilt)
    assert result["status"] == "imported"
    assert result["deleted"] == 1
    assert events(conn)[0]["licensee"] == "Corrected owner"
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 2


def test_accepted_event_requires_an_occurrence(conn):
    with pytest.raises(ValueError, match="at least one occurrence"):
        import_report(conn, report(occurrences=[]))


def test_source_spans_are_one_based(conn):
    bad = Occurrence(1, "A", "u", [], 0, 1, "block")
    with pytest.raises(ValueError, match="line range"):
        import_report(conn, report(occurrences=[bad]))


def test_reselecting_a_historical_source_restores_its_current_events(conn):
    first = report(raw=b"A", licence="000111", licensee="A owner")
    second = report(raw=b"B", licence="000222", licensee="B owner")
    first_id = import_report(conn, first)["source_report_id"]
    import_report(conn, second)
    result = import_report(conn, first)
    assert result["status"] == "reselected"
    assert result["source_report_id"] == first_id
    assert [item["licence_number"] for item in events(conn)] == ["000111"]
    assert scalar(conn, "SELECT source_report_id FROM report_heads WHERE report_date = '2026-01-01'") == first_id


def test_empty_head_can_be_replaced_by_historical_nonempty_source(conn):
    first = report(raw=b"A", licence="000111")
    first_id = import_report(conn, first)["source_report_id"]
    empty_source = source(b"B")
    empty = ParsedReport("2026-01-01", empty_source, b"B", [], [], source_block_count=0)
    import_report(conn, empty)
    assert events(conn) == []
    assert import_report(conn, first)["status"] == "reselected"
    assert [item["licence_number"] for item in events(conn)] == ["000111"]
    assert scalar(conn, "SELECT source_report_id FROM report_heads WHERE report_date = '2026-01-01'") == first_id


def test_failed_replacement_rolls_back_head_and_current_events(conn):
    first = report(raw=b"A", licence="000111")
    first_id = import_report(conn, first)["source_report_id"]
    conn.execute("""CREATE TRIGGER reject_test_event BEFORE INSERT ON licence_events
                  WHEN NEW.licence_number = '000999'
                  BEGIN SELECT RAISE(ABORT, 'test replacement failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="test replacement failure"):
        import_report(conn, report(raw=b"B", licence="000999"))
    assert [item["licence_number"] for item in events(conn)] == ["000111"]
    assert scalar(conn, "SELECT source_report_id FROM report_heads WHERE report_date = '2026-01-01'") == first_id
    assert scalar(conn, "SELECT count(*) FROM source_reports") == 1
