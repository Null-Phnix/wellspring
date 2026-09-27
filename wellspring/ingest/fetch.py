"""Bounded public AER downloads; no authentication or implicit zero days."""
from __future__ import annotations

import calendar
import io
import re
import stat
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from .parser import MAX_REPORT_BYTES

MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_EXPANDED = 128 * 1024 * 1024
USER_AGENT = "Wellspring/0.1 (non-commercial ST1 research)"


def validate_url(url: str) -> str:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in {"aer.ca", "www.aer.ca", "static.aer.ca"}
            or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443) or parts.query or parts.fragment
            or not parts.path.startswith(("/prd/data/well-lic/", "/data/well-lic/"))):
        raise ValueError("only public AER ST1 HTTPS source URLs are allowed")
    return url


class _AERRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class Download:
    url: str
    status: str
    raw: bytes | None
    error: str | None = None


def download(url: str, *, archive: bool = False, opener=None) -> Download:
    validate_url(url)
    limit = MAX_ARCHIVE_BYTES if archive else MAX_REPORT_BYTES
    opener = opener or urllib.request.build_opener(_AERRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                  "Accept": "application/zip,text/plain,*/*"})
    try:
        with opener.open(request, timeout=30) as response:
            validate_url(response.geturl())
            raw = response.read(limit + 1)
            if len(raw) > limit:
                return Download(url, "failed", None, "source exceeds byte limit")
            if not raw:
                return Download(url, "failed", None, "empty HTTP response is not a zero-event report")
            return Download(url, "downloaded", raw)
    except urllib.error.HTTPError as error:
        return Download(url, "missing" if error.code == 404 else "failed", None, f"HTTP {error.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return Download(url, "failed", None, f"{type(error).__name__}: {error}")


def day_url(day: date) -> str:
    return f"https://static.aer.ca/prd/data/well-lic/WELLS{day:%m%d}.TXT"


def archive_url(year: int, month: int) -> str:
    date(year, month, 1)
    return f"https://www.aer.ca/prd/data/well-lic/dwll{year:04d}-{month:02d}.zip"


def archive_members(raw: bytes, year: int, month: int) -> dict[str, tuple[str, bytes]]:
    """Read flat ST1 entries without writing ZIP-controlled filesystem paths."""
    date(year, month, 1)
    if not raw or len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("empty or oversized archive")
    result: dict[str, tuple[str, bytes]] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > 366 or sum(i.file_size for i in infos) > MAX_ARCHIVE_EXPANDED:
                raise ValueError("archive expanded size or entry count exceeds limit")
            for info in infos:
                match = re.fullmatch(r"WELLS(\d{2})(\d{2})\.TXT", info.filename, re.I)
                if (not match or info.is_dir() or info.flag_bits & 1
                        or stat.S_ISLNK(info.external_attr >> 16)
                        or info.file_size > MAX_REPORT_BYTES
                        or info.file_size > max(info.compress_size, 1) * 200):
                    raise ValueError(f"unsafe or unexpected archive entry: {info.filename!r}")
                member_month, day = map(int, match.groups())
                if member_month != month:
                    raise ValueError("archive contains a different month")
                report_date = date(year, month, day).isoformat()
                if report_date in result:
                    raise ValueError("archive has duplicate date members")
                with archive.open(info) as stream:
                    content = stream.read(MAX_REPORT_BYTES + 1)
                if len(content) != info.file_size or len(content) > MAX_REPORT_BYTES:
                    raise ValueError("archive member has inconsistent size")
                result[report_date] = (info.filename, content)
    except zipfile.BadZipFile as error:
        raise ValueError("invalid or corrupt ZIP archive") from error
    return result


def month_dates(year: int, month: int) -> list[str]:
    return [date(year, month, n).isoformat() for n in range(1, calendar.monthrange(year, month)[1] + 1)]
