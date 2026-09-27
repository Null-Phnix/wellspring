"""The model's SQL must remain inside the public, bounded event projection."""

from __future__ import annotations

import time

import pytest

from wellspring.api.query import QueryRefusal, SCHEMA_TEXT, execute_readonly


@pytest.fixture
def records():
    return [
        {"id": "a", "licence_number": "00123", "report_date": "2026-09-01", "event_type": "issued",
         "licensee": "O'Brien Energy", "substance": "Gas", "latitude": 53.1,
         "longitude": -113.5, "source": {"url": "https://example.invalid/private"}},
        {"id": "b", "licence_number": "00124", "report_date": "2026-09-02", "event_type": "amended",
         "licensee": "Other", "substance": "Oil", "latitude": None, "longitude": None},
        {"id": "c", "licence_number": "00125", "report_date": "2026-09-02", "event_type": "issued",
         "licensee": None, "substance": "Gas", "latitude": 54.0, "longitude": -112.0},
    ]


def run(records, sql, deadline=None):
    return execute_readonly(records, sql, time.monotonic() + 5 if deadline is None else deadline)


def refused(records, sql, code=None):
    with pytest.raises(QueryRefusal) as caught:
        run(records, sql)
    if code:
        assert caught.value.code == code
    assert caught.value.message
    assert "sqlite" not in caught.value.message.lower()
    assert "/tmp" not in caught.value.message


def test_schema_is_only_public_projection():
    assert "CREATE TABLE events" in SCHEMA_TEXT
    assert "source" not in SCHEMA_TEXT
    assert "licence_number" in SCHEMA_TEXT


def test_select_preserves_typed_values_and_leading_zeros(records):
    result = run(records, "SELECT licence_number, latitude FROM events ORDER BY id")
    assert result == {"columns": ["licence_number", "latitude"], "rows": [
        {"licence_number": "00123", "latitude": 53.1},
        {"licence_number": "00124", "latitude": None},
        {"licence_number": "00125", "latitude": 54.0},
    ], "row_count": 3, "truncated": False}


def test_aggregation_and_iso_date_function(records):
    result = run(records, "SELECT date(report_date, 'start of month') AS month, "
                  "COUNT(*) AS n FROM events GROUP BY month")
    assert result["rows"] == [{"month": "2026-09-01", "n": 3}]


def test_quoted_apostrophe_and_semicolon(records):
    result = run(records, "SELECT licence_number FROM events WHERE licensee = 'O''Brien Energy' AND ';' = ';';")
    assert result["rows"] == [{"licence_number": "00123"}]


def test_quoted_comment_markers_are_data(records):
    result = run(records, "SELECT '-- /* ; */' AS marker FROM events LIMIT 1")
    assert result["rows"] == [{"marker": "-- /* ; */"}]


@pytest.mark.parametrize("sql", [
    "INSERT INTO events(id) VALUES('x')", "UPDATE events SET licensee='x'",
    "DELETE FROM events", "DROP TABLE events", "PRAGMA table_info(events)",
    "ATTACH DATABASE '/tmp/anything' AS secret",
    "SELECT * FROM events; DELETE FROM events",
    "SELECT * FROM events; -- hide more SQL",
    "SELECT id FROM events; 'ignored suffix'",
    'SELECT id FROM events; "ignored suffix"',
    "SELECT * FROM events /* comment */",
    "WITH x AS (SELECT * FROM events) SELECT * FROM x",
    "SELECT * FROM sqlite_master",
    "SELECT load_extension('x') FROM events",
])
def test_unsafe_or_unsupported_sql_is_refused(records, sql):
    refused(records, sql)


def test_source_metadata_is_not_queryable(records):
    refused(records, "SELECT source FROM events")


def test_quoted_system_table_is_not_queryable(records):
    refused(records, 'SELECT name FROM "sqlite_master"')


def test_comments_do_not_bypass_select_gate(records):
    refused(records, "/* prefix */ SELECT id FROM events", "INVALID_SQL")


def test_duplicate_aliases_are_refused(records):
    refused(records, "SELECT id AS x, licence_number AS x FROM events", "RESULT_LIMIT")


def test_missing_table_is_refused(records):
    refused(records, "SELECT * FROM missing")


def test_row_cap_uses_201st_row_for_truncation():
    records = [{"id": str(index)} for index in range(201)]
    result = run(records, "SELECT id FROM events ORDER BY CAST(id AS INTEGER)")
    assert result["row_count"] == len(result["rows"]) == 200
    assert result["truncated"] is True
    assert result["rows"][-1] == {"id": "199"}


def test_exactly_200_rows_is_not_marked_truncated():
    result = run([{"id": str(index)} for index in range(200)], "SELECT id FROM events")
    assert result["row_count"] == 200
    assert result["truncated"] is False


def test_expired_deadline_refuses_before_build(records):
    with pytest.raises(QueryRefusal) as caught:
        run(records, "SELECT * FROM events", deadline=time.monotonic() - 1)
    assert caught.value.code == "QUERY_TIMEOUT"


def test_expensive_query_hits_shared_deadline():
    records = [{"id": str(index)} for index in range(300)]
    with pytest.raises(QueryRefusal) as caught:
        run(records, "SELECT COUNT(*) FROM events a, events b, events c",
            deadline=time.monotonic() + 0.1)
    assert caught.value.code == "QUERY_TIMEOUT"


def test_sql_and_result_cell_limits(records):
    refused(records, "SELECT '" + "a" * 4096 + "' FROM events", "INVALID_SQL")
    records[0]["licensee"] = "\n" * 2200
    refused(records, "SELECT licensee FROM events WHERE id='a'", "RESULT_LIMIT")


def test_total_result_limit():
    records = [{"id": str(index), "licensee": "x" * 3000} for index in range(100)]
    refused(records, "SELECT licensee FROM events", "RESULT_LIMIT")


def test_invalid_unicode_sql_is_sanitized(records):
    refused(records, "SELECT '\ud800' FROM events", "INVALID_SQL")


def test_input_records_and_file_are_unchanged(records, tmp_path):
    before = [dict(item) for item in records]
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    refused(records, f"ATTACH DATABASE '{sentinel}' AS secret")
    refused(records, "DELETE FROM events")
    assert records == before
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_bad_public_input_is_sanitized(records):
    records[0]["latitude"] = float("nan")
    with pytest.raises(QueryRefusal) as caught:
        run(records, "SELECT latitude FROM events")
    assert caught.value.code == "QUERY_UNAVAILABLE"
    assert "nan" not in caught.value.message.lower()
