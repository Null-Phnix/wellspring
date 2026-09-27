# Wellspring: Alberta well-licence explorer

Original build spec, written before the first commit and trimmed afterwards to the parts that describe the product. The build ran as a two-day exercise: ship a smaller working thing over a bigger broken one. What actually shipped, and where it differs from this plan, is recorded in `EVIDENCE.md` and `../DECISIONS.md`.

## Why this exists
The Alberta Energy Regulator publishes every well licence it issues as a daily fixed-width text report. That feed is public but awkward: no API, no history view, no map. Wellspring turns it into a small, honest, public explorer so the daily licensing activity in the province can be browsed, filtered, mapped and questioned in plain English. It is an independent portfolio project, not a commercial product and not affiliated with the AER or any data vendor.

## Data source
AER ST1, Well Licences Issued Daily List. Public fixed-width text reports, one per day:
https://static.aer.ca/prd/data/well-lic/WELLS{MMDD}.TXT (example: WELLS0925.TXT for 25 Sep 2026; the year is the current year, files roll). Monthly archives exist as ZIP files for backfill.
Each record is a 5-line block: well name, licence number, mineral rights, ground elevation; UWI (unique well identifier), surface co-ordinates, AER field centre, projected depth; AER classification, field, terminating zone; drilling operation, well purpose, well type, substance; licensee, surface location (LSD-SEC-TWP-RGE-MER). The report also carries amendment, cancellation and update sections; those are parsed as separate event types. A real daily file is kept in `../fixtures/` for parser tests.
Terms: AER public data; the AER is attributed in the README and the UI footer.

## Scope (must ship)
1. Python ingestion (`wellspring/ingest`): fetch a date range of ST1 files (backfill from 2026-01-01, then daily), parse the fixed-width blocks into typed records, dedupe on (licence number, event type, report date), keep the source bytes for provenance, write to SQLite locally and publish a content-addressed export to S3. pytest suite with real-file fixtures covering at least: a normal new licence, an amendment, a cancellation, a day with zero licences, a malformed block.
2. Geospatial: convert Alberta DLS surface locations (LSD-Section-Township-Range-Meridian) to approximate latitude and longitude with the township grid method, documented and labelled approximate in the UI, accuracy to roughly a section. Unit-test against known coordinates. Unsupported locations keep a null position and a reason, never a guessed point.
3. API (`wellspring/api`): Python on AWS Lambda behind API Gateway. Endpoints: /licences (filters: date range, licensee, substance, field centre, terminating zone, well type; paginated; a points projection for the map), /stats/daily, /stats/top-licensees, /stats/top-formations, /ask (see 5). Read-only. Loads the published export at cold start. Every response carries coverage metadata so missing or failed days are visible, not silent.
4. Angular front end (`web`, Angular 18+, standalone components, TypeScript strict): Dashboard (licences per day, substance mix, top 10 licensees, top 10 target formations for a selectable window, coverage strip), Licences table (all filters, sortable, paginated, CSV export, filter state in the URL), Map (Leaflet, surface positions coloured by substance, popup per record, approximate-position note), Ask (plain-English question box), About. Unit tests for the table, the DLS display pipe, dashboard helpers and Ask states. Deployed as static files to S3 behind CloudFront, with 403 and 404 rewritten to index.html so deep links survive a refresh.
5. Ask: takes a plain-English question, has a language model write a single read-only SQL statement against the documented schema, validates it, runs it with a row limit and a time budget, and returns the rows together with the SQL so the user can check the work. Anything that is not a single SELECT is refused. Read-only is enforced at the database connection, not only by inspecting the text. A daily call allowance protects the demo's inference budget. The provider key lives in AWS SSM Parameter Store, never in the repository.
6. Automation: an EventBridge schedule runs ingestion daily at 07:00 Mountain. Tests run on every change before merge.
7. AWS: free tier where possible; one CloudFormation template so the whole stack deploys from scratch; private buckets with CloudFront origin access; a $5/month budget alarm.
8. README in plain English, no marketing: what it is, the data source and its terms, the architecture, the DLS approximation caveat, how to run locally, how to deploy, and how it was built.

## Out of scope
Production volumes, current well status, pipelines, paid data, user accounts, native mobile.

## Quality gates
Plan before build: the record schema and API contract are reviewed before code. Every change is merged at a pinned commit after an independent review and a verified test run. Nothing is called done until the URL is live and the tests are green. Decisions are logged with dates in `../DECISIONS.md`.

## Milestones
M1: parser, tests, local SQLite, a sample month backfilled. M2: Lambda API live on AWS with the data and approximate positions. M3: Angular dashboard, table and map live on CloudFront. M4: Ask, daily schedule, README, full history backfill, release tag.
