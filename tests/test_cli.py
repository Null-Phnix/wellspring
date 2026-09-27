import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

from wellspring.ingest.cli import ingest_month, main

ARCHIVE = Path(__file__).parents[1] / "fixtures/dwll2026-08.zip"


def test_real_month_import_export_and_idempotent_rerun(tmp_path):
    kwargs = dict(year=2026, month=8, db=tmp_path / "data/db.sqlite3", output=tmp_path / "out", archive_path=ARCHIVE)
    first = ingest_month(**kwargs)
    second = ingest_month(**kwargs)
    assert first["status"] == second["status"] == "complete"
    assert first["event_count"] == 1130
    assert first["occurrence_count"] == 1455
    assert first["coverage"]["reports_loaded"] == 31
    assert len(first["coverage"]["empty_dates"]) == 7
    assert second["export_sha256"] == first["export_sha256"]
    assert all(d["import_status"] == "idempotent" for d in second["dates"])
    rows = [json.loads(line) for line in (tmp_path / "out" / second["export_file"]).read_text().splitlines()]
    assert len(rows) == 1130
    with sqlite3.connect(kwargs["db"]) as c:
        assert c.execute("SELECT count(*) FROM source_reports").fetchone()[0] == 31
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_missing_archive_dates_are_not_zero_reports(tmp_path):
    with zipfile.ZipFile(ARCHIVE) as z:
        raw = z.read("WELLS0801.TXT")
    short = tmp_path / "short.zip"
    with zipfile.ZipFile(short, "w") as z: z.writestr("WELLS0801.TXT", raw)
    result = ingest_month(year=2026, month=8, db=tmp_path / "x.db", output=tmp_path / "out", archive_path=short)
    assert result["status"] == "incomplete"
    assert result["coverage"]["empty_dates"] == ["2026-08-01"]
    assert len(result["coverage"]["missing_dates"]) == 30


def test_wrong_year_archive_header_fails_without_fabricating_year(tmp_path):
    result = ingest_month(year=2025, month=8, db=tmp_path / "x.db", output=tmp_path / "out", archive_path=ARCHIVE)
    assert result["event_count"] == 0
    assert len(result["coverage"]["failed_dates"]) == 31


def test_deadline_prevents_work(tmp_path):
    result = ingest_month(year=2026, month=8, db=tmp_path / "x.db", output=tmp_path / "out", archive_path=ARCHIVE, stop_at="2000-01-01T00:00:00Z")
    assert result["status"] == "stopped"
    with sqlite3.connect(tmp_path / "x.db") as c:
        assert c.execute("SELECT count(*) FROM source_reports").fetchone()[0] == 0


def test_cli_invalid_month_returns_error(tmp_path,capsys):
    assert main(["month", "2026-13", "--db", str(tmp_path / "x.db")]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_manifest_publish_failure_preserves_previous_snapshot(tmp_path, monkeypatch):
    from wellspring.ingest import cli
    kwargs = dict(year=2026, month=8, db=tmp_path / "x.db", output=tmp_path / "out", archive_path=ARCHIVE)
    previous = ingest_month(**kwargs)
    revised = tmp_path / "revised.zip"
    with zipfile.ZipFile(ARCHIVE) as old, zipfile.ZipFile(revised, "w") as new:
        for name in old.namelist():
            new.writestr(name, old.read(name).replace(b"CRUDE OIL", b"TEST  OIL"))
    def fail(*args): raise OSError("simulated manifest publication failure")
    monkeypatch.setattr(cli, "_write_json", fail)
    import pytest
    with pytest.raises(OSError):
        ingest_month(**{**kwargs, "archive_path": revised})
    published = json.loads((tmp_path / "out/manifest.json").read_text())
    assert published == previous
    assert hashlib.sha256((tmp_path / "out" / published["export_file"]).read_bytes()).hexdigest() == published["export_sha256"]


def test_fetch_failure_cannot_replace_last_good_snapshot(tmp_path, monkeypatch):
    from wellspring.ingest import cli
    from wellspring.ingest.fetch import Download
    kwargs = dict(year=2026, month=8, db=tmp_path / "x.db", output=tmp_path / "out")
    previous = ingest_month(**kwargs, archive_path=ARCHIVE)
    monkeypatch.setattr(cli, "download", lambda url, **kw: Download(url, "failed", None, "simulated timeout"))
    assert ingest_month(**kwargs)["status"] == "failed"
    published = json.loads((tmp_path / "out/manifest.json").read_text())
    assert published == previous
    assert json.loads((tmp_path / "out/last-attempt.json").read_text())["status"] == "failed"


def test_initial_fetch_failure_publishes_no_dataset_manifest(tmp_path, monkeypatch):
    from wellspring.ingest import cli
    from wellspring.ingest.fetch import Download
    monkeypatch.setattr(cli, "download", lambda url, **kw: Download(url, "missing", None, "HTTP404"))
    r = ingest_month(year=2026, month=8, db=tmp_path / "x.db", output=tmp_path / "out")
    assert r["status"] == "failed"
    assert not (tmp_path / "out/manifest.json").exists()
    assert (tmp_path / "out/last-attempt.json").exists()
