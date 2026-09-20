# Linked-chart prototype — NEM-036

Date: 2026-09-20. Changes remain uncommitted.

## Implemented and verified

An optional, lazy-loaded chart on the stored-price page pairs real prices with a clearly
labelled synthetic energy trace. Both panels share interval selection and a full-day or
six-hour zoom window. Exact prices/gap states remain available as text and in the table.

- Clean locked npm installation, contract verification, formatting, strict TypeScript and
  production build pass. Installation reports zero known vulnerabilities at verification.
- `npm run check`: 40 desktop/mobile Chromium cases pass, including all earlier price
  and navigation cases plus chart checks.
- Tests compare both SVG cursor x positions, verify that zoom changes their geometry,
  inspect disconnected price paths, select negative/missing/source-null values, and
  check next-day midnight labels in Australia/Sydney on a daylight-saving transition day.
- Mouse movement and actual touchscreen taps work in either panel; keyboard range and
  native window controls work; 320-pixel resizing and hide/reopen lifecycle pass.
- Failed chart-chunk downloads show a safe message and leave the 288-row price table.
- `npm run test:live` passes two cases using the packaged Java API and disposable PostgreSQL.
  Both now open the charts and verify the paired cursor and exact readout.
- Desktop/mobile screenshots reviewed: panels align, synthetic labelling is prominent,
  controls wrap on mobile and the price table stays independently scrollable.

## Bundle and timing observations

| Asset | Minified | gzip |
| --- | --- | --- |
| Main application JS | 311.88 kB | 98.64 kB |
| Optional chart JS | 518.76 kB | 176.64 kB |
| CSS | 4.03 kB | 1.47 kB |

The chart import is absent from network requests until the visitor asks to show it.
Removing the unused slider component reduced the chart chunk from 533.81 kB to 518.76 kB;
the default size warning remains visible and is accepted for this optional proof.

A dedicated measurement rerun recorded first ECharts init-to-finished durations of
78.4 ms (desktop viewport) and 82.6 ms (mobile emulation), both below the 2-second smoke
guard. Measurements exclude chunk download/parse and are single local Chromium samples,
not physical-phone, slow-network or sustained interaction benchmarks. They do not justify
claims about larger datasets or launch performance. SVG uses 288 samples per panel.

## Scope and next work

No battery dispatch/model output is fabricated. The synthetic trace is only a chart
interaction aid. Free-form drag/pinch chart zoom and automatic animation are not enabled;
users choose shared windows with native controls. Cross-browser and full assistive-tech
validation remain launch/product work. Backend Java code was unchanged.

NEM-015's scoped frontend slices are complete. Review the broader M3 exit evidence before
closing that milestone and starting M4. Hosted CI has not run; local checks and configured
workflows must not be represented as a hosted run. See [decision 014](../../decisions/014-linked-chart-prototype.md).
