# Wellspring: Alberta well-licence explorer (demo project for the GeoLOGIC application)

Owner: Josii. Hands: Tenjin (backend, data, AWS), Nabu (Angular front end). Overseer: Anubis. Repo: Scriptorium first, mirror to GitHub Null-Phnix/wellspring when Josii approves.
Deadline: 2 days from kickoff. Ship a smaller working thing over a bigger broken one.

## Why this exists
GeoLOGIC Systems (Calgary) is hiring a Junior Software Developer: cloud-first AWS product, AI in daily development, Angular/TypeScript, Python, SQL, REST, Git; nice-to-haves AWS, LLM tooling, interest in energy, geospatial, large-scale data. Their own Daily Oil Bulletin site (dobenergy.com/data/licences) publishes "Well Licences Issued, Daily New Locations, Top Target Formations" from the AER's public ST1 feed. Wellspring is a small, honest, public version of that idea, built from the same public feed, so Josii can show Angular, AWS, Python data work and geospatial handling in one link. It is a portfolio piece, not a competitor.

## Data source
AER ST1, Well Licences Issued Daily List. Public fixed-width text reports, one per day:
https://static.aer.ca/prd/data/well-lic/WELLS{MMDD}.TXT (example: WELLS0925.TXT for 25 Sep 2026; the year is the current year, files roll)
Each record is a 5-line block: well name, licence number, mineral rights, ground elevation; UWI (unique identifier), surface co-ordinates, AER field centre, projected depth; AER classification, field, terminating zone; drilling operation, well purpose, well type, substance; licensee, surface location (LSD-SEC-TWP-RGE-MER). Also carries amendments, cancellations and updates sections; parse those as separate event types. Sample saved in this folder as WELLS0925.sample.txt.
Terms: AER public data; attribute the AER in the README and UI footer. Do not touch dobenergy.com or anything Geologic owns.

## Scope (must ship)
1. Python ingestion (`wellspring/ingest`): fetch a date range of ST1 files (backfill 2026-01-01 to today, then daily), parse the fixed-width blocks into typed records, dedupe on (licence_number, event_type, date), write to SQLite locally and to S3 as raw text plus a parquet or JSONL export. pytest suite with real-file fixtures covering at least: a normal new licence, an amendment, a cancellation, a day with zero licences, a malformed block. Target 40+ tests.
2. Geospatial: convert Alberta DLS surface locations (LSD-Section-Township-Range-Meridian) to approximate lat/lon using the township grid method (documented, labelled approximate in the UI; accuracy to roughly a section is fine). Unit-test against 5 known coordinates.
3. API (`wellspring/api`): Python on AWS Lambda behind a function URL or API Gateway. Endpoints: /licences (filters: date range, licensee, substance, field centre, terminating zone, well type; paginated), /stats/daily, /stats/top-licensees, /stats/top-formations, /ask (see 5). Read-only. Loads the export from S3 into memory or SQLite at cold start.
4. Angular front end (`wellspring/web`, Angular 18+, standalone components, TypeScript strict): pages: Dashboard (licences per day chart, substance mix, top 10 licensees, top 10 target formations for a selectable window), Licences table (filters above, sortable, CSV export), Map (Leaflet, plotted surface locations, colour by substance, popup with the record), Ask (natural-language box). Angular unit tests for the licences table and the DLS display pipe at minimum. Deployed as static files to S3 + CloudFront.
5. LLM feature: /ask takes a plain-English question, generates a read-only SQL query against the documented schema, runs it with a row limit, and returns rows plus the SQL it wrote (shown in the UI so the user can check it). Use the cheapest capable model available through Josii's existing provider setup; key from ~/.config/anubis/env.conf, never in the repo. Refuse anything that is not a SELECT.
6. Automation: EventBridge schedule runs ingestion daily at 07:00 Mountain. GitHub Actions (or Scriptorium CI) runs pytest and Angular tests on every push.
7. AWS: everything on free tier where possible; one CloudFormation or SAM template (or Terraform, pick one and say why) so it deploys from scratch; AWS Budgets alarm at $5/month. Josii creates the AWS account and puts credentials in env.conf; hands never see or print them.
8. README written in plain English, no marketing: what it is, the data source and its terms, the architecture in one diagram, the DLS approximation caveat, how to run locally, how it was built (Josii designed and directed it and reviewed the code; implementation by AI coding agents under his review). No em-dashes anywhere in the repo docs.

## Out of scope
Production data, well status, pipelines, anything paid, user accounts, mobile.

## Quality gates (Josii's standing rules)
Plan before build: post the plan and the parser record schema to the Scriptorium repo board before writing code; Josii or Anubis approve. Pinned-commit approvals for the milestone merges. No claiming done without the URL live and the tests green in CI. If a fallback model touches the code, review that diff before building on it. Keep a DECISIONS.md with dates.

## Milestones
M1 (day 1 AM): parser + tests + local SQLite, sample month backfilled. M2 (day 1 PM): Lambda API live on AWS with the data. M3 (day 2 AM): Angular dashboard + table + map live on CloudFront. M4 (day 2 PM): /ask, daily schedule, README, CI green, Josii walkthrough.
