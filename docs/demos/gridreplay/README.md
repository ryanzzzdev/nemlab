# GridReplay static demo

`index.html` is a self-contained, no-backend preview of the GridReplay journey:
an event catalogue with filters, event cards carrying detector/coverage/
methodology metadata, and a replay view with a play/pause/scrub cursor
synchronised across four charts (price, scheduled demand, generation by
technology, regional flows). It embeds a seeded synthetic NSW1 generator —
series are illustrative, not Open Electricity data — and simplified detectors
(negative-price run, $1,000-threshold spike, provisional renewable share,
fallback demand ramp). It is a discussion aid, not the NEM-018 design.

Open `index.html` directly in a browser, or serve the directory:

```sh
python3 -m http.server 8899
# then open http://127.0.0.1:8899/
```

The "Open in BatteryLab" link navigates to the sibling `../batterylab/` demo;
the region/day parameters document the intended contract but that demo only
embeds its two validated fixture days.

## Tests

`data.test.js` extracts the embedded generator and detectors from `index.html`
and verifies series integrity, detector boundary/dedup behaviour and catalogue
event windows. It has no dependencies:

```sh
node data.test.js
```

`smoke.js` loads the page in jsdom and checks the catalogue, filters, empty
state, rendered charts, cursor wiring and the BatteryLab link:

```sh
npm install   # once — installs the pinned jsdom devDependency
node smoke.js
```
