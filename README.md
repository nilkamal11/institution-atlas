# Institution Atlas

Institution Atlas describes one university across public education and research sources while keeping each source's reporting boundary, period, unit, and release vintage visible. The pilot institution is the University of Delaware.

The site is generated from structured data in this repository. The build writes complete HTML with every default value, label, unit, reporting period, vintage, suppression state, table, and chart. JavaScript adds peer and vintage switching, downloads, and other controls; it is not required to read the site.

## Pages

- **Identity & peers** shows the reviewed identifier crosswalk, reporting boundary, related organizations, and four peer modes with provenance.
- **IPEDS core** shows Fall 2023 and Fall 2022 enrollment, an accessible chart and table, peer records, and a visible “What changed?” comparison.
- **College Scorecard** shows 2024 cost, aid, admissions, retention, and completion measures; separately dated debt and earnings cohorts; and all 30 submitted DFR peers.
- **Research · HERD** shows FY2024 R&D expenditures, funding sources, personnel, peer comparisons, and boundary review status.
- **NSF awards** shows exact-UEI award coverage, active records, recent award-year trends, directorate coverage, and linked award records.
- **Evidence** links every confirmed identifier and each reconciliation badge to the official evidence, exact bulk release, and source-row locator.
- **Maintenance** names Nil Shah as the monthly review owner and publishes the review cadence, history, source assignments, and link-check record.

Four HERD peer records with broader or unresolved reporting boundaries remain visible and are excluded from the median.

## Structured data and exports

The source data is in [`data`](data). Stable copies are published under `/data/` on GitHub Pages.

- [`data/atlas.json`](data/atlas.json) contains the institution, peer, IPEDS, HERD, Scorecard, and NSF records used by the site.
- [`data/scorecard.json`](data/scorecard.json) contains the dated College Scorecard API snapshot for Delaware and its 30 submitted DFR peers.
- [`data/nsf-awards.json`](data/nsf-awards.json) contains the dated exact-UEI NSF Awards snapshot, aggregates, and recent award records.
- [`data/reconciliation.csv`](data/reconciliation.csv) records each displayed University of Delaware value and its source-row locator.
- [`data/vintage-diff.csv`](data/vintage-diff.csv) records changes between retained IPEDS vintages.
- [`data/source-contracts.json`](data/source-contracts.json) records source grain, universe, boundary, period, release, missing-value rules, ownership, and review cadence.
- [`data/maintenance-log.json`](data/maintenance-log.json) records completed reviews and the next review.
- [`data/link-check.json`](data/link-check.json) records the latest automated check of every official link in the generated pages.

## Build and validation

The scripts use the Python standard library. From the repository root:

```powershell
python scripts\refresh_scorecard_nsf.py
python scripts\build_static_site.py
python scripts\validate_static_site.py
python scripts\validate_release.py
python scripts\check_official_links.py --record
```

Preview the same files served by GitHub Pages:

```powershell
python -m http.server 8770 --directory docs
```

The scheduled GitHub Action runs monthly, refreshes College Scorecard and NSF Awards, selects the latest common nonmissing Scorecard years, rebuilds the site, checks official links, and publishes a new maintenance record when the source data changes.

## Official source entry points

- [IPEDS Fall 2023 reported data](https://nces.ed.gov/ipeds/reported-data/html/130943?surveyNumber=15&viewMode=print&year=2023)
- [IPEDS EF2023A bulk release](https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip)
- [2025 IPEDS Data Feedback Report](https://nces.ed.gov/ipeds/dfr/2025/ReportHTML.aspx?unitId=130943)
- [NCSES Academic Institution Profile](https://ncsesdata.nsf.gov/profiles/site?method=view&tin=U3284001)
- [College Scorecard institution profile](https://collegescorecard.ed.gov/school/?130943-University-of-Delaware)
- [College Scorecard data and documentation](https://collegescorecard.ed.gov/data/)
- [NSF Awards exact-UEI query](https://api.nsf.gov/services/v1/awards.json?ueiNumber=T72NHKM259N3)
- [NSF Awards API documentation](https://resources.research.gov/common/webapi/awardapisearch-v1.htm)

The browser-facing IPEDS report is paired with its exact bulk release and row locator because the general institution-profile route can redirect repeatedly for automated clients.
