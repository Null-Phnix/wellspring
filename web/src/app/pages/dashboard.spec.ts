import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ApiService } from '../api/api.service';
import { Coverage, DataMeta } from '../api/types';
import { DashboardPage, clipRange, coverageCells, dateRange, summarise } from './dashboard';

const coverage: Coverage = {
  reports_loaded: 3, loaded_dates: ['2026-09-01', '2026-09-02', '2026-09-03'], empty_dates: ['2026-09-02'],
  failed_dates: ['2026-09-04'], missing_dates: ['2026-09-05'], parse_issue_count: 1,
};
const meta = (c: Coverage | null): DataMeta => ({ schema_version: 1, data_as_of: '2026-09-27T05:42:56Z', date_from: '2026-09-01', date_to: '2026-09-06', event_type: 'issued', coverage: c });

describe('dashboard helpers', () => {
  it('dateRange is inclusive and clipped to a year', () => {
    expect(dateRange('2026-09-01', '2026-09-03')).toEqual(['2026-09-01', '2026-09-02', '2026-09-03']);
    expect(dateRange('2020-01-01', '2026-09-03').length).toBe(366);
  });

  it('clipRange orders the window and keeps only its last year', () => {
    expect(clipRange('2026-09-06', '2026-09-01')).toEqual({ date_from: '2026-09-01', date_to: '2026-09-06' });
    expect(clipRange('2020-01-01', '2026-09-03')).toEqual({ date_from: '2025-09-03', date_to: '2026-09-03' });
    expect(clipRange('2026-01-01', '2026-09-03')).toEqual({ date_from: '2026-01-01', date_to: '2026-09-03' });
  });

  it('coverageCells classifies every date and falls back to counted dates', () => {
    const cells = coverageCells(coverage, dateRange('2026-09-01', '2026-09-06'), new Set(['2026-09-06']));
    expect(cells.map(c => c.status)).toEqual(['loaded', 'empty', 'loaded', 'failed', 'missing', 'loaded']);
    expect(coverageCells(null, ['2026-09-01'], new Set()).map(c => c.status)).toEqual(['unknown']);
  });

  it('summarise counts statuses in plain words', () => {
    const cells = coverageCells(coverage, dateRange('2026-09-01', '2026-09-07'), new Set());
    expect(summarise(cells)).toBe('3 daily lists loaded (1 with no licences), 1 failed, 1 missing, 2 not published yet.');
  });
});

describe('DashboardPage', () => {
  it('draws bars that link to the day, a coverage strip, and links for every slice, for a fixed window from the URL', async () => {
    const stats = (items: unknown[]) => Promise.resolve({ items, meta: meta(coverage) });
    const paramMap = convertToParamMap({ date_from: '2026-09-01', date_to: '2026-09-06' });
    const asked: unknown[] = [];
    await TestBed.configureTestingModule({
      imports: [DashboardPage],
      providers: [provideRouter([]), { provide: ActivatedRoute, useValue: { queryParamMap: of(paramMap), snapshot: { queryParamMap: paramMap } } }, { provide: ApiService, useValue: {
        daily: (q: unknown) => { asked.push(q); return stats([{ date: '2026-09-01', count: 4 }, { date: '2026-09-03', count: 2 }]); },
        topLicensees: () => stats([{ licensee: 'CENOVUS ENERGY INC.', count: 3 }, { licensee: null, count: 1 }]),
        topFormations: () => stats([{ terminating_zone: 'MCMURRAY FM', count: 2 }]),
        substances: () => stats([{ substance: 'GAS', count: 6 }]),
      } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(DashboardPage);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const bars = el.querySelectorAll('.bars a.bar');
    expect(bars.length).toBe(2);
    expect(bars[0].getAttribute('href')).toContain('date_from=2026-09-01');
    expect(bars[0].getAttribute('href')).toContain('event_type=issued');
    expect(asked[0]).toMatchObject({ date_from: '2026-09-01', date_to: '2026-09-06', event_type: 'issued' });
    expect(el.querySelector('.bars .gap.failed')).not.toBeNull();
    expect(el.querySelector('.strip')?.children.length).toBe(6);
    expect(el.textContent).toContain('3 daily lists loaded (1 with no licences), 1 failed, 1 missing, 1 not published yet.');
    expect(el.textContent).toContain('2026-09-04: daily list failed to load');
    const links = [...el.querySelectorAll('.cols a')].map(a => a.getAttribute('href'));
    expect(links.some(h => h?.includes('licensee=CENOVUS'))).toBe(true);
    expect(links.some(h => h?.includes('terminating_zone=MCMURRAY'))).toBe(true);
    expect(links.some(h => h?.includes('substance=GAS'))).toBe(true);
    expect(el.textContent).toContain('(unknown)');
  });
});
