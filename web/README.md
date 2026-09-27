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

## Deploy

Live at https://d157m2vmtz6y3j.cloudfront.net (CloudFront distribution `E2OWOTRIGM4VB1`, site bucket `wellspring-demo-sitebucket-qepuhrtijij0`, region ca-central-1). The build keeps `<base href="/">`; CloudFront maps 403 and 404 to `/index.html` with status 200, which is what keeps deep links working on refresh (see DECISIONS.md).

From the repository root, after `npm run build` in `web/` (the AWS wrapper reads the owner's credentials inside the process and never prints them):

    python3 scripts/aws_task.py s3 sync web/dist/web/browser s3://wellspring-demo-sitebucket-qepuhrtijij0 --cache-control 'public,max-age=31536000,immutable' --exclude index.html --only-show-errors
    python3 scripts/aws_task.py s3 cp web/dist/web/browser/index.html s3://wellspring-demo-sitebucket-qepuhrtijij0/index.html --cache-control no-cache --content-type text/html --only-show-errors
    python3 scripts/aws_task.py cloudfront create-invalidation --distribution-id E2OWOTRIGM4VB1 --paths '/*'

Hashed assets are immutable and kept (no `--delete`), so clients mid-session keep working during a rollout; only `index.html` is uncached. Screenshots of the live pages are in `../docs/screenshots/`.
