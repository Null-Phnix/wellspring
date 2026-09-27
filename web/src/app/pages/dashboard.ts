import { Component, computed, inject, resource, signal } from '@angular/core';
import { ApiService, isoDaysAgo } from '../api/api.service';

@Component({
  selector: 'app-dashboard',
  template: `
    <h1>Dashboard</h1>
    <label>Window
      <select (change)="days.set(+$any($event.target).value)">
        @for (d of [7, 30, 90]; track d) {
          <option [value]="d" [selected]="d === days()">Last {{ d }} days</option>
        }
      </select>
    </label>

    @if (data.value(); as v) {
      <section>
        <h2>Licences issued per day</h2>
        <div class="bars" role="img" [attr.aria-label]="'Licences issued per day, last ' + days() + ' days'">
          @for (r of v.daily; track r.date) {
            <div class="bar" [style.height.%]="(100 * r.count) / v.max" [title]="r.date + ': ' + r.count"></div>
          }
        </div>
        <p class="muted">
          {{ v.daily[0]?.date }} to {{ v.daily[v.daily.length - 1]?.date }}, {{ v.total }} licences issued,
          {{ v.meta.coverage.reports_loaded }} daily lists loaded
          @if (v.meta.coverage.missing_dates.length) { , {{ v.meta.coverage.missing_dates.length }} missing }
        </p>
      </section>
      <div class="cols">
        <section>
          <h2>Substance mix</h2>
          <table><tbody>
            @for (s of v.substances; track s.substance) { <tr><td>{{ s.substance ?? '(unknown)' }}</td><td class="num">{{ s.count }}</td></tr> }
          </tbody></table>
        </section>
        <section>
          <h2>Top 10 licensees</h2>
          <table><tbody>
            @for (s of v.licensees; track s.licensee) { <tr><td>{{ s.licensee ?? '(unknown)' }}</td><td class="num">{{ s.count }}</td></tr> }
          </tbody></table>
        </section>
        <section>
          <h2>Top 10 target formations</h2>
          <table><tbody>
            @for (s of v.formations; track s.terminating_zone) { <tr><td>{{ s.terminating_zone ?? '(unknown)' }}</td><td class="num">{{ s.count }}</td></tr> }
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
  readonly days = signal(30);
  private readonly range = computed(() => ({ date_from: isoDaysAgo(this.days()), date_to: isoDaysAgo(0) }));

  // ponytail: CSS bars, no chart lib; swap one in when Josii wants axes or hover
  readonly data = resource({
    params: () => this.range(),
    loader: async ({ params }) => {
      const [daily, licensees, formations, substances] = await Promise.all([
        this.api.daily(params),
        this.api.topLicensees({ ...params, limit: 10 }),
        this.api.topFormations({ ...params, limit: 10 }),
        this.api.substances(params),
      ]);
      return {
        daily: daily.items, licensees: licensees.items, formations: formations.items, substances: substances.items,
        meta: daily.meta,
        max: Math.max(1, ...daily.items.map(d => d.count)),
        total: daily.items.reduce((n, d) => n + d.count, 0),
      };
    },
  });
}
