import { parseDls } from '../dls.pipe';
import { AskResponse, DataMeta, Dls, EventType, LicenceEvent, LicencePage, LicenceQuery, SortKey, Stats, StatsQuery } from './types';

// Six records lifted from fixtures/WELLS0925.TXT plus four shape-faithful
// placeholders (SAMPLE licensees) for the field centres and substances the
// fixture is thin on. Replayed across the last 90 business days so the
// dashboard has a series to draw. Dev only; environment.mock switches it off.
const BASE = [
  ['IMP 26 N08-H13 ST LEMING 16-11-66-3', '102/16-11-066-03W4/02', 610.2, 'BONNYVILLE', 1677, 'DEV (NC)', 'LEMING', 'CLEARWATER FM', 'HORIZONTAL', 'RESUMPTION', 'PRODUCTION', 'CRUDE BITUMEN', 'IMPERIAL OIL RESOURCES LIMITED', '16-12-066-03W4'],
  ['RBY 02 HZ EDWAND 6-2-62-16', '102/06-02-062-16W4/00', 689.8, 'BONNYVILLE', 4000, 'DEV (C)', 'EDWAND', 'CLEARWATER FM', 'HORIZONTAL', 'NEW', 'PRODUCTION', 'CRUDE OIL', 'RUBELLITE ENERGY INC.', '13-26-061-16W4'],
  ['CNRL HZ CADOTTE 16-2-85-17', '100/16-02-085-17W5/00', 679.8, 'SLAVE LAKE', 2775, 'DEV (NC)', 'UNDEFINED', 'BLUESKY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION (SCHEME)', 'CRUDE BITUMEN', 'CANADIAN NATURAL RESOURCES LIMITED', '04-10-085-17W5'],
  ['CNRL HZ CADOTTE 16-10-85-17', '100/16-10-085-17W5/00', 679.7, 'SLAVE LAKE', 2750, 'DEV (NC)', 'CADOTTE', 'BLUESKY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION (SCHEME)', 'CRUDE BITUMEN', 'CANADIAN NATURAL RESOURCES LIMITED', '04-10-085-17W5'],
  ['REFRACTION ENRGY PEMBINA 2-32-46-9', '100/02-32-046-09W5/00', 931.4, 'DRAYTON VALLEY', 7066, 'DEV (NC)', 'PEMBINA', 'DUVERNAY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION', 'GAS', 'REFRACTION ENERGY CORP.', '07-07-047-09W5'],
  ['CNUL HZ CADOTTE 16-2-85-17', '102/16-02-085-17W5/00', 679.8, 'SLAVE LAKE', 2775, 'DEV (NC)', 'UNDEFINED', 'BLUESKY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION (SCHEME)', 'CRUDE BITUMEN', 'CANADIAN NATURAL UPGRADING LIMITED', '04-10-085-17W5'],
  ['SAMPLE HZ KAKWA 4-17-63-6', '100/04-17-063-06W6/00', 1012.5, 'GRANDE PRAIRIE', 5400, 'DEV (NC)', 'KAKWA', 'MONTNEY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION', 'GAS', 'SAMPLE GAS CORP.', '04-17-063-06W6'],
  ['SAMPLE FIREBAG 12-30-93-7', '100/12-30-093-07W4/00', 512.0, 'FORT MCMURRAY', 480, 'DEV (NC)', 'FIREBAG', 'MCMURRAY FM', 'HORIZONTAL', 'NEW', 'PRODUCTION (SCHEME)', 'CRUDE BITUMEN', 'SAMPLE OIL SANDS LTD.', '12-30-093-07W4'],
  ['SAMPLE WEMBLEY 8-22-72-8', '100/08-22-072-08W6/00', 780.3, 'GRANDE PRAIRIE', 3900, 'DEV (NC)', 'WEMBLEY', 'CHARLIE LAKE FM', 'HORIZONTAL', 'NEW', 'PRODUCTION', 'CRUDE OIL', 'SAMPLE ENERGY INC.', '08-22-072-08W6'],
  ['SAMPLE WD CROSSFIELD 10-5-27-1', '100/10-05-027-01W5/00', 1100.0, 'CALGARY', 1800, 'DEV (NC)', 'CROSSFIELD', 'BASAL QUARTZ FM', 'VERTICAL', 'NEW', 'DISPOSAL', 'WATER', 'SAMPLE WATER SERVICES LTD.', '10-05-027-01W5'],
] as const;

const TODAY = new Date();
TODAY.setUTCHours(0, 0, 0, 0);
const iso = (daysAgo: number): string => new Date(TODAY.getTime() - daysAgo * 864e5).toISOString().slice(0, 10);

// ponytail: rough township grid so mock pins land in Alberta. The real API
// returns null coordinates until Tenjin's verified DLS approximation exists.
function approxLatLon(d: Dls): [number, number] {
  const merLon = ({ 4: -110, 5: -114, 6: -118 } as Record<number, number>)[d.meridian] ?? -114;
  const lat = 49 + (d.township - 1) * 0.0873 + (Math.floor((d.section - 1) / 6) + 0.5) * 0.0145;
  const lon = merLon - (d.range - 1) * 0.145 - 0.07;
  return [lat, lon];
}

function make(b: (typeof BASE)[number], licence_number: string, event_type: EventType, report_date: string): LicenceEvent {
  const [well_name, uwi, ground_elevation_m, field_centre, projected_depth_m, aer_classification, field, terminating_zone,
    drilling_operation, well_purpose, well_type, substance, licensee, surface_location] = b;
  const dls = parseDls(surface_location);
  const [latitude, longitude] = dls ? approxLatLon(dls) : [null, null];
  const sparse = event_type === 'amended' || event_type === 'cancelled' || event_type === 'updated';
  const full = <T>(v: T): T | null => (sparse ? null : v); // amendment and cancellation blocks carry few fields
  return {
    id: `${licence_number}:${event_type}:${report_date}`, schema_version: 1, report_date, event_type, licence_number,
    well_name, uwi, mineral_rights: full('ALBERTA CROWN'), surface_coordinates_text: full('N 213.6M E 251.5M'),
    field_centre: full(field_centre), aer_classification: full(aer_classification), field: full(field),
    terminating_zone: full(terminating_zone), drilling_operation: full(drilling_operation), well_purpose: full(well_purpose),
    well_type: full(well_type), substance: full(substance), licensee: full(licensee), surface_location: full(surface_location),
    ground_elevation_m: full(ground_elevation_m), projected_depth_m: full(projected_depth_m),
    dls: sparse ? null : dls, latitude: sparse ? null : latitude, longitude: sparse ? null : longitude,
    coordinate_method: sparse ? null : 'mock-township-grid', location_accuracy: sparse ? null : 'approximate',
    occurrence_count: 1,
    occurrences: [{ ordinal: 1, well_name, uwi, changes: [], source_line_start: 0, source_line_end: 0, raw_text: '' }],
    source: { url: `https://static.aer.ca/prd/data/well-lic/WELLS${report_date.slice(5, 7)}${report_date.slice(8, 10)}.TXT`, sha256: '', retrieved_at: TODAY.toISOString(), parser_version: 'mock' },
  };
}

const ALL: LicenceEvent[] = [];
{
  let seq = 525000;
  const num = (n: number) => String(n).padStart(7, '0');
  for (let day = 89; day >= 0; day--) {
    const date = iso(day);
    const weekday = new Date(date).getUTCDay();
    if (weekday === 0 || weekday === 6) continue; // the AER publishes on business days
    const n = 3 + ((day * 7) % 8); // 3 to 10 new licences a day, deterministic
    for (let i = 0; i < n; i++) ALL.push(make(BASE[(day + i) % BASE.length], num(seq++), 'issued', date));
    if (day % 5 === 0) ALL.push(make(BASE[day % BASE.length], num(seq - 40), 'amended', date));
    if (day % 7 === 0) ALL.push(make(BASE[(day + 1) % BASE.length], num(seq - 20), 'updated', date));
    if (day % 11 === 0) ALL.push(make(BASE[(day + 3) % BASE.length], num(seq - 60), 'cancelled', date));
  }
}
const REPORT_DATES = new Set(ALL.map(r => r.report_date));

function select(q: StatsQuery): LicenceEvent[] {
  const like = (v: string | null, f?: string) => !f || (v ?? '').toLowerCase().includes(f.toLowerCase());
  const type = q.event_type ?? 'issued';
  return ALL.filter(r =>
    (type === 'all' || r.event_type === type) &&
    (!q.date_from || r.report_date >= q.date_from) && (!q.date_to || r.report_date <= q.date_to) &&
    like(r.licensee, q.licensee) && like(r.substance, q.substance) && like(r.field_centre, q.field_centre) &&
    like(r.terminating_zone, q.terminating_zone) && like(r.well_type, q.well_type),
  );
}

function meta(q: StatsQuery): DataMeta {
  return {
    schema_version: 1, data_as_of: TODAY.toISOString(), date_from: q.date_from ?? null, date_to: q.date_to ?? null,
    event_type: q.event_type ?? 'issued',
    coverage: { reports_loaded: REPORT_DATES.size, missing_dates: [], failed_dates: [], parse_issue_count: 0 },
  };
}

export function mockLicences(q: LicenceQuery): LicencePage {
  const sort: SortKey = q.sort ?? 'report_date';
  const dir = (q.order ?? 'desc') === 'asc' ? 1 : -1;
  const items = select(q).sort((a, b) => (a[sort] ?? '').localeCompare(b[sort] ?? '') * dir || a.id.localeCompare(b.id));
  const page = Math.max(1, q.page ?? 1);
  const page_size = Math.min(200, Math.max(1, q.page_size ?? 50));
  return { items: items.slice((page - 1) * page_size, page * page_size), total: items.length, page, page_size, meta: meta(q) };
}

export function mockStats(path: string, q: StatsQuery): Stats<Record<string, unknown>> {
  const key = ({ daily: 'report_date', 'top-licensees': 'licensee', 'top-formations': 'terminating_zone', substances: 'substance' } as const)[path as 'daily'];
  if (!key) throw new Error(`unknown stats path ${path}`);
  const counts = new Map<string | null, number>();
  for (const r of select(q)) counts.set(r[key], (counts.get(r[key]) ?? 0) + 1);
  const label = key === 'report_date' ? 'date' : key;
  const items = [...counts].map(([name, count]) => ({ [label]: name, count }));
  items.sort((a, b) => (key === 'report_date' ? String(a['date']).localeCompare(String(b['date'])) : Number(b['count']) - Number(a['count'])));
  return { items: items.slice(0, q.limit ?? (key === 'report_date' ? Infinity : 10)), meta: meta(q) };
}

export function mockAsk(question: string): AskResponse {
  const q = { date_from: iso(30), date_to: iso(0) };
  if (/\b(drop|delete|update|insert|alter|truncate|pragma|attach)\b/i.test(question)) {
    return { status: 'refused', columns: [], rows: [], sql: null, row_limit: 200, truncated: false,
      refusal: { code: 'not_select', message: 'Only a single read-only SELECT is allowed.' }, meta: meta(q) };
  }
  const rows = mockStats('top-licensees', { ...q, limit: 5 }).items.map(r => ({ licensee: r['licensee'], licences: r['count'] }));
  const sql = [
    'SELECT licensee, COUNT(*) AS licences',
    'FROM licence_events',
    "WHERE event_type = 'issued' AND report_date >= date('now', '-30 days')",
    'GROUP BY licensee',
    'ORDER BY licences DESC',
    'LIMIT 5;',
  ].join('\n');
  return { status: 'ok', columns: ['licensee', 'licences'], rows, sql, row_limit: 200, truncated: false, refusal: null, meta: meta(q) };
}
