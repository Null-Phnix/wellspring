import { defaultQuery, filtersOf, paramsFor, queryFromParams } from './filters';

describe('URL filter state', () => {
  const params = (o: Record<string, string>) => (k: string) => o[k] ?? null;

  it('fills defaults and keeps valid values from the URL', () => {
    const q = queryFromParams(params({ licensee: 'cenovus', event_type: 'all', sort: 'licensee', order: 'asc', page: '3', date_from: '2026-09-01' }));
    expect(q).toMatchObject({ licensee: 'cenovus', event_type: 'all', sort: 'licensee', order: 'asc', page: 3, date_from: '2026-09-01' });
    expect(q.date_to).toBe(defaultQuery().date_to);
  });

  it('ignores values the contract would reject', () => {
    const q = queryFromParams(params({ sort: 'DROP TABLE', order: 'sideways', event_type: 'bogus', page: '-4' }));
    expect(q).toMatchObject({ sort: 'report_date', order: 'desc', event_type: 'issued', page: 1 });
  });

  it('round-trips through params and drops page 1', () => {
    const q = { ...defaultQuery(), licensee: 'arc', page: 1, sort: 'substance' as const };
    const p = paramsFor(q);
    expect(p['page']).toBeUndefined();
    expect(p['licensee']).toBe('arc');
    expect(queryFromParams(params(p))).toEqual(q);
  });

  it('filtersOf keeps only the filter keys', () => {
    expect(filtersOf({ licensee: 'x', sort: 'licensee', page: 2, page_size: 50 })).toEqual({ licensee: 'x' });
  });
});
