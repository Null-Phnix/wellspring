import { Component, computed, inject, resource, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../api/api.service';
import { EVENT_TYPES, LicenceEvent, LicencePage as Page, LicenceQuery, SortKey } from '../api/types';
import { DlsPipe } from '../dls.pipe';
import { FILTER_KEYS, defaultQuery, filtersOf, paramsFor, queryFromParams } from '../filters';

export const PAGE_SIZE = 50;
export const CSV_CAP = 2000; // rows; named in the export button's tooltip and in the note after an export

type Column = { key: keyof LicenceEvent; label: string; sort?: SortKey };
const COLUMNS: Column[] = [
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
const CSV_COLUMNS: Column[] = [
  ...COLUMNS,
  { key: 'uwi', label: 'UWI' },
  { key: 'field', label: 'Field' },
  { key: 'latitude', label: 'Latitude (approximate)' },
  { key: 'longitude', label: 'Longitude (approximate)' },
  { key: 'location_reason', label: 'Location reason' },
];

/** CSV of the given columns, RFC 4180 quoting; feeds the export button. */
export function toCsv(rows: LicenceEvent[], columns = CSV_COLUMNS): string {
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(c => cell(c.label)), ...rows.map(r => columns.map(c => cell(r[c.key])))]
    .map(line => line.join(',')).join('\n');
}

@Component({
  selector: 'app-licences',
  imports: [DlsPipe, RouterLink],
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
      <label>Licensee <input name="licensee" placeholder="contains" [value]="q().licensee ?? ''"></label>
      <label>Substance <input name="substance" list="substances" placeholder="exact value" [value]="q().substance ?? ''"></label>
      <datalist id="substances">
        <option>CRUDE BITUMEN</option><option>CRUDE OIL</option><option>GAS</option><option>WATER</option>
      </datalist>
      <label>Field centre <input name="field_centre" placeholder="exact value" [value]="q().field_centre ?? ''"></label>
      <label>Terminating zone <input name="terminating_zone" placeholder="exact value" [value]="q().terminating_zone ?? ''"></label>
      <label>Well type <input name="well_type" placeholder="exact value" [value]="q().well_type ?? ''"></label>
      <span class="actions">
        <button>Apply</button>
        <button type="button" class="secondary" (click)="reset()">Reset</button>
      </span>
    </form>

    <p class="toolbar">
      @if (page.value(); as p) { <span>{{ p.total }} events match.</span> }
      <a routerLink="/map" [queryParams]="mapParams()">Show these on the map</a>
      <button type="button" class="link" (click)="exportCsv()" [disabled]="exporting() || !page.value()"
              [title]="'Exports every event matching the current filters, sorted as shown, up to ' + csvCap + ' rows'">
        {{ exporting() ? 'Exporting…' : 'Export CSV (all matching, up to ' + csvCap + ' rows)' }}
      </button>
      @if (exportNote()) { <span class="muted">{{ exportNote() }}</span> }
    </p>

    @if (page.value(); as p) {
      <div class="table-wrap">
        <table class="licences">
          <thead><tr>
            <th scope="col"><span class="sr-only">Details</span></th>
            @for (c of columns; track c.key) {
              <th scope="col" [attr.aria-sort]="c.sort && q().sort === c.sort ? (q().order === 'asc' ? 'ascending' : 'descending') : null">
                @if (c.sort) {
                  <button type="button" class="sort" (click)="sortBy(c.sort)">
                    {{ c.label }}
                    @if (q().sort === c.sort) { <span aria-hidden="true">{{ q().order === 'asc' ? '▲' : '▼' }}</span> }
                  </button>
                } @else { {{ c.label }} }
              </th>
            }
          </tr></thead>
          <tbody>
            @for (r of p.items; track r.id) {
              <tr>
                <td>
                  <button type="button" class="expand" (click)="toggle(r.id)" [attr.aria-expanded]="expanded().has(r.id)"
                          [attr.aria-label]="'Full record for licence ' + r.licence_number">{{ expanded().has(r.id) ? '−' : '+' }}</button>
                </td>
                <td>{{ r.report_date }}</td><td>{{ r.licence_number }}</td><td>{{ r.event_type }}</td>
                <td>{{ r.well_name }}</td><td>{{ r.licensee }}</td><td>{{ r.substance }}</td>
                <td>{{ r.field_centre }}</td><td>{{ r.terminating_zone }}</td><td>{{ r.well_type }}</td>
                <td>{{ (r.dls ?? r.surface_location) | dls }}</td>
              </tr>
              @if (expanded().has(r.id)) {
                <tr class="detail"><td colspan="11">
                  <dl>
                    <dt>UWI</dt><dd>{{ r.uwi ?? 'n/a' }}</dd>
                    <dt>Field</dt><dd>{{ r.field ?? 'n/a' }}</dd>
                    <dt>AER classification</dt><dd>{{ r.aer_classification ?? 'n/a' }}</dd>
                    <dt>Drilling operation</dt><dd>{{ r.drilling_operation ?? 'n/a' }}</dd>
                    <dt>Well purpose</dt><dd>{{ r.well_purpose ?? 'n/a' }}</dd>
                    <dt>Mineral rights</dt><dd>{{ r.mineral_rights ?? 'n/a' }}</dd>
                    <dt>Ground elevation</dt><dd>{{ r.ground_elevation_m == null ? 'n/a' : r.ground_elevation_m + ' m' }}</dd>
                    <dt>Projected depth</dt><dd>{{ r.projected_depth_m == null ? 'n/a' : r.projected_depth_m + ' m' }}</dd>
                    <dt>Surface co-ordinates</dt><dd>{{ r.surface_coordinates_text ?? 'n/a' }}</dd>
                    <dt>Position</dt>
                    <dd>
                      @if (r.latitude != null && r.longitude != null) {
                        {{ r.latitude }}, {{ r.longitude }} ({{ r.location_accuracy ?? 'approximate' }}, {{ r.coordinate_method ?? 'method not stated' }})
                      } @else { none. Reason: {{ r.location_reason ?? 'not given' }} }
                    </dd>
                    <dt>Occurrences in this list</dt><dd>{{ r.occurrence_count }}</dd>
                    <dt>Source report date</dt><dd>{{ r.report_date }}</dd>
                    <dt>Source</dt><dd><a [href]="r.source.url" rel="noopener">{{ r.source.url }}</a>, retrieved {{ r.source.retrieved_at }}, parser {{ r.source.parser_version }}</dd>
                  </dl>
                </td></tr>
              }
            } @empty {
              <tr><td colspan="11">No events match.</td></tr>
            }
          </tbody>
        </table>
      </div>
      <nav class="pager" aria-label="Pages">
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
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly columns = COLUMNS;
  readonly eventTypes = ['all', ...EVENT_TYPES];
  readonly csvCap = CSV_CAP;

  /** The URL query string is the filter state, shared with the map and the dashboard's links. */
  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  readonly q = computed<LicenceQuery>(() => ({ ...queryFromParams(k => this.params().get(k)), page_size: PAGE_SIZE }));
  readonly page = resource({ params: () => this.q(), loader: ({ params }) => this.api.licences(params) });
  readonly rows = computed(() => this.page.value()?.items ?? []);
  readonly mapParams = computed(() => paramsFor(filtersOf(this.q())));
  readonly expanded = signal(new Set<string>());
  readonly exporting = signal(false);
  readonly exportNote = signal('');

  apply(ev: Event): void {
    ev.preventDefault();
    const fd = new FormData(ev.target as HTMLFormElement);
    const next: Record<string, unknown> = { sort: this.q().sort, order: this.q().order, page: 1 };
    for (const f of FILTER_KEYS) {
      const v = String(fd.get(f) ?? '').trim();
      if (v) next[f] = v;
    }
    this.navigate(next as LicenceQuery);
  }

  reset(): void {
    this.navigate(defaultQuery());
  }

  /** Server-side sort (contract allowlist); the same column again flips the order. */
  sortBy(sort: SortKey): void {
    const q = this.q();
    this.navigate({ ...q, page: 1, sort, order: q.sort === sort && q.order === 'asc' ? 'desc' : 'asc' });
  }

  go(delta: number): void {
    this.navigate({ ...this.q(), page: (this.q().page ?? 1) + delta });
  }

  pages(p: Page): number {
    return Math.max(1, Math.ceil(p.total / p.page_size));
  }

  toggle(id: string): void {
    this.expanded.update(s => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  /** Every event matching the current filters, paged through the API up to CSV_CAP rows. */
  async exportCsv(): Promise<void> {
    this.exporting.set(true);
    this.exportNote.set('');
    try {
      const { sort, order } = this.q();
      const { items, total, capped } = await this.api.allLicences({ ...filtersOf(this.q()), sort, order }, CSV_CAP);
      const url = URL.createObjectURL(new Blob([toCsv(items)], { type: 'text/csv' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: `wellspring-licences-${this.q().date_from ?? 'all'}-${this.q().date_to ?? 'today'}.csv` });
      a.click();
      URL.revokeObjectURL(url);
      this.exportNote.set(capped ? `Exported the first ${items.length} of ${total} matching events (cap ${CSV_CAP}).` : `Exported all ${items.length} matching events.`);
    } catch {
      this.exportNote.set('Export failed.');
    } finally {
      this.exporting.set(false);
    }
  }

  private navigate(q: LicenceQuery): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: paramsFor(q) });
  }
}
