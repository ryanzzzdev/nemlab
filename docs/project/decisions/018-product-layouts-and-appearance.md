# 018 — Product layouts and shared appearance

Date: 2026-09-24

Status: Accepted

## Context and acceptance

The user selected the GridReplay mock as the visual reference and asked for the real page to stay close to it: full-width GridReplay and centered BatteryLab, with dark/light/auto appearance support. The user delegated implementation choices in the same discussion.

## Decision

Preserve the mocks' compact panels, rounded borders and restrained typography. BatteryLab uses a centered 1160px workspace, a scenario-side column and teal accents. GridReplay uses the viewport width, amber accents, catalogue above vertically aligned replay panels. The reference appearances are light BatteryLab and dark GridReplay.

Appearance is one shared preference: Light and Dark explicitly override the device; Auto (the initial default) follows `prefers-color-scheme` and reacts to changes. A route change preserves that choice. Thus Auto can show either page in either palette; it does not force a different theme for each product. This gives predictable navigation while keeping product identity in layout and accents. Separate route defaults and independent per-product preferences were considered but would make the three-option control ambiguous.

Use existing React/plain CSS and ECharts. CSS semantic colors use `light-dark()` with `color-scheme`; a small same-origin head script restores the preference before first paint. React provides the preference and resolved chart appearance, with cross-tab storage updates and a usable in-memory fallback when storage is blocked. No new UI dependency is needed. Current verification targets Chromium; broader browser acceptance remains launch work.

## Scope and follow-up

[NEM-042](../backlog.md#nem-042) implements the appearance system and honest pre-integration layouts. The static mocks remain unchanged. Neither synthetic catalogue events nor mock simulation results are copied into the application as real data. NEM-043–NEM-045 deliver BatteryLab's form, lifecycle, comparison and saved-result journey; NEM-018 later connects the GridReplay catalogue and replay controls while preserving this visual direction.
