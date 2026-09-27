import { Component, inject, signal } from '@angular/core';
import { ApiService } from '../api/api.service';
import { AskResponse } from '../api/types';

@Component({
  selector: 'app-ask',
  template: `
    <h1>Ask</h1>
    <p class="muted">
      Ask a plain-English question about Alberta well licences. The model writes a read-only SQL query, runs it with
      a row limit, and the SQL is shown so you can check it. Anything that is not a single SELECT is refused.
    </p>
    <form (submit)="submit($event)">
      <textarea name="question" rows="3" required
                placeholder="Which licensees were issued the most gas well licences in the last 30 days?"></textarea>
      <button [disabled]="busy()">{{ busy() ? 'Asking…' : 'Ask' }}</button>
    </form>
    @if (answer(); as a) {
      @if (a.status === 'ok') {
        <h2>SQL</h2>
        <pre><code>{{ a.sql }}</code></pre>
        <h2>Rows</h2>
        <table>
          <thead><tr>@for (c of a.columns; track c) { <th scope="col">{{ c }}</th> }</tr></thead>
          <tbody>
            @for (row of a.rows; track $index) {
              <tr>@for (c of a.columns; track c) { <td>{{ row[c] }}</td> }</tr>
            } @empty {
              <tr><td [attr.colspan]="a.columns.length || 1">No rows.</td></tr>
            }
          </tbody>
        </table>
        @if (a.truncated) { <p class="muted">Showing the first {{ a.row_limit }} rows.</p> }
      } @else {
        <p class="error">Refused ({{ a.refusal.code }}): {{ a.refusal.message }}</p>
      }
    } @else if (error()) {
      <p class="error">{{ error() }}</p>
    }
  `,
})
export class AskPage {
  private readonly api = inject(ApiService);
  readonly answer = signal<AskResponse | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);

  async submit(ev: Event): Promise<void> {
    ev.preventDefault();
    const question = String(new FormData(ev.target as HTMLFormElement).get('question') ?? '').trim();
    if (!question) return;
    this.busy.set(true);
    this.error.set('');
    this.answer.set(null);
    try {
      this.answer.set(await this.api.ask(question));
    } catch {
      this.error.set('The question could not be answered right now.');
    } finally {
      this.busy.set(false);
    }
  }
}
