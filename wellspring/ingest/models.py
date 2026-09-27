"""Shared v1 event vocabulary. Strings preserve source identifiers and zeros."""
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = 1
PARSER_VERSION = "0.1.0"


class EventType(StrEnum):
    ISSUED = "issued"
    REENTRY = "reentry"
    AMENDED = "amended"
    CANCELLED = "cancelled"
    UPDATED = "updated"


TEXT_FIELDS = (
    "well_name", "uwi", "mineral_rights", "surface_coordinates_text", "field_centre",
    "aer_classification", "field", "terminating_zone", "drilling_operation",
    "well_purpose", "well_type", "substance", "licensee", "surface_location",
)
NUMBER_FIELDS = ("ground_elevation_m", "projected_depth_m")


@dataclass(frozen=True)
class Source:
    url: str
    sha256: str
    retrieved_at: str
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True)
class ParseIssue:
    code: str
    message: str
    line_start: int
    line_end: int


@dataclass
class Occurrence:
    ordinal: int
    well_name: str | None
    uwi: str | None
    changes: list[dict[str, str]]
    source_line_start: int
    source_line_end: int
    raw_text: str


@dataclass
class LicenceEvent:
    id: str
    report_date: str
    event_type: EventType
    licence_number: str
    source: Source
    occurrences: list[Occurrence] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
    well_name: str | None = None
    uwi: str | None = None
    mineral_rights: str | None = None
    surface_coordinates_text: str | None = None
    field_centre: str | None = None
    aer_classification: str | None = None
    field: str | None = None
    terminating_zone: str | None = None
    drilling_operation: str | None = None
    well_purpose: str | None = None
    well_type: str | None = None
    substance: str | None = None
    licensee: str | None = None
    surface_location: str | None = None
    ground_elevation_m: float | None = None
    projected_depth_m: float | None = None
    dls: dict[str, int] | None = None
    latitude: float | None = None
    longitude: float | None = None
    coordinate_method: str | None = None
    location_accuracy: str | None = None

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrences)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "event_type": self.event_type.value,
                "occurrence_count": self.occurrence_count}


@dataclass
class ParsedReport:
    report_date: str
    source: Source
    raw_bytes: bytes
    events: list[LicenceEvent]
    issues: list[ParseIssue]
    source_block_count: int
    duplicate_block_count: int = 0

    @property
    def status(self) -> str:
        return "partial" if self.issues else ("loaded" if self.events else "empty")


class ReportError(ValueError):
    """The report identity/envelope could not be trusted; import nothing."""
