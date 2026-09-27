"""Lambda handler for the immutable Wellspring JSONL export.

The handler deliberately has no database, source-report fetcher, SQL engine, or
model client.  It accepts only a narrow set of query parameters and reads the
dataset named by the published manifest once per Lambda execution environment.
"""

from __future__ import annotations

from functools import cmp_to_key
import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from wellspring.ingest.models import EventType


SCHEMA_VERSION = 1
DEFAULT_MANIFEST_KEY = "published/manifest.json"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:4200"
CACHE_TTL_SECONDS = 60
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
EVENT_TYPES = frozenset(event_type.value for event_type in EventType)
TEXT_FILTERS = frozenset({"licensee", "substance", "field_centre", "terminating_zone", "well_type"})
SORT_FIELDS = frozenset({"report_date", "licence_number", "licensee", "substance", "field_centre", "terminating_zone", "well_type"})
POINT_FIELDS = (
    "id", "licence_number", "well_name", "licensee", "substance", "report_date",
    "latitude", "longitude", "coordinate_method", "location_accuracy", "location_reason",
    "surface_location",
)
ROUTES = {
    "/licences": frozenset({"GET"}),
    "/stats/daily": frozenset({"GET"}),
    "/stats/top-licensees": frozenset({"GET"}),
    "/stats/top-formations": frozenset({"GET"}),
    "/stats/substances": frozenset({"GET"}),
    "/ask": frozenset({"POST"}),
}


class DatasetUnavailable(RuntimeError):
    """The published manifest or immutable export cannot be trusted."""


_cached_key: tuple[str, str, str] | None = None
_cached_dataset: "Dataset | None" = None
_cached_error: DatasetUnavailable | None = None
_cached_at: float | None = None


class Dataset:
    def __init__(self, records: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
        self.records = records
        self.manifest = manifest


def reset_dataset_cache() -> None:
    """Clear the process cache.  This is used by local tests and not by requests."""
    global _cached_key, _cached_dataset, _cached_error, _cached_at
    _cached_key = None
    _cached_dataset = None
    _cached_error = None
    _cached_at = None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle API Gateway HTTP API v2 and Lambda Function URL request events."""
    try:
        request = _request(event)
    except ValueError as exc:
        return _error(400, "BAD_REQUEST", str(exc), None)

    path, method, query, origin = request
    cors = _cors_headers(origin)
    if method == "OPTIONS":
        if path not in ROUTES:
            return _error(404, "UNKNOWN_ROUTE", "Unknown route.", cors)
        return _response(204, None, cors)
    if path not in ROUTES:
        return _error(404, "UNKNOWN_ROUTE", "Unknown route.", cors)
    if method not in ROUTES[path]:
        return _error(405, "METHOD_NOT_ALLOWED", "Method is not allowed for this route.", cors)

    try:
        if path == "/ask":
            return _response(200, _ask(event), cors)
        dataset = _dataset()
        if path == "/licences":
            return _licences(dataset, query, cors)
        if path == "/stats/daily":
            return _daily(dataset, query, cors)
        if path == "/stats/top-licensees":
            return _top(dataset, query, cors, "licensee")
        if path == "/stats/top-formations":
            return _top(dataset, query, cors, "terminating_zone")
        return _top(dataset, query, cors, "substance")
    except DatasetUnavailable:
        return _error(503, "DATASET_UNAVAILABLE", "The published dataset is unavailable.", cors)
    except ValueError as exc:
        return _error(400, "BAD_PARAMETER", str(exc), cors)


def _request(event: Any) -> tuple[str, str, dict[str, str], str | None]:
    if not isinstance(event, dict):
        raise ValueError("Request event must be an object.")
    context = event.get("requestContext")
    http = context.get("http") if isinstance(context, dict) else None
    method = http.get("method") if isinstance(http, dict) else event.get("httpMethod")
    path = event.get("rawPath") or (http.get("path") if isinstance(http, dict) else None) or event.get("path")
    if not isinstance(method, str) or not isinstance(path, str):
        raise ValueError("Request method and path are required.")
    raw_query = event.get("queryStringParameters") or {}
    if not isinstance(raw_query, dict):
        raise ValueError("Query parameters must be an object.")
    query: dict[str, str] = {}
    for key, value in raw_query.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Query parameters must be text.")
        query[key] = value
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}
    origin = next((v for k, v in headers.items() if isinstance(k, str) and k.lower() == "origin" and isinstance(v, str)), None)
    return path.rstrip("/") or "/", method.upper(), query, origin


def _dataset() -> Dataset:
    global _cached_key, _cached_dataset, _cached_error, _cached_at
    data_dir = os.environ.get("DATA_DIR", "")
    bucket = os.environ.get("DATA_BUCKET", "")
    manifest_key = os.environ.get("MANIFEST_KEY", DEFAULT_MANIFEST_KEY)
    if bool(data_dir) == bool(bucket):
        raise DatasetUnavailable("Set exactly one of DATA_DIR or DATA_BUCKET.")
    cache_key = (data_dir, bucket, manifest_key)
    if _cached_key == cache_key and _cached_at is not None and time.monotonic() - _cached_at < CACHE_TTL_SECONDS:
        if _cached_error is not None:
            raise _cached_error
        if _cached_dataset is not None:
            return _cached_dataset
    try:
        if data_dir:
            manifest_bytes, export_bytes = _read_local(data_dir, manifest_key)
        else:
            manifest_bytes, export_bytes = _read_s3(bucket, manifest_key)
        manifest = _parse_manifest(manifest_bytes)
        _validate_export_hash(manifest, export_bytes)
        records = _parse_jsonl(export_bytes)
        dataset = Dataset(records, manifest)
    except DatasetUnavailable as exc:
        _cached_key, _cached_dataset, _cached_error, _cached_at = cache_key, None, exc, time.monotonic()
        raise
    except Exception as exc:
        error = DatasetUnavailable("Unable to load published dataset.")
        _cached_key, _cached_dataset, _cached_error, _cached_at = cache_key, None, error, time.monotonic()
        raise error from exc
    _cached_key, _cached_dataset, _cached_error, _cached_at = cache_key, dataset, None, time.monotonic()
    return dataset


def _safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise DatasetUnavailable("Manifest path is missing.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DatasetUnavailable("Manifest path is invalid.")
    return path


def _read_local(data_dir: str, manifest_key: str) -> tuple[bytes, bytes]:
    root = Path(data_dir).resolve()
    manifest_path = (root / Path(*_safe_relative_path(manifest_key).parts)).resolve()
    if root not in manifest_path.parents:
        raise DatasetUnavailable("Manifest path is outside DATA_DIR.")
    try:
        manifest_bytes = _read_local_file(manifest_path, MAX_MANIFEST_BYTES, "Manifest")
        manifest = _parse_manifest(manifest_bytes)
        export_path = (manifest_path.parent / Path(*_safe_relative_path(manifest["export_file"]).parts)).resolve()
        if manifest_path.parent not in export_path.parents:
            raise DatasetUnavailable("Export path is outside manifest directory.")
        return manifest_bytes, _read_local_file(export_path, MAX_EXPORT_BYTES, "Export")
    except (OSError, UnicodeError) as exc:
        raise DatasetUnavailable("Local published dataset cannot be read.") from exc


def _read_local_file(path: Path, limit: int, label: str) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise DatasetUnavailable(f"{label} exceeds its configured size limit.")
    return content


def _read_s3(bucket: str, manifest_key: str) -> tuple[bytes, bytes]:
    if not isinstance(bucket, str) or not bucket:
        raise DatasetUnavailable("DATA_BUCKET is invalid.")
    manifest_path = _safe_relative_path(manifest_key)
    try:
        import boto3  # Imported only in the deployed S3 configuration.
        client = boto3.client("s3")
        manifest_bytes = _read_s3_body(client.get_object(Bucket=bucket, Key=str(manifest_path))["Body"], MAX_MANIFEST_BYTES, "Manifest")
        manifest = _parse_manifest(manifest_bytes)
        export_relative = _safe_relative_path(manifest["export_file"])
        export_key = manifest_path.parent / export_relative
        export_bytes = _read_s3_body(client.get_object(Bucket=bucket, Key=str(export_key))["Body"], MAX_EXPORT_BYTES, "Export")
        return manifest_bytes, export_bytes
    except DatasetUnavailable:
        raise
    except Exception as exc:
        raise DatasetUnavailable("Published S3 dataset cannot be read.") from exc


def _read_s3_body(body: Any, limit: int, label: str) -> bytes:
    content = body.read(limit + 1)
    if not isinstance(content, bytes):
        raise DatasetUnavailable(f"{label} response is invalid.")
    if len(content) > limit:
        raise DatasetUnavailable(f"{label} exceeds its configured size limit.")
    return content


def _parse_manifest(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, parse_constant=_reject_nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetUnavailable("Manifest is not valid JSON.") from exc
    if not isinstance(value, dict) or not isinstance(value.get("export_file"), str):
        raise DatasetUnavailable("Manifest does not name an export_file.")
    return value


def _validate_export_hash(manifest: dict[str, Any], export_bytes: bytes) -> None:
    expected = manifest.get("export_sha256")
    if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise DatasetUnavailable("Manifest export_sha256 is invalid.")
    if hashlib.sha256(export_bytes).hexdigest() != expected:
        raise DatasetUnavailable("Published export hash does not match manifest.")


def _parse_jsonl(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetUnavailable("Export is not UTF-8 JSONL.") from exc
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line, parse_constant=_reject_nonfinite)
        except json.JSONDecodeError as exc:
            raise DatasetUnavailable("Export contains invalid JSONL.") from exc
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            raise DatasetUnavailable("Export contains an invalid record.")
        report_date = record.get("report_date")
        if not isinstance(report_date, str) or not _is_iso_date(report_date):
            raise DatasetUnavailable("Export record report_date is invalid.")
        if record.get("event_type") not in EVENT_TYPES:
            raise DatasetUnavailable("Export record event_type is invalid.")
        records.append(record)
    return records


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _allowed_origins() -> frozenset[str]:
    configured = os.environ.get("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return frozenset(part.strip() for part in configured.split(",") if part.strip())


def _cors_headers(origin: str | None) -> dict[str, str]:
    if origin is None or origin not in _allowed_origins():
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Vary": "Origin",
    }


def _response(status: int, body: dict[str, Any] | None, cors: dict[str, str] | None) -> dict[str, Any]:
    headers = {"content-type": "application/json; charset=utf-8"}
    headers.update(cors or {})
    return {"statusCode": status, "headers": headers, "body": "" if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":"))}


def _error(status: int, code: str, message: str, cors: dict[str, str] | None) -> dict[str, Any]:
    return _response(status, {"error": {"code": code, "message": message}, "schema_version": SCHEMA_VERSION}, cors)


def _parse_date(value: str, name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD).") from exc


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _int_param(query: dict[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = query.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _filtered(dataset: Dataset, query: dict[str, str], *, allow_page: bool = False, allow_sort: bool = False, allow_fields: bool = False, allow_limit: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = set(TEXT_FILTERS) | {"date_from", "date_to", "event_type"}
    if allow_page:
        allowed |= {"page", "page_size"}
    if allow_sort:
        allowed |= {"sort", "order"}
    if allow_fields:
        allowed.add("fields")
    if allow_limit:
        allowed.add("limit")
    unknown = set(query) - allowed
    if unknown:
        raise ValueError(f"Unsupported parameter: {sorted(unknown)[0]}.")
    date_from = _parse_date(query["date_from"], "date_from") if "date_from" in query else None
    date_to = _parse_date(query["date_to"], "date_to") if "date_to" in query else None
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from must be on or before date_to.")
    event_type = query.get("event_type", "issued")
    if event_type != "all" and event_type not in EVENT_TYPES:
        raise ValueError("event_type must be issued, reentry, amended, cancelled, updated, or all.")
    rows = []
    for record in dataset.records:
        report_date = record.get("report_date")
        if not isinstance(report_date, str):
            continue
        if date_from and report_date < date_from:
            continue
        if date_to and report_date > date_to:
            continue
        if event_type != "all" and record.get("event_type") != event_type:
            continue
        matched = True
        for field in TEXT_FILTERS:
            requested = query.get(field)
            if requested is None:
                continue
            actual = record.get(field)
            if field == "licensee":
                if not isinstance(actual, str) or requested.casefold() not in actual.casefold():
                    matched = False
                    break
            elif actual != requested:
                matched = False
                break
        if matched:
            rows.append(record)
    return rows, _meta(dataset, rows, date_from, date_to, event_type)


def _meta(dataset: Dataset, rows: list[dict[str, Any]], date_from: str | None, date_to: str | None, event_type: str) -> dict[str, Any]:
    loaded_dates = sorted(record["report_date"] for record in rows if isinstance(record.get("report_date"), str))
    manifest = dataset.manifest
    manifest_from = _manifest_date(manifest.get("date_from"))
    manifest_to = _manifest_date(manifest.get("date_to"))
    return {
        "schema_version": SCHEMA_VERSION,
        "data_as_of": manifest.get("data_as_of") if isinstance(manifest.get("data_as_of"), str) else None,
        "date_from": date_from if date_from is not None else (manifest_from or (loaded_dates[0] if loaded_dates else None)),
        "date_to": date_to if date_to is not None else (manifest_to or (loaded_dates[-1] if loaded_dates else None)),
        "event_type": event_type,
        "coverage": _coverage_for_window(manifest.get("coverage"), date_from or manifest_from, date_to or manifest_to),
    }


def _coverage_for_window(coverage: Any, date_from: str | None, date_to: str | None) -> dict[str, Any] | None:
    if not isinstance(coverage, dict):
        return None
    sliced = dict(coverage)
    loaded_dates = coverage.get("loaded_dates")
    if isinstance(loaded_dates, list) and all(isinstance(day, str) and _is_iso_date(day) for day in loaded_dates):
        sliced["loaded_dates"] = [day for day in loaded_dates if _in_window(day, date_from, date_to)]
        sliced["reports_loaded"] = len(sliced["loaded_dates"])
    for key in ("empty_dates", "missing_dates", "failed_dates", "retry_failed_dates"):
        days = coverage.get(key)
        if isinstance(days, list) and all(isinstance(day, str) and _is_iso_date(day) for day in days):
            sliced[key] = [day for day in days if _in_window(day, date_from, date_to)]
    issues = coverage.get("parse_issues_by_date")
    if isinstance(issues, dict):
        sliced["parse_issues_by_date"] = {day:count for day,count in issues.items() if _in_window(day,date_from,date_to)}
        sliced["parse_issue_count"] = sum(sliced["parse_issues_by_date"].values())
    return sliced


def _in_window(day: str, date_from: str | None, date_to: str | None) -> bool:
    return (date_from is None or day >= date_from) and (date_to is None or day <= date_to)


def _manifest_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _compare_records(field: str, order: str):
    def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        left_value, right_value = left.get(field), right.get(field)
        left_key = "" if left_value is None else str(left_value)
        right_key = "" if right_value is None else str(right_value)
        if left_value is None and right_value is not None:
            return 1
        if right_value is None and left_value is not None:
            return -1
        if left_key != right_key:
            if order == "desc":
                return -1 if left_key > right_key else 1
            return -1 if left_key < right_key else 1
        left_id, right_id = str(left.get("id", "")), str(right.get("id", ""))
        return -1 if left_id < right_id else (1 if left_id > right_id else 0)
    return cmp_to_key(compare)


def _licences(dataset: Dataset, query: dict[str, str], cors: dict[str, str]) -> dict[str, Any]:
    rows, meta = _filtered(dataset, query, allow_page=True, allow_sort=True, allow_fields=True)
    fields = query.get("fields")
    if fields not in (None, "points"):
        raise ValueError("fields must be points when supplied.")
    sort = query.get("sort", "report_date")
    if sort not in SORT_FIELDS:
        raise ValueError("sort is not supported.")
    order = query.get("order", "asc")
    if order not in {"asc", "desc"}:
        raise ValueError("order must be asc or desc.")
    page = _int_param(query, "page", 1, 1, 2_147_483_647)
    page_size = _int_param(query, "page_size", 50, 1, 200)
    ordered = sorted(rows, key=_compare_records(sort, order))
    start = (page - 1) * page_size
    items = ordered[start:start + page_size]
    if fields == "points":
        items = [{field: item.get(field) for field in POINT_FIELDS} for item in items]
    return _response(200, {"items": items, "total": len(ordered), "page": page, "page_size": page_size, "meta": meta}, cors)


def _daily(dataset: Dataset, query: dict[str, str], cors: dict[str, str]) -> dict[str, Any]:
    rows, meta = _filtered(dataset, query)
    coverage = meta["coverage"]
    loaded_dates = coverage.get("loaded_dates", []) if isinstance(coverage, dict) else []
    unavailable_dates = (
        {day for key in ("missing_dates", "failed_dates") for day in coverage.get(key, []) if isinstance(day, str)}
        if isinstance(coverage, dict) else set()
    )
    counts: dict[str, int] = {day: 0 for day in loaded_dates if isinstance(day, str) and day not in unavailable_dates}
    for record in rows:
        report_date = record.get("report_date")
        if isinstance(report_date, str):
            counts[report_date] = counts.get(report_date, 0) + 1
    return _response(200, {"items": [{"date": day, "count": counts[day]} for day in sorted(counts)], "meta": meta}, cors)


def _top(dataset: Dataset, query: dict[str, str], cors: dict[str, str], field: str) -> dict[str, Any]:
    rows, meta = _filtered(dataset, query, allow_limit=True)
    limit = _int_param(query, "limit", 10, 1, 50)
    counts: dict[str | None, int] = {}
    for record in rows:
        value = record.get(field)
        value = value if isinstance(value, str) else None
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0] is None, item[0] or ""))[:limit]
    output_key = "licensee" if field == "licensee" else ("terminating_zone" if field == "terminating_zone" else "substance")
    return _response(200, {"items": [{output_key: value, "count": count} for value, count in ordered], "meta": meta}, cors)


def _ask(event):
    from . import ask
    from .query import QueryRefusal
    started = time.monotonic()
    deadline = started + ask.WALL_SECONDS
    dataset = None
    result = None
    try:
        with ask.hard_deadline(deadline):
            dataset = _dataset()
            if not ask.configured():
                candidate = _ask_refusal(dataset)
            else:
                candidate = ask.answer(event, dataset.records, deadline,
                    date_range=(dataset.manifest.get("date_from"), dataset.manifest.get("date_to")))
                candidate["meta"] = _meta(dataset, [], None, None, "all")
        result = candidate
    except (ask.AskRefusal, QueryRefusal) as exc:
        result = _ask_refusal(dataset, exc.code, exc.message)
    except DatasetUnavailable:
        result = _ask_refusal(None)
    except Exception:
        result = _ask_refusal(dataset)
    # Bounded operational metadata only; no question, SQL, key or provider body.
    print(json.dumps({"event": "ask", "status": result["status"],
                      "duration_ms": round((time.monotonic() - started) * 1000),
                      "row_count": result.get("row_count", 0),
                      "model": result.get("model")}))
    return result


def _ask_refusal(dataset: Dataset | None, code="ASK_UNAVAILABLE", message="Question answering is temporarily unavailable.") -> dict[str, Any]:
    meta = _meta(dataset, [], None, None, "all") if dataset is not None else _null_meta()
    return {
        "status": "refused", "columns": [], "rows": [], "row_count": 0, "model": None, "sql": None, "row_limit": 200,
        "truncated": False,
        "refusal": {"code": code, "message": message},
        "meta": meta,
    }


def _null_meta() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "data_as_of": None, "date_from": None, "date_to": None, "event_type": None, "coverage": None}
