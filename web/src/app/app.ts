import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './api/api.service';
import { AER_ST1_URL, REPO_URL } from './pages/about';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, DatePipe],
  templateUrl: './app.html',
})
export class App {
  readonly api = inject(ApiService);
  readonly repo = REPO_URL;
  readonly aer = AER_ST1_URL;
}
