"""SQLite persistence for immutable ST1 source reports and current events.

The database keeps every distinct source body seen for a report date.  The
``licence_events`` table is deliberately a materialized *current* view for a
date: a successfully parsed replacement atomically deletes that date's old
rows before inserting the new rows.  The source rows remain available for an
audit or a future reparse.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .models import EventType, LicenceEvent, ParseIssue, ParsedReport, SCHEMA_VERSION, Source


_ATTEMPT_STATUSES = frozenset(
    {"imported", "reselected", "idempotent", "refused_partial", "failed", "not_found", "fetch_failed", "parse_failed", "error"}
)
_STORE_SCHEMA_VERSION = 2
_EVENT_COLUMNS = (
    "well_name", "uwi", "mineral_rights", "surface_coordinates_text", "field_centre",
    "aer_classification", "field", "terminating_zone", "drilling_operation", "well_purpose",
    "well_type", "substance", "licensee", "surface_location", "ground_elevation_m",
    "projected_depth_m", "latitude", "longitude", "coordinate_method", "location_accuracy",
)


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (and migrate) a local Wellspring database."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        _migrate(conn)
    except Exception:
        conn.close()
        raise
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    # ``user_version`` makes incompatible future migrations explicit while the
    # metadata row is useful to consumers which only have SQL access.
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > _STORE_SCHEMA_VERSION:
        raise RuntimeError(f"database schema {version} is newer than supported {_STORE_SCHEMA_VERSION}")
    if version == 0:
        conn.executescript(
            """
            BEGIN;
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE source_reports (
                id INTEGER PRIMARY KEY,
                report_date TEXT NOT NULL,
                source_url TEXT NOT NULL,
                sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
                raw_bytes BLOB NOT NULL,
                retrieved_at TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                import_status TEXT NOT NULL CHECK(import_status IN ('valid', 'partial')),
                created_at TEXT NOT NULL,
                -- A parser update is a new interpretation of the same source
                -- body, and therefore must be retained and eligible to replace
                -- the current date's materialized events.
                UNIQUE(report_date, sha256, parser_version),
                UNIQUE(id, report_date)
            );
            CREATE INDEX source_reports_date_idx ON source_reports(report_date, id DESC);

            CREATE TABLE licence_events (
                id INTEGER PRIMARY KEY,
                event_key TEXT NOT NULL,
                report_date TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('issued', 'reentry', 'amended', 'cancelled', 'updated')),
                licence_number TEXT NOT NULL,
                source_report_id INTEGER NOT NULL REFERENCES source_reports(id) ON DELETE RESTRICT,
                event_json TEXT NOT NULL CHECK(json_valid(event_json)),
                well_name TEXT,
                uwi TEXT,
                mineral_rights TEXT,
                surface_coordinates_text TEXT,
                field_centre TEXT,
                aer_classification TEXT,
                field TEXT,
                terminating_zone TEXT,
                drilling_operation TEXT,
                well_purpose TEXT,
                well_type TEXT,
                substance TEXT,
                licensee TEXT,
                surface_location TEXT,
                ground_elevation_m REAL,
                projected_depth_m REAL,
                latitude REAL,
                longitude REAL,
                coordinate_method TEXT,
                location_accuracy TEXT,
                UNIQUE(licence_number, event_type, report_date)
            );
            CREATE INDEX licence_events_date_idx ON licence_events(report_date);
            CREATE INDEX licence_events_licensee_idx ON licence_events(licensee);
            CREATE INDEX licence_events_substance_idx ON licence_events(substance);
            CREATE INDEX licence_events_field_centre_idx ON licence_events(field_centre);
            CREATE INDEX licence_events_terminating_zone_idx ON licence_events(terminating_zone);
            CREATE INDEX licence_events_well_type_idx ON licence_events(well_type);

            -- Snapshots retain parsed output for every valid source version.
            -- ``licence_events`` remains the compact current materialization.
            CREATE TABLE report_event_snapshots (
                id INTEGER PRIMARY KEY,
                source_report_id INTEGER NOT NULL REFERENCES source_reports(id) ON DELETE CASCADE,
                event_key TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('issued', 'reentry', 'amended', 'cancelled', 'updated')),
                licence_number TEXT NOT NULL,
                event_json TEXT NOT NULL CHECK(json_valid(event_json)),
                UNIQUE(source_report_id, licence_number, event_type)
            );
            CREATE INDEX report_event_snapshots_source_idx ON report_event_snapshots(source_report_id);

            CREATE TABLE report_heads (
                report_date TEXT PRIMARY KEY,
                source_report_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_report_id, report_date)
                    REFERENCES source_reports(id, report_date) ON DELETE RESTRICT
            );

            CREATE TABLE event_occurrences (
                id INTEGER PRIMARY KEY,
                licence_event_id INTEGER NOT NULL REFERENCES licence_events(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                well_name TEXT,
                uwi TEXT,
                source_line_start INTEGER NOT NULL CHECK(source_line_start >= 1),
                source_line_end INTEGER NOT NULL CHECK(source_line_end >= source_line_start),
                raw_text TEXT NOT NULL,
                UNIQUE(licence_event_id, ordinal)
            );
            CREATE INDEX event_occurrences_uwi_idx ON event_occurrences(uwi);

            CREATE TABLE event_changes (
                id INTEGER PRIMARY KEY,
                occurrence_id INTEGER NOT NULL REFERENCES event_occurrences(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                change_json TEXT NOT NULL CHECK(json_valid(change_json)),
                field_name TEXT,
                before_value TEXT,
                after_value TEXT,
                UNIQUE(occurrence_id, ordinal)
            );

            CREATE TABLE parse_issues (
                id INTEGER PRIMARY KEY,
                source_report_id INTEGER NOT NULL REFERENCES source_reports(id) ON DELETE CASCADE,
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                line_start INTEGER NOT NULL CHECK(line_start >= 1),
                line_end INTEGER NOT NULL CHECK(line_end >= line_start)
            );
            CREATE INDEX parse_issues_report_idx ON parse_issues(source_report_id);

            CREATE TABLE ingest_attempts (
                id INTEGER PRIMARY KEY,
                requested_date TEXT NOT NULL,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('imported', 'reselected', 'idempotent', 'refused_partial', 'failed', 'not_found', 'fetch_failed', 'parse_failed', 'error')),
                error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX ingest_attempts_date_idx ON ingest_attempts(requested_date, id DESC);
            INSERT INTO schema_metadata(key, value) VALUES ('schema_version', '2');
            INSERT INTO schema_metadata(key, value) VALUES ('record_schema_version', '1');
            PRAGMA user_version = 2;
            COMMIT;
            """
        )
    elif version == 1:
        # v1 kept only the current materialization.  It did not retain parsed
        # event snapshots for historical raw versions, so migration could make
        # a non-current source appear to be an empty report.  Preserve that DB
        # unchanged and require a fresh v2 database rebuilt from raw sources.
        raise RuntimeError(
            "Wellspring database schema v1 cannot be migrated safely; rebuild a fresh v2 database from raw sources"
        )


def record_attempt(
    conn: sqlite3.Connection, requested_date: str, source_url: str, status: str, error: str | None = None
) -> None:
    """Record a fetch/import outcome without changing current event rows."""
    _valid_date(requested_date, "requested_date")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError("source_url must be a non-empty string")
    if status not in _ATTEMPT_STATUSES:
        raise ValueError(f"unsupported ingest attempt status: {status!r}")
    if error is not None and not isinstance(error, str):
        raise ValueError("error must be text or None")
    conn.execute(
        "INSERT INTO ingest_attempts(requested_date, source_url, status, error, created_at) VALUES (?, ?, ?, ?, ?)",
        (requested_date, source_url, status, error, _utcnow()),
    )


def import_report(conn: sqlite3.Connection, report: ParsedReport) -> dict[str, Any]:
    """Persist a fully valid report, or safely record why it was not applied.

    Reports with parse issues are retained as immutable raw source evidence and
    recorded as attempts, but their partial event set never replaces current
    rows.  A repeated raw SHA for the same date is idempotent.
    """
    try:
        _validate_report(report)
    except Exception as exc:
        requested_date = getattr(report, "report_date", None)
        source = getattr(report, "source", None)
        if isinstance(requested_date, str) and isinstance(source, Source) and isinstance(source.url, str) and source.url:
            record_attempt(conn, requested_date, source.url, "failed", str(exc))
        raise

    with _transaction(conn):
        existing = conn.execute(
            """SELECT id, import_status FROM source_reports
               WHERE report_date = ? AND sha256 = ? AND parser_version = ?""",
            (report.report_date, report.source.sha256, report.source.parser_version),
        ).fetchone()
        if existing is not None:
            if existing["import_status"] == "partial":
                record_attempt(conn, report.report_date, report.source.url, "refused_partial")
                return _result("refused_partial", report, inserted=0, deleted=0, source_report_id=existing["id"])
            head = conn.execute(
                "SELECT source_report_id FROM report_heads WHERE report_date = ?", (report.report_date,)
            ).fetchone()
            if head is not None and head["source_report_id"] == existing["id"]:
                record_attempt(conn, report.report_date, report.source.url, "idempotent")
                return _result("idempotent", report, inserted=0, deleted=0, source_report_id=existing["id"])
            deleted = _select_head(conn, report.report_date, existing["id"])
            record_attempt(conn, report.report_date, report.source.url, "reselected")
            return _result("reselected", report, inserted=_snapshot_count(conn, existing["id"]), deleted=deleted,
                           source_report_id=existing["id"])

        source_status = "partial" if report.issues else "valid"
        source_report_id = _insert_source_report(conn, report, source_status)
        _insert_issues(conn, source_report_id, report.issues)
        if report.issues:
            record_attempt(conn, report.report_date, report.source.url, "refused_partial", "parser reported issues")
            return _result("refused_partial", report, inserted=0, deleted=0, source_report_id=source_report_id)

        for event in report.events:
            _insert_snapshot(conn, source_report_id, event)
        deleted = _select_head(conn, report.report_date, source_report_id)
        record_attempt(conn, report.report_date, report.source.url, "imported")
        return _result("imported", report, inserted=len(report.events), deleted=deleted, source_report_id=source_report_id)


def events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return current events in the same public shape as ``LicenceEvent.to_dict``."""
    rows = conn.execute(
        "SELECT event_json FROM licence_events ORDER BY report_date, event_type, licence_number"
    ).fetchall()
    return [json.loads(row["event_json"]) for row in rows]


def _insert_source_report(conn: sqlite3.Connection, report: ParsedReport, status: str) -> int:
    cursor = conn.execute(
        """INSERT INTO source_reports
           (report_date, source_url, sha256, raw_bytes, retrieved_at, parser_version, import_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (report.report_date, report.source.url, report.source.sha256, report.raw_bytes,
         report.source.retrieved_at, report.source.parser_version, status, _utcnow()),
    )
    return int(cursor.lastrowid)


def _insert_issues(conn: sqlite3.Connection, source_report_id: int, issues: list[ParseIssue]) -> None:
    conn.executemany(
        "INSERT INTO parse_issues(source_report_id, code, message, line_start, line_end) VALUES (?, ?, ?, ?, ?)",
        [(source_report_id, issue.code, issue.message, issue.line_start, issue.line_end) for issue in issues],
    )


def _insert_snapshot(conn: sqlite3.Connection, source_report_id: int, event: LicenceEvent) -> None:
    payload = event.to_dict()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    conn.execute(
        """INSERT INTO report_event_snapshots
           (source_report_id, event_key, event_type, licence_number, event_json) VALUES (?, ?, ?, ?, ?)""",
        (source_report_id, event.id, event.event_type.value, event.licence_number, encoded),
    )


def _select_head(conn: sqlite3.Connection, report_date: str, source_report_id: int) -> int:
    """Replace one date's materialization and point its head at a valid snapshot."""
    deleted = conn.execute("DELETE FROM licence_events WHERE report_date = ?", (report_date,)).rowcount
    snapshots = conn.execute(
        "SELECT event_json FROM report_event_snapshots WHERE source_report_id = ? ORDER BY id", (source_report_id,)
    ).fetchall()
    for row in snapshots:
        _insert_event_payload(conn, source_report_id, json.loads(row["event_json"]))
    conn.execute(
        """INSERT INTO report_heads(report_date, source_report_id, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(report_date) DO UPDATE SET source_report_id = excluded.source_report_id,
                                                updated_at = excluded.updated_at""",
        (report_date, source_report_id, _utcnow()),
    )
    return deleted


def _insert_event_payload(conn: sqlite3.Connection, source_report_id: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    flat_values = [payload.get(name) for name in _EVENT_COLUMNS]
    columns = ", ".join(_EVENT_COLUMNS)
    placeholders = ", ".join("?" for _ in _EVENT_COLUMNS)
    cursor = conn.execute(
        f"""INSERT INTO licence_events
            (event_key, report_date, event_type, licence_number, source_report_id, event_json, {columns})
            VALUES (?, ?, ?, ?, ?, ?, {placeholders})""",
        (payload["id"], payload["report_date"], payload["event_type"], payload["licence_number"],
         source_report_id, encoded, *flat_values),
    )
    licence_event_id = int(cursor.lastrowid)
    for occurrence in payload["occurrences"]:
        occurrence_id = conn.execute(
            """INSERT INTO event_occurrences
               (licence_event_id, ordinal, well_name, uwi, source_line_start, source_line_end, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (licence_event_id, occurrence["ordinal"], occurrence["well_name"], occurrence["uwi"],
             occurrence["source_line_start"], occurrence["source_line_end"], occurrence["raw_text"]),
        ).lastrowid
        for ordinal, change in enumerate(occurrence["changes"]):
            field_name, before_value, after_value = _change_columns(change)
            conn.execute(
                """INSERT INTO event_changes(occurrence_id, ordinal, change_json, field_name, before_value, after_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (occurrence_id, ordinal, json.dumps(change, sort_keys=True, separators=(",", ":"), allow_nan=False),
                 field_name, before_value, after_value),
            )


def _snapshot_count(conn: sqlite3.Connection, source_report_id: int) -> int:
    return int(conn.execute(
        "SELECT count(*) FROM report_event_snapshots WHERE source_report_id = ?", (source_report_id,)
    ).fetchone()[0])


def _change_columns(change: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    # The parser's compact representation is intentionally flexible.  Preserve
    # it exactly in JSON while exposing conventional before/after forms for SQL.
    field_name = change.get("field") or change.get("name")
    before = change.get("before") or change.get("old")
    after = change.get("after") or change.get("new") or change.get("value")
    return field_name, before, after


def _validate_report(report: ParsedReport) -> None:
    if not isinstance(report, ParsedReport):
        raise ValueError("report must be a ParsedReport")
    _valid_date(report.report_date, "report_date")
    _validate_source(report.source, report.raw_bytes)
    if not isinstance(report.source_block_count, int) or report.source_block_count < 0:
        raise ValueError("source_block_count must be a non-negative integer")
    if not isinstance(report.duplicate_block_count, int) or report.duplicate_block_count < 0:
        raise ValueError("duplicate_block_count must be a non-negative integer")
    if not isinstance(report.events, list) or not isinstance(report.issues, list):
        raise ValueError("events and issues must be lists")
    seen_keys: set[tuple[str, str, str]] = set()
    for event in report.events:
        _validate_event(event, report)
        key = (event.licence_number, event.event_type.value, event.report_date)
        if key in seen_keys:
            raise ValueError(f"duplicate event in report: {key}")
        seen_keys.add(key)
    for issue in report.issues:
        if not isinstance(issue, ParseIssue):
            raise ValueError("issues must contain ParseIssue values")
        if not isinstance(issue.code, str) or not issue.code or not isinstance(issue.message, str):
            raise ValueError("parse issues require a code and text message")
        _valid_line_range(issue.line_start, issue.line_end, "parse issue")


def _validate_source(source: Source, raw_bytes: bytes) -> None:
    if not isinstance(source, Source):
        raise ValueError("report.source must be a Source")
    if not isinstance(raw_bytes, bytes):
        raise ValueError("raw_bytes must be bytes")
    if not isinstance(source.url, str) or not source.url:
        raise ValueError("source.url must be a non-empty string")
    if not isinstance(source.sha256, str) or len(source.sha256) != 64 or any(c not in "0123456789abcdef" for c in source.sha256):
        raise ValueError("source.sha256 must be a lowercase SHA-256 hex digest")
    if hashlib.sha256(raw_bytes).hexdigest() != source.sha256:
        raise ValueError("source SHA-256 does not match raw_bytes")
    if not isinstance(source.parser_version, str) or not source.parser_version:
        raise ValueError("source.parser_version must be non-empty text")
    if not isinstance(source.retrieved_at, str):
        raise ValueError("source.retrieved_at must be ISO-8601 text")
    try:
        datetime.fromisoformat(source.retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("source.retrieved_at must be ISO-8601 text") from exc


def _validate_event(event: LicenceEvent, report: ParsedReport) -> None:
    if not isinstance(event, LicenceEvent):
        raise ValueError("events must contain LicenceEvent values")
    if event.schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported event schema_version: {event.schema_version!r}")
    if not isinstance(event.event_type, EventType):
        raise ValueError("event_type must be an EventType")
    if event.report_date != report.report_date:
        raise ValueError("event report_date must match report_date")
    _valid_date(event.report_date, "event.report_date")
    if not isinstance(event.id, str) or not event.id or not isinstance(event.licence_number, str) or not event.licence_number:
        raise ValueError("event id and licence_number must be non-empty text")
    if event.source != report.source:
        raise ValueError("event source must match report source")
    if not isinstance(event.occurrences, list) or not event.occurrences:
        raise ValueError("accepted events require at least one occurrence")
    occurrence_ordinals: set[int] = set()
    for occurrence in event.occurrences:
        if not isinstance(occurrence.ordinal, int) or occurrence.ordinal < 0 or occurrence.ordinal in occurrence_ordinals:
            raise ValueError("occurrence ordinals must be unique non-negative integers")
        occurrence_ordinals.add(occurrence.ordinal)
        _valid_line_range(occurrence.source_line_start, occurrence.source_line_end, "occurrence")
        if not isinstance(occurrence.raw_text, str):
            raise ValueError("occurrence raw_text must be text")
        if not isinstance(occurrence.changes, list) or any(
            not isinstance(change, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in change.items())
            for change in occurrence.changes
        ):
            raise ValueError("occurrence changes must be string dictionaries")
    _ensure_finite(event.to_dict())


def _valid_date(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def _valid_line_range(start: Any, end: Any, name: str) -> None:
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError(f"{name} line range is invalid")


def _ensure_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("event values may not contain NaN or infinity")
    if isinstance(value, dict):
        for item in value.values():
            _ensure_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _ensure_finite(item)


class _transaction:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        return False


def _result(status: str, report: ParsedReport, *, inserted: int, deleted: int, source_report_id: int) -> dict[str, Any]:
    return {
        "status": status,
        "report_date": report.report_date,
        "source_report_id": source_report_id,
        "inserted": inserted,
        "deleted": deleted,
        "issues": len(report.issues),
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
