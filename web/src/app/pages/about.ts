import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

export const REPO_URL = 'https://github.com/Null-Phnix/wellspring';
export const AER_ST1_URL = 'https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st1';

@Component({
  selector: 'app-about',
  imports: [RouterLink],
  template: `
    <h1>About Wellspring</h1>
    <p>
      Wellspring is a small public explorer for Alberta well licences: which licences the Alberta Energy Regulator
      issued each day, to whom, for what, and roughly where. It is a portfolio project, not a product.
    </p>

    <h2>How this was built</h2>
    <p>
      Josii directed Wellspring and reviewed its changes in Scriptorium. Tenjin and Nabu are AI coding agents: Tenjin
      implemented ingestion, the API and AWS setup; Nabu implemented the Angular app. The work used automated reviews,
      tests and runtime checks, with evidence and limitations recorded alongside each milestone. Data comes from the
      Alberta Energy Regulator's public ST1 Well Licences Issued Daily reports. Map positions are approximate, derived
      from legal land descriptions with the township grid method.
    </p>

    <h2>The pages</h2>
    <ul>
      <li><a routerLink="/">Dashboard</a>: licences issued per day for a window, the substance mix, the top licensees and target formations, and which daily lists are behind the numbers.</li>
      <li><a routerLink="/licences">Licences</a>: every event with filters, sorting, paging, the full record per row, and a CSV export of the current filter.</li>
      <li><a routerLink="/map">Map</a>: approximate surface positions for the current filter, coloured by substance.</li>
      <li><a routerLink="/ask">Ask</a>: a plain-English question answered with a read-only SQL query the server writes and shows.</li>
    </ul>

    <h2>Data and its limits</h2>
    <p>
      Source: <a [href]="aer" rel="noopener">AER ST1, Well Licences Issued Daily List</a>, public data, attributed to the
      Alberta Energy Regulator. The daily lists are fetched once a day; days the source did not publish, or that failed
      to load, are shown as gaps, never as zeros. Positions come from the township grid method and are accurate to
      roughly a section (about 1.6 km); they are unsuitable for navigation, land decisions or measurement.
    </p>
    <p>Source code: <a [href]="repo" rel="noopener">{{ repo }}</a>.</p>
  `,
})
export class AboutPage {
  readonly repo = REPO_URL;
  readonly aer = AER_ST1_URL;
}
