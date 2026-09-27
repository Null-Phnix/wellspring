# Wellspring evidence and open gates

Snapshot: September 27, 2026. Distinguish implementation, review, merge,
deployment and observed runtime. A local test pass is not a forge CI receipt.

| Area | Evidence | Remaining gate or limit |
| --- | --- | --- |
| M1 ingestion | Real August backfill: 31 reports, 1,130 events, 1,455 occurrences; idempotence and SQLite integrity checked | Full January-to-current backlog is not loaded |
| M2 initial deployment | Source e32c27e; both Lambda hashes matched the deployment bundle; ten HTTP checks passed | Later follow-up source must be deployed and reverified separately |
| M2 review close-out | Change #274, head 222e1d4, 231 Python tests; independent review approved | Pinned merge mandate #280 awaits owner approval |
| Map contract addition | Change #279 adds surface_location to points and documents all coverage fields; 232 Python tests | Review, merge and deployment pending |
| Scheduled intake | Lambda started 13:00:44 UTC and ended normally; one invocation metric in that minute; manifest published 13:00:46.971395 UTC | A manual test was not used as scheduled-run evidence |
| Current source coverage | 57 loaded reports through September 26; 2,100 events; 899 issued; no failed dates after the scheduled run | September 27 is not yet published |
| Coordinates | 77 government ATS references, seven held-out checks, five independently re-fetched by the owner agent; 865 mapped events | 1.201 km maximum observed sample error is not a universal guarantee |
| Frontend | Tenjin independently loaded the live dashboard and a filtered licence-table deep link, then refreshed it; no captured browser errors | Nabu owns the full UI/test/deploy receipts on issue #4 |
| M4 Ask | Current live response is ASK_UNAVAILABLE; implementation plan posted on issue #1 | Provider key absent from the authorized configuration; plan approval and implementation remain |
| Release | Private mirror approval exists in board reply #127 | No v0.1.0 tag or GitHub mirror until the required release steps finish |

## September 26 diagnosis

The overnight WELLS0926.TXT file explicitly carried a September 26, 2025 header.
The strict date guard correctly rejected it for a September 26, 2026 request.
By the scheduled morning intake, AER had replaced it with a valid 2026 empty
report, which loaded successfully. This was separate from the unsupported-DLS
parser bug. The local cache now revalidates a cached report and re-fetches stale
or incomplete data, retaining rejected bytes by hash.

## Tests and review

The unsupported-DLS regression modifies only the surface meridian in a real
fixture block, retains all 48 events through SQLite and cloud publication, and
checks the null location reason. Generated contract tests check the live Ask
refusal and both mapped and unplotted examples. Structural and date-validation
failures remain covered.

The initial frontend baseline checked by Tenjin passed eight unit tests and a
production build under Node 26.10.0. Nabu has reported 30 tests on the newer UI
work; that reported count is separate from Tenjin's baseline run and the forge's
actual combined check. The requested combined command is:

```bash
python3 -m pip install -q -e '.[test]' && python3 -m pytest -q && (cd web && npm ci --no-audit --no-fund && npm test -- --watch=false && npm run build)
```

The forge runner configuration is owner-controlled. Do not call the author-logged
check rollup proof that this command ran in the forge.

## Runtime receipts

API: https://yjzy2hz1z1.execute-api.ca-central-1.amazonaws.com

Site: https://d157m2vmtz6y3j.cloudfront.net/

CloudFront distribution E2OWOTRIGM4VB1 was read directly: both 403 and 404 rewrite
to `/index.html`, HTTP 200, with zero error caching. The direct
`/licences?licensee=cenovus` link and a full refresh returned the filtered table
with 106 matching events in the observed default window.

Local receipts are under `output/deployment/` in the development worktree:
`verified-deployment.json`, `final-http-smoke.json`,
`scheduled-ingest-morning.json`, `cloudfront-morning.json`,
`morning-access-audit.json`, `morning-usage.json` and `s3-price.json`.
Generated outputs stay out of Git; the concise claims and reproduction commands
are preserved here and in the Scriptorium task Chronicle.

See [M1 detail](M1-EVIDENCE.md), [M2 detail](M2-EVIDENCE.md),
[DLS references](DLS.md) and [deployment/recovery](DEPLOYMENT.md).


## Afternoon M4 source validation

The earlier provider and merge blockers were resolved by the owner. The approved
DeepSeek key was copied to one SSM SecureString without printing its value or
storing it in source/bundles/command arguments. The requested `deepseek-chat`
alias is accepted by the authenticated provider and currently reports
`deepseek-flash` as its served model. A bounded authentication probe returned
`SELECT 1;` in 0.735 seconds using 23 tokens. This probe is not one of the required
post-deployment business-query receipts.

M4 implements the read-only SQLite boundary, one shared deadline, 200-row cap,
provider refusal handling, secret read and atomic 100-attempt daily quota.
The source was checked with the integrated backend suite and 31 frontend tests
plus a production build. An independent local integration review found three
issues (unverified/unsafe provider model metadata and incomplete enabled-state
deployment verification); they were fixed and rechecked. Exact counts and source
SHAs are recorded in the task Chronicle. Live M4 deployment and the three real
question receipts still require their own evidence before release.
