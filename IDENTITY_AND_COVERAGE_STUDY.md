# University of Delaware identity and coverage study

**Verified:** 2026-09-13  
**Study status:** first-pass complete  
**Build status:** recommended to proceed with the three-page prototype  
**Pilot boundary:** `CORE`

## Decision

University of Delaware passes the handoff's Tier 0 gate and is a sound prototype institution. It has one current IPEDS reporting institution, an exact FY2024 HERD-to-IPEDS match, and no University of Delaware-administered FFRDC on the current federal master list.

The identity study also found the boundary problem the prototype is meant to expose. Delaware's own records link cleanly, but four institutions in its 30-member Data Feedback Report comparison group are present in HERD under a broader or differently named NCSES reporting entity with no UNITID on the HERD row. The interface and data model therefore need the boundary dimension from the first release.

## Tier 0 gate

| Required check | Evidence | Result |
|---|---|---|
| One principal IPEDS institution | IPEDS HD2024 has University of Delaware at UNITID `130943`, OPEID `00143100`, and no system code. College Scorecard returns `main_campus = 1` and `branches = 1`. | Pass |
| HERD coverage | The FY2024 HERD public-use file maps UNITID `130943` to NCSES institution `U3284001`; the medical-school flag is false. The [NCSES profile](https://ncsesdata.nsf.gov/profiles/site?method=view&tin=U3284001) also contains HERD, GSS, SED, and facilities data. | Pass |
| No FFRDC | The [FY2026 NCSES Master Government List of FFRDCs](https://ncses.nsf.gov/resource/master-gov-lists-ffrdc), current as of February 2026, contains no Delaware entry and no University of Delaware administrator. | Pass |

The ROR record has six child organizations and one related hospital. That does not overturn the Tier 0 result for IPEDS and HERD, but it does require an explicit publications boundary. The proposed dispositions are recorded in `DELAWARE_RELATED_ORGANIZATIONS.csv` and remain provisional until reviewed.

## Confirmed identity spine

| System | Confirmed value | Join use |
|---|---|---|
| IPEDS | UNITID `130943` | Primary institution key |
| Federal student aid | OPEID8 `00143100`; OPEID6 `001431` | Scorecard and aid-related data |
| Federal entity | UEI `T72NHKM259N3`; legacy DUNS `059007500`; EIN `51-6000297` | Awards, audits, and legal-entity sources |
| NCSES/HERD | NCSES ID `U3284001`; HERD `inst_id` `001431` | HERD, GSS, SED, and facilities |
| ROR | `01sbq1a82` | Research-organization bridge |
| OpenAlex | `I86501945` | Publications and citation graph |
| NIH RePORTER | organization IPF code `2076701` | NIH project records |
| NSF Awards | UEI `T72NHKM259N3` | Exact awardee filter |

These values are recorded row by row with evidence in `DELAWARE_IDENTITY_REGISTRY.csv`. The two patent assignee strings are only probable because an official PatentsView or USPTO entity check was not completed. They must remain hidden from a production page until confirmed.

## Peer provenance and coverage

The [2025 IPEDS Data Feedback Report](https://nces.ed.gov/ipeds/dfr/2025/ReportHTML.aspx?unitId=130943) says that the custom comparison group chosen by University of Delaware contains 30 institutions. The atlas should store this group as `DFR_SUBMITTED` with vintage `IPEDS_DFR_2025`. It should not describe the group as official.

Coverage across the 31 institutions, including Delaware:

| Source | Coverage result | Meaning |
|---|---:|---|
| IPEDS HD2024 | 31 exact UNITID matches | Full coverage at the IPEDS reporting-institution grain |
| College Scorecard 2026-06-10 institution file | 31 exact UNITID matches | Full institution-level coverage; individual measures still have their own missingness |
| HERD FY2024 | 27 exact UNITID matches; 4 conditional boundary matches; 0 unexplained absences | All institutions can be located, but four cannot be joined as if the HERD and IPEDS boundaries were identical |

The four HERD boundary cases are:

| IPEDS comparison institution | HERD reporting entity | NCSES ID | Why conditional |
|---|---|---|---|
| Ohio State University-Main Campus | Ohio State University, The | `U2388001` | HERD row has no UNITID |
| Texas A & M University-College Station | Texas A&M University, College Station and Health Science Center | `U4774001` | HERD explicitly combines the main campus and health science center |
| University of Connecticut | University of Connecticut | `U3280001` | HERD row has no UNITID |
| University of Maryland-College Park | University of Maryland | `U4758001` | HERD row has no UNITID and uses a broader label |

The full membership and row-level coverage are in `DELAWARE_DFR_PEER_COVERAGE.csv`.

## Source readiness

### Include in the prototype

1. **Identity and peers:** identity registry, aliases, related organizations, Carnegie attributes, and the 2025 `DFR_SUBMITTED` comparison group.
2. **IPEDS core:** directory/institutional characteristics and enrollment for UNITID `130943`, with release vintage, response status, units, and reporting period visible.
3. **HERD:** FY2024 research expenditures at the Delaware `CORE` boundary, plus explicit peer coverage and disabled comparisons where a boundary mapping has not been approved.

### Confirmed for later pages

University of Delaware has confirmed coverage in GSS, SED, research facilities, College Scorecard institution data, NSF Awards, NIH RePORTER, USAspending, OpenAlex, ClinicalTrials.gov, IRS filings, and the Federal Audit Clearinghouse through a published single-audit report. These sources stay outside the first three pages.

### Conditional before later use

- OpenAlex requires approved handling for ROR child and related organizations.
- College Scorecard field-of-study data requires a new coverage and suppression audit at the OPEID6 × CIP4 × credential grain.
- Federal Audit Clearinghouse API access requires a free Data.gov key; the institution's own single-audit report confirms relevance but does not replace an API reconciliation.
- DAPIP and EADA require current file extraction and join-key verification.
- ClinicalTrials.gov and AACT use sponsor strings rather than a stable institution identifier.
- PatentsView requires official access and reviewed assignee resolution.
- Source-derived downloads should remain disabled until redistribution terms are settled.

## What should be built next

The three-page prototype can now proceed without changing the proposed schema:

1. Load the confirmed crosswalk and related-organization tables as reviewed dimensions.
2. Pin one IPEDS enrollment vintage, complete its component contract, and ingest it without overwriting prior releases.
3. Ingest HERD FY2024 with both UNITID and NCSES identifiers. Treat the four peer boundary rows as conditional mappings.
4. Implement the persistent institution, boundary, peer mode, data year, and release-vintage controls.
5. Add downloads only for records whose source contract permits redistribution.
6. Run the eleven acceptance tests from the handoff, including byte-identical reruns and a failing test for an invalid cross-source ratio.

The next build is roughly **4–6 working days** for one engineer: one day for the registry and contracts, two days for the three pages and shared controls, one day for rerunnable ingestion and vintage diffs, and one to two days for reconciliation, browser testing, and fixes. MIT should follow as a separate acceptance test because Lincoln Laboratory and affiliated institutes require additional boundary logic.

## Decisions still needed before publication

- Name the owner of the source contracts and monthly change review.
- Decide whether the site will redistribute source-derived downloads or link to official files only.
- Set the threshold for review of vintage-to-vintage changes.
- Choose hosting and storage before deployment.

These decisions do not block the prototype's local data model and page build. Until the redistribution decision is made, the safe prototype behavior is to link to official sources and keep derived downloads off.

## Verification basis

This study used current live API responses and official public files where noted, plus static inspection of the downloaded IPEDS HD2024, HERD FY2024, and College Scorecard 2026-06-10 institution files. Dynamic counts from NSF, NIH, OpenAlex, and ClinicalTrials.gov were used only to confirm that Delaware is present; they are not reported as institutional performance measures.
