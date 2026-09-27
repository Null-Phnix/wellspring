import { LicencePoint } from '../api/types';
import { colourFor, describeFilters, popup } from './map';

const point = (extra: Partial<LicencePoint> = {}): LicencePoint => ({
  id: 'x', licence_number: '0525384', well_name: 'OUC HZ FERRIER 3-6-38-8', licensee: 'ORLEN UPSTREAM CANADA LTD.', substance: 'CRUDE OIL',
  report_date: '2026-09-01', latitude: 52.25, longitude: -115.15, coordinate_method: 'alberta_dls_grid_approximation_v1',
  location_accuracy: 'approximate', location_reason: null, ...extra,
});

describe('map helpers', () => {
  it('colours known substances and greys the rest', () => {
    expect(colourFor('GAS')).not.toBe(colourFor('CRUDE OIL'));
    expect(colourFor('HELIUM')).toBe(colourFor(null));
  });

  it('builds an escaped popup with the approximate note and a DLS line only when the projection has it', () => {
    const html = popup(point({ licensee: 'A <B> & "C"' }));
    expect(html).toContain('A &lt;B&gt; &amp; &quot;C&quot;');
    expect(html).toContain('Licence 0525384, 2026-09-01');
    expect(html).toContain('township grid method');
    expect(html).not.toContain('DLS');
    expect(popup(point({ surface_location: '16-12-066-03W4' }))).toContain('DLS 16-12-066-03 W4M');
    expect(popup(point({ well_name: null }))).toContain('Well name not reported');
  });

  it('describes the active filters in words', () => {
    expect(describeFilters({ date_from: '2026-09-01', date_to: '2026-09-27', licensee: 'cenovus', substance: 'GAS' }))
      .toBe('issued licences, 2026-09-01 to 2026-09-27, licensee contains "cenovus", substance GAS');
    expect(describeFilters({ event_type: 'all' })).toBe('all licences, all dates');
  });
});
