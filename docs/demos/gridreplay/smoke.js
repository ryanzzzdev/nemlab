/* DOM smoke test for index.html using jsdom: loads the page, checks the
 * rendered catalogue, filters, empty state, replay charts, cursor wiring and
 * the BatteryLab navigation link.
 *
 *   npm install   # once — installs the pinned jsdom devDependency
 *   node smoke.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

let JSDOM;
try { ({ JSDOM } = require("jsdom")); }
catch {
  console.log("jsdom not installed — run `npm install` in this directory first. Skipping.");
  process.exit(0);
}

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  resources: "usable",
  beforeParse(window) { window.Element.prototype.scrollIntoView = () => {}; }
});
const { window } = dom;
const { document } = window;
const $ = id => document.getElementById(id);

let pass = 0, fail = 0;
const ok = (name, cond, info = "") => {
  if (cond) pass++; else fail++;
  console.log(`${cond ? "PASS" : "FAIL"} ${name} ${info}`);
};

setTimeout(() => {
  try {
    // ---- catalogue renders ----
    const cards = () => document.querySelectorAll("#cards .card");
    ok("5 catalogue cards", cards().length === 5, `(${cards().length})`);
    ok("empty state hidden", $("empty").hidden);
    ok("replay hidden until selection", $("replay").hidden);

    // ---- filters ----
    $("f-type").value = "spike";
    $("f-type").dispatchEvent(new window.Event("change"));
    ok("spike filter -> 1 card", cards().length === 1);
    $("f-type").value = "neg";
    $("f-type").dispatchEvent(new window.Event("change"));
    ok("neg filter -> 2 cards", cards().length === 2);
    $("f-region").value = "QLD1";
    $("f-region").dispatchEvent(new window.Event("change"));
    ok("unsupported region -> empty state", !$("empty").hidden && cards().length === 0);
    $("f-region").value = "NSW1"; $("f-type").value = "all";
    $("f-region").dispatchEvent(new window.Event("change"));
    $("f-type").dispatchEvent(new window.Event("change"));
    ok("reset -> 5 cards", cards().length === 5);

    // ---- open a replay (first card = day A negative run) ----
    cards()[0].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    ok("replay visible", !$("replay").hidden);
    ok("title set", $("rp-title").textContent.includes("Negative-price run"));
    ok("meta names NSW1 + AEST window",
      $("rp-meta").textContent.includes("NSW1") && $("rp-meta").textContent.includes("AEST"));
    const href = $("rp-batt").getAttribute("href");
    ok("BatteryLab link contract", href.includes("../batterylab/") && href.includes("day=2025-10-12"),
      `(${href})`);
    for (const n of ["price", "demand", "gen", "flow"])
      ok(`${n} chart drawn`, $("s-" + n).querySelectorAll("path").length > 0);
    ok("event band highlighted", document.querySelectorAll("rect.evband").length === 4);
    ok("cursor lines present", document.querySelectorAll("line.cursor").length === 4);
    ok("readout populated", $("readout").querySelectorAll(".ro").length === 13);
    ok("clock at event start", $("clock").textContent.startsWith("10:05"),
      `(${$("clock").textContent})`);
    ok("provenance footer", $("rp-prov").textContent.includes("demo-001")
      && $("rp-prov").textContent.includes("288/288"));

    // ---- cursor scrub ----
    $("slider").value = "180";
    $("slider").dispatchEvent(new window.Event("input"));
    ok("scrub moves clock", $("clock").textContent.startsWith("15:00"),
      `(${$("clock").textContent})`);
    const curX = $("cur-price").getAttribute("x1");
    ok("cursor x updated", Math.abs(+curX - (58 + 180 * (980 - 58 - 14) / 287)) < 0.5,
      `(${curX})`);

    // ---- cross-midnight event card ----
    cards()[2].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    ok("cross-midnight note shown", $("rp-meta").textContent.includes("previous market day"));
    ok("explicit sim day", $("rp-sim").textContent.includes("2026-07-08"));

    console.log(`\n${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
  } catch (e) {
    console.log("ERROR:", e.stack);
    process.exit(1);
  }
}, 600);
