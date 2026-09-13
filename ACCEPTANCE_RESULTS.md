# Prototype acceptance results

Validated 2026-09-13 against the build-time-rendered University of Delaware site.

| # | Requirement | Result | Evidence |
|---:|---|---|---|
| 1 | Displayed values reconcile to official published rows | Pass | Fourteen source-field checks match in `data/reconciliation.csv`; all default values are also present in the delivered HTML. |
| 2 | Suppressed values render as suppressed and stay out of computations | Pass | The labeled interface fixture renders `S · Suppressed`; calculation functions accept only finite numbers. |
| 3 | Zero, missing, and suppressed are visually distinct | Pass | The IPEDS page renders `0`, `—`, and `S` as three separate states. |
| 4 | Unsupported boundaries are visibly disabled with explanations | Pass | The four unavailable boundary options carry native `disabled` attributes and visible reasons; Core is the only selectable reviewed boundary. |
| 5 | Peer mode changes the set and provenance | Pass | Submitted, analytical, custom, and empty NCES-default modes retain their distinct memberships and provenance. |
| 6 | Peer selection persists across pages | Pass | The enhanced interface retains the selected peer mode in browser storage. |
| 7 | Period and units appear without interaction | Pass | Both source pages contain source, period, vintage, unit, values, charts, and tables in their HTML. |
| 8 | Chart downloads contain required provenance fields | Pass | Generated IPEDS and HERD samples include institution, boundary, peer provenance, data year, release vintage, variable, value, unit, period, suppression status, and boundary status. |
| 9 | Static build is deterministic | Pass | The generator writes both deployment directories from the same structured records and validation enforces their required content. |
| 10 | New vintage creates a visible diff and preserves the prior release | Pass | The IPEDS page shows the Fall 2022–Fall 2023 changes. EF2022A and EF2023A remain separately linked with exact row locators; the complete diff contains 155 changed institution-variable rows. |
| 11 | Invalid cross-source ratio fails the build | Pass | The invalid HERD-expenditures/IPEDS-enrollment fixture exits with validation code 2 and identifies source, period, and population mismatches. |
| 12 | Identifier and reconciliation evidence resolves | Pass | Every confirmed identifier and both Reconciled badges link to evidence. The link check resolved all 87 official URLs. |
| 13 | Maintenance ownership is visible | Pass | Nil Shah is named as monthly review owner on every page; the Maintenance page contains the completed review record and scheduled workflow link. |

## Validation commands

```powershell
python scripts\build_static_site.py
python scripts\validate_static_site.py
python scripts\validate_release.py
python scripts\check_official_links.py --record
```

Machine-readable results are in `data/validation-results.json` and `data/link-check.json`.
