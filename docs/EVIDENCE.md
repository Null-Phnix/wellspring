# Wellspring evidence and limitations

Observed September 27, 2026. Implementation, review, merge, deployment and runtime
are separate evidence. Scriptorium issue #1 contains the coordinated receipts.

| Area | Verified evidence | Limit |
| --- | --- | --- |
| M1 ingestion | August fixture: 31 reports, 1,130 events and 1,455 occurrences; idempotence and SQLite integrity checked | Later reports may revise historical data |
| M2 follow-ups | Changes #274 and #279 merged; unsupported DLS no longer rejects a valid report; generated contracts and points projection corrected | Structural/header-date errors remain fatal |
| M3 frontend | Live dashboard, filtered licence table, map, Ask and About; 31 tests in 8 files and production build passed locally, also independently reproduced by Nabu | Unit tests do not prove every browser/device |
| M4 Ask | Change #285 source 17e7e7a independently approved and forge-verified; merged main a4c337a deployed and configuration verified | Generated SQL can still misunderstand a question |
| Current dataset | 266 loaded reports, January 1 to September 27 request: 8,811 events, 3,763 issued, 3,685 approximate positions | January 11/16, July 9 and September 27 fail source validation; gaps are not zeroes |
| Scheduled intake | Actual Lambda start 13:00:44 UTC; normal END/REPORT and one invocation metric in that minute; manifest publication 13:00:46.971395 UTC | Later manual smoke calls are not scheduled-run evidence |
| Coordinates | 77 government ATS references, 7 held out; 5 independently refetched; maximum observed sample error 1.201 km | Not a universal bound or surveyed wellhead position |
| Access | Both buckets private; CloudFront-only public site access; narrow API secret/quota grants; scoped ingestion writes | Account administrator privileges were not exhaustively audited |

## Tests and forge evidence

The integrated M4 source passed **316 backend tests**, **31 web tests in 8 files**
and the Angular production build. The 316 backend tests passed under both
Python 3.11 and 3.14. The M4 predecessor a4c337a passed 310 backend
tests; Nabu independently reproduced those 310 plus the same 31 web tests.
Six additional regressions cover the official ST1/ archive wrapper without
allowing traversal, arbitrary nesting or duplicate days. SQL tests cover read-only enforcement, DML/DDL, PRAGMA,
ATTACH, comments, multi-statements including quoted trailers, invalid functions,
metadata access, timeouts and result limits. Integration tests cover unavailable
secrets/provider/counter, atomic quota allocation, actual served-model metadata,
credential-echo refusal and deployment configuration drift.

The combined command is:

```bash
python3 -m pip install -q -e '.[test]' && python3 -m pytest -q && (cd web && npm ci --no-audit --no-fund && npm test -- --watch=false && npm run build)
```

Angular uses Vitest/jsdom here, not ChromeHeadless. GitHub's checked-in workflow
runs Python 3.11/3.14 and Node 22 lanes. The exact-head forge metadata records a
passed check for change #285 at 17e7e7afd9cea36d64bc7f1e188965780e4319fc and an
approved independent review. That metadata alone does not disclose the executed
command. Anubis confirmed in issue #1 #174 that this was the Python-only check. The
combined command is locally verified, but an owner setting is required before
the forge runs it. Anubis explicitly allowed release with that distinction; no
combined forge result is claimed. GitHub workflow outcomes must also be read
back after mirroring.

## Deployment and scheduled operation

- Site: https://d157m2vmtz6y3j.cloudfront.net/
- API: https://yjzy2hz1z1.execute-api.ca-central-1.amazonaws.com
- Stack: `wellspring-demo`, `ca-central-1`.
- Verified backend source: `e9ef5d21b27a29db96ac73041a304f4366843088`.
- Both Lambda code packages matched SHA-256
  `abecaf7dfb23da1f9371734c557f3b935f115f0235cb7eaafc0e49d5d6853937`.
- Ask enabled state, provider/model/key reference/daily limit and actual API
  environment were read back. Only the secret reference is an environment value.
- Daily schedule restored and read back as ENABLED, `cron(0 7 * * ? *)`,
  `America/Edmonton`. It checks recent completed days intentionally.
- CloudFront E2OWOTRIGM4VB1 has actual 403/404 responses to `/index.html`, HTTP 200,
  zero error caching. A filtered deep link survived full reload.
- Nabu's About deployment (#283, 0ad77a4, bundle main-ODYG5JHL.js) aligns with the
  corrected README authorship paragraph from repo-board #134.

The September 26 rolling source initially carried a **September 26, 2025**
header. Strict validation correctly refused it as a 2026 report. By the real
scheduled morning run, AER supplied a valid 2026 empty report. The local cache
now revalidates/refetches stale content and retains rejected bytes by hash.
This source-date failure was separate from the unsupported-DLS parser defect.

A later manual full-history ingestion smoke retained all 8,811 events and
retried September 24 to 26 successfully, using 216 MB of 512 MB and 4.243 seconds.
Its manifest publication was 17:10:32.053070 UTC. This is separate from the last
actual scheduled run at 13:00:44 UTC, which processed the then-current 2,100-event
snapshot. The schedule was restored and verified ENABLED after deployment.

## Initial M4 Ask acceptance (August to September snapshot)

The three responses were independently compared with Python counts from the
hash-verified snapshot, rather than checked only for HTTP 200. Snapshot SHA-256:
`0cba13ea39ebbb11b753c82f9757cf7da862a59809213c8bc4162a024938a942`.
Configured alias: `deepseek-chat`; all three returned actual model
`deepseek-flash`, `status:ok`, and `truncated:false`.

| Question | Returned result | Rows | Elapsed |
| --- | --- | --- | --- |
| Top five issued licensees in August 2026 | Canadian Natural 73, Cenovus 69, Spur 48, Strathcona 15, Headwater 14 | 5 | 5.786 s |
| September issued GAS by field centre | Bonnyville 1, Drayton Valley 30, Edmonton 5, Fort McMurray 3, Grande Prairie 23, Red Deer 10, Slave Lake 1 | 7 | 1.479 s |
| Issued events by Monday-based week, YYYY-%W | Weeks 31 to 38: 71, 98, 102, 112, 139, 89, 103, 185 | 8 | 1.180 s |

Full questions, SQL, rows and curl reproduction commands are on issue #1 #171;
local `ask-real-receipts.json` retains responses and expected rows. The GAS query
used substring matching, which matches the independently checked exact GAS
counts on this snapshot; that is not a universal semantic-correctness guarantee.
A requested DROP TABLE returned READ_ONLY_REQUIRED, no SQL and no rows. The
counter was 4 after these attempts and 5 after a separate browser query returned
899 issued events with inspectable SQL and no captured console errors.

## Wider historical snapshot deployed

The original January-to-current scope was fetched and parsed in isolation, then
reviewed and published after change #289 merged. The live snapshot includes 266 valid report dates, 37 empty dates, 8,811 events and
11,324 occurrences. Counts: 3,763 issued, 1,113 amended, 3,469 updated and 466
cancelled. The export is 18,501,272 bytes, SHA-256
`89656c14cb785a92200680590a4bfe6f406bad8821573138c72c3c060ec8f2e6`.
All original 2,100 event IDs remain present. Owner checks re-read every usable
report header/hash, all eight archive layouts and SQLite integrity. API loading
plus grouped SQL ran locally in 0.284 seconds at 134.4 MiB peak RSS. That is local
capacity evidence. Live Lambda reports subsequently measured 213 MB cold and
251 MB on a warm snapshot refresh, triggering the release configuration increase
to 512 MiB. Post-update readback at 17:16 UTC confirmed UPDATE_COMPLETE,
API MemorySize 512, Timeout 15 and Successful update state; the code hash
remained unchanged and a fresh API call still returned all 8,811 events.

January 11 and 16 lack an end marker; July 9 contains a literal `/---W/` UWI in
an amendment. Independent owner downloads from the rolling daily endpoints
matched the same byte hashes, so the failures were not just stale archives.
September 27 still serves a 2025 header. All four remain failed dates, not zeroes
or silently accepted partial days. No validation rule was weakened to fill them.
July's official ZIP uses `ST1/`; the shared reader now supports that exact wrapper
while preserving limits and path/duplicate rejection. Raw source archives and
individual reports are retained locally and in the private data bucket under
raw/backfill-2026/. The API readback confirms 8,811 events and 266 valid dates.
Repeated live Ask checks returned the same August top five and September GAS
counts, plus 38 weekly rows across the expanded dataset. All matched independent
counts, with no truncation, in 8.271/1.699/1.759 seconds. DROP was refused again.
The shared counter read 26/100 at 17:10 UTC, including other live callers. Full
questions, SQL and answers are in [ASK-RECEIPTS.md](ASK-RECEIPTS.md).

## Release procedure and known limits

The owner approved a **private** `Null-Phnix/wellspring` mirror. Tag v0.1.0 only
after required work merges with the configured forge check and independent
review approved at the pinned head. The combined forge setting limitation above
remains explicit. Scriptorium
Scribe Git permissions disallow raw tag creation; the owner-admin governed tag
operation must target the exact merged release commit. Then mirror only main and
the tag, verify private visibility and matching hashes, and record the final
URLs and receipts on issue #1. No tag or mirror completion is implied by this
pre-release document.

Limitations: four explicit source-validation gaps in historical coverage; approximate
and sometimes absent coordinates; preliminary/revisable source data; a shared
100-attempt UTC-day Ask quota; 200 returned rows and a ten-second wall budget;
model-generated SQL may misunderstand requests; no user accounts or production
SLA; owner-managed budget alarm not independently verified. This is an
independent educational demo, not an AER or GeoLOGIC product.

Raw runtime receipts remain outside Git under `output/deployment/`, including
`verified-deployment.json`, `scheduled-ingest-morning.json`,
`m4-ingest-smoke.json`, `m4-access-audit.json`, `m4-schedule-counter.json`,
`ask-real-receipts.json`, `full-history-ask-receipts.json`,
`full-history-api-readback.json`, `full-history-ingest-invoke.json`,
`full-history-schedule.json`, and `cloudfront-morning.json`. The concise evidence and
reproduction instructions are retained in Git and the forge Chronicle.

See [M1 detail](M1-EVIDENCE.md), [M2 detail](M2-EVIDENCE.md),
[DLS references](DLS.md), [SQL boundary](ASK-SAFETY.md),
[cost/access](COST-ACCESS.md) and [deployment/recovery](DEPLOYMENT.md).
