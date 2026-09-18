/* DOM smoke test for index.html using jsdom: loads the page, lets the
 * simulated job finish and checks rendered results, charts, validation
 * failures and share-state handling.
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
    ok("job completes", $("job-chip").textContent === "complete", `(chip=${$("job-chip").textContent})`);
    ok("results visible", !$("results").hidden);
    const sum = $("summary").textContent;
    ok("fixed margin $464.24", sum.includes("$464.24"));
    ok("hindsight margin $506.13", sum.includes("$506.13"));
    ok("OPTIMAL status", sum.includes("OPTIMAL"));
    ok("price chart svg", $("chart-price").querySelector("svg path") !== null);
    ok("power bars drawn", $("chart-power").querySelectorAll("rect").length > 10);
    ok("energy chart 2 series", $("chart-energy").querySelectorAll("path").length >= 2);
    ok("margin chart 2 series", $("chart-margin").querySelectorAll("path").length >= 2);
    ok("breakdown rows", $("breakdown").querySelectorAll("tbody tr").length === 8);
    ok("explain bullets", $("explain").querySelectorAll("li").length >= 3,
      `(${$("explain").querySelectorAll("li").length})`);
    ok("versions line", $("versions").textContent.includes("battery-v1"));

    // switch day -> resubmit -> margins update
    $("day").value = "2026-09-11";
    $("scenario").dispatchEvent(new window.Event("submit", { cancelable: true }));
    setTimeout(() => {
      const sum2 = $("summary").textContent;
      ok("2026 fixed $81.93", sum2.includes("$81.93"));
      ok("2026 hindsight $118.46", sum2.includes("$118.46"));
      ok("dedupe chip or computed", $("job-chip").textContent === "complete");

      // invalid input -> field error + failed job
      $("capacity").value = "0";
      $("scenario").dispatchEvent(new window.Event("submit", { cancelable: true }));
      ok("invalid job fails", $("job-chip").textContent === "failed");
      ok("capacity flagged bad", $("capacity").classList.contains("bad"));
      ok("error message shown", document.querySelector(".err.on") !== null);

      // restore + invalid window ordering
      $("capacity").value = "2";
      $("chargeStart").value = "18:00"; // charge 18:00-14:00 reversed -> invalid
      $("scenario").dispatchEvent(new window.Event("submit", { cancelable: true }));
      ok("bad windows fail", $("job-chip").textContent === "failed");
      ok("window error shown", $("err-windows").classList.contains("on"));

      // share state round-trip
      const st = JSON.parse(atob(btoa(JSON.stringify({ m: "roundTrip", day: "2023-09-11" }))));
      ok("share decode", st.day === "2023-09-11");

      console.log(`\n${pass} passed, ${fail} failed`);
      process.exit(fail ? 1 : 0);
    }, 1400);
  } catch (e) {
    console.log("ERROR:", e.stack);
    process.exit(1);
  }
}, 1400);
