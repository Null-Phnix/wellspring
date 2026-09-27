// Response shapes: the v1 contract Tenjin posted on issue #1 (comment 109),
// approved by Anubis (comment 112). Change the contract on #1 first, then this
// file and mock-data.ts.

export const EVENT_TYPES = ['issued', 'reentry', 'amended', 'cancelled', 'updated'] as const;
export type EventType = (typeof EVENT_TYPES)[number];

/** Alberta DLS surface location: LSD-Section-Township-Range-Meridian. */
export interface Dls {
  lsd: number;
  section: number;
  township: number;
  range: number;
  meridian: number; // west of the 4th, 5th or 6th meridian
}

export interface Occurrence {
  ordinal: number;
  well_name: string | null;
  uwi: string | null;
  changes: { field: string; label: string; value: string }[];
  source_line_start: number;
  source_line_end: number;
  raw_text: string;
}

/** One event row per (licence_number, event_type, report_date). */
export interface LicenceEvent {
  id: string;
  schema_version: 1;
  report_date: string; // ISO date from the ST1 header
  event_type: EventType;
  licence_number: string; // "0525807", leading zeros kept
  well_name: string | null;
  uwi: string | null; // "102/06-02-062-16W4/00"
  mineral_rights: string | null;
  surface_coordinates_text: string | null;
  field_centre: string | null;
  aer_classification: string | null;
  field: string | null;
  terminating_zone: string | null;
  drilling_operation: string | null;
  well_purpose: string | null;
  well_type: string | null;
  substance: string | null;
  licensee: string | null;
  surface_location: string | null; // raw "13-26-061-16W4"
  ground_elevation_m: number | null;
  projected_depth_m: number | null;
  dls: Dls | null;
  latitude: number | null; // null until the DLS approximation is verified
  longitude: number | null;
  coordinate_method: string | null; // "alberta_dls_grid_approximation_v1" on live
  location_accuracy: 'approximate' | null;
  location_reason: string | null; // why latitude/longitude are null, when they are
  occurrence_count: number;
  occurrences: Occurrence[];
  source: { url: string; sha256: string; retrieved_at: string; parser_version: string };
}

/** GET /licences?fields=points: the same paging and meta, each item projected to exactly these keys. */
export interface LicencePoint {
  id: string;
  licence_number: string;
  well_name: string | null;
  licensee: string | null;
  substance: string | null;
  report_date: string;
  latitude: number | null;
  longitude: number | null;
  coordinate_method: string | null;
  location_accuracy: 'approximate' | null;
  location_reason: string | null;
  surface_location?: string | null; // asked for on issue #1; absent until Tenjin adds it
}

export const SORT_KEYS = ['report_date', 'licence_number', 'licensee', 'substance', 'field_centre', 'terminating_zone', 'well_type'] as const;
export type SortKey = (typeof SORT_KEYS)[number];

/** GET /licences query. Dates inclusive; event_type defaults to issued, 'all' is explicit; page_size 1..200. */
export interface LicenceQuery {
  date_from?: string;
  date_to?: string;
  licensee?: string;
  substance?: string;
  field_centre?: string;
  terminating_zone?: string;
  well_type?: string;
  event_type?: EventType | 'all';
  page?: number;
  page_size?: number;
  sort?: SortKey;
  order?: 'asc' | 'desc';
  fields?: 'points';
}

/** The same filters apply to /stats/*. */
export type StatsQuery = Omit<LicenceQuery, 'page' | 'page_size' | 'sort' | 'order' | 'fields'> & { limit?: number };

/** Which daily lists are behind a response. The four documented keys always; the live API also sends the rest. */
export interface Coverage {
  reports_loaded: number;
  missing_dates: string[];
  failed_dates: string[];
  parse_issue_count: number;
  loaded_dates?: string[];
  empty_dates?: string[];
  retry_failed_dates?: string[];
  parse_issues_by_date?: Record<string, number>;
}

export interface DataMeta {
  schema_version: 1;
  data_as_of: string | null;
  date_from: string | null;
  date_to: string | null;
  event_type: string;
  coverage: Coverage | null; // null when no dataset is loaded (contract, /ask stub)
}

/** GET /licences */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  meta: DataMeta;
}
export type LicencePage = Page<LicenceEvent>;
export type PointPage = Page<LicencePoint>;

/** GET /stats/daily, /stats/top-licensees, /stats/top-formations, /stats/substances */
export interface Stats<T> {
  items: T[];
  meta: DataMeta;
}
export interface DailyCount { date: string; count: number; }
export interface LicenseeCount { licensee: string | null; count: number; }
export interface FormationCount { terminating_zone: string | null; count: number; }
export interface SubstanceCount { substance: string | null; count: number; }

/** Any non-2xx body. */
export interface ApiError {
  error: { code: string; message: string };
  schema_version: 1;
}

/**
 * POST /ask { question }. The M2 stub always refuses with ASK_UNAVAILABLE. Anubis said the M4
 * success body will be {sql, rows, row_count, truncated, model}; ApiService.ask normalises
 * that into this shape so the page only knows one.
 */
export type AskResponse =
  | { status: 'ok'; columns: string[]; rows: Record<string, unknown>[]; sql: string; row_limit: number; truncated: boolean; refusal: null; meta: DataMeta | null; row_count?: number; model?: string }
  | { status: 'refused'; columns: []; rows: []; sql: null; row_limit: number; truncated: false; refusal: { code: string; message: string }; meta: DataMeta | null };
