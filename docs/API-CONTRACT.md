# API and record contract v1

Approved for M1 by Anubis in Wellspring issue #1 comment #112, following Tenjin's
plan/schema comment #109. Shared with Nabu on issue #2 comment #110. This contract
is a client/mock target; no HTTP API is claimed implemented in M1.

`wellspring/ingest/models.py` owns the event enum:
`issued`, `reentry`, `amended`, `cancelled`, `updated`.
Only query parameters add `all`. The record schema is
`contracts/licence-event.schema.json`; sample responses are in `contracts/`.
Example record values come from the real fixture; their fixed retrieval
timestamp is illustrative mock metadata, not a historical download receipt.

## Record semantics

Keys use snake_case. Licence numbers and UWIs are strings, including leading
zeros and alphanumeric prefixes. Dates use `YYYY-MM-DD`. `report_date` is the
report header date, not the download date or an invented current year.

One event contains ordered `occurrences`, each with its original UWI, well
name, changed label/value fields, raw block and 1-based source line span.
Scalar summary fields are null if ambiguous across occurrences. Unreported
fields are null; there is no unlabelled carry-forward from historical events.
`source` links the report URL, byte SHA-256, retrieval time and parser version.
Coordinates and their method/accuracy are null until later verified conversion.

## Licences

`GET /licences` returns:

```json
{"items": [], "total": 0, "page": 1, "page_size": 50, "meta": {}}
```

Filters: `date_from`, `date_to` (inclusive), `licensee`, `substance`,
`field_centre`, `terminating_zone`, `well_type`, `event_type`.
Default event filter is `issued`, so update activity does not inflate newly
issued licence totals. `all` is explicit. Page starts at 1; page_size is 1..200.
Sort allowlist: report_date, licence_number, licensee, substance, field_centre,
terminating_zone, well_type. `order` is asc or desc; ties use the stable event ID.
Text filters will use exact values; the client should not assume full-text search.

## Statistics

The same filters apply to all statistical routes. Each returns `{items,meta}`.

| Route | Item |
|---|---|
| `/stats/daily` | `{date, count}` |
| `/stats/top-licensees` | `{licensee: string or null, count}` |
| `/stats/top-formations` | `{terminating_zone: string or null, count}` |
| `/stats/substances` | `{substance: string or null, count}` |

Missing or failed reports must remain visible as coverage gaps. Only a parsed
empty report supports a zero-event day. Null grouping values mean unreported,
not a guessed company/formation. The client CSV exports loaded rows, labelled
as such; it is not a full-database export.

## Shared metadata

```json
{
  "schema_version": 1,
  "data_as_of": null,
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "event_type": "issued",
  "coverage": {
    "reports_loaded": 31,
    "missing_dates": [],
    "failed_dates": [],
    "parse_issue_count": 0
  }
}
```

`data_as_of` is an ISO timestamp or null; the date endpoints can be null for
an empty/unloaded dataset. General errors are
`{error:{code,message},schema_version:1}`.

## Ask (M4)

`POST /ask {question:string}` returns either:

```json
{"status":"ok","columns":[],"rows":[],"sql":"SELECT ...","row_limit":200,"truncated":false,"refusal":null,"meta":{}}
```

or

```json
{"status":"refused","columns":[],"rows":[],"sql":null,"row_limit":200,"truncated":false,"refusal":{"code":"READ_ONLY_REQUIRED","message":"Only read-only data questions are supported."},"meta":{}}
```

SQL must pass a read-only SQLite authorizer, single-statement and table
allowlist checks plus row/time limits. Checking a SELECT prefix alone is not
sufficient. API/provider errors must not expose keys, stack traces or private
configuration. No model call is present in M1.

## Frontend coordination still pending

Nabu should use `report_date`, `latitude`, and `longitude` from the approved
contract, replacing the earlier brainstorming names event_date/lat/lon. API
base URL belongs in one environment file. CloudFront must rewrite 403/404 to
index.html for Angular deep links in M2/M3. Acknowledgement of the final mock
fixtures and any client changes remains explicit on issue #2.
