# M2 implementation and runtime evidence

Observed September 27, 2026. This is a backend milestone; the frontend and Ask
model feature remain separate. Local tests and a live candidate do not imply
that a pending Scriptorium change has merged.

## Data and location

- August plus September 1-26 request: 56 reports loaded, 2,100 event rows,
  899 issued events. September 26 fails the source-header validation and remains
  an explicit failed date. The January-to-current backlog is still incomplete.
- 865 events have approximate surface positions. 1,201 lack a surface location;
  34 are outside the converter's validated band. Those positions remain null.
- 77 source-linked Government of Alberta ATS reference polygons, including seven
  held-out verification checks. Measured maximum centroid error is 1.201 km on
  those samples only. The owner independently re-fetched five verification
  polygons and reproduced their centroids. No surveyed wellhead accuracy claim.
- Source bytes are retained in the private data bucket. Initial archive retrieval
  time comes from the M1 source receipt; cached daily files preserve their local
  download timestamp instead of being labelled freshly fetched on every rerun.

## Local checks

The final integrated suite passed 226 tests. Tests include source preservation, geographic references, HTTP
validation and coverage, failed refreshes, publication ordering, ETag guards,
unsafe deployment refusal and deployed-code hash verification logic.

An independent worker found two deployment defects: publication could overwrite
runtime data while the schedule was enabled, and an asynchronous update receipt
could be mistaken for deployment proof. Both were fixed and independently
rechecked. Publication now requires a disabled schedule, preserves loaded dates,
and conditionally switches the manifest; a separate verification command checks
the stack state and both deployed Lambda code hashes.

## Runtime candidate

CloudFormation `wellspring-demo` exists in `ca-central-1`.

- API: https://yjzy2hz1z1.execute-api.ca-central-1.amazonaws.com
- CloudFront domain: https://d157m2vmtz6y3j.cloudfront.net
- Site bucket: `wellspring-demo-sitebucket-qepuhrtijij0`

The first candidate returned HTTP 200 for licences, points projection, all four
statistics routes and the Ask refusal; HTTP 400 for page_size 201; HTTP 404 for
an unknown route; HTTP 204 with the configured origin for CORS preflight.
A real invocation of the ingestion Lambda completed without FunctionError and
retained all 2,100 events. This was a manual invocation, not proof that a future
scheduled invocation has run.

Final code deployment must be confirmed with `scripts/deploy.py verify` after
UPDATE_COMPLETE. The local `output/deployment/verified-deployment.json` receipt
records the committed source, code hash, function revisions and current outputs.
`publish-receipt.json` alone explicitly means update requested, not completed.
The schedule starts disabled and must only be enabled after that readback.

Nabu owns uploading the Angular app and using the real API origin. A provisioned
CloudFront domain alone is not proof of a working frontend. Ask currently returns
`ASK_UNAVAILABLE`; no paid provider call, SQL generation or execution is present.
The $5 AWS budget alarm remains Josii's responsibility under the current handoff.


## Morning review close-out

The unsupported-DLS report rejection is reproduced by changing only the surface
meridian in the first real September 25 fixture block from W4 to unsupported W3.
The corrected parser retains all 48 events, preserves the source location and
sets `location_reason=invalid_surface_dls`; SQLite and cloud publication both
retain the loaded day. Structural corruption and report-date mismatches still
fail closed. The parser version is now 0.1.1 so prior partial interpretations
can be retried without confusing them with this interpretation.

Generated contract examples now use the M2 enrichment path, including a real
cancelled record with missing surface location, and the Ask unavailable refusal.
The integrated suite passes 231 tests.

September 26 was unrelated: the downloaded WELLS0926.TXT explicitly says
`DATE: 26 September 2025`, while the requested date was September 26, 2026. The
rolling filename contains stale prior-year data. The original bytes and receipt
remain under output/source-data/raw/ and manifest.json; no date is relabelled.

The 07:00 Mountain scheduled invocation on September 27 ran at13:00:44 UTC and
finished normally. Its published manifest timestamp is13:00:46.971395 UTC.
AER had then replaced the stale September26 filename with a valid2026 empty
report: coverage now has57loaded reports, nofailed dates and2,100events.
The local backfill cache now revalidates headers before reuse, preserves any
rejected bytes by hash and re-fetches stale or incomplete entries.
