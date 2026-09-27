import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { mockAsk, mockLicences, mockPoints, mockStats } from './mock-data';
import { AskResponse, DailyCount, DataMeta, FormationCount, LicenceEvent, LicencePage, LicencePoint, LicenceQuery, LicenseeCount, Page, PointPage, Stats, StatsQuery, SubstanceCount } from './types';

/** ISO date (UTC) n days ago; 0 is today. */
export function isoDaysAgo(n: number): string {
  return new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
}

export const PAGE_SIZE_MAX = 200; // contract cap on page_size

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBase;
  /** data_as_of from the most recent response, for the footer. */
  readonly dataAsOf = signal<string | null>(null);

  licences(q: LicenceQuery): Promise<LicencePage> {
    return this.remember(environment.mock
      ? Promise.resolve(mockLicences(q))
      : firstValueFrom(this.http.get<LicencePage>(`${this.base}/licences`, { params: clean({ ...q, fields: undefined }) })));
  }

  /** The slim projection for the map. */
  points(q: LicenceQuery): Promise<PointPage> {
    return this.remember(environment.mock
      ? Promise.resolve(mockPoints(q))
      : firstValueFrom(this.http.get<PointPage>(`${this.base}/licences`, { params: clean({ ...q, fields: 'points' }) })));
  }

  /** Every event matching q, paged through the API up to cap rows (CSV export). */
  allLicences(q: LicenceQuery, cap: number): Promise<{ items: LicenceEvent[]; total: number; capped: boolean }> {
    return pageAll(p => this.licences({ ...q, page: p, page_size: PAGE_SIZE_MAX }), cap);
  }

  /** Every point matching q, up to cap (map). */
  allPoints(q: LicenceQuery, cap: number): Promise<{ items: LicencePoint[]; total: number; capped: boolean }> {
    return pageAll(p => this.points({ ...q, page: p, page_size: PAGE_SIZE_MAX }), cap);
  }

  daily(q: StatsQuery): Promise<Stats<DailyCount>> {
    return this.stats('daily', q);
  }

  topLicensees(q: StatsQuery): Promise<Stats<LicenseeCount>> {
    return this.stats('top-licensees', q);
  }

  topFormations(q: StatsQuery): Promise<Stats<FormationCount>> {
    return this.stats('top-formations', q);
  }

  substances(q: StatsQuery): Promise<Stats<SubstanceCount>> {
    return this.stats('substances', q);
  }

  async ask(question: string): Promise<AskResponse> {
    const raw = environment.mock
      ? mockAsk(question)
      : await firstValueFrom(this.http.post<unknown>(`${this.base}/ask`, { question }));
    return normaliseAsk(raw);
  }

  private stats<T>(path: string, q: StatsQuery): Promise<Stats<T>> {
    return this.remember(environment.mock
      ? Promise.resolve(mockStats(path, q) as Stats<T>)
      : firstValueFrom(this.http.get<Stats<T>>(`${this.base}/stats/${path}`, { params: clean(q) })));
  }

  private remember<T extends { meta: DataMeta }>(p: Promise<T>): Promise<T> {
    return p.then(r => {
      if (r.meta?.data_as_of) this.dataAsOf.set(r.meta.data_as_of);
      return r;
    });
  }
}

/** Page through fetch(page) until cap rows or the end; says whether the cap cut the result. */
export async function pageAll<T>(fetch: (page: number) => Promise<Page<T>>, cap: number): Promise<{ items: T[]; total: number; capped: boolean }> {
  const first = await fetch(1);
  const items = [...first.items];
  const pages = Math.min(Math.ceil(cap / first.page_size), Math.ceil(first.total / first.page_size));
  for (let p = 2; p <= pages; p++) items.push(...(await fetch(p)).items);
  return { items: items.slice(0, cap), total: first.total, capped: first.total > cap };
}

/** Accept both the contract's /ask body and the M4 success body Anubis described. */
export function normaliseAsk(raw: unknown): AskResponse {
  const r = (raw ?? {}) as Record<string, unknown>;
  if (r['status'] === 'ok' || r['status'] === 'refused') return raw as AskResponse;
  const meta = (r['meta'] as DataMeta | undefined) ?? null;
  const row_limit = Number(r['row_limit'] ?? 200);
  const refusal = r['refusal'] as { code: string; message: string } | null | undefined;
  if (refusal) return { status: 'refused', columns: [], rows: [], sql: null, row_limit, truncated: false, refusal, meta };
  const rows = (r['rows'] as Record<string, unknown>[] | undefined) ?? [];
  return {
    status: 'ok', rows, sql: String(r['sql'] ?? ''), row_limit, truncated: Boolean(r['truncated']), refusal: null, meta,
    columns: (r['columns'] as string[] | undefined) ?? Object.keys(rows[0] ?? {}),
    row_count: r['row_count'] as number | undefined, model: r['model'] as string | undefined,
  };
}

/** Drop empty filters so the query string only carries what the user set. */
function clean(q: object): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') out[k] = String(v);
  return out;
}
