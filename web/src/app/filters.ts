import { Params } from '@angular/router';
import { isoDaysAgo } from './api/api.service';
import { EVENT_TYPES, LicenceQuery, SORT_KEYS, StatsQuery } from './api/types';

/** The filter keys the table, the map and the dashboard share through the URL query string. */
export const FILTER_KEYS = ['date_from', 'date_to', 'licensee', 'substance', 'field_centre', 'terminating_zone', 'well_type', 'event_type'] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
const URL_KEYS = [...FILTER_KEYS, 'sort', 'order', 'page'] as const;

/** Last 30 days of issued licences, newest first. */
export function defaultQuery(): LicenceQuery {
  return { date_from: isoDaysAgo(30), date_to: isoDaysAgo(0), event_type: 'issued', sort: 'report_date', order: 'desc', page: 1 };
}

/** A query from URL params. Defaults fill what the URL leaves out; values the contract would reject are ignored. */
export function queryFromParams(get: (key: string) => string | null, defaults: LicenceQuery = defaultQuery()): LicenceQuery {
  const q: Record<string, unknown> = { ...defaults };
  for (const k of URL_KEYS) {
    const v = get(k)?.trim();
    if (!v) continue;
    if (k === 'page') q[k] = Math.max(1, Math.floor(Number(v)) || 1);
    else if (k === 'sort') { if ((SORT_KEYS as readonly string[]).includes(v)) q[k] = v; }
    else if (k === 'order') { if (v === 'asc' || v === 'desc') q[k] = v; }
    else if (k === 'event_type') { if (v === 'all' || (EVENT_TYPES as readonly string[]).includes(v)) q[k] = v; }
    else q[k] = v;
  }
  return q as LicenceQuery;
}

/** URL params for a query: every set key, except page 1 and anything that is not shareable state. */
export function paramsFor(q: LicenceQuery): Params {
  const out: Params = {};
  for (const k of URL_KEYS) {
    const v = q[k];
    if (v === undefined || v === '' || (k === 'page' && v === 1)) continue;
    out[k] = String(v);
  }
  return out;
}

/** The filter part only, for stats calls and the map. */
export function filtersOf(q: LicenceQuery): StatsQuery {
  const out: Record<string, unknown> = {};
  for (const k of FILTER_KEYS) if (q[k] !== undefined && q[k] !== '') out[k] = q[k];
  return out as StatsQuery;
}
