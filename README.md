# Institution Atlas

Institution Atlas is a three-page prototype for describing one university across public education and research sources while keeping each source's reporting boundary, period, unit, and release vintage visible.

The pilot institution is the University of Delaware. Its reviewed core-campus identity connects IPEDS UNITID `130943` to NCSES HERD ID `U3284001` and the other identifiers listed in the identity registry.

## Pages

- **Identity & peers** shows the reviewed crosswalk, the reporting-boundary choices, related organizations, and four peer modes with provenance.
- **IPEDS core** shows Fall 2023 and Fall 2022 enrollment, the active peer median, response status, and source-vintage downloads.
- **Research · HERD** shows FY2024 R&D expenditures, funding sources, personnel, and peer coverage. Four peer records with unresolved HERD boundaries remain visible and are excluded from the median.

The active boundary and peer group persist across all three pages. Sources are checked monthly; the interface shows the last verified date. New releases are added as new vintages rather than replacing prior files.

## Evidence and methods

- [`data/reconciliation.csv`](data/reconciliation.csv) records the source-row reconciliation for every University of Delaware value displayed on the two data pages.
- [`data/vintage-diff.csv`](data/vintage-diff.csv) records changes between the retained Fall 2022 and Fall 2023 IPEDS releases.
- [`data/source-contracts.json`](data/source-contracts.json) records grain, universe, boundary, period, release, missing-value, and reuse rules for the four prototype sources.
- [`analytical-peer-model.json`](analytical-peer-model.json) records the analytical-peer inputs, weights, transformations, and full ranking.
- [`ACCEPTANCE_RESULTS.md`](ACCEPTANCE_RESULTS.md) records the eleven prototype acceptance checks.
- [`IDENTITY_AND_COVERAGE_STUDY.md`](IDENTITY_AND_COVERAGE_STUDY.md) contains the identity and coverage study that preceded the build.

## Run locally

The site has no package dependencies. From the repository root:

```powershell
python -m http.server 8770 --directory dist
```

Open `http://127.0.0.1:8770/`.

## Rebuild and validate

The build script reads the official source files in the AAGeneral workspace and writes deterministic site data. Set `AAGENERAL_ROOT` if the repository is outside that workspace.

```powershell
$env:AAGENERAL_ROOT = "C:\path\to\AAGeneral"
python scripts\build_site_data.py
python scripts\validate_release.py
```

The validation script independently reads the official IPEDS and HERD rows, regenerates the reconciliation, vintage snapshots, vintage diff, and download samples, and enforces the cross-source ratio rule. It uses only the Python standard library.

## Official sources

- [IPEDS institution profile](https://nces.ed.gov/ipeds/institution-profile/130943)
- [IPEDS reported data](https://nces.ed.gov/ipeds/reported-data/130943)
- [2025 IPEDS Data Feedback Report](https://nces.ed.gov/ipeds/dfr/2025/ReportHTML.aspx?unitId=130943)
- [NCSES Academic Institution Profile](https://ncsesdata.nsf.gov/profiles/site?method=view&tin=U3284001)

This repository republishes a small, selected set of public-source facts for the prototype. The source contracts retain official links and mark redistribution review as a production prerequisite.
