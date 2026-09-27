# Decisions

Dated, one per line, newest first. Why, not just what.

- 2026-09-27: Independent M1 review found stale A/B/A report selection, shifted-column corruption and a two-file export publication failure. Track the current source per date, reject shifted fixed-width origins, and publish content-addressed JSONL before the atomic manifest pointer. Add original-reproducer regressions before claiming those paths corrected. (Tenjin)

- 2026-09-27: M1 stores one event per licence/type/header-date and all distinct UWI occurrences under it. The real September 25 fixture has 48 event keys but 84 blocks; dropping repeated keys would lose data. Source bytes/parser-version history is retained; partial parses cannot replace valid records. (Tenjin; issue #1 comments #109/#112)
- 2026-09-27: Shared names are report_date, latitude and longitude, with one event enum in models.py and explicit null coordinates until verified DLS conversion. Nabu mocks the approved response contract; no inferred current-well status. (Tenjin; issue #1 comment #112)
- 2026-09-27: Use the official August 2026 monthly ZIP for M1's complete sample-month backfill and strict header-date checks for rolling daily URLs. Empty, missing, failed and stopped dates are separate. Requests identify Wellspring; no authenticated data source is used. (Tenjin)
- 2026-09-27: Keep runtime ingestion dependency-free Python 3.11+ and standard SQLite/JSONL for the first milestone. AWS, LLM provider use and GitHub mirroring are not part of M1; the workflow file is prepared locally for later authorized mirroring. (Tenjin)

- 2026-09-26: Project created from docs/SPEC.md. Lanes: Tenjin ingestion/parser/API/AWS/CI, Nabu Angular web. Scriptorium is the source of truth; GitHub mirror only on Josii approval. (Anubis)
