import { Pipe, PipeTransform } from '@angular/core';
import { Dls } from './api/types';

const RAW = /^(\d{1,2})-(\d{1,2})-(\d{1,3})-(\d{1,2})\s*W(\d)M?$/i;

/** Parse an ST1 surface location such as "13-26-061-16W4". */
export function parseDls(raw: string): Dls | null {
  const m = RAW.exec(raw.trim());
  if (!m) return null;
  const [, lsd, section, township, range, meridian] = m.map(Number);
  return { lsd, section, township, range, meridian };
}

/** Display a DLS location as LSD-SEC-TWP-RGE WnM, zero-padded the way the AER prints it. */
@Pipe({ name: 'dls' })
export class DlsPipe implements PipeTransform {
  transform(value: Dls | string | null | undefined): string {
    const d = typeof value === 'string' ? parseDls(value) : value;
    if (!d) return typeof value === 'string' ? value : '';
    const p = (n: number, w: number) => String(n).padStart(w, '0');
    return `${p(d.lsd, 2)}-${p(d.section, 2)}-${p(d.township, 3)}-${p(d.range, 2)} W${d.meridian}M`;
  }
}
