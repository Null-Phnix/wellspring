# Wellspring web

Angular 22 front end for Wellspring (docs/SPEC.md section 4). Standalone components, strict TypeScript, zoneless, vitest.

## Run

    npm install
    npm start        # http://localhost:4200, mocked data (see below)
    npm test         # unit tests through the Angular CLI
    npm run build    # dist/web/browser, static files for S3 + CloudFront

## API base URL and mocks

`src/environments/environment.ts` holds `apiBase` and `mock`. With `mock: true` (development), `ApiService` answers from `src/app/api/mock-data.ts`, a replay of records from `fixtures/WELLS0925.TXT` across the last 90 business days. `environment.prod.ts` swaps in on `ng build`; set its `apiBase` to the Lambda function URL once M2 lands.

The response shapes the app expects live in `src/app/api/types.ts` and mirror the v1 contract on issue #1 (comment 109). Change the contract on #1 first, then `types.ts` and `mock-data.ts`.

## Pages

- Dashboard: licences per day, substance mix, top 10 licensees, top 10 target formations, 7/30/90 day window.
- Licences: filters (date range, licensee, substance, field centre, terminating zone, well type), sortable table, CSV export, paging.
- Map: Leaflet, surface locations coloured by substance, popup per record, positions labelled approximate.
- Ask: plain-English question, the SQL the model wrote, rows or the refusal.

## Deploy notes

Angular routes are client-side. CloudFront needs custom error responses mapping 403 and 404 to `/index.html` with status 200 (Tenjin's template). Upload the contents of `dist/web/browser`.
