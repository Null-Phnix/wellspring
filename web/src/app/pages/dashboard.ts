import { Component, computed, effect, inject, resource } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService, isoDaysAgo } from '../api/api.service';
import { Coverage, StatsQuery } from '../api/types';
import { queryFromParams } from '../filters';

export type CoverageStatus = 'loaded' | 'empty' | 'failed' | 'missing' | 'unknown';
export const MAX_DAYS = 366; // a custom range longer than this is clipped to its last year

/** A window ordered and clipped to its last MAX_DAYS days, so the stats calls, totals, bars and strip all cover the same dates. */
export function clipRange(date_from: string, date_to: string): { date_from: string; date_to: string } {
  const [from, to] = date_from <= date_to ? [date_from, date_to] : [date_to, date_from];
  const earliest = new Date(Date.parse(to) - (MAX_DAYS - 1) * 864e5).toISOString().slice(0, 10);
  return { date_from: from < earliest ? earliest : from, date_to: to };
}

/** Every ISO date from `from` to `to` inclusive (clipped like clipRange). */
export function dateRange(from: string, to: string): string[] {
  const r = clipRange(from, to);
  const out: string[] = [];
  for (let t = Date.parse(r.date_from), end = Date.parse(r.date_to); t <= end; t += 864e5) out.push(new Date(t).toISOString().slice(0, 10));
  return out;
}

/** What the API says about each date in the window. `counted` covers older manifests without loaded_dates. */
export function coverageCells(c: Coverage | null, dates: string[], counted: ReadonlySet<string>): { date: string; status: CoverageStatus }[] {
  const has = (k: keyof Coverage, d: string) => ((c?.[k] as string[] | undefined) ?? []).includes(d);
  return dates.map(date => ({
    date,
    status: has('failed_dates', date) ? 'failed' : has('missing_dates', date) ? 'missing' : has('empty_dates', date) ? 'empty'
      : has('loaded_dates', date) || counted.has(date) ? 'loaded' : 'unknown',
  }));
}

const LABELS: Record<CoverageStatus, string> = {
  loaded: 'daily list loaded', empty: 'daily list loaded, no licences', failed: 'daily list failed to load',
  missing: 'daily list missing at the source', unknown: 'not published yet',
};

export function summarise(cells: { status: CoverageStatus }[]): string {
  const n = (s: CoverageStatus) => cells.filter(c => c.status === s).length;
  return `${n('loaded') + n('empty')} daily lists loaded (${n('empty')} with no licences), ${n('failed')} failed, ${n('missing')} missing, ${n('unknown')} not published yet.`;
}

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  template: `
    <h1>Dashboard</h1>
    <form class="window" (submit)="applyRange($event)">
      <span class="presets" role="group" aria-label="Window">
        @for (d of [7, 30, 90]; track d) {
          <button type="button" [class.active]="preset() === d" [attr.aria-pressed]="preset() === d" (click)="setDays(d)">Last {{ d }} days</button>
        }
      </span>
      <label>From <input type="date" name="date_from" [value]="range().date_from" required></label>
      <label>To <input type="date" name="date_to" [value]="range().date_to" required></label>
      <button>Apply</button>
    </form>

    @if (data.value(); as v) {
      <section>
        <h2>
          Licences issued per day
          <span class="muted">(<a routerLink="/licences" [queryParams]="slice({})">{{ v.total }} in the window</a>, most in a day {{ v.max }})</span>
        </h2>
        <div class="bars" role="list" aria-label="Licences issued per day">
          @for (b of v.bars; track b.date) {
            @if (b.count != null) {
              <a class="bar" role="listitem" routerLink="/licences" [queryParams]="slice({ date_from: b.date, date_to: b.date })"
                 [style.height.%]="(100 * b.count) / v.max" [title]="b.date + ': ' + b.count + ' issued'"
                 [attr.aria-label]="b.date + ': ' + b.count + ' issued, open in the table'"></a>
            } @else {
              <span role="listitem" [class]="'bar gap ' + b.status" [title]="b.date + ': ' + labels[b.status]" [attr.aria-label]="b.date + ': ' + labels[b.status]"></span>
            }
          }
        </div>
        <p class="muted">{{ v.range.date_from }} to {{ v.range.date_to }}. Bars link to that day's licences. Days with no bar are explained by the coverage strip.</p>
      </section>

      <section>
        <h2>Coverage</h2>
        <div class="strip" aria-hidden="true">
          @for (c of v.cells; track c.date) { <i [class]="c.status" [title]="c.date + ': ' + labels[c.status]"></i> }
        </div>
        <p class="muted">{{ v.summary }}</p>
        @if (v.problems.length) {
          <ul class="problems">
            @for (p of v.problems; track p.date) { <li>{{ p.date }}: {{ labels[p.status] }}</li> }
          </ul>
        }
        <p class="legend">
          <span><i class="loaded"></i>loaded</span><span><i class="empty"></i>loaded, no licences</span>
          <span><i class="failed"></i>failed</span><span><i class="missing"></i>missing</span><span><i class="unknown"></i>not published yet</span>
        </p>
      </section>

      <div class="cols">
        <section>
          <h2>Substance mix</h2>
          <table><tbody>
            @for (s of v.substances; track s.substance) {
              <tr>
                <td>@if (s.substance) { <a routerLink="/licences" [queryParams]="slice({ substance: s.substance })">{{ s.substance }}</a> } @else { (unknown) }</td>
                <td class="num">{{ s.count }}</td>
              </tr>
            }
          </tbody></table>
        </section>
        <section>
          <h2>Top 10 licensees</h2>
          <table><tbody>
            @for (s of v.licensees; track s.licensee) {
              <tr>
                <td>@if (s.licensee) { <a routerLink="/licences" [queryParams]="slice({ licensee: s.licensee })">{{ s.licensee }}</a> } @else { (unknown) }</td>
                <td class="num">{{ s.count }}</td>
              </tr>
            }
          </tbody></table>
        </section>
        <section>
          <h2>Top 10 target formations</h2>
          <table><tbody>
            @for (s of v.formations; track s.terminating_zone) {
              <tr>
                <td>@if (s.terminating_zone) { <a routerLink="/licences" [queryParams]="slice({ terminating_zone: s.terminating_zone })">{{ s.terminating_zone }}</a> } @else { (unknown) }</td>
                <td class="num">{{ s.count }}</td>
              </tr>
            }
          </tbody></table>
        </section>
      </div>
    } @else if (data.error()) {
      <p class="error">Could not load stats.</p>
    } @else {
      <p class="muted">Loading…</p>
    }
  `,
})
export class DashboardPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly labels = LABELS;

  /** The window comes from the URL (date_from, date_to), defaulting to the last 30 days. */
  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  readonly range = computed(() => {
    const q = queryFromParams(k => this.params().get(k));
    return clipRange(q.date_from!, q.date_to!);
  });
  readonly preset = computed(() => [7, 30, 90].find(d => this.range().date_from === isoDaysAgo(d) && this.range().date_to === isoDaysAgo(0)) ?? null);

  // ponytail: CSS bars, no chart lib (Anubis: keep it)
  readonly data = resource({
    params: () => this.range(),
    loader: async ({ params: range }) => {
      const q: StatsQuery = { ...range, event_type: 'issued' };
      const [daily, licensees, formations, substances] = await Promise.all([
        this.api.daily(q), this.api.topLicensees({ ...q, limit: 10 }), this.api.topFormations({ ...q, limit: 10 }), this.api.substances(q),
      ]);
      const counts = new Map(daily.items.map(d => [d.date, d.count]));
      const dates = dateRange(range.date_from, range.date_to);
      const cells = coverageCells(daily.meta.coverage, dates, new Set(counts.keys()));
      const status = new Map(cells.map(c => [c.date, c.status]));
      return {
        range, licensees: licensees.items, formations: formations.items, substances: substances.items, cells,
        bars: dates.map(date => ({ date, count: counts.get(date) ?? null, status: status.get(date) ?? 'unknown' })),
        max: Math.max(1, ...daily.items.map(d => d.count)),
        total: daily.items.reduce((n, d) => n + d.count, 0),
        summary: summarise(cells),
        problems: cells.filter(c => c.status === 'failed' || c.status === 'missing'),
      };
    },
  });

  constructor() {
    // A hand-edited URL with a window longer than MAX_DAYS is rewritten to the clipped one, so the address matches what is drawn.
    effect(() => {
      const p = this.params();
      const from = p.get('date_from');
      const to = p.get('date_to');
      const r = this.range();
      if (from && to && (from !== r.date_from || to !== r.date_to)) {
        void this.router.navigate([], { relativeTo: this.route, queryParams: r, queryParamsHandling: 'merge', replaceUrl: true });
      }
    });
  }

  /** Query params for a table view of one slice of this window. */
  slice(extra: Record<string, string>): Record<string, string> {
    return { ...this.range(), event_type: 'issued', ...extra };
  }

  setDays(days: number): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: { date_from: isoDaysAgo(days), date_to: isoDaysAgo(0) } });
  }

  applyRange(ev: Event): void {
    ev.preventDefault();
    const fd = new FormData(ev.target as HTMLFormElement);
    const date_from = String(fd.get('date_from') ?? '');
    const date_to = String(fd.get('date_to') ?? '');
    if (!date_from || !date_to) return;
    void this.router.navigate([], { relativeTo: this.route, queryParams: clipRange(date_from, date_to) });
  }
}
