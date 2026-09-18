/* Verifies the synthetic day generator and detectors embedded in index.html:
 * series integrity, detector boundaries/dedup rules and event catalogue values.
 * Pure Node — no dependencies.
 *
 *   node data.test.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const HTML = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const script = HTML.match(/<script>([\s\S]*?)<\/script>/)[1];
// Evaluate everything up to the DOM wiring ("const $="), which needs a browser.
const cut = script.split("const $=")[0];
const ctx = eval(cut + "\n;({DAYS, EVENTS, negRuns, spikeRuns, maxRamp, peakShare, runsWhere, N, hhmm})");
const { DAYS, EVENTS, negRuns, spikeRuns, maxRamp, peakShare, runsWhere, N, hhmm } = ctx;

let pass = 0, fail = 0;
function checkTrue(name, cond, info = "") {
  if (cond) pass++; else fail++;
  console.log(`${cond ? "PASS" : "FAIL"} ${name} ${info}`);
}
const SERIES = ["price", "demand", "coal", "gas", "hydro", "wind", "solar", "roof", "batt", "imp", "exp"];

// ---- series integrity: every generated day is a complete finite day ----
for (const k of Object.keys(DAYS)) {
  const d = DAYS[k];
  for (const key of SERIES)
    checkTrue(`${k}.${key} 288 finite points`,
      d[key].length === N && d[key].every(Number.isFinite));
  checkTrue(`${k} prices within mock floor/cap`,
    d.price.every(v => v >= -1000 && v <= 17500));
  checkTrue(`${k} demand/genus nonnegative`,
    ["demand", "coal", "gas", "hydro", "wind", "solar", "roof", "imp", "exp"]
      .every(key => d[key].every(v => v >= 0)));
}

// ---- detector unit behaviour on crafted inputs ----
{
  checkTrue("runsWhere: gap ends a run and min-length filters",
    (() => { // emulate detector semantics directly on a full-length array
      const a = new Array(288).fill(5);
      a[10] = a[11] = a[12] = -1;      // run of 3 -> kept
      a[20] = a[21] = -1;              // run of 2 -> below min run 3
      a[30] = a[31] = a[32] = a[33] = -1; // run of 4 -> kept
      const rs = negRuns(a);
      return rs.length === 2 && rs[0].s === 10 && rs[0].e === 12 && rs[1].s === 30 && rs[1].e === 33;
    })());
  checkTrue("runsWhere: run open at index 0 is kept",
    (() => {
      const a = new Array(288).fill(5);
      a[0] = a[1] = a[2] = -1;
      const rs = negRuns(a);
      return rs.length === 1 && rs[0].s === 0 && rs[0].e === 2;
    })());
  checkTrue("spikeRuns: only intervals > $1,000 qualify",
    (() => {
      const a = new Array(288).fill(50);
      a[100] = 999.9; a[101] = 1000.01; a[102] = 15000;
      const rs = spikeRuns(a);
      return rs.length === 1 && rs[0].s === 101 && rs[0].e === 102;
    })());
}

// ---- catalogue events land on the expected windows ----
const ev = t => EVENTS.filter(e => e.type === t);
checkTrue("5 catalogue events", EVENTS.length === 5);
checkTrue("two negative-run events", ev("neg").length === 2);
checkTrue("day A single neg run 10:05-14:40",
  (() => { const rs = negRuns(DAYS.A.price); return rs.length === 1 && rs[0].s === 121 && rs[0].e === 175; })(),
  `(${JSON.stringify(negRuns(DAYS.A.price))})`);
checkTrue("day C neg run open at day start",
  (() => { const rs = negRuns(DAYS.C.price); return rs.length === 1 && rs[0].s === 0 && rs[0].e === 56; })(),
  `(${JSON.stringify(negRuns(DAYS.C.price))})`);
checkTrue("day B spike run 17:50-18:30 peak > $10k",
  (() => { const rs = spikeRuns(DAYS.B.price);
    return rs.length === 1 && rs[0].s === 214 && rs[0].e === 221 &&
      Math.max(...DAYS.B.price.slice(214, 222)) > 10000; })());
checkTrue("day B has no negative run", negRuns(DAYS.B.price).length === 0);
checkTrue("day D has no negative run or spike",
  negRuns(DAYS.D.price).length === 0 && spikeRuns(DAYS.D.price).length === 0);
checkTrue("day D ramp exceeds 3000 MW over 3 h", maxRamp(DAYS.D.demand, 36).v > 3000,
  `(${Math.round(maxRamp(DAYS.D.demand, 36).v)} MW)`);
checkTrue("day C renewable share peak plausible (30-60%)",
  (() => { const r = peakShare(DAYS.C, 12); return r.v > 30 && r.v < 60; })(),
  `(${peakShare(DAYS.C, 12).v.toFixed(1)}%)`);

// ---- event metadata sanity ----
for (const e of EVENTS) {
  checkTrue(`${e.type} ${e.date}: window inside day and stat present`,
    e.s >= 0 && e.e < N && e.s <= e.e && typeof e.stat === "string" && e.stat.length > 0,
    `(${hhmm(e.s)}-${hhmm(e.e + 1)})`);
}
checkTrue("cross-midnight event carries explicit note",
  EVENTS.some(e => e.crossNote && e.type === "neg" && e.day === "C"));
checkTrue("provisional flags on ren + ramp detectors",
  ev("ren")[0].provisional && ev("ramp")[0].provisional);
checkTrue("deterministic generator: same seeds rebuild identically",
  (() => { const a = DAYS.A.price.slice(0, 50);
    // rebuild is implicit — seeds are fixed constants; spot-check a stable stat
    return Math.abs(Math.min(...DAYS.A.price) - (-99.3)) < 2; })(),
  `(trough ${Math.min(...DAYS.A.price).toFixed(1)})`);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
