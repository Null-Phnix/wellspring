import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
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
  source: { url: 'https://static.aer.ca/prd/data/well-lic/WELLS0925.TXT', sha256: '', retrieved_at: '2026-09-27T00:00:00Z', parser_version: 'test' },
});
const META = { schema_version: 1 as const, data_as_of: null, date_from: null, date_to: null, event_type: 'issued',
  coverage: { reports_loaded: 1, missing_dates: [], failed_dates: [], parse_issue_count: 0 } };
const page = (total: number): LicencePage => ({
  items: [lic(1, 'CNRL', 'GAS'), lic(2, 'ARC', 'CRUDE OIL'), lic(3, 'IMPERIAL', 'CRUDE BITUMEN')], total, page: 1, page_size: 50, meta: META,
});

describe('LicencesPage', () => {
  const calls: LicenceQuery[] = [];

  async function render(total = 3) {
    calls.length = 0;
    await TestBed.configureTestingModule({
      imports: [LicencesPage],
      providers: [provideRouter([]), { provide: ApiService, useValue: { licences: async (q: LicenceQuery) => { calls.push(q); return { ...page(total), page: q.page ?? 1 }; } } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(LicencesPage);
    await fixture.whenStable();
    return fixture;
  }
  const column = (el: HTMLElement, i: number) =>
    [...el.querySelectorAll('tbody tr:not(.detail)')].map(tr => tr.children[i].textContent?.trim());

  it('renders one row per event with the DLS formatted and asks for the default query', async () => {
    const el = (await render()).nativeElement as HTMLElement;
    expect(el.querySelectorAll('tbody tr').length).toBe(3);
    expect(column(el, 5)).toEqual(['CNRL', 'ARC', 'IMPERIAL']);
    expect(column(el, 10)[0]).toBe('04-10-085-17 W5M');
    expect(calls[0]).toMatchObject({ event_type: 'issued', sort: 'report_date', order: 'desc', page: 1, page_size: 50 });
  });

  it('sorts server-side through the URL on header click and flips on the second click', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    const header = () => [...el.querySelectorAll('th button.sort')].find(b => b.textContent?.includes('Licensee')) as HTMLButtonElement;
    header().click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ sort: 'licensee', order: 'asc', page: 1 });
    header().click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ sort: 'licensee', order: 'desc' });
    expect(header().closest('th')?.getAttribute('aria-sort')).toBe('descending');
  });

  it('maps the filter form to query params', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('input[name=licensee]') as HTMLInputElement).value = 'cnrl';
    (el.querySelector('select[name=event_type]') as HTMLSelectElement).value = 'all';
    el.querySelector('form')!.requestSubmit();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ licensee: 'cnrl', event_type: 'all', page: 1 });
  });

  it('pages through the URL', async () => {
    const fixture = await render(120);
    const el = fixture.nativeElement as HTMLElement;
    const button = (label: string) => [...el.querySelectorAll('nav.pager button')].find(b => b.textContent?.trim() === label) as HTMLButtonElement;
    expect(el.querySelector('nav.pager span')?.textContent).toContain('of 3');
    button('Next').click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ page: 2 });
    button('Previous').click();
    await fixture.whenStable();
    expect(calls.at(-1)).toMatchObject({ page: 1 });
  });

  it('expands a row to the full record with the location reason and source report date', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('button.expand') as HTMLButtonElement).click();
    await fixture.whenStable();
    const detail = el.querySelector('tr.detail')?.textContent ?? '';
    expect(detail).toContain('not_yet_converted');
    expect(detail).toContain('Source report date');
    expect(detail).toContain('2026-09-21');
    expect(el.querySelector('button.expand')?.getAttribute('aria-expanded')).toBe('true');
  });

  it('assembles CSV with a header row, extra columns and quoted commas', () => {
    const [head, row] = toCsv([lic(1, 'ACME, INC.', 'GAS')]).split('\n');
    expect(head.startsWith('Date,Licence,Event')).toBe(true);
    expect(head).toContain('Location reason');
    expect(row).toContain('"ACME, INC."');
    expect(row.endsWith(',not_yet_converted')).toBe(true);
  });
});
