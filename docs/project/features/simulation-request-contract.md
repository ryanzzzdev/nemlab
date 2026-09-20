# Simulation request contract v1

Date: 2026-09-20. NEM-039 implementation contract; transport-independent, not yet an HTTP API.

One request selects a region and completed NEM market day on/after 2021-10-01, an aggregate
site, efficiency, costs and one ordered charge/discharge window. All fields are required
except the mutually exclusive efficiency alternatives. No battery count, implicit defaults,
unrestricted strategy or client-supplied engine version is accepted by this boundary.

Decimal inputs use BigDecimal (future JSON adapters must preserve decimal strings).
Input precision is at most 38 digits and absolute scale at most 18 before normalisation,
matching the stored-price representation budget. Trailing zeros normalise away; zero has
one representation. Physical quantities and each cost are in [0, 1,000,000]; capacity must
be positive. These are conservative finite-arithmetic admission ceilings, not a promise
of optimality at every scale or final public launch limits. Exact decimal energy ordering
must satisfy minimum <= initial <= maximum <= capacity before double conversion.

Supply either charge/discharge efficiencies in [0.01, 1], or roundTrip in [0.0001, 1].
Round-trip normalisation uses the existing engine square-root rule and preserves the two
resulting legs via BigDecimal.valueOf(double). Identity uses these legs, not the chosen
input form. Original exact normalised decimal physical/cost inputs remain available;
only execution converts to doubles. Supplied engine efficiency legs are reused as-is.

Window boundaries are integer minutes from local midnight in fixed UTC+10, 0..1440 and
five-minute aligned. 1440 means next midnight. Core ScheduleWindows validates nonempty,
ordered, nonoverlapping windows. No wrap or daylight-saving conversion is allowed.

Validation fails with a field path and stable code (REQUIRED, OUT_OF_RANGE,
DECIMAL_LIMIT, INVALID_BOUNDS, INVALID_WINDOWS, AMBIGUOUS_EFFICIENCY). The first error is
returned; parsing malformed decimal/date/enum text belongs to the future HTTP adapter.
Unknown or incomplete stored data produces PRICE_DAY_UNAVAILABLE or PRICE_DAY_INCOMPLETE.
Neither condition fetches OE or submits refresh work.

Preparation captures the current revision once and reads that immutable revision. A source
correction afterwards cannot change the prepared prices. This operation is read-only:
NEM-040 persists the revision reference and parameters atomically with job submission;
preparation does not create orphan price_snapshot rows or jobs.

Scenario identity is SHA-256 of a versioned, fixed-order newline-separated representation
of region, date, exact normalised parameters/windows, revision UUID, model and both strategy
versions, solver version, and standard cooperative solver limits. Runtime profile v1 binds
this representation; future result-affecting execution changes must version the profile.
Snapshot row IDs, retrieval timestamps, input scale and chosen efficiency input form are
excluded. Changed price revisions or result-affecting inputs must yield different keys.
A stable key identifies inputs, not a guarantee of identical wall-clock solver termination.
No execution options are supplied by the client. The ordered-comparison-v1 execution profile now binds a 512 MiB child heap, two active processors and a 15-second hard deadline under NEM-040.
