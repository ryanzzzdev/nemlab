# 014 — Linked charts with Apache ECharts

Date: 2026-09-20
Status: Accepted for the bounded 288-interval prototype under delegated frontend choice.

## Decision

Use Apache ECharts 6.1.0 (Apache-2.0), loaded only after an explicit request to view the
prototype. Register line, grid, mark-line, inside-zoom and SVG renderer modules. Use one
instance with two grids, a shared selected interval and a dataZoom window targeting both
x axes. ResizeObserver resizes the instance; cleanup disposes it.

The top panel uses stored prices; the second uses a conspicuously labelled synthetic
triangular energy percentage to prove interactions before simulation results exist.
It has no physical interpretation and is independent of prices. Null observations
remain disconnected. Floating-point conversion is for plotting only; exact strings
remain in the selected-interval readout and table.

Native interval/window controls support keyboard and touch; mouse movement or taps on
either panel select the shared cursor. Zoom offers full-day and six-hour windows. We
intentionally do not capture wheel/pinch gestures, which remain page navigation. Both
axes use fixed UTC+10 interval-end labels, including the next-day midnight boundary.

## Alternatives and consequences

Two separate chart instances would require more event coordination and resize handling.
One shared instance suffices for this bounded prototype. SVG supports DOM-level geometry
checks; canvas and larger datasets can be evaluated when measured need arises.

The optional chart chunk is 518.76 kB (176.64 kB gzip), and still triggers Vite's default
500 kB warning. Keep that warning visible. On-demand loading prevents that cost on normal
price reads. Initial render measured about 78–83 ms locally for 288 points; this is not
network download time, a slow-device benchmark or a production latency guarantee.
Reassess rendering and bundle budgets before the final product charts are released.

## Evidence

[Chart findings](../evidence/frontend/chart-findings.md) record 40 browser checks, two
real API/browser checks, geometry verification and timing limits. The existing exact
price table remains usable if the optional module fails to load. Native controls provide
text alternatives for the synthetic series; no full accessibility certification is claimed.

This accepts the ECharts portion of decision 005. Forms/tables and final BatteryLab and
GridReplay presentation remain their own work. Primary reference:
[Apache ECharts axes and zoom](https://echarts.apache.org/handbook/en/concepts/axis/).
