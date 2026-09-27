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
M2 enriches supported surface DLS positions with approximate coordinates.
Unsupported positions remain null with a nullable `location_reason`; see
`docs/DLS.md` for source checks and measured limits.

## M2 delivery boundary

M2 serves a read-only, immutable JSONL export through a Lambda HTTP API v2
event or Lambda Function URL event. The Lambda reads the manifest named by
`MANIFEST_KEY` (default `published/manifest.json`) from exactly one configured
source: local `DATA_DIR` for development/tests, or `DATA_BUCKET` in deployment.
The manifest must contain `export_file` and lowercase `export_sha256`. The API
reads only that file, verifies its SHA-256 before parsing, and fails closed with
`503 DATASET_UNAVAILABLE` if either file is missing, malformed, or mismatched.
It never fetches a source report URL and does not select an export by filename.

The publisher writes a content-addressed `events-<sha256>.jsonl` before
atomically replacing its manifest. A bare `export_file` is in the manifest's
directory; nested relative paths are also allowed. The API rereads the manifest
at most once every 60 seconds in a warm Lambda environment. If a newly observed
manifest or export fails validation, the request returns `503`; the prior export
is not represented as current data.

Manifests are limited to 2 MiB and exports to 64 MiB. Records must have a
non-empty `id`, a valid ISO `report_date`, and an `event_type` in the shared
ingestion vocabulary. Non-finite JSON values, malformed records, or over-limit
objects fail closed with `503`.

`data_as_of` is the snapshot publication time, not proof that every requested
source day succeeded. `coverage` identifies gaps and `retry_failed_dates`
identifies unsuccessful refreshes whose previous valid records were retained.
`parse_issues_by_date` lets the API return window-scoped parse issue counts. The API never
turns a missing or failed report into a zero-event day. A missing manifest
coverage object is represented as `null`, not invented zeroes.

## Licences

`GET /licences` returns:

```json
{"items": [], "total": 0, "page": 1, "page_size": 50, "meta": {}}
```

Filters: `date_from`, `date_to` (inclusive ISO dates), `licensee`, `substance`,
`field_centre`, `terminating_zone`, `well_type`, `event_type`.
Default event filter is `issued`, so update activity does not inflate newly
issued licence totals. `all` is explicit. Page starts at 1; page_size is 1..200.
Sort allowlist: report_date, licence_number, licensee, substance, field_centre,
terminating_zone, well_type. `order` is asc or desc; ties use the stable event ID.
`licensee` is a literal, case-insensitive substring match. `%` and `_` have no
special meaning. All other text filters are exact, case-sensitive values; the
client should not assume full-text search.

`fields=points` returns the same pagination, `total`, and metadata while
projecting each item to exactly:
`id`, `licence_number`, `well_name`, `licensee`, `substance`, `report_date`,
`latitude`, `longitude`, `coordinate_method`, `location_accuracy`, and
`location_reason`, and `surface_location`. Every projection key is present; unreported values are null.
No other `fields` value is accepted.

## Statistics

The same filters apply to all statistical routes. Each returns `{items,meta}`.
Top-N routes accept `limit` from 1 through 50, default 10. Counts sort descending,
then by grouping value with null last. Daily rows sort ascending by date. Licence
sorting accepts only the allowlist above, with `order=asc|desc` and stable `id`
tie-breaking.

| Route | Item |
|---|---|
| `/stats/daily` | `{date, count}` |
| `/stats/top-licensees` | `{licensee: string or null, count}` |
| `/stats/top-formations` | `{terminating_zone: string or null, count}` |
| `/stats/substances` | `{substance: string or null, count}` |

Missing or failed reports must remain visible as coverage gaps. Coverage date
arrays are sliced to the requested date window and `reports_loaded` is the
count of `loaded_dates` in that window. Loaded dates include parsed empty days.
Daily statistics emit zero for a loaded date with no matching events, but never
invent a zero for a missing or failed date. Null grouping values mean unreported,
not a guessed company/formation. The client CSV export fetches matching rows up to its stated 2,000-row cap;
it is not a complete export when the match count exceeds that cap.

## Shared metadata

```json
{
  "schema_version": 1,
  "data_as_of": null,
  "date_from": "2026-08-01",
  "date_to": "2026-08-02",
  "event_type": "issued",
  "coverage": {
    "reports_loaded": 2,
    "loaded_dates": ["2026-08-01", "2026-08-02"],
    "empty_dates": ["2026-08-02"],
    "retry_failed_dates": [],
    "parse_issues_by_date": {},
    "missing_dates": [],
    "failed_dates": [],
    "parse_issue_count": 0
  }
}
```

`data_as_of` is an ISO timestamp from the manifest or null; the date endpoints
are null only when there is no requested or declared dataset range. An empty
filtered result retains its requested range. General errors are
`{error:{code,message},schema_version:1}`.

Every successful data response includes this `meta` shape. `date_from` and
`date_to` are the supplied inclusive filters, otherwise the loaded manifest's
declared range (falling back to loaded record dates for older manifests). API errors are `400 BAD_PARAMETER`, `404
UNKNOWN_ROUTE`, `405 METHOD_NOT_ALLOWED`, and `503 DATASET_UNAVAILABLE`.

The API accepts only `GET`, `POST`, and `OPTIONS`. CORS echoes an `Origin` only
when it is listed in comma-separated `ALLOWED_ORIGINS` (development default:
`http://localhost:4200`); it never sends wildcard origins or credential headers.
Its allow-methods value is `GET, POST, OPTIONS` and allow-headers is
`content-type`.

## Ask (M4)

`POST /ask {question:string}` accepts a question of at most 1,200 characters.
The provider receives that question and the fixed public `events` schema only.
It does not receive credentials, source files or database access. The configured
DeepSeek alias is `deepseek-chat`; the API reports the provider's actual served
model, currently `deepseek-flash` for that alias.

Success:

```json
{"status":"ok","sql":"SELECT ...","columns":["licensee","count"],"rows":[],"row_count":0,"truncated":false,"model":"deepseek-flash","row_limit":200,"refusal":null,"meta":{}}
```

Refusal:

```json
{"status":"refused","sql":null,"columns":[],"rows":[],"row_count":0,"truncated":false,"model":null,"row_limit":200,"refusal":{"code":"ASK_UNAVAILABLE","message":"Question answering is temporarily unavailable."},"meta":{}}
```

`meta` is the full shared metadata when the dataset is available, otherwise the
full shape with null dataset fields. The existing status discriminator and
columns/rows/sql/refusal fields remain compatible with Nabu's renderer. Missing
provider configuration, unavailable secret/counter/provider and exhausted daily
quota return `ASK_UNAVAILABLE`. Other safe refusals include `INVALID_QUESTION`,
`READ_ONLY_REQUIRED`, `UNSAFE_QUERY`, `INVALID_SQL`, `QUERY_TIMEOUT`,
`QUERY_UNAVAILABLE` and `RESULT_LIMIT`. The frontend displays the returned code
and message rather than inventing an answer.

A model attempt requires one atomic daily-counter increment first. The shared
demo cap defaults to 100 attempts per UTC day; failed provider attempts are not
refunded. The counter stores a date key, count and expiry only, never prompts
or IPs. A counter error fails closed without calling the model. The model key is
read from one SSM SecureString by the API role and cached in process for at most
five minutes. It is not a Lambda environment value or a repository artifact.

Generated SQL is untrusted. It runs against a separate public-data snapshot,
reopened in immutable read-only mode with query_only, an authorizer and SQLite
limits. Only one SELECT in the documented subset is accepted. Output is capped
at 200 rows, with a 201st row indicating truncation. The request uses one
absolute deadline throughout data loading, secret/quota reads, the model call,
snapshot creation and execution. A 9.5-second process alarm leaves encoding and
runtime overhead within the ten-second wall budget. Logs contain status,
duration, row count and served model only. See [the SQL boundary](ASK-SAFETY.md).

## Frontend coordination

Nabu confirmed the v1 field names and nullability in issue #2 comment #117.
M2 adds nullable `location_reason` and the points projection above. Nabu owns
the production API base URL, mock flag and frontend deployment. The CloudFront
template already rewrites 403/404 to index.html for Angular deep links.
