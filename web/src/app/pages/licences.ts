import { Component, computed, inject, resource, signal } from '@angular/core';
import { ApiService, isoDaysAgo } from '../api/api.service';
import { EVENT_TYPES, LicenceEvent, LicencePage as Page, LicenceQuery, SortKey } from '../api/types';
import { DlsPipe } from '../dls.pipe';

const COLUMNS: { key: keyof LicenceEvent; label: string; sort?: SortKey }[] = [
  { key: 'report_date', label: 'Date', sort: 'report_date' },
  { key: 'licence_number', label: 'Licence', sort: 'licence_number' },
  { key: 'event_type', label: 'Event' },
  { key: 'well_name', label: 'Well name' },
  { key: 'licensee', label: 'Licensee', sort: 'licensee' },
  { key: 'substance', label: 'Substance', sort: 'substance' },
  { key: 'field_centre', label: 'Field centre', sort: 'field_centre' },
  { key: 'terminating_zone', label: 'Terminating zone', sort: 'terminating_zone' },
  { key: 'well_type', label: 'Well type', sort: 'well_type' },
  { key: 'surface_location', label: 'Surface location' },
];
const FILTERS = ['date_from', 'date_to', 'licensee', 'substance', 'field_centre', 'terminating_zone', 'well_type', 'event_type'] as const;

/** CSV of the given columns, RFC 4180 quoting; feeds the export button. */
export function toCsv(rows: LicenceEvent[], columns = COLUMNS): string {
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(c => cell(c.label)), ...rows.map(r => columns.map(c => cell(r[c.key])))]
    .map(line => line.join(',')).join('\n');
}

@Component({
  selector: 'app-licences',
  imports: [DlsPipe],
  template: `
    <h1>Licences</h1>
    <form class="filters" (submit)="apply($event)">
      <label>From <input type="date" name="date_from" [value]="q().date_from ?? ''"></label>
      <label>To <input type="date" name="date_to" [value]="q().date_to ?? ''"></label>
      <label>Event
        <select name="event_type">
          @for (t of eventTypes; track t) { <option [value]="t" [selected]="t === (q().event_type ?? 'issued')">{{ t }}</option> }
        </select>
      </label>
      <label>Licensee <input name="licensee" [value]="q().licensee ?? ''"></label>
      <label>Substance <input name="substance" list="substances" placeholder="exact value" [value]="q().substance ?? ''"></label>
      <datalist id="substances">
        <option>CRUDE BITUMEN</option><option>CRUDE OIL</option><option>GAS</option><option>WATER</option>
      </datalist>
      <label>Field centre <input name="field_centre" placeholder="exact value" [value]="q().field_centre ?? ''"></label>
      <label>Terminating zone <input name="terminating_zone" placeholder="exact value" [value]="q().terminating_zone ?? ''"></label>
      <label>Well type <input name="well_type" placeholder="exact value" [value]="q().well_type ?? ''"></label>
      <button>Apply</button>
      <button type="button" (click)="exportCsv()" [disabled]="!page.value()">Export CSV (loaded rows)</button>
    </form>

    @if (page.value(); as p) {
      <p class="muted">{{ p.total }} events</p>
      <table class="licences">
        <thead><tr>
          @for (c of columns; track c.key) {
            <th scope="col" [class.sortable]="c.sort" (click)="c.sort && sortBy(c.sort)"
                [attr.aria-sort]="c.sort && q().sort === c.sort ? (q().order === 'asc' ? 'ascending' : 'descending') : null">
              {{ c.label }}
              @if (c.sort && q().sort === c.sort) { <span>{{ q().order === 'asc' ? '▲' : '▼' }}</span> }
            </th>
          }
        </tr></thead>
        <tbody>
          @for (r of p.items; track r.id) {
            <tr>
              <td>{{ r.report_date }}</td><td>{{ r.licence_number }}</td><td>{{ r.event_type }}</td>
              <td>{{ r.well_name }}</td><td>{{ r.licensee }}</td><td>{{ r.substance }}</td>
              <td>{{ r.field_centre }}</td><td>{{ r.terminating_zone }}</td><td>{{ r.well_type }}</td>
              <td>{{ (r.dls ?? r.surface_location) | dls }}</td>
            </tr>
          } @empty {
            <tr><td colspan="10">No events match.</td></tr>
          }
        </tbody>
      </table>
      <nav class="pager">
        <button type="button" (click)="go(-1)" [disabled]="p.page <= 1">Previous</button>
        <span>Page {{ p.page }} of {{ pages(p) }}</span>
        <button type="button" (click)="go(1)" [disabled]="p.page >= pages(p)">Next</button>
      </nav>
    } @else if (page.error()) {
      <p class="error">Could not load licences.</p>
    } @else {
      <p class="muted">Loading…</p>
    }
  `,
})
export class LicencesPage {
  private readonly api = inject(ApiService);
  readonly columns = COLUMNS;
  readonly eventTypes = ['all', ...EVENT_TYPES];
  readonly q = signal<LicenceQuery>({
    date_from: isoDaysAgo(30), date_to: isoDaysAgo(0), event_type: 'issued', page: 1, page_size: 50, sort: 'report_date', order: 'desc',
  });

  readonly page = resource({ params: () => this.q(), loader: ({ params }) => this.api.licences(params) });
  readonly rows = computed(() => this.page.value()?.items ?? []);

  apply(ev: Event): void {
    ev.preventDefault();
    const fd = new FormData(ev.target as HTMLFormElement);
    const next = { ...this.q(), page: 1 } as Record<string, unknown>;
    for (const f of FILTERS) {
      const v = String(fd.get(f) ?? '').trim();
      if (v) next[f] = v; else delete next[f];
    }
    this.q.set(next as LicenceQuery);
  }

  /** Server-side sort (contract allowlist); same column again flips the order. */
  sortBy(sort: SortKey): void {
    this.q.update(q => ({ ...q, page: 1, sort, order: q.sort === sort && q.order === 'asc' ? 'desc' : 'asc' }));
  }

  go(delta: number): void {
    this.q.update(q => ({ ...q, page: (q.page ?? 1) + delta }));
  }

  pages(p: Page): number {
    return Math.max(1, Math.ceil(p.total / p.page_size));
  }

  exportCsv(): void {
    const url = URL.createObjectURL(new Blob([toCsv(this.rows())], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), {
      href: url, download: `licences-${this.q().date_from ?? 'all'}-${this.q().date_to ?? 'today'}.csv`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }
}
