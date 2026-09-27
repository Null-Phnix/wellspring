import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ApiService } from './api/api.service';
import { App } from './app';
import { signal } from '@angular/core';

describe('App', () => {
  it('renders the shell with the five pages, the AER attribution, data as of and the repo link', async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), { provide: ApiService, useValue: { dataAsOf: signal('2026-09-27T13:00:46Z'), substances: () => Promise.resolve({ items: [], meta: null }) } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('nav a').length).toBe(5);
    const footer = el.querySelector('footer')?.textContent ?? '';
    expect(footer).toContain('Alberta Energy Regulator, ST1 Well Licences Issued Daily');
    expect(footer).toContain('Data as of 2026-09-27 13:00 UTC');
    expect(el.querySelector('footer a[href*="github.com/Null-Phnix/wellspring"]')).not.toBeNull();
  });
});
