import hashlib
import json
import sys
import types

import pytest

from wellspring.api import handler


def _record(identifier, **overrides):
    base = {
        "id": identifier, "report_date": "2026-08-01", "event_type": "issued",
        "licence_number": "0000001", "well_name": "North Well", "licensee": "Acme Energy Ltd.",
        "substance": "CRUDE OIL", "field_centre": "CENTRE", "terminating_zone": "VIKING",
        "well_type": "OIL", "latitude": 52.1, "longitude": -112.2,
        "coordinate_method": "dls_township_grid", "location_accuracy": "approximate",
    }
    return {**base, **overrides}


@pytest.fixture(autouse=True)
def dataset(tmp_path, monkeypatch):
    records = [
        _record("b", licence_number="0000002", licensee="Acme Energy Ltd."),
        _record("a", licence_number="0000001", licensee="ACME Exploration", report_date="2026-08-02"),
        _record("c", licence_number="0000003", event_type="amended", licensee=None, substance=None),
    ]
    payload = ("\n".join(json.dumps(row) for row in records) + "\n").encode()
    (tmp_path / "events-test.jsonl").write_bytes(payload)
    manifest = {
        "schema_version": 1, "export_file": "events-test.jsonl",
        "export_sha256": hashlib.sha256(payload).hexdigest(), "data_as_of": "2026-09-27T00:00:00Z",
        "date_from": "2026-08-01", "date_to": "2026-08-03",
        "coverage": {"reports_loaded": 3, "loaded_dates": ["2026-08-01", "2026-08-02", "2026-08-03"], "empty_dates": ["2026-08-03"], "missing_dates": [], "failed_dates": ["2026-08-04"], "parse_issue_count": 0},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATA_BUCKET", raising=False)
    monkeypatch.setenv("MANIFEST_KEY", "manifest.json")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.cloudfront.net,http://localhost:4200")
    handler.reset_dataset_cache()
    yield tmp_path
    handler.reset_dataset_cache()


def call(path, method="GET", query=None, origin="http://localhost:4200"):
    event = {"rawPath": path, "requestContext": {"http": {"method": method}}, "queryStringParameters": query, "headers": {"origin": origin}}
    result = handler.lambda_handler(event, None)
    return result, json.loads(result["body"]) if result["body"] else None


def test_licences_filters_literal_licensee_and_pagination():
    response, body = call("/licences", query={"licensee": "acme", "page": "1", "page_size": "1", "sort": "licence_number"})
    assert response["statusCode"] == 200
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == ["a"]
    assert body["meta"]["coverage"]["empty_dates"] == ["2026-08-03"]
    assert body["meta"]["date_to"] == "2026-08-03"
    response, body = call("/licences", query={"licensee": "%"})
    assert body["total"] == 0


def test_exact_filters_dates_event_types_and_stats():
    response, body = call("/licences", query={"substance": "crude oil"})
    assert body["total"] == 0
    response, body = call("/stats/daily", query={"event_type": "all", "date_from": "2026-08-01", "date_to": "2026-08-02"})
    assert body["items"] == [{"date": "2026-08-01", "count": 2}, {"date": "2026-08-02", "count": 1}]
    response, body = call("/stats/top-licensees", query={"event_type": "all", "limit": "50"})
    assert body["items"][0] == {"licensee": "ACME Exploration", "count": 1}


def test_daily_uses_loaded_coverage_for_zeroes_and_slices_coverage():
    response, body = call("/stats/daily", query={"date_from": "2026-08-02", "date_to": "2026-08-04", "licensee": "not found"})
    assert response["statusCode"] == 200
    assert body["items"] == [{"date": "2026-08-02", "count": 0}, {"date": "2026-08-03", "count": 0}]
    assert body["meta"]["coverage"] == {"reports_loaded": 2, "loaded_dates": ["2026-08-02", "2026-08-03"], "empty_dates": ["2026-08-03"], "missing_dates": [], "failed_dates": ["2026-08-04"], "parse_issue_count": 0}


def test_points_projection_has_stable_nulls_and_shared_pagination():
    response, body = call("/licences", query={"event_type": "all", "fields": "points", "page_size": "200"})
    assert response["statusCode"] == 200
    assert body["total"] == 3 and body["page_size"] == 200
    amended = next(row for row in body["items"] if row["id"] == "c")
    assert set(amended) == set(handler.POINT_FIELDS)
    assert amended["location_reason"] is None


@pytest.mark.parametrize("query", [{"page": "0"}, {"page_size": "201"}, {"date_from": "bad"}, {"event_type": "drop table"}, {"file": "events"}])
def test_bad_parameters_are_explicit(query):
    response, body = call("/licences", query=query)
    assert response["statusCode"] == 400
    assert body["error"]["code"] == "BAD_PARAMETER"


def test_hash_mismatch_fails_closed(dataset):
    manifest = json.loads((dataset / "manifest.json").read_text())
    manifest["export_sha256"] = "0" * 64
    (dataset / "manifest.json").write_text(json.dumps(manifest))
    handler.reset_dataset_cache()
    response, body = call("/licences")
    assert response["statusCode"] == 503
    assert body["error"]["code"] == "DATASET_UNAVAILABLE"


def test_s3_loader_uses_manifest_directory_and_verifies_export(monkeypatch):
    record = _record("s3")
    payload = (json.dumps(record) + "\n").encode()
    manifest = json.dumps({"export_file": "events-test.jsonl", "export_sha256": hashlib.sha256(payload).hexdigest()}).encode()
    requested = []

    class Client:
        def get_object(self, *, Bucket, Key):
            requested.append((Bucket, Key))
            value = manifest if Key == "published/manifest.json" else payload
            return {"Body": types.SimpleNamespace(read=lambda limit=-1: value)}

    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setenv("DATA_BUCKET", "wellspring-public-data")
    monkeypatch.setenv("MANIFEST_KEY", "published/manifest.json")
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda service: Client()))
    handler.reset_dataset_cache()
    response, body = call("/licences")
    assert response["statusCode"] == 200 and body["total"] == 1
    assert requested == [("wellspring-public-data", "published/manifest.json"), ("wellspring-public-data", "published/events-test.jsonl")]


def test_cache_refresh_does_not_serve_a_corrupt_new_snapshot(monkeypatch, dataset):
    response, _ = call("/licences")
    assert response["statusCode"] == 200
    manifest = json.loads((dataset / "manifest.json").read_text())
    manifest["export_sha256"] = "0" * 64
    (dataset / "manifest.json").write_text(json.dumps(manifest))
    cached_at = handler._cached_at
    assert cached_at is not None
    monkeypatch.setattr(handler.time, "monotonic", lambda: cached_at + 61.0)
    response, body = call("/licences")
    assert response["statusCode"] == 503
    assert body["error"]["code"] == "DATASET_UNAVAILABLE"


def test_no_source_url_fetching(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access is not part of the API")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    response, body = call("/licences")
    assert response["statusCode"] == 200


def test_preflight_cors_and_refusal_stub():
    response, body = call("/licences", method="OPTIONS", origin="https://example.cloudfront.net")
    assert response["statusCode"] == 204 and body is None
    assert response["headers"]["Access-Control-Allow-Origin"] == "https://example.cloudfront.net"
    assert response["headers"]["Access-Control-Allow-Headers"] == "content-type"
    response, body = call("/ask", method="POST")
    assert response["statusCode"] == 200
    assert body["status"] == "refused" and body["sql"] is None
    assert body["refusal"]["code"] == "ASK_UNAVAILABLE"
    assert body["meta"]["coverage"]["loaded_dates"] == ["2026-08-01", "2026-08-02", "2026-08-03"]


def test_ask_refusal_is_truthful_without_a_dataset(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("DATA_BUCKET", raising=False)
    handler.reset_dataset_cache()
    response, body = call("/ask", method="POST")
    assert response["statusCode"] == 200
    assert body["refusal"] == {"code": "ASK_UNAVAILABLE", "message": "Question answering is not available in this release."}
    assert body["meta"] == {"schema_version": 1, "data_as_of": None, "date_from": None, "date_to": None, "event_type": None, "coverage": None}


@pytest.mark.parametrize("record", [_record("bad-date", report_date="2026-8-01"), _record("bad-kind", event_type="invalid")])
def test_malformed_record_fails_closed(dataset, record):
    payload = (json.dumps(record) + "\n").encode()
    (dataset / "events-test.jsonl").write_bytes(payload)
    manifest = json.loads((dataset / "manifest.json").read_text())
    manifest["export_sha256"] = hashlib.sha256(payload).hexdigest()
    (dataset / "manifest.json").write_text(json.dumps(manifest))
    handler.reset_dataset_cache()
    response, body = call("/licences")
    assert response["statusCode"] == 503 and body["error"]["code"] == "DATASET_UNAVAILABLE"


def test_nonfinite_json_and_bounded_local_export_fail_closed(dataset):
    payload = b'{"id":"nan","report_date":"2026-08-01","event_type":"issued","latitude":NaN}\n'
    (dataset / "events-test.jsonl").write_bytes(payload)
    manifest = json.loads((dataset / "manifest.json").read_text())
    manifest["export_sha256"] = hashlib.sha256(payload).hexdigest()
    (dataset / "manifest.json").write_text(json.dumps(manifest))
    handler.reset_dataset_cache()
    response, _ = call("/licences")
    assert response["statusCode"] == 503
    (dataset / "events-test.jsonl").write_bytes(b"x" * (handler.MAX_EXPORT_BYTES + 1))
    handler.reset_dataset_cache()
    response, _ = call("/licences")
    assert response["statusCode"] == 503


def test_route_and_method_failures_are_explicit():
    response, body = call("/not-a-route")
    assert response["statusCode"] == 404 and body["error"]["code"] == "UNKNOWN_ROUTE"
    response, body = call("/ask")
    assert response["statusCode"] == 405 and body["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_retry_failures_and_parse_counts_are_window_scoped():
    from wellspring.api.handler import _coverage_for_window
    coverage={'loaded_dates':['2026-08-01'],'retry_failed_dates':['2026-08-01'],'parse_issues_by_date':{'2026-09-26':1},'parse_issue_count':1}
    result=_coverage_for_window(coverage,'2026-08-01','2026-08-31')
    assert result['retry_failed_dates']==['2026-08-01']
    assert result['parse_issue_count']==0


def test_points_keep_surface_location_text_and_explicit_missing_value(monkeypatch):
    records = [
        _record("located", surface_location="16-12-066-03W4"),
        _record("missing", surface_location=None),
    ]
    monkeypatch.setattr(handler, "_dataset", lambda: handler.Dataset(records, {}))
    response, body = call("/licences", query={"fields": "points"})
    assert response["statusCode"] == 200
    by_id = {row["id"]: row for row in body["items"]}
    assert by_id["located"]["surface_location"] == "16-12-066-03W4"
    assert by_id["missing"]["surface_location"] is None
