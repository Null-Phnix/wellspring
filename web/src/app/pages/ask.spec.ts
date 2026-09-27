import { TestBed } from '@angular/core/testing';
import { ApiService } from '../api/api.service';
import { AskResponse } from '../api/types';
import { AskPage } from './ask';

describe('AskPage', () => {
  let resolve!: (r: AskResponse) => void;
  let reject!: (e: unknown) => void;
  let asked: string[];

  async function render() {
    asked = [];
    await TestBed.configureTestingModule({
      imports: [AskPage],
      providers: [{ provide: ApiService, useValue: { ask: (q: string) => { asked.push(q); return new Promise<AskResponse>((res, rej) => { resolve = res; reject = rej; }); } } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(AskPage);
    await fixture.whenStable();
    return fixture;
  }
  const settle = async (fixture: { whenStable(): Promise<unknown>; detectChanges(): void }) => { await Promise.resolve(); fixture.detectChanges(); await fixture.whenStable(); };

  it('shows a loading state while the server thinks, then the SQL and rows', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('button.chip') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(asked.length).toBe(1);
    expect(el.textContent).toContain('Asking the server');
    resolve({ status: 'ok', columns: ['licensee', 'n'], rows: [{ licensee: 'CENOVUS ENERGY INC.', n: 99 }], sql: 'SELECT licensee, COUNT(*) AS n FROM licence_events', row_limit: 200, truncated: true, refusal: null, meta: null, model: 'small' });
    await settle(fixture);
    expect(el.querySelector('pre code')?.textContent).toContain('SELECT licensee');
    expect(el.querySelectorAll('tbody tr').length).toBe(1);
    expect(el.querySelector('.badge')?.textContent).toContain('truncated at 200');
    expect(el.textContent).toContain('answered by small');
  });

  it('renders ASK_UNAVAILABLE as a calm notice with the message verbatim', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('textarea') as HTMLTextAreaElement).value = 'anything';
    el.querySelector('form')!.requestSubmit();
    resolve({ status: 'refused', columns: [], rows: [], sql: null, row_limit: 200, truncated: false, refusal: { code: 'ASK_UNAVAILABLE', message: 'Question answering is not available in this release.' }, meta: null });
    await settle(fixture);
    expect(el.querySelector('.notice')?.textContent).toContain('Question answering is not available in this release.');
    expect(el.querySelector('.error')).toBeNull();
  });

  it('renders any other refusal as an error with the code and message', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('button.chip') as HTMLButtonElement).click();
    resolve({ status: 'refused', columns: [], rows: [], sql: null, row_limit: 200, truncated: false, refusal: { code: 'READ_ONLY_REQUIRED', message: 'Only read-only questions.' }, meta: null });
    await settle(fixture);
    expect(el.querySelector('.error')?.textContent).toContain('READ_ONLY_REQUIRED');
    expect(el.querySelector('.error')?.textContent).toContain('Only read-only questions.');
  });

  it('reports a failed request without pretending it was refused', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('button.chip') as HTMLButtonElement).click();
    reject(new Error('network'));
    await settle(fixture);
    expect(el.querySelector('.error')?.textContent).toContain('could not be sent');
  });
});
