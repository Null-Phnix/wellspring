import { TestBed } from '@angular/core/testing';
import { ApiService } from '../api/api.service';
import { LicenceEvent, LicencePage, LicenceQuery } from '../api/types';
import { LicencesPage, toCsv } from './licences';

const lic = (n: number, licensee: string, substance: string): LicenceEvent => ({
  id: `052580${n}:issued:2026-09-2${n}`, schema_version: 1, report_date: `2026-09-2${n}`, event_type: 'issued',
  licence_number: `052580${n}`, well_name: `WELL ${n}`, uwi: `100/0${n}-10-085-17W5/00`, mineral_rights: 'ALBERTA CROWN',
  surface_coordinates_text: null, field_centre: 'SLAVE LAKE', aer_classification: 'DEV (NC)', field: 'CADOTTE',
  terminating_zone: 'BLUESKY FM', drilling_operation: 'HORIZONTAL', well_purpose: 'NEW', well_type: 'PRODUCTION',
  substance, licensee, surface_location: '04-10-085-17W5', ground_elevation_m: 600, projected_depth_m: 2750,
  dls: { lsd: 4, section: 10, township: 85, range: 17, meridian: 5 }, latitude: null, longitude: null,
  coordinate_method: null, location_accuracy: null, location_reason: 'not_yet_converted', occurrence_count: 1, occurrences: [],
  source: { url: '', sha256: '', retrieved_at: '', parser_version: 'test' },
});
const META = { schema_version: 1 as const, data_as_of: null, date_from: null, date_to: null, event_type: 'issued',
  coverage: { reports_loaded: 1, missing_dates: [], failed_dates: [], parse_issue_count: 0 } };
const PAGE: LicencePage = {
  items: [lic(1, 'CNRL', 'GAS'), lic(2, 'ARC', 'CRUDE OIL'), lic(3, 'IMPERIAL', 'CRUDE BITUMEN')],
  total: 3, page: 1, page_size: 50, meta: META,
};

describe('LicencesPage', () => {
  const calls: LicenceQuery[] = [];

  async function render() {
    calls.length = 0;
    await TestBed.configureTestingModule({
      imports: [LicencesPage],
      providers: [{ provide: ApiService, useValue: { licences: async (q: LicenceQuery) => { calls.push(q); return PAGE; } } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(LicencesPage);
    await fixture.whenStable();
    return fixture;
  }
  const column = (el: HTMLElement, i: number) =>
    [...el.querySelectorAll('tbody tr')].map(tr => tr.children[i].textContent?.trim());

  it('renders one row per event with the DLS formatted', async () => {
    const el = (await render()).nativeElement as HTMLElement;
    expect(el.querySelectorAll('tbody tr').length).toBe(3);
    expect(column(el, 4)).toEqual(['CNRL', 'ARC', 'IMPERIAL']);
    expect(column(el, 9)[0]).toBe('04-10-085-17 W5M');
    expect(calls[0]).toMatchObject({ event_type: 'issued', sort: 'report_date', order: 'desc', page: 1 });
  });

  it('asks the server to sort on header click and flips the order on the second click', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    // the table re-renders after each fetch, so find the header again each time
    const header = () => [...el.querySelectorAll('th')].find(th => th.textContent?.includes('Licensee'))!;
    header().click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ sort: 'licensee', order: 'asc', page: 1 });
    header().click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ sort: 'licensee', order: 'desc' });
    expect(header().getAttribute('aria-sort')).toBe('descending');
  });

  it('applies the filter form as query params', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('input[name=licensee]') as HTMLInputElement).value = 'cnrl';
    (el.querySelector('select[name=event_type]') as HTMLSelectElement).value = 'all';
    el.querySelector('form')!.requestSubmit();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ licensee: 'cnrl', event_type: 'all', page: 1 });
  });

  it('exports CSV with a header row and quoted commas', () => {
    const [head, row] = toCsv([lic(1, 'ACME, INC.', 'GAS')]).split('\n');
    expect(head.startsWith('Date,Licence,Event')).toBe(true);
    expect(row).toContain('"ACME, INC."');
  });
});
