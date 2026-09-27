# Decisions

Dated, one per line, newest first. Why, not just what.

- 2026-09-27: Web lane types (web/src/app/api/types.ts) mirror the v1 contract from issue #1 comment 109 and the mocks (mock-data.ts, toggled by environment.mock) serve those shapes, so the skeleton runs without the backend and integration is a URL change. Contract changes go through #1 first, then those two files. Charts are CSS bars, no chart library until one is asked for; Leaflet is the only added dependency. (Nabu)

- 2026-09-26: Project created from docs/SPEC.md. Lanes: Tenjin ingestion/parser/API/AWS/CI, Nabu Angular web. Scriptorium is the source of truth; GitHub mirror only on Josii approval. (Anubis)
