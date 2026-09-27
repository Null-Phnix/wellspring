# M1 evidence, September 27 2026

These are local results. AWS, public URLs, DLS-derived coordinates and real
LLM calls are not implemented or claimed here.

## Actual sources

- Seed fixture WELLS0925.TXT, header September 25, 2026: 31 issued, 1 amended,
  3 cancelled and 13 grouped updated events. 48 event rows retain 84 occurrences.
- August 2026 official monthly ZIP, SHA-256
  `ec92c3f83ceba89d37b0b6678e7dc6e2956b2ff307074cf298049767f8cf41cc`:
  31 daily reports, including 7 empty days; no missing/failed days.
- August result: 406 issued, 145 amended, 30 cancelled, 549 updated event rows.
  Total 1,130 event rows preserve 1,455 source occurrences. There are no discarded
  malformed blocks in this dataset.
- Real source edge cases covered: butted RESUMPTION/PRODUCTION columns,
  1F1/1S0/AA/AB UWI prefixes, AER classification label without a colon,
  repeated licence/date with different UWI suffixes, and same-day issue/cancel.

## Reproduce

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m wellspring.ingest.cli month 2026-08 \
  --archive fixtures/dwll2026-08.zip \
  --db data/wellspring.sqlite3 --output output/2026-08
```

The tests independently assert known real-fixture counts and text fields,
error/refusal cases, bounded archive validation, source dates and lines,
idempotence, parser-version replacement, transactional rollback and successful
end-to-end import/export. Synthetic mutations are labelled in the tests.

The real local SQLite import passed `PRAGMA integrity_check` and
`PRAGMA foreign_key_check`. A second import retains 31 source interpretations,
does not duplicate 1,130 events, and gives an identical JSONL content hash.
Exports use content-addressed filenames and an atomic manifest pointer; a
failed manifest publication cannot change its previously referenced bytes.
Full raw reports are retained independently of current event materialization.
Partial parses retain source and diagnostics but never replace valid events.

The final integrated suite has 100 passing tests. A separate read-only reviewer
reproduced source reselection, column-shift refusal, partial-import preservation,
and export publication failure behavior after the fixes. This local review
does not replace Scriptorium's independent review or merge approval.

## Remaining scope

- The full January-to-current backlog remains for later ingestion work.
- Separately headed reentry input currently has synthetic coverage only.
- M2 API and cloud template, verified DLS approximation, M3 client, M4 Ask,
  scheduled ingestion and actual forge check receipt are separate gates.
