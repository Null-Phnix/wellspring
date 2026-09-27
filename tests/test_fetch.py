import io
import zipfile
from pathlib import Path
from datetime import date
from urllib.error import HTTPError, URLError

import pytest

from wellspring.ingest.fetch import archive_members, archive_url, day_url, download, month_dates, validate_url


def zipped(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, content in entries:
            z.writestr(name, content)
    return stream.getvalue()


def test_actual_archive_month_coverage():
    raw = (Path(__file__).parents[1] / "fixtures/dwll2026-08.zip").read_bytes()
    assert set(archive_members(raw, 2026, 8)) == set(month_dates(2026, 8))


@pytest.mark.parametrize("name", ["../WELLS0801.TXT", "/WELLS0801.TXT", "x/WELLS0801.TXT", "WELLS0832.TXT", "WELLS0901.TXT", "other.exe"])
def test_archive_rejects_unexpected_paths_or_dates(name):
    with pytest.raises(ValueError):
        archive_members(zipped([(name, b"synthetic")]), 2026, 8)


def test_duplicate_archive_member_is_refused():
    with pytest.warns(UserWarning):
        raw = zipped([("WELLS0801.TXT", b"one"), ("WELLS0801.TXT", b"two")])
    with pytest.raises(ValueError, match="duplicate"):
        archive_members(raw, 2026, 8)


def test_not_a_zip_is_refused():
    with pytest.raises(ValueError, match="ZIP"):
        archive_members(b"<html>error</html>", 2026, 8)


def test_official_st1_wrapper_preserves_member_name_and_bytes():
    raw = zipped([("ST1/", b""), ("ST1/WELLS0701.txt", b"exact report bytes")])
    assert archive_members(raw, 2026, 7) == {
        "2026-07-01": ("ST1/WELLS0701.txt", b"exact report bytes")
    }


@pytest.mark.parametrize("name", ["ST1/../WELLS0701.TXT", "ST1/nested/WELLS0701.TXT", "other/", "ST1/other.txt"])
def test_archive_wrapper_does_not_allow_other_paths(name):
    with pytest.raises(ValueError):
        archive_members(zipped([(name, b"synthetic")]), 2026, 7)


def test_flat_and_wrapped_same_date_is_still_duplicate():
    raw = zipped([("WELLS0701.TXT", b"one"), ("ST1/WELLS0701.TXT", b"two")])
    with pytest.raises(ValueError, match="duplicate"):
        archive_members(raw, 2026, 7)


@pytest.mark.parametrize("url", ["http://static.aer.ca/prd/data/well-lic/WELLS0801.TXT", "https://evil.test/prd/data/well-lic/WELLS0801.TXT", "https://static.aer.ca.evil.test/prd/data/well-lic/WELLS0801.TXT", "https://u:p@static.aer.ca/prd/data/well-lic/WELLS0801.TXT", "https://static.aer.ca:444/prd/data/well-lic/WELLS0801.TXT", "https://static.aer.ca/other/data.txt"])
def test_download_url_is_confined_to_public_source(url):
    with pytest.raises(ValueError):
        validate_url(url)


class Reply(io.BytesIO):
    def geturl(self):
        return day_url(date(2026, 8, 1))


class Opener:
    def __init__(self, data=None, error=None): self.data, self.error = data, error
    def open(self, request, timeout):
        assert request.get_header("User-agent").startswith("Wellspring/")
        assert timeout == 30
        if self.error: raise self.error
        return Reply(self.data)


@pytest.mark.parametrize("code,status", [(404, "missing"), (403, "failed"), (500, "failed")])
def test_http_failures_are_distinct_from_empty_days(code, status):
    url = day_url(date(2026, 8, 1))
    assert download(url, opener=Opener(error=HTTPError(url, code, "test", {}, None))).status == status


def test_empty_http_body_is_failure():
    assert download(day_url(date(2026, 8, 1)), opener=Opener(b"")).status == "failed"


def test_success_keeps_exact_bytes():
    raw = b"synthetic fixture bytes\r\n"
    d = download(day_url(date(2026, 8, 1)), opener=Opener(raw))
    assert d.status == "downloaded" and d.raw == raw


def test_network_error_is_recordable_failure():
    d = download(day_url(date(2026, 8, 1)), opener=Opener(error=URLError("offline")))
    assert d.status == "failed" and "offline" in d.error


def test_month_dates_handle_leap_year():
    assert len(month_dates(2024, 2)) == 29 and len(month_dates(2026, 2)) == 28
    assert archive_url(2026, 8).endswith("dwll2026-08.zip")
