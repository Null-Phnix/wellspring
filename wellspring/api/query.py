"""Bounded, read-only SQL over the public event projection.

The caller owns the absolute monotonic deadline. No connection to the published
dataset or source reports is exposed to generated SQL.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import Any


TEXT_COLUMNS = (
    "id", "licence_number", "report_date", "event_type", "licensee",
    "substance", "field_centre", "terminating_zone", "well_type",
    "well_purpose", "surface_location",
)
REAL_COLUMNS = ("latitude", "longitude")
COLUMNS = TEXT_COLUMNS + REAL_COLUMNS
ROW_LIMIT = 200
MAX_SQL_BYTES = 4096
MAX_INPUT_ROWS = 100_000
MAX_CELL_BYTES = 4096
MAX_RESULT_BYTES = 256 * 1024
MAX_COLUMNS = 24
SAFE_FUNCTIONS = frozenset({
    "count", "sum", "avg", "min", "max", "total",
    "date", "time", "datetime", "julianday", "strftime",
    "coalesce", "ifnull", "nullif", "lower", "upper", "like",
})

SCHEMA_TEXT = """Public SQLite schema (one table):
CREATE TABLE events (
  id TEXT, licence_number TEXT, report_date TEXT, event_type TEXT,
  licensee TEXT, substance TEXT, field_centre TEXT,
  terminating_zone TEXT, well_type TEXT, well_purpose TEXT,
  surface_location TEXT, latitude REAL, longitude REAL
);
Submit one SELECT from events. Dates are ISO YYYY-MM-DD text; null means
unreported. Use COUNT/SUM/AVG/MIN/MAX/TOTAL, date/time/datetime/julianday/
strftime, COALESCE/IFNULL/NULLIF, LOWER/UPPER and LIKE as needed.
No WITH, comments, other tables, writes, PRAGMA, ATTACH or extensions.
At most 200 rows are returned.
"""


class QueryRefusal(Exception):
    """A safe public refusal; internal SQLite errors are never surfaced."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _refuse(code: str, message: str) -> QueryRefusal:
    return QueryRefusal(code, message)


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise _refuse("QUERY_TIMEOUT", "The question took too long to answer.")


def _validate_sql(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise _refuse("INVALID_SQL", "The SQL is empty or exceeds its size limit.")
    try:
        sql_size = len(sql.encode("utf-8"))
    except UnicodeError:
        raise _refuse("INVALID_SQL", "The SQL is empty or exceeds its size limit.") from None
    if sql_size > MAX_SQL_BYTES:
        raise _refuse("INVALID_SQL", "The SQL is empty or exceeds its size limit.")
    # SQLite's execute() also enforces one statement. This small scanner makes
    # the supported subset explicit and does not mistake quoted semicolons or
    # comment markers for statement separators.
    quote: str | None = None
    semicolon: int | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if semicolon is not None:
            if not char.isspace():
                raise _refuse("INVALID_SQL", "Submit exactly one SELECT statement.")
            index += 1
            continue
        if quote is not None:
            if char == quote:
                if following == quote:
                    index += 2
                    continue
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "-" and following == "-" or char == "/" and following == "*":
            raise _refuse("INVALID_SQL", "SQL comments are not supported.")
        elif char in ("`", "["):
            raise _refuse("INVALID_SQL", "This identifier quoting is not supported.")
        elif char == ";":
            semicolon = index
        index += 1
    if quote is not None:
        raise _refuse("INVALID_SQL", "The SQL contains an unclosed quote.")
    statement = sql[:semicolon] if semicolon is not None else sql
    if not re.match(r"\s*SELECT\b", statement, flags=re.IGNORECASE):
        raise _refuse("UNSAFE_QUERY", "Only a SELECT from events is supported.")
    return statement


def _input_row(record: dict[str, Any]) -> tuple[Any, ...]:
    if not isinstance(record, dict):
        raise _refuse("QUERY_UNAVAILABLE", "The public data could not be queried.")
    values: list[Any] = []
    for name in TEXT_COLUMNS:
        value = record.get(name)
        if value is not None and (not isinstance(value, str) or len(value.encode("utf-8")) > MAX_CELL_BYTES):
            raise _refuse("QUERY_UNAVAILABLE", "The public data could not be queried.")
        values.append(value)
    for name in REAL_COLUMNS:
        value = record.get(name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise _refuse("QUERY_UNAVAILABLE", "The public data could not be queried.")
        values.append(value)
    return tuple(values)


def _limits(connection: sqlite3.Connection) -> None:
    connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_SQL_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_CELL_BYTES)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, MAX_COLUMNS)
    connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 32)
    connection.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 4)
    connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)


def _authorizer(action: int, arg1: str | None, arg2: str | None,
                database: str | None, _source: str | None) -> int:
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    # SQLite reports database=None for an empty-column table read, as used by
    # COUNT(*) and SELECT literals FROM events. It reports main for named cells.
    if action == sqlite3.SQLITE_READ and arg1 == "events" and (
        (database == "main" and (not arg2 or arg2 in COLUMNS)) or
        (database is None and not arg2)
    ):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and arg2 and arg2.lower() in SAFE_FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int)):
        safe = value
    elif isinstance(value, float) and math.isfinite(value):
        safe = value
    else:
        raise _refuse("RESULT_LIMIT", "The SQL result exceeds its safe limits.")
    if len(json.dumps(safe, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_CELL_BYTES:
        raise _refuse("RESULT_LIMIT", "The SQL result exceeds its safe limits.")
    return safe


def execute_readonly(records: list[dict], sql: str, deadline: float) -> dict[str, Any]:
    """Execute one bounded SELECT against a private public-data snapshot.

    ``deadline`` is an absolute ``time.monotonic()`` value shared with request
    parsing and any upstream provider call. It is never reset here.
    """
    _check_deadline(deadline)
    statement = _validate_sql(sql)
    if not isinstance(records, list) or len(records) > MAX_INPUT_ROWS:
        raise _refuse("QUERY_UNAVAILABLE", "The public data could not be queried.")
    try:
        with tempfile.TemporaryDirectory(prefix="wellspring-ask-") as directory:
            path = Path(directory) / "events.sqlite"
            writer = sqlite3.connect(path)
            try:
                _limits(writer)
                writer.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                writer.execute("CREATE TABLE events (" + ", ".join(
                    f'"{name}" {"REAL" if name in REAL_COLUMNS else "TEXT"}' for name in COLUMNS
                ) + ")")
                placeholders = ",".join("?" for _ in COLUMNS)
                with writer:
                    for record in records:
                        _check_deadline(deadline)
                        writer.execute(f"INSERT INTO events VALUES ({placeholders})", _input_row(record))
                _check_deadline(deadline)
            finally:
                writer.close()

            # Close the sole writer before opening SQLite's immutable, read-only
            # view. The authorizer is installed only on this query connection.
            reader = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
            try:
                _limits(reader)
                reader.execute("PRAGMA query_only=ON")
                reader.set_authorizer(_authorizer)
                reader.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                _check_deadline(deadline)
                cursor = reader.execute(statement)
                columns = [item[0] for item in cursor.description or ()]
                if not columns or len(columns) > MAX_COLUMNS or len(set(columns)) != len(columns) or any(
                    not isinstance(name, str) or not name or len(name.encode("utf-8")) > 128 for name in columns
                ):
                    raise _refuse("RESULT_LIMIT", "The SQL result exceeds its safe limits.")
                rows: list[dict[str, Any]] = []
                result_bytes = 0
                for _ in range(ROW_LIMIT + 1):
                    _check_deadline(deadline)
                    item = cursor.fetchone()
                    if item is None:
                        break
                    if len(rows) == ROW_LIMIT:
                        _check_deadline(deadline)
                        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": True}
                    row = {name: _safe_value(value) for name, value in zip(columns, item)}
                    result_bytes += len(json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                    if result_bytes > MAX_RESULT_BYTES:
                        raise _refuse("RESULT_LIMIT", "The SQL result exceeds its safe limits.")
                    rows.append(row)
                _check_deadline(deadline)
                return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": False}
            finally:
                reader.close()
    except QueryRefusal:
        raise
    except sqlite3.Error:
        if time.monotonic() >= deadline:
            raise _refuse("QUERY_TIMEOUT", "The question took too long to answer.") from None
        # Authorization errors, syntax failures, and SQLite limits use the
        # same stable message; database paths and engine errors stay private.
        raise _refuse("INVALID_SQL", "The SQL cannot be run on public events.") from None
    except (OSError, ValueError, TypeError, OverflowError):
        raise _refuse("QUERY_UNAVAILABLE", "The public data could not be queried.") from None
