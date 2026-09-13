# Prototype acceptance results

Validated 2026-09-13 against the three-page University of Delaware build.

| # | Requirement | Result | Evidence |
|---:|---|---|---|
| 1 | Displayed values reconcile to official published rows | Pass | 14 source-field checks match in `data/reconciliation.csv`. |
| 2 | Suppressed values render as suppressed and stay out of computations | Pass | The labeled interface fixture renders `S · Suppressed`; the calculation functions accept only finite numbers. The fixture is explicitly identified as a display test. |
| 3 | Zero, missing, and suppressed are visually distinct | Pass | The IPEDS page renders `0`, `—`, and `S` as three separate states. |
| 4 | Unsupported boundaries disable source panels with an explanation | Pass | Browser-tested all non-core choices; the page displays the reviewed-entity warning and disables the data panels. |
| 5 | Peer mode changes the set and provenance | Pass | Browser-tested submitted, analytical, custom, and empty NCES-default modes. |
| 6 | Peer selection persists across pages | Pass | Browser-tested navigation from HERD to Identity and IPEDS with the selected peer mode retained. |
| 7 | Period and units appear without interaction | Pass | Both source pages show source, period, vintage, and unit above the charts and repeat period and unit below them. |
| 8 | Chart downloads contain required provenance fields | Pass | Generated IPEDS and HERD samples include institution, boundary, peer provenance, data year, release vintage, variable, value, unit, period, suppression status, and boundary status. |
| 9 | Unchanged rerun is byte-identical | Pass | Two builds produced SHA-256 `3d6c300637f46e89dc4f79a38ac3a8102fc31bbc2edf2203ab40c7995a01d684`. |
| 10 | New vintage creates a diff and preserves the prior release | Pass | Official Fall 2022 and Fall 2023 files remain separately queryable; the generated diff contains 155 changed institution-variable rows. |
| 11 | Invalid cross-source ratio fails the build | Pass | The invalid HERD-expenditures/IPEDS-enrollment fixture exits with validation code 2 and identifies source, period, and population mismatches. |

## Browser checks

The default desktop state, a 390 × 844 phone viewport, all three page links, persistent controls, the analytical method dialog, the custom peer editor, the prior-vintage selector, and boundary guardrails were checked in the in-app browser. No browser warnings or errors were recorded.

## Validation command

```powershell
python scripts\validate_release.py
```

The recorded machine-readable result is in `data/validation-results.json`.
