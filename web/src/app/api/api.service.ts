import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { mockAsk, mockLicences, mockStats } from './mock-data';
import { AskResponse, DailyCount, FormationCount, LicencePage, LicenceQuery, LicenseeCount, Stats, StatsQuery, SubstanceCount } from './types';

/** ISO date (UTC) n days ago; 0 is today. */
export function isoDaysAgo(n: number): string {
  return new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBase;

  licences(q: LicenceQuery): Promise<LicencePage> {
    return environment.mock
      ? Promise.resolve(mockLicences(q))
      : firstValueFrom(this.http.get<LicencePage>(`${this.base}/licences`, { params: clean(q) }));
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

  ask(question: string): Promise<AskResponse> {
    return environment.mock
      ? Promise.resolve(mockAsk(question))
      : firstValueFrom(this.http.post<AskResponse>(`${this.base}/ask`, { question }));
  }

  private stats<T>(path: string, q: StatsQuery): Promise<Stats<T>> {
    return environment.mock
      ? Promise.resolve(mockStats(path, q) as Stats<T>)
      : firstValueFrom(this.http.get<Stats<T>>(`${this.base}/stats/${path}`, { params: clean(q) }));
  }
}

/** Drop empty filters so the query string only carries what the user set. */
function clean(q: object): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') out[k] = String(v);
  return out;
}
