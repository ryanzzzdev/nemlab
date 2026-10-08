# M5 state review — 2026-10-08

## Conclusion

GridReplay is complete as a local feature milestone, with the known hardening exceptions below carried explicitly to launch. This is not public-release readiness or a claim that every original acceptance check passed. Admin is now a separate M6; launch becomes M7. See [decision 023](../decisions/023-milestone-separation.md).

## Evidence reviewed

- The [October journal](../journal/2026-10.md) records the 2026-10-02 NEM-064 exit review: real import → detection → publication → catalogue → replay → BatteryLab, 393 backend tests, 124 browser tests and six real-stack checks. Maximum real replay observed was one day, approximately 48 KB and 16 series; this does not establish maximum seven-day performance.
- Discovery delivery is committed in backend `5e01125`, with completion recorded in `b12da66`; frontend `67c1cd6`, `40ff212`, `9ecabd1` and `17388de` contain the discovery UI and subsequent compatibility/sort fixes.
- NEM-091 records 462 backend tests, 114 contract response captures across 23 operations, and 126 browser tests passing for the discovery release. These are recorded campaign results, not suites rerun during this review.
- Fresh browser smoke at `http://127.0.0.1:5173/gridreplay`: catalogue shows 114 events and eight highlights; opening the September 4 price spike displays replay charts and the exact 16,599.89 price; keyboard cursor movement updates the interval/readouts; BatteryLab handoff opens September 4 in NSW1 without automatically running a simulation.

The delivered scope includes Highlights/All events, selection reasons, typed sorting/filtering, previews, preserved event links, price reversals and grouped negative episodes. The unusual-ramp detector exists; zero qualifying results in the live month reflect insufficient prior baseline history, not proof of no unusual ramps.

## Remaining work and ownership

| Item | Ownership / state |
| --- | --- |
| Admin product scope and UI decision | M6, NEM-093 discussion next; existing operator APIs/runbook remain available |
| Grid coverage endpoint and bounded price-date refresh | M6, NEM-082 / NEM-092; do not infer completion from working-tree changes |
| Prior demand history for unusual ramps; other regions' v2 publication | Optional bounded data operations to scope during M6; NSW1 v2 is live, other recorded September regional catalogues remain v1 |
| Reduced-motion treatment, chart-failure recovery evidence, maximum-window payload/render verification | M7, NEM-094; original exit review recorded these limits |
| Hosted CI | NEM-038 remains open; M3 is still formally in progress |
| Deployment, release coverage and operational readiness | M7, NEM-020 and BLK-006 |

## Record reconciliation

The roadmap body already recorded M5 complete while its table still said Planned. NEM-018 and NEM-064 were stale against the October 2 exit review; NEM-059 still described pending frontend synchronization despite its delivered evidence. Their records are reconciled with the existing evidence and explicit hardening carry-over. No application changes, new full test run, deployment or commit were performed for this review.
