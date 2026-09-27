import { Component, inject, signal, viewChild, ElementRef } from '@angular/core';
import { ApiService } from '../api/api.service';
import { AskResponse } from '../api/types';

export const EXAMPLES = [
  'Which licensees were issued the most licences in the last 30 days?',
  'How many gas well licences were issued in September, by field centre?',
  'Which target formations appear most often this month?',
];

@Component({
  selector: 'app-ask',
  template: `
    <h1>Ask</h1>
    <p class="muted">
      Ask a plain-English question about Alberta well licences. The server writes a read-only SQL query, runs it with
      a row limit, and shows the SQL so you can check it. Anything that is not a single SELECT is refused.
    </p>
    <p class="chips" role="group" aria-label="Example questions">
      @for (q of examples; track q) { <button type="button" class="chip" (click)="ask(q)">{{ q }}</button> }
    </p>
    <form (submit)="submit($event)">
      <textarea #box name="question" rows="3" required [placeholder]="examples[0]"></textarea>
      <button [disabled]="busy()">{{ busy() ? 'Asking…' : 'Ask' }}</button>
    </form>

    @if (busy()) {
      <p class="muted" role="status" aria-live="polite">Asking the server…</p>
    } @else if (answer(); as a) {
      @if (a.status === 'ok') {
        <h2>SQL</h2>
        <pre><code>{{ a.sql }}</code></pre>
        <h2>
          Rows
          @if (a.truncated) { <span class="badge">truncated at {{ a.row_limit }} rows</span> }
          @if (a.model) { <span class="muted">answered by {{ a.model }}</span> }
        </h2>
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
      } @else if (a.refusal.code === 'ASK_UNAVAILABLE') {
        <p class="notice" role="status">{{ a.refusal.message }} This part of Wellspring is not switched on yet; the rest of the site works without it.</p>
      } @else {
        <p class="error" role="alert">The server refused this question ({{ a.refusal.code }}): {{ a.refusal.message }}</p>
      }
    } @else if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }
  `,
})
export class AskPage {
  private readonly api = inject(ApiService);
  private readonly box = viewChild.required<ElementRef<HTMLTextAreaElement>>('box');
  readonly examples = EXAMPLES;
  readonly answer = signal<AskResponse | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);

  submit(ev: Event): void {
    ev.preventDefault();
    void this.ask(String(new FormData(ev.target as HTMLFormElement).get('question') ?? ''));
  }

  async ask(question: string): Promise<void> {
    question = question.trim();
    if (!question || this.busy()) return;
    this.box().nativeElement.value = question;
    this.busy.set(true);
    this.error.set('');
    this.answer.set(null);
    try {
      this.answer.set(await this.api.ask(question));
    } catch {
      this.error.set('The question could not be sent right now. Try again in a moment.');
    } finally {
      this.busy.set(false);
    }
  }
}
