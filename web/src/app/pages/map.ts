import { Component, ElementRef, afterNextRender, computed, effect, inject, resource, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import * as L from 'leaflet';
import { ApiService } from '../api/api.service';
import { LicencePoint, StatsQuery } from '../api/types';
import { DlsPipe } from '../dls.pipe';
import { filtersOf, paramsFor, queryFromParams } from '../filters';

export const MAP_CAP = 1000; // ponytail: newest 1000 points, stated on screen; cluster or tile if Josii wants more
const COLOURS: Record<string, string> = { 'CRUDE BITUMEN': '#b45309', 'CRUDE OIL': '#15803d', 'GAS': '#1d4ed8', 'WATER': '#0e7490' };
const OTHER = '#6b7280';
const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const dls = new DlsPipe();

export function colourFor(substance: string | null): string {
  return COLOURS[substance ?? ''] ?? OTHER;
}

/** Popup HTML for one point; every value is escaped. The DLS line appears once the points projection carries surface_location. */
export function popup(p: LicencePoint): string {
  const esc = (s: string | null | undefined) => (s ?? '').replace(/[&<>"]/g, c => ESC[c] ?? c);
  const lines = [
    `<strong>${esc(p.well_name) || 'Well name not reported'}</strong>`,
    `Licence ${esc(p.licence_number)}, ${esc(p.report_date)}`,
    esc(p.licensee) || 'Licensee not reported',
    esc(p.substance) || 'Substance not reported',
  ];
  if (p.surface_location) lines.push(`DLS ${esc(dls.transform(p.surface_location))}`);
  lines.push('<small>Approximate position, township grid method</small>');
  return lines.join('<br>');
}

/** The active filters in words, for the line above the map. */
export function describeFilters(f: StatsQuery): string {
  const parts = [
    `${f.event_type ?? 'issued'} licences`,
    f.date_from && f.date_to ? `${f.date_from} to ${f.date_to}` : f.date_from ? `from ${f.date_from}` : f.date_to ? `to ${f.date_to}` : 'all dates',
    f.licensee ? `licensee contains "${f.licensee}"` : '',
    f.substance ? `substance ${f.substance}` : '',
    f.field_centre ? `field centre ${f.field_centre}` : '',
    f.terminating_zone ? `terminating zone ${f.terminating_zone}` : '',
    f.well_type ? `well type ${f.well_type}` : '',
  ];
  return parts.filter(Boolean).join(', ');
}

@Component({
  selector: 'app-map',
  imports: [RouterLink],
  template: `
    <h1>Map</h1>
    <p class="muted">
      Approximate surface positions, derived from each licence's legal land description by the township grid
      method (accurate to roughly a section, about 1.6 km). Not for navigation or land decisions.
    </p>
    <p class="toolbar">
      <span>Showing {{ summary() }}.</span>
      <a routerLink="/licences" [queryParams]="tableParams()">Edit filters in the table</a>
    </p>
    <div #map class="map" role="region" aria-label="Map of well licence surface locations"></div>
    <p class="legend">
      @for (e of legend; track e[0]) { <span><i [style.background]="e[1]"></i>{{ e[0] }}</span> }
      <span><i [style.background]="other"></i>Other</span>
    </p>
    @if (data.value(); as v) {
      <p class="muted">
        @if (v.loaded && !v.plotted) {
          No positions for these filters: {{ v.loaded }} events matched, none has coordinates yet.
        } @else if (!v.loaded) {
          No events match these filters.
        } @else {
          {{ v.plotted }} of {{ v.total }} matching events plotted.
          @if (v.capped) { Only the newest {{ cap }} were loaded; narrow the filters to see the rest. }
          @if (v.loaded - v.plotted) { {{ v.loaded - v.plotted }} loaded events have no coordinates (the table shows the reason). }
        }
      </p>
    } @else if (data.error()) {
      <p class="error">Could not load positions.</p>
    } @else {
      <p class="muted">Loading positions…</p>
    }
  `,
})
export class MapPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('map');
  private readonly map = signal<L.Map | null>(null);
  private readonly layer = L.layerGroup();
  readonly legend = Object.entries(COLOURS);
  readonly other = OTHER;
  readonly cap = MAP_CAP;

  /** Same URL filter state as the table. */
  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  readonly filters = computed(() => filtersOf(queryFromParams(k => this.params().get(k))));
  readonly tableParams = computed(() => paramsFor(this.filters()));
  readonly summary = computed(() => describeFilters(this.filters()));

  readonly data = resource({
    params: () => this.filters(),
    loader: async ({ params }) => {
      const { items, total, capped } = await this.api.allPoints({ ...params, sort: 'report_date', order: 'desc' }, MAP_CAP);
      const plottable = items.filter(p => p.latitude != null && p.longitude != null);
      return { items: plottable, plotted: plottable.length, loaded: items.length, total, capped };
    },
  });

  constructor() {
    afterNextRender(() => {
      const map = L.map(this.host().nativeElement).setView([54.5, -115], 5);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
      this.layer.addTo(map);
      this.map.set(map);
    });
    effect(() => {
      const map = this.map();
      const items = this.data.value()?.items;
      if (map && items) this.plot(map, items);
    });
  }

  private plot(map: L.Map, items: LicencePoint[]): void {
    this.layer.clearLayers();
    for (const p of items) {
      L.circleMarker([p.latitude!, p.longitude!], { radius: 6, color: colourFor(p.substance), weight: 1, fillOpacity: 0.7 })
        .bindPopup(popup(p))
        .addTo(this.layer);
    }
    if (items.length) map.fitBounds(L.latLngBounds(items.map(p => [p.latitude!, p.longitude!] as [number, number])).pad(0.1), { maxZoom: 9 });
  }
}
