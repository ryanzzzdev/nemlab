# 018 — Product layouts and shared appearance

Date: 2026-09-24

Status: Accepted

## Context and acceptance

The user initially selected the GridReplay mock as the visual reference: full-width GridReplay and centered BatteryLab, with dark/light/auto appearance support. NEM-042 implemented that direction in frontend commit `362f1f4`. After reviewing the real pages on 2026-09-24, the user found the width change inconsistent and accepted updating the plan to center both products, with a wider GridReplay workspace. This revision supersedes only the original full-width layout choice; the mock remains the reference for panels, typography and accents.

## Decision

Preserve the mocks' compact panels, rounded borders and restrained typography. BatteryLab uses a centered workspace capped at 1160px, a scenario-side column and teal accents. GridReplay uses a centered workspace capped at 1440px, amber accents, catalogue above vertically aligned replay panels. Keep the shared header/navigation aligned in the same centered 1160px container across both routes, with consistent responsive gutters. Both workspaces fill the available width below their caps without horizontal page overflow. The reference appearances are light BatteryLab and dark GridReplay.

The wider GridReplay cap gives charts and event cards extra room while avoiding an edge-to-edge ultrawide layout. Using 1160px for both was considered, but would unnecessarily constrain the denser replay view. NEM-043 now implements the revised centered layout and verifies both width caps, header alignment and narrow-screen behavior.

Appearance is one shared preference: Light and Dark explicitly override the device; Auto (the initial default) follows `prefers-color-scheme` and reacts to changes. A route change preserves that choice. Thus Auto can show either page in either palette; it does not force a different theme for each product. This gives predictable navigation while keeping product identity in layout and accents. Separate route defaults and independent per-product preferences were considered but would make the three-option control ambiguous.

Use existing React/plain CSS and ECharts. CSS semantic colors use `light-dark()` with `color-scheme`; a small same-origin head script restores the preference before first paint. React provides the preference and resolved chart appearance, with cross-tab storage updates and a usable in-memory fallback when storage is blocked. No new UI dependency is needed. Current verification targets Chromium; broader browser acceptance remains launch work.

## Scope and follow-up

Accepted refinement, 2026-09-25: the user selected the BatteryLab demo as the primary visual target over the current real page, including inputs, buttons and their positions, all panel treatments and integrated chart styling. NEM-047 will align the real page closely with it. Simulation ID/status/source/Copy link and monitoring controls belong immediately below the simulation button in compact secondary styling, rather than in a prominent result-column panel. The previously requested financial-breakdown ordering, automatically visible charts, collapsed interval detail and standalone Prices page take precedence over conflicting demo details. Shared centered layouts and dark/light/auto remain accepted. See the [UX refinement plan](../features/ui-refinement.md) for the current target; implemented as NEM-047 and NEM-048 in frontend `ef4c25f`, keeping the shared site header and theme picker rather than the demo's bespoke band.

[NEM-042](../backlog.md#nem-042) completed the appearance system and original pre-integration layouts; its completion evidence remains historical. [NEM-043](../backlog.md#nem-043) first applies the centered-layout revision, then delivers BatteryLab's form and lifecycle. NEM-044–NEM-045 deliver comparison and saved-result acceptance; NEM-018 later connects the GridReplay catalogue and replay controls while preserving this visual direction. The static mocks remain unchanged. Neither synthetic catalogue events nor mock simulation results are copied into the application as real data.


### GridReplay fidelity clarification — 2026-09-25

The user reaffirmed that the real GridReplay should look as close to its demo as possible. Treat its complete composition as the primary visual reference: compact filter row and event cards, catalogue above replay, heading/action positions, playback controls, readout strip, chart order/legends/event shading and secondary provenance. NEM-060 builds and visually reviews this early, with NEM-061/064 checking the integrated result. Preserve the accepted centered widths, shared header and Light/Dark/Auto behavior. Synthetic data, provisional detector formulas and unsupported causal copy are not accepted merely because they appear in the mock. See the [fidelity matrix](../features/gridreplay.md#demo-fidelity-is-a-delivery-requirement).
