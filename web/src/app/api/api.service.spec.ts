import { normaliseAsk, pageAll } from './api.service';
import { Page } from './types';

const META = { schema_version: 1 as const, data_as_of: null, date_from: null, date_to: null, event_type: 'issued', coverage: null };

describe('pageAll', () => {
  const server = (total: number, page_size: number) => {
    const pages: number[] = [];
    const fetch = async (page: number): Promise<Page<number>> => {
      pages.push(page);
      const start = (page - 1) * page_size;
      return { items: Array.from({ length: Math.min(page_size, total - start) }, (_, i) => start + i), total, page, page_size, meta: META };
    };
    return { fetch, pages };
  };

  it('pages through everything when under the cap', async () => {
    const s = server(450, 200);
    const r = await pageAll(s.fetch, 2000);
    expect(r).toMatchObject({ total: 450, capped: false });
    expect(r.items.length).toBe(450);
    expect(s.pages).toEqual([1, 2, 3]);
  });

  it('stops at the cap and says so', async () => {
    const s = server(450, 200);
    const r = await pageAll(s.fetch, 300);
    expect(r).toMatchObject({ total: 450, capped: true });
    expect(r.items.length).toBe(300);
    expect(s.pages).toEqual([1, 2]);
  });
});

describe('normaliseAsk', () => {
  it('passes the contract body through', () => {
    const refused = { status: 'refused', columns: [], rows: [], sql: null, row_limit: 200, truncated: false, refusal: { code: 'ASK_UNAVAILABLE', message: 'no' }, meta: META };
    expect(normaliseAsk(refused)).toBe(refused);
  });

  it('accepts the M4 success body Anubis described', () => {
    const r = normaliseAsk({ sql: 'SELECT 1', rows: [{ licensee: 'A', n: 2 }], row_count: 1, truncated: false, model: 'm' });
    expect(r.status).toBe('ok');
    if (r.status === 'ok') {
      expect(r.columns).toEqual(['licensee', 'n']);
      expect(r.model).toBe('m');
      expect(r.row_limit).toBe(200);
    }
  });

  it('treats any body with a refusal as refused', () => {
    const r = normaliseAsk({ refusal: { code: 'READ_ONLY_REQUIRED', message: 'x' }, rows: [] });
    expect(r.status).toBe('refused');
  });
});
