# M4 ask SQL boundary

`wellspring.api.query.execute_readonly(records, sql, deadline)` accepts the
already validated public export records, one SQL statement, and an **absolute**
`time.monotonic()` deadline supplied by the request handler. Snapshot creation,
query preparation, execution, and result fetching all consume the same remaining
time. It returns `columns`, object `rows`, `row_count`, and `truncated`, or raises
`QueryRefusal(code, message)` with a stable public message.

The query sees one typed SQLite table, `main.events`, containing only `id`,
`licence_number`, `report_date`, `event_type`, `licensee`, `substance`,
`field_centre`, `terminating_zone`, `well_type`, `well_purpose`,
`surface_location`, `latitude`, and `longitude`. All columns except the final
two coordinates are `TEXT`; coordinates are `REAL`. Unknown and absent source
values are SQL `NULL`. Source URLs, report text, provenance, and other export
fields are never copied into this snapshot. `SCHEMA_TEXT` is the provider-facing
schema description.

The writer connection creates and fills a private temporary file and closes
before the query connection opens it with `mode=ro&immutable=1`. The reader has
`query_only=ON`. Its SQLite authorizer allows SELECT, reads of approved columns
from `main.events`, and a short function allowlist for aggregations, dates, null
handling, case conversion, and LIKE. All other actions are denied, including
writes, schema and system table reads, ATTACH, PRAGMA, and extension calls.
This authorizer and the immutable connection are the execution boundary; the
SQL prefix check only defines the supported syntax.

Supported SQL begins with `SELECT` and may have one trailing semicolon. The
scanner recognizes doubled quotes and semicolons inside single or double
quotes. Comments, backtick or bracket identifiers, `WITH` (including recursive
CTEs), and multiple statements are refused. SQLite then parses and executes
exactly one statement. SQL is limited to 4 KiB; the snapshot to 100,000 events;
expressions to depth 32; output to 24 distinct columns, 200 rows, 4 KiB per
cell, and 256 KiB total row JSON. A 201st row sets `truncated=true` and is not
returned. SQLite progress handlers interrupt costly preparation or execution
when the shared deadline expires. Failures return safe refusals without raw SQL
engine errors or temporary paths.

These controls bound the query component. The caller must give it only the
verified public export and carry the same deadline through body validation and
the provider call. The caller must not include `QueryRefusal` internals or raw
SQLite exceptions in HTTP responses.
