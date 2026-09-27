"""Parse ST1 reports by section and fixed columns, retaining source evidence.

The report's title/header is not a record layout: the issued data columns
start at 4,41,51,72. Changes use a different layout and can span many lines.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime, timezone

from .models import (
    EventType, LicenceEvent, NUMBER_FIELDS, Occurrence, ParsedReport,
    ParseIssue, ReportError, Source, TEXT_FIELDS,
)

MAX_REPORT_BYTES = 4 * 1024 * 1024
MONTHS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"), 1)}
DATE = re.compile(r"^\s*DATE:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*$")
LICENCE = re.compile(r"(?<!\d)\d{7}(?!\d)")
UWI = re.compile(r"^[A-Z0-9]{2,3}/\d{2}-\d{2}-\d{3}-\d{2}W\d/\d{1,2}$")
DLS = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{1,3})-(\d{1,2})W([456])$", re.I)
SECTIONS = {
    "AMENDMENTS OF WELL LICENCES": EventType.AMENDED,
    "WELL LICENCES CANCELLED": EventType.CANCELLED,
    "WELL LICENCES CANCELED": EventType.CANCELLED,
    "WELL LICENCES UPDATED": EventType.UPDATED,
    "RE-ENTRY WELL LICENCES": EventType.REENTRY,
    "RE-ENTRY WELL LICENCES ISSUED": EventType.REENTRY,
    "WELL LICENCES RE-ENTERED": EventType.REENTRY,
}
CHANGE_FIELDS = {
    "UWI": "uwi", "WELL NAME": "well_name", "BOTTOMHOLE LOCATION": "bottomhole_location",
    "SURFACE LOCATION": "surface_location", "SURFACE CO-ORDINATES": "surface_coordinates_text",
    "GROUND ELEVATION": "ground_elevation_m", "PROJECTED DEPTH": "projected_depth_m",
    "WELL TYPE": "well_type", "TARGET SUBSTANCE": "substance", "TERMINATING ZONE": "terminating_zone",
    "DRILLING OPERATION": "drilling_operation", "MINERAL RIGHTS": "mineral_rights",
    "AER CLASSIFICATION/CONFIDENTIAL STATUS": "aer_classification",
}


def parse_dls(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    match = DLS.fullmatch(value.strip())
    if not match:
        return None
    lsd, section, township, range_, meridian = map(int, match.groups())
    if not (1 <= lsd <= 16 and 1 <= section <= 36 and 1 <= township <= 126 and 1 <= range_ <= 30):
        return None
    return dict(lsd=lsd, section=section, township=township, range=range_, meridian=meridian)


def _text(value: str) -> str | None:
    return value.strip() or None


def _metres(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"-?\d+(?:\.\d+)?\s*M", value, re.I):
        raise ValueError(f"invalid metre value: {value!r}")
    result = float(value[:-1].strip())
    if not math.isfinite(result):
        raise ValueError("non-finite metre value")
    return result


def _licence(line: str) -> re.Match[str] | None:
    return next((m for m in LICENCE.finditer(line) if 35 <= m.start() <= 45), None)


def _header_line(line: str) -> bool:
    text = line.strip()
    return (not text or set(text) <= {"-", " "} or text == "ALBERTA ENERGY REGULATOR"
            or text == "WELL LICENCES ISSUED  DAILY LIST" or DATE.fullmatch(line) is not None
            or text.startswith(("WELL NAME ", "WELL NAME AND U.I.D.", "UNIQUE IDENTIFIER ",
                                    "AER CLASSIFICATION ", "DRILLING OPERATION ", "LICENSEE "))
            or re.fullmatch(r"PAGE\s*:?\s*\d+", text) is not None)


def _issued(block: list[tuple[int, str]]) -> dict:
    lines = [line for _, line in block if line.strip()]
    if len(lines) != 5:
        raise ValueError(f"issued/reentry record needs five nonblank lines, got {len(lines)}")
    a, b, c, d, e = lines
    # Fixed columns only make sense when their left-aligned origins agree.
    # Trimming all cells would otherwise hide a shifted line and turn the
    # touching RESUMPTION/PRODUCTION values into plausible corrupted strings.
    for line, end in ((a, 41), (b, 27), (c, 41), (d, 41), (e, 72)):
        if line[:4] != "    " or (line[4:end].strip() and line[4].isspace()):
            raise ValueError("issued record does not align with fixed columns")
    # Source numeric columns are deliberately not derived from the headings.
    licence = a[41:51].strip()
    if not re.fullmatch(r"\d{7}", licence):
        raise ValueError("invalid licence number in issued column")
    uwi = b[4:27].strip()
    if not UWI.fullmatch(uwi):
        raise ValueError("invalid UWI in issued column")
    result = dict(
        licence_number=licence, well_name=_text(a[4:41]), mineral_rights=_text(a[51:72]),
        ground_elevation_m=_metres(a[72:]), uwi=uwi,
        surface_coordinates_text=_text(b[27:51]), field_centre=_text(b[51:72]),
        projected_depth_m=_metres(b[72:]), aer_classification=_text(c[4:41]),
        field=_text(c[41:72]), terminating_zone=_text(c[72:]), drilling_operation=_text(d[4:41]),
        well_purpose=_text(d[41:51]), well_type=_text(d[51:72]), substance=_text(d[72:]),
        licensee=_text(e[4:72]), surface_location=_text(e[72:]), changes=[],
    )
    if not result["well_name"]:
        raise ValueError("missing well name")
    if result["projected_depth_m"] is not None and result["projected_depth_m"] < 0:
        raise ValueError("negative projected depth")
    return result


def _changed(block: list[tuple[int, str]], event_type: EventType) -> dict:
    first = block[0][1]
    match = _licence(first)
    assert match is not None
    result = dict(licence_number=match.group(), well_name=_text(first[4:match.start()]), uwi=None, changes=[])
    nonblank = [line for _, line in block[1:] if line.strip()]
    if not nonblank:
        raise ValueError("change/cancellation lacks identifier row")
    # Two- and three-digit prefixes are retained exactly as reported, not
    # heuristically normalized into a potentially different identifier.
    result["uwi"] = _text(nonblank[0][4:51])
    if result["uwi"] is not None and not UWI.fullmatch(result["uwi"]):
        raise ValueError("invalid UWI in change/cancellation")
    if event_type == EventType.CANCELLED:
        if len(nonblank) != 1 or first[match.end():].strip() or nonblank[0][51:].strip():
            raise ValueError("unexpected cancellation content")
        return result
    label: str | None = None
    values: list[str] = []

    def finish() -> None:
        if label is None:
            return
        value = " ".join(values).strip()
        if not value:
            raise ValueError(f"change field {label} has no value")
        field_name = CHANGE_FIELDS.get(label, re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"))
        result["changes"].append(dict(field=field_name, label=label, value=value))

    for offset, (_, line) in enumerate(block):
        if offset and line[:51].strip() and not UWI.fullmatch(line[4:51].strip()):
            raise ValueError("unexpected left-column change continuation")
        right = (line[match.end():] if offset == 0 else line[51:]).strip()
        if not right:
            continue
        if re.fullmatch(r"[A-Z0-9 /()&.-]+:", right) or right == "AER CLASSIFICATION/CONFIDENTIAL STATUS":
            finish()
            label, values = right.removesuffix(":").strip(), []
        elif label is not None:
            values.append(right)
        else:
            raise ValueError("change value has no field label")
    finish()
    if not result["changes"]:
        raise ValueError("amended/updated record has no changes")
    return result


def parse_report(raw: bytes, *, source_url: str = "fixture:unknown", expected_date: str | None = None,
                 retrieved_at: str | None = None) -> ParsedReport:
    if not raw or len(raw) > MAX_REPORT_BYTES:
        raise ReportError("empty or oversized report")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ReportError("report is not valid UTF-8/ASCII") from error
    if "\x00" in text or "\t" in text:
        raise ReportError("NUL/tab characters invalidate fixed-width input")
    lines = text.splitlines()
    if any(len(line) > 1024 for line in lines):
        raise ReportError("report line exceeds limit")
    if not any(line.strip() == "ALBERTA ENERGY REGULATOR" for line in lines):
        raise ReportError("not an AER report")
    if not any("WELL LICENCES ISSUED  DAILY LIST" in line for line in lines):
        raise ReportError("wrong report type")
    dates = []
    for line in lines:
        match = DATE.fullmatch(line)
        if match:
            day, month, year = match.groups()
            try:
                dates.append(date(int(year), MONTHS[month.lower()], int(day)).isoformat())
            except (KeyError, ValueError) as error:
                raise ReportError("invalid report date") from error
    if not dates or len(set(dates)) != 1:
        raise ReportError("missing or conflicting report date")
    report_date = dates[0]
    if expected_date is not None and report_date != date.fromisoformat(expected_date).isoformat():
        raise ReportError(f"report date {report_date} does not match requested {expected_date}")
    if not any("END OF WELL LICENCES DAILY LIST" in line for line in lines):
        raise ReportError("report is truncated: no end marker")
    if not any("WELL NAME" in line and "LICENCE NUMBER" in line for line in lines):
        raise ReportError("missing issued table header")
    source = Source(source_url, hashlib.sha256(raw).hexdigest(),
                    retrieved_at or datetime.now(timezone.utc).isoformat())
    issues: list[ParseIssue] = []
    groups: dict[tuple[str, EventType], list[tuple[dict, Occurrence]]] = {}
    section = EventType.ISSUED
    block: list[tuple[int, str]] = []
    blocks = duplicates = 0
    seen_blocks: set[tuple[EventType, str]] = set()
    ended = False

    def flush() -> None:
        nonlocal blocks, duplicates
        if not block:
            return
        while block and not block[-1][1].strip():
            block.pop()
        blocks += 1
        raw_text = "\n".join(line for _, line in block)
        try:
            record = _issued(block) if section in (EventType.ISSUED, EventType.REENTRY) else _changed(block, section)
            signature = (section, raw_text)
            if signature in seen_blocks:
                duplicates += 1
                return
            seen_blocks.add(signature)
            key = (record["licence_number"], section)
            children = groups.setdefault(key, [])
            occurrence = Occurrence(len(children), record.get("well_name"), record.get("uwi"),
                                    record["changes"], block[0][0], block[-1][0], raw_text)
            children.append((record, occurrence))
        except ValueError as error:
            issues.append(ParseIssue("malformed_block", str(error), block[0][0], block[-1][0]))

    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if "END OF WELL LICENCES DAILY LIST" in line:
            flush(); block = []; ended = True
            continue
        if ended:
            if stripped:
                issues.append(ParseIssue("trailing_content", "content follows end marker", number, number))
            continue
        if stripped in SECTIONS:
            flush(); block = []; section = SECTIONS[stripped]
            continue
        if _header_line(line):
            # Blank lines occur *inside* update blocks, so retain them until
            # the next actual record/section. Known headings are not content.
            if block and not stripped:
                block.append((number, line))
            continue
        if _licence(line):
            flush(); block = [(number, line)]
        elif block:
            block.append((number, line))
        else:
            issues.append(ParseIssue("unexpected_line", stripped[:160], number, number))
    events = []
    for (licence, kind), children in groups.items():
        identifier = hashlib.sha256(f"{report_date}|{kind.value}|{licence}".encode()).hexdigest()
        event = LicenceEvent(identifier, report_date, kind, licence, source,
                             [occurrence for _, occurrence in children])
        for name in (*TEXT_FIELDS, *NUMBER_FIELDS):
            values = [record.get(name) for record, _ in children]
            setattr(event, name, values[0] if all(v == values[0] for v in values) else None)
        event.dls = parse_dls(event.surface_location)
        if event.surface_location and event.dls is None:
            issues.append(ParseIssue("invalid_surface_dls", event.surface_location,
                                     children[0][1].source_line_start, children[-1][1].source_line_end))
        events.append(event)
    return ParsedReport(report_date, source, raw, events, issues, blocks, duplicates)
