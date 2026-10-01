# BatteryLab static demo

`index.html` is a self-contained, no-backend preview of the BatteryLab journey:
scenario form, simulated job lifecycle, fixed-schedule vs perfect-hindsight
comparison, synchronised charts, financial breakdown, methodology and share
links. It embeds the two validated NSW1 Open Electricity price fixtures and a
JavaScript port of the `battery-v1` engine (fixed schedule, exact ordered-window
hindsight with an evaluated dual bound, validation and accounting). It is a
visualisation aid, not the NEM-017 frontend.

Open `index.html` directly in a browser, or serve the directory:

```sh
python3 -m http.server 8899
# then open http://127.0.0.1:8899/
```

## Tests

`engine.test.js` extracts the embedded price table and engine from `index.html`
and verifies them against the contract reference fixtures, the source CSV
fixtures in `reference/java/core/src/test/resources/prices/`, and the published Java benchmark
margins. It has no dependencies:

```sh
node engine.test.js
```

`smoke.js` loads the page in jsdom and checks the job lifecycle, rendered
results, charts, validation failures and share-state handling:

```sh
npm install   # once — installs the pinned jsdom devDependency
node smoke.js
```
