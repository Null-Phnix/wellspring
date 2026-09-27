"""Local M1 ingestion CLI. No cloud resources or model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .fetch import archive_members, archive_url, day_url, download, month_dates
from .models import ReportError
from .parser import parse_report
from .store import connect, events, import_report, record_attempt


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_time(stop_at: str | None) -> bool:
    if stop_at is None:
        return True
    deadline = datetime.fromisoformat(stop_at.replace("Z", "+00:00"))
    if deadline.tzinfo is None:
        raise ValueError("stop-at requires an explicit timezone")
    # A fetch is bounded to 30 seconds. Do not start one across the hard stop.
    return datetime.now(timezone.utc) + timedelta(seconds=35) < deadline


def ingest_month(*, year: int, month: int, db: Path, output: Path,
                 archive_path: Path | None = None, stop_at: str | None = None) -> dict:
    url = archive_url(year, month)
    output.mkdir(parents=True, exist_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db)
    archive_sha = None
    attempts = []
    try:
        if not _has_time(stop_at):
            return {"status": "stopped", "reason": "hard stop", "month": f"{year:04d}-{month:02d}"}
        if archive_path:
            # Local archive was downloaded once; preserve exactly those bytes.
            from .fetch import MAX_ARCHIVE_BYTES
            with archive_path.open("rb") as stream:
                raw = stream.read(MAX_ARCHIVE_BYTES + 1)
        else:
            fetched = download(url, archive=True)
            if fetched.status != "downloaded":
                for day in month_dates(year, month):
                    record_attempt(conn, day, url, "not_found" if fetched.status == "missing" else "fetch_failed", fetched.error)
                result = {"status": "failed", "source_url": url, "reason": fetched.error,
                          "month": f"{year:04d}-{month:02d}", "coverage": {"missing_dates": month_dates(year, month) if fetched.status == "missing" else [], "failed_dates": month_dates(year, month) if fetched.status != "missing" else []}}
                # A network error is an attempt receipt, not a new dataset.
                # Keep any previously published manifest/export usable.
                _write_json(output / "last-attempt.json", result)
                return result
            raw = fetched.raw
        assert raw is not None
        archive_sha = hashlib.sha256(raw).hexdigest()
        raw_dir = output / "raw"
        raw_dir.mkdir(exist_ok=True)
        (raw_dir / f"{archive_sha}.zip").write_bytes(raw)
        members = archive_members(raw, year, month)
        for day in month_dates(year, month):
            if not _has_time(stop_at):
                attempts.append({"date": day, "status": "stopped"})
                continue
            if day not in members:
                record_attempt(conn, day, url, "not_found", "date absent from monthly archive")
                attempts.append({"date": day, "status": "missing"})
                continue
            name, content = members[day]
            source_url = f"{url}#{name}"
            digest = hashlib.sha256(content).hexdigest()
            (raw_dir / f"{digest}.txt").write_bytes(content)
            try:
                report = parse_report(content, source_url=source_url, expected_date=day)
                result = import_report(conn, report)
                attempts.append({"date": day, "status": report.status if result["status"] != "refused_partial" else "failed",
                                 "import_status": result["status"], "sha256": digest,
                                 "events": len(report.events), "source_blocks": report.source_block_count,
                                 "duplicate_blocks": report.duplicate_block_count,
                                 "parse_issues": [issue.__dict__ for issue in report.issues]})
            except ReportError as error:
                record_attempt(conn, day, source_url, "parse_failed", str(error))
                attempts.append({"date": day, "status": "failed", "reason": str(error), "sha256": digest})
        current = [e for e in events(conn) if e["report_date"].startswith(f"{year:04d}-{month:02d}-")]
        # Publish immutable content first, then atomically point the manifest
        # at it. A failed manifest write leaves the old snapshot coherent.
        tmp = output / "events.pending.jsonl"
        with tmp.open("w") as stream:
            for event in current:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
        export_sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
        export = output / f"events-{export_sha}.jsonl"
        tmp.replace(export)
        missing = [a["date"] for a in attempts if a["status"] == "missing"]
        failed = [a["date"] for a in attempts if a["status"] == "failed"]
        stopped = [a["date"] for a in attempts if a["status"] == "stopped"]
        result = {"schema_version": 1, "status": "complete" if not (missing or failed or stopped) else "incomplete",
                  "month": f"{year:04d}-{month:02d}", "source_url": url, "archive_sha256": archive_sha,
                  "generated_at": _utcnow(), "source": "Alberta Energy Regulator ST1; preliminary, noncommercial educational reproduction; not official or endorsed",
                  "coverage": {"expected_dates": len(attempts), "reports_loaded": sum(a["status"] in {"loaded", "empty"} for a in attempts),
                               "empty_dates": [a["date"] for a in attempts if a["status"] == "empty"],
                               "missing_dates": missing, "failed_dates": failed, "stopped_dates": stopped},
                  "event_count": len(current), "occurrence_count": sum(e["occurrence_count"] for e in current),
                  "counts_by_type": dict(Counter(e["event_type"] for e in current)),
                  "export_file": export.name, "export_sha256": export_sha, "dates": attempts}
        _write_json(output / "manifest.json", result)
        return result
    finally:
        conn.close()


def ingest_range(*, date_from: date, date_to: date, db: Path, stop_at: str | None = None) -> dict:
    """Current rolling daily files only. Header dates prevent wrong-year reuse."""
    if date_to < date_from or (date_to - date_from).days > 365:
        raise ValueError("date range must be ordered and at most 366 days")
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db)
    results = []
    try:
        day = date_from
        while day <= date_to:
            if not _has_time(stop_at):
                results.append({"date": day.isoformat(), "status": "stopped"})
                break
            url = day_url(day)
            fetched = download(url)
            if fetched.status != "downloaded":
                record_attempt(conn, day.isoformat(), url, "not_found" if fetched.status == "missing" else "fetch_failed", fetched.error)
                results.append({"date": day.isoformat(), "status": fetched.status, "error": fetched.error})
            else:
                try:
                    report = parse_report(fetched.raw, source_url=url, expected_date=day.isoformat())
                    results.append(import_report(conn, report))
                except ReportError as error:
                    record_attempt(conn, day.isoformat(), url, "parse_failed", str(error))
                    results.append({"date": day.isoformat(), "status": "failed", "error": str(error)})
            day += timedelta(days=1)
        return {"items": results, "status": "complete" if all(r["status"] in {"imported", "reselected", "idempotent"} for r in results) else "incomplete"}
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    month = sub.add_parser("month", help="Backfill one official monthly archive")
    month.add_argument("month", help="YYYY-MM")
    month.add_argument("--archive", type=Path, help="Use a previously downloaded archive")
    month.add_argument("--output", type=Path, default=Path("output/backfill"))
    day_range = sub.add_parser("range", help="Fetch daily files with header-date verification")
    day_range.add_argument("date_from", type=date.fromisoformat)
    day_range.add_argument("date_to", type=date.fromisoformat)
    for command in (month, day_range):
        command.add_argument("--db", type=Path, default=Path("data/wellspring.sqlite3"))
        command.add_argument("--stop-at", help="ISO timestamp with timezone")
    args = parser.parse_args(argv)
    try:
        if args.command == "month":
            selected = date.fromisoformat(args.month + "-01")
            result = ingest_month(year=selected.year, month=selected.month, db=args.db,
                                  output=args.output, archive_path=args.archive, stop_at=args.stop_at)
        else:
            result = ingest_range(date_from=args.date_from, date_to=args.date_to, db=args.db, stop_at=args.stop_at)
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
