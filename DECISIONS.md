# Decisions

Dated, one per line, newest first. Why, not just what.

- 2026-09-27: M2 uses plain CloudFormation so the installed AWS CLI can reproduce the data/site buckets, scoped functions, HTTP API, CloudFront and timezone-aware schedule without a SAM build dependency. The two-phase code-key update keeps artifacts in the template-owned data bucket; scheduled intake remains disabled until validated. (Tenjin; issue #1 #125/#126)
- 2026-09-27: API uses literal case-insensitive substring matching for licensee, exact matching for other text filters, a capped points projection, shared event enum and explicit coverage gaps. Ask returns an unavailable refusal until M4 implements it. (Tenjin and Nabu; issue #1 #119)
- 2026-09-27: Display coordinates use an offline DLS grid approximation checked against independent Government of Alberta ATS polygons. Unsupported or absent surface locations remain null with a reason; measured sample error is not a universal surveying guarantee. (Tenjin; docs/DLS.md)

- 2026-09-27: Web lane types (web/src/app/api/types.ts) mirror the v1 contract from issue #1 comment 109 and the mocks (mock-data.ts, toggled by environment.mock) serve those shapes, so the skeleton runs without the backend and integration is a URL change. Contract changes go through #1 first, then those two files. Charts are CSS bars, no chart library until one is asked for; Leaflet is the only added dependency. (Nabu)
- 2026-09-27: Independent M1 review found stale A/B/A report selection, shifted-column corruption and a two-file export publication failure. Track the current source per date, reject shifted fixed-width origins, and publish content-addressed JSONL before the atomic manifest pointer. Add original-reproducer regressions before claiming those paths corrected. (Tenjin)

- 2026-09-27: M1 stores one event per licence/type/header-date and all distinct UWI occurrences under it. The real September 25 fixture has 48 event keys but 84 blocks; dropping repeated keys would lose data. Source bytes/parser-version history is retained; partial parses cannot replace valid records. (Tenjin; issue #1 comments #109/#112)
- 2026-09-27: Shared names are report_date, latitude and longitude, with one event enum in models.py and explicit null coordinates until verified DLS conversion. Nabu mocks the approved response contract; no inferred current-well status. (Tenjin; issue #1 comment #112)
- 2026-09-27: Use the official August 2026 monthly ZIP for M1's complete sample-month backfill and strict header-date checks for rolling daily URLs. Empty, missing, failed and stopped dates are separate. Requests identify Wellspring; no authenticated data source is used. (Tenjin)
- 2026-09-27: Keep runtime ingestion dependency-free Python 3.11+ and standard SQLite/JSONL for the first milestone. AWS, LLM provider use and GitHub mirroring are not part of M1; the workflow file is prepared locally for later authorized mirroring. (Tenjin)

- 2026-09-26: Project created from docs/SPEC.md. Lanes: Tenjin ingestion/parser/API/AWS/CI, Nabu Angular web. Scriptorium is the source of truth; GitHub mirror only on Josii approval. (Anubis)
