import { Component, ElementRef, afterNextRender, effect, inject, resource, signal, viewChild } from '@angular/core';
import * as L from 'leaflet';
import { ApiService, isoDaysAgo } from '../api/api.service';
import { LicenceEvent } from '../api/types';
import { DlsPipe } from '../dls.pipe';

const COLOURS: Record<string, string> = { 'CRUDE BITUMEN': '#b45309', 'CRUDE OIL': '#15803d', 'GAS': '#1d4ed8', 'WATER': '#0e7490' };
const OTHER = '#6b7280';
const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const PAGE_SIZE = 200; // contract cap on page_size
const MAX_PAGES = 5; // ponytail: 1000 newest events; Tenjin's M2 contract may add a slim points projection (issue #1 comment 125)

@Component({
  selector: 'app-map',
  template: `
    <h1>Map</h1>
    <p class="muted">
      Surface locations of licences issued in the last 30 days. Positions are <strong>approximate</strong>: converted
      from the DLS surface location by the township grid method, accurate to roughly a section (about 1.6 km).
    </p>
    <div #map class="map" role="region" aria-label="Map of well licence surface locations"></div>
    <p class="legend">
      @for (e of legend; track e[0]) { <span><i [style.background]="e[1]"></i>{{ e[0] }}</span> }
      <span><i [style.background]="other"></i>Other</span>
      @if (data.value(); as v) {
        <span class="muted">
          {{ v.plotted }} of {{ v.loaded }} loaded events plotted; {{ v.total }} issued in the window.
          @if (v.capped) { Loading is capped at {{ cap }} events, newest first. }
          Unplotted events have no coordinates yet.
        </span>
      }
    </p>
  `,
})
export class MapPage {
  private readonly api = inject(ApiService);
  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('map');
  private readonly map = signal<L.Map | null>(null);
  private readonly dls = new DlsPipe();
  readonly legend = Object.entries(COLOURS);
  readonly other = OTHER;
  readonly cap = PAGE_SIZE * MAX_PAGES;

  readonly data = resource({
    loader: async () => {
      const q = { date_from: isoDaysAgo(30), date_to: isoDaysAgo(0), page_size: PAGE_SIZE };
      const first = await this.api.licences({ ...q, page: 1 });
      const items = [...first.items];
      const pages = Math.min(MAX_PAGES, Math.ceil(first.total / first.page_size));
      for (let p = 2; p <= pages; p++) items.push(...(await this.api.licences({ ...q, page: p })).items);
      const plottable = items.filter(r => r.latitude != null && r.longitude != null);
      return { items: plottable, plotted: plottable.length, loaded: items.length, total: first.total, capped: first.total > items.length };
    },
  });

  constructor() {
    afterNextRender(() => {
      const map = L.map(this.host().nativeElement).setView([54.5, -115], 5);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
      this.map.set(map);
    });
    effect(() => {
      const map = this.map();
      const items = this.data.value()?.items;
      if (map && items) this.plot(map, items);
    });
  }

  private plot(map: L.Map, items: LicenceEvent[]): void {
    const layer = L.layerGroup().addTo(map);
    for (const r of items) {
      L.circleMarker([r.latitude!, r.longitude!], { radius: 6, color: COLOURS[r.substance ?? ''] ?? OTHER, weight: 1, fillOpacity: 0.7 })
        .bindPopup(popup(r, this.dls.transform(r.dls ?? r.surface_location)))
        .addTo(layer);
    }
  }
}

function popup(r: LicenceEvent, dls: string): string {
  const esc = (s: string | null) => (s ?? '').replace(/[&<>"]/g, c => ESC[c] ?? c);
  return `<strong>${esc(r.well_name)}</strong><br>` +
    `Licence ${esc(r.licence_number)} (${esc(r.event_type)}, ${esc(r.report_date)})<br>` +
    `${esc(r.licensee)}<br>${esc(r.substance)}, ${esc(r.well_type)}<br>` +
    `${esc(r.field_centre)}, ${esc(r.terminating_zone)}<br>` +
    `<small>${esc(dls)} (${esc(r.location_accuracy ?? 'approximate')} position)</small>`;
}
