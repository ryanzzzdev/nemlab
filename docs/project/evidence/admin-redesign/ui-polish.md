# Admin UI/UX polish — NEM-124

Resumed: 2026-10-10. Changes remain uncommitted unless already absorbed into subsequent layout commits.

## Changes

- Data Operations and Access give tables the full available width until a record is selected; a close control returns focus to the main grid. Data Operations/Panes/CSS portions of the interrupted pass are now incorporated in the newer layout baseline; preserve those commits.
- Simulation actions sit below the record heading, rather than after all provenance details. The comparison is transposed to metrics-by-strategy with explicit AUD/MWh context, net margin emphasis and exact returned numeric values available through accessible cell labels/title.
- Summary values are plain informational elements rather than disabled buttons. Section contrast, long-value wrapping and native dark controls follow the independent Admin theme.
- Collapsed rail links retain explicit accessible names/tooltips. Signed-out screens omit the irrelevant density picker; welcome/access copy includes simulations.
- Activity's scoped mode now matches both region and overlapping market dates. All recent deliberately expands the scope; simulation activity uses its own history label.

## Verification

The interrupted pass recorded 126 public and 33 Admin browser tests passing. The resumed live review used the user's supplied one-use local sign-in link and inspected real Coverage, Simulations and Access. Light desktop 1440×900 and dark 1280×720 review verified the available table width, inspector actions, contained result comparison, sticky close control and themed scrollbars. No imports, publications, simulations or access decisions were submitted.

Final current `npm run check` passed: contract/format/type checks, both production builds, **126 public browser tests and 33 Admin browser tests**. The environment initially lacked Playwright Chromium; installing the official browser into `/tmp/nemlab-playwright` resolved test startup. The final run used that temporary cache. New regression coverage checks inspector space/focus and activity date filtering; collapsed rail accessible names are also asserted. No console errors were observed during the live review.

No backend implementation changes or new backend test run. This pass does not certify every M6 workflow or production readiness; M7 gates remain unchanged.
