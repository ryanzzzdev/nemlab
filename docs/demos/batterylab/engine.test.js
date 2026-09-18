/* Verifies the battery-v1 engine port embedded in index.html against the
 * contract reference fixtures, the source CSV price fixtures and the published
 * Java benchmark margins. Pure Node — no dependencies.
 *
 *   node engine.test.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const HTML = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
// Extract the embedded PRICES table and ENGINE IIFE exactly as shipped.
const pricesSrc = HTML.slice(HTML.indexOf("const PRICES"), HTML.indexOf(";", HTML.indexOf("const PRICES")) + 1);
const engineSrc = HTML.slice(HTML.indexOf("const ENGINE"), HTML.indexOf("// ---------------- UI"));
const PRICES = eval(pricesSrc + "\n;PRICES");
const ENGINE = eval(engineSrc + "\n;ENGINE");

let pass = 0, fail = 0;
function check(name, actual, expected, tol = 1e-6) {
  const ok = Math.abs(actual - expected) <= tol;
  if (ok) pass++; else fail++;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}: got ${actual}, want ${expected}`);
}
function checkTrue(name, cond, info = "") {
  if (cond) pass++; else fail++;
  console.log(`${cond ? "PASS" : "FAIL"} ${name} ${info}`);
}

// ---- embedded price data must equal the checked-in CSV fixtures ----
function loadDay(day) {
  const p = path.join(__dirname, "..", "..", "..", "core", "src", "test", "resources", "prices", `${day}.csv`);
  return fs.readFileSync(p, "utf8").trim().split("\n").slice(1).map(l => +l.split(",")[1]);
}
for (const day of ["2023-09-11", "2026-09-11"]) {
  const csv = loadDay(day);
  checkTrue(`embedded ${day} = CSV fixture (${csv.length} points)`,
    PRICES[day] && PRICES[day].length === 288 && PRICES[day].every((v, i) => v === csv[i]));
}

// ---- contract reference fixtures: two adjacent intervals ----
function fixture({ capacity = 1, eMin = 0, eMax = 1, eInit = 0, chargeMW = 12, dischargeMW = 12,
                   importLimit = 12, exportLimit = 12, etaC = 1, etaD = 1,
                   importFee = 0, exportFee = 0, degradation = 0, prices }) {
  return { capacity, eMin, eMax, eInit, chargeMW, dischargeMW, importLimit, exportLimit,
    efficiencyMode: "legs", etaC, etaD, importFee, exportFee, degradation,
    chargeStart: 0, chargeEnd: 1, dischargeStart: 1, dischargeEnd: 2,
    intervals: prices.length, prices };
}

let r = ENGINE.run(fixture({ prices: [-30, 200] }));
check("neg purchase fixed margin", r.fixed.accounting.margin, 230);
check("neg purchase hindsight margin", r.hindsight.accounting.margin, 230);
checkTrue("neg purchase OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ etaD: .9, importFee: 2, exportFee: 2, degradation: 10, prices: [-30, 200] }));
check("losses+costs fixed margin", r.fixed.accounting.margin, 197.2);
check("losses+costs hindsight margin", r.hindsight.accounting.margin, 197.2);
check("losses MWh", r.fixed.accounting.lossesMWh, 0.1);
checkTrue("losses OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ prices: [100, 10] }));
check("losing fixed margin", r.fixed.accounting.margin, -90);
check("losing hindsight margin", r.hindsight.accounting.margin, 0);
checkTrue("losing OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ exportLimit: 6, prices: [0, 100] }));
check("export limit fixed margin", r.fixed.accounting.margin, 50);
check("export limit hindsight margin", r.hindsight.accounting.margin, 50);
check("export limit Q", r.fixed.dispatch.intervals.c[0], 0.5);

r = ENGINE.run(fixture({ eInit: 1, eMax: 1, prices: [0, 100] }));
check("no headroom fixed margin", r.fixed.accounting.margin, 0);
check("no headroom hindsight margin", r.hindsight.accounting.margin, 0);
checkTrue("no headroom OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ prices: [0, 0] }));
check("zero prices fixed margin", r.fixed.accounting.margin, 0);
check("zero prices hindsight margin", r.hindsight.accounting.margin, 0);
checkTrue("zero prices OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ chargeMW: 0, prices: [-30, 200] }));
check("disabled import fixed margin", r.fixed.accounting.margin, 0);
check("disabled import hindsight margin", r.hindsight.accounting.margin, 0);
checkTrue("disabled import OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(fixture({ prices: [-30, -10] }));
check("negative sale fixed margin", r.fixed.accounting.margin, 20);

// ---- real NSW1 days vs published Java benchmark margins ----
// standard site: 1 MW/2 MWh, r=.9, fees 2/2, degradation 10, 10:00-14:00/17:00-21:00
function realInput(prices) {
  return { capacity: 2, eMin: 0, eMax: 2, eInit: 0, chargeMW: 1, dischargeMW: 1,
           importLimit: 1, exportLimit: 1, efficiencyMode: "roundTrip", roundTrip: .9,
           importFee: 2, exportFee: 2, degradation: 10,
           chargeStart: 120, chargeEnd: 168, dischargeStart: 204, dischargeEnd: 252,
           intervals: 288, prices };
}

r = ENGINE.run(realInput(PRICES["2026-09-11"]));
check("NSW1 2026-09-11 fixed margin", r.fixed.accounting.margin, 54.949676);
check("NSW1 2026-09-11 hindsight margin", r.hindsight.accounting.margin, 91.472558);
checkTrue("NSW1 2026 OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

r = ENGINE.run(realInput(PRICES["2023-09-11"]));
check("NSW1 2023-09-11 fixed margin", r.fixed.accounting.margin, 437.258414);
check("NSW1 2023-09-11 hindsight margin", r.hindsight.accounting.margin, 479.141462);
checkTrue("NSW1 2023 OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

const big = realInput(PRICES["2023-09-11"]);
for (const k of ["capacity", "eMax", "chargeMW", "dischargeMW", "importLimit", "exportLimit"]) big[k] *= 100;
r = ENGINE.run(big);
check("large site hindsight margin", r.hindsight.accounting.margin, 47914.146176, 1e-3);
checkTrue("large site OPTIMAL", r.hindsight.status === "OPTIMAL", `(gap=${r.hindsight.absoluteGap})`);

// ---- seeded invariants: certified optimal and never worse than the baseline ----
let seed = 42;
const rand = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
let invFail = 0;
for (let t = 0; t < 200; t++) {
  const inp = {
    capacity: 0.5 + rand() * 50, chargeMW: rand() * 20, dischargeMW: rand() * 20,
    importLimit: rand() * 20, exportLimit: rand() * 20,
    eMin: 0, efficiencyMode: "roundTrip", roundTrip: .6 + rand() * .4,
    importFee: rand() * 5, exportFee: rand() * 5, degradation: rand() * 15,
    chargeStart: Math.floor(rand() * 100), intervals: 288,
    prices: Array.from({ length: 288 }, () => rand() * 400 - 100)
  };
  inp.eMax = inp.capacity; inp.eInit = rand() * inp.eMax;
  inp.chargeEnd = inp.chargeStart + 1 + Math.floor(rand() * (140 - inp.chargeStart));
  inp.dischargeStart = inp.chargeEnd + Math.floor(rand() * 50);
  inp.dischargeEnd = Math.min(288, inp.dischargeStart + 1 + Math.floor(rand() * 200));
  const res = ENGINE.run(inp);
  if (res.errors) { console.log("unexpected validation error", res.errors); invFail++; break; }
  if (res.hindsight.status !== "OPTIMAL") { console.log(`seeded ${t}: status=${res.hindsight.status} gap=${res.hindsight.absoluteGap}`); invFail++; }
  else if (res.hindsight.accounting.margin < res.fixed.accounting.margin - 0.01 - 1e-6) { console.log(`seeded ${t}: hindsight < fixed`); invFail++; }
}
checkTrue("200 seeded scenarios: all OPTIMAL and hindsight >= fixed", invFail === 0, `(${invFail} failures)`);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
