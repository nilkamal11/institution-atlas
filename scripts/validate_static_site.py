import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8-sig"))
scorecard_data = json.loads((ROOT / "data" / "scorecard.json").read_text(encoding="utf-8-sig"))
nsf_data = json.loads((ROOT / "data" / "nsf-awards.json").read_text(encoding="utf-8-sig"))
nih_data = json.loads((ROOT / "data" / "nih-reporter.json").read_text(encoding="utf-8-sig"))
usaspending_data = json.loads((ROOT / "data" / "usaspending.json").read_text(encoding="utf-8-sig"))
openalex_data = json.loads((ROOT / "data" / "openalex.json").read_text(encoding="utf-8-sig"))
ncses_gss_data = json.loads((ROOT / "data" / "ncses-gss.json").read_text(encoding="utf-8-sig"))
ncses_sed_data = json.loads((ROOT / "data" / "ncses-sed.json").read_text(encoding="utf-8-sig"))
ncses_facilities_data = json.loads((ROOT / "data" / "ncses-facilities.json").read_text(encoding="utf-8-sig"))
clinical_trials_data = json.loads((ROOT / "data" / "clinical-trials.json").read_text(encoding="utf-8-sig"))
carnegie_data = json.loads((ROOT / "data" / "carnegie.json").read_text(encoding="utf-8-sig"))
failures = []


def require(condition, message):
    if not condition:
        failures.append(message)


for name in ["index.html", "ipeds.html", "scorecard.html", "herd.html", "ncses-gss.html", "ncses-doctorates.html", "ncses-facilities.html", "nsf-awards.html", "nih-reporter.html", "usaspending.html", "openalex.html", "clinical-trials.html", "carnegie.html", "evidence.html", "maintenance.html", "styles.css", "app.js", "atlas-data.js", "data/scorecard.json", "data/nsf-awards.json", "data/nih-reporter.json", "data/usaspending.json", "data/openalex.json", "data/ncses-gss.json", "data/ncses-sed.json", "data/ncses-facilities.json", "data/clinical-trials.json", "data/carnegie.json"]:
    require((DOCS / name).exists(), f"missing generated file: {name}")

identity = (DOCS / "index.html").read_text(encoding="utf-8")
ipeds = (DOCS / "ipeds.html").read_text(encoding="utf-8")
scorecard = (DOCS / "scorecard.html").read_text(encoding="utf-8")
herd = (DOCS / "herd.html").read_text(encoding="utf-8")
nsf = (DOCS / "nsf-awards.html").read_text(encoding="utf-8")
nih = (DOCS / "nih-reporter.html").read_text(encoding="utf-8")
usaspending = (DOCS / "usaspending.html").read_text(encoding="utf-8")
openalex = (DOCS / "openalex.html").read_text(encoding="utf-8")
gss = (DOCS / "ncses-gss.html").read_text(encoding="utf-8")
sed = (DOCS / "ncses-doctorates.html").read_text(encoding="utf-8")
facilities = (DOCS / "ncses-facilities.html").read_text(encoding="utf-8")
trials = (DOCS / "clinical-trials.html").read_text(encoding="utf-8")
carnegie = (DOCS / "carnegie.html").read_text(encoding="utf-8")
evidence = (DOCS / "evidence.html").read_text(encoding="utf-8")
maintenance = (DOCS / "maintenance.html").read_text(encoding="utf-8")
all_html = "\n".join([identity, ipeds, scorecard, herd, gss, sed, facilities, nsf, nih, usaspending, openalex, trials, carnegie, evidence, maintenance])

require("24,221" in ipeds and "19,772" in ipeds and "4,449" in ipeds, "IPEDS focal values are not in delivered HTML")
require("465780" in herd or "$465.8M" in herd, "HERD focal value is not in delivered HTML")
require("$17,799" in scorecard and "79.7%" in scorecard and "$72,950" in scorecard and "$24,572" in scorecard, "Scorecard focal values are not in delivered HTML")
nsf_estimated = f'${nsf_data["active_estimated_total_amount"] / 1_000_000:,.1f}M'
require(f'{nsf_data["all_time_record_count"]:,}' in nsf and f'{nsf_data["active_award_count"]:,}' in nsf and nsf_estimated in nsf and f'{nsf_data["recent_award_count"]:,}' in nsf, "NSF award values are not in delivered HTML")
nih_current = nih_data["year_summary"][-1]
require(f'{nih_data["record_count"]:,}' in nih and f'{nih_data["distinct_core_projects"]:,}' in nih and f'${nih_current["award_amount"] / 1_000_000:,.1f}M' in nih, "NIH RePORTER values are not in delivered HTML")
usa_current = usaspending_data["year_summary"][-1]
require(f'{usaspending_data["prime_award_count"]:,}' in usaspending and f'${usa_current["obligations"] / 1_000_000:,.1f}M' in usaspending and f'${usaspending_data["five_year_obligations"] / 1_000_000_000:,.2f}B' in usaspending, "USAspending values are not in delivered HTML")
require(f'{openalex_data["works_count"]:,}' in openalex and f'{openalex_data["open_access_works"]:,}' in openalex and f'{openalex_data["topic_classified_works"]:,}' in openalex, "OpenAlex values are not in delivered HTML")
require("2,442" in gss and "217" in gss and "162" in gss and "72 of 631" in gss, "GSS focal values are not in delivered HTML")
require("273" in sed and "243" in sed and "+2" in sed and "75 of 460" in sed, "SED focal values are not in delivered HTML")
require("853k NASF" in facilities and "375k NASF" in facilities and "83 of 602" in facilities, "Facilities focal values are not in delivered HTML")
require(f'{clinical_trials_data["exact_name_record_count"]:,}' in trials and f'{clinical_trials_data["lead_sponsor_count"]:,}' in trials and f'{clinical_trials_data["collaborator_count"]:,}' in trials, "ClinicalTrials.gov values are not in delivered HTML")
require(carnegie_data["classifications"]["institutional_2025"] in carnegie and "Research 1" in carnegie and carnegie_data["classifications"]["student_access_and_earnings_2025"] in carnegie, "Carnegie classification values are not in delivered HTML")
require("24,039" in ipeds and "24,221" in ipeds and "+182" in ipeds, "Fall 2022 to Fall 2023 comparison is incomplete")
require("What changed?" in ipeds, "IPEDS What changed section is missing")
require("EF2022A.zip" in ipeds and "EF2023A.zip" in ipeds, "exact IPEDS bulk release links are missing")
require("UNITID=130943" in ipeds and "EFALEVEL=1" in ipeds, "IPEDS source-row locator is missing")
require('<svg class="static-chart"' in ipeds and '<table>' in ipeds, "IPEDS build-time chart/table fallback is missing")
require('<svg class="static-chart"' in herd and '<table>' in herd, "HERD build-time chart/table fallback is missing")
require(scorecard.count('<svg class="static-chart"') >= 2 and '<table>' in scorecard, "Scorecard build-time chart/table fallback is missing")
require('<svg class="static-chart"' in nsf and '<table>' in nsf, "NSF build-time chart/table fallback is missing")
require('<svg class="static-chart"' in nih and '<table>' in nih, "NIH build-time chart/table fallback is missing")
require('<svg class="static-chart"' in usaspending and '<table>' in usaspending, "USAspending build-time chart/table fallback is missing")
require('<svg class="static-chart"' in openalex and '<table>' in openalex, "OpenAlex build-time chart/table fallback is missing")
for label, page in [("GSS", gss), ("SED", sed), ("Facilities", facilities), ("ClinicalTrials.gov", trials), ("Carnegie", carnegie)]:
    require('<svg class="static-chart"' in page and '<table>' in page, f"{label} build-time chart/table fallback is missing")
require('href="evidence.html#ipeds-reconciliation"' in ipeds, "IPEDS Reconciled badge is not linked")
require('href="evidence.html#herd-reconciliation"' in herd, "HERD Reconciled badge is not linked")
require('href="evidence.html#scorecard-reconciliation"' in scorecard, "Scorecard Reconciled badge is not linked")
require('href="evidence.html#nsf-reconciliation"' in nsf, "NSF Reconciled badge is not linked")
require('href="evidence.html#nih-reconciliation"' in nih, "NIH Reconciled badge is not linked")
require('href="evidence.html#usaspending-reconciliation"' in usaspending, "USAspending Reconciled badge is not linked")
require('href="evidence.html#openalex-reconciliation"' in openalex, "OpenAlex Reconciled badge is not linked")
require('href="evidence.html#gss-reconciliation"' in gss, "GSS Reconciled badge is not linked")
require('href="evidence.html#sed-reconciliation"' in sed, "SED Reconciled badge is not linked")
require('href="evidence.html#facilities-reconciliation"' in facilities, "Facilities Reconciled badge is not linked")
require('href="evidence.html#trials-reconciliation"' in trials, "ClinicalTrials.gov Reconciled badge is not linked")
require('href="evidence.html#carnegie-reconciliation"' in carnegie, "Carnegie Reconciled badge is not linked")
require(all(f'id="{source}-reconciliation"' in evidence for source in ["scorecard", "nsf", "nih", "usaspending", "openalex", "gss", "sed", "facilities", "trials", "carnegie"]), "new source evidence records are missing")
require(identity.count('class="id-link"') >= 19, "focal identifier links are incomplete")
require(identity.count("surveyNumber=15") >= 31, "peer UNITID links are incomplete")
require(herd.count("ncsesdata.nsf.gov/profiles") >= 27, "peer NCSES identifier links are incomplete")
require("Nil Shah" in maintenance and "Monthly" in maintenance and "Maintenance log" in maintenance, "maintenance ownership or record is missing")
require(all_html.count("Core + FFRDC — unavailable") >= 13, "unsupported boundary choices are not visibly unavailable")
require(all_html.count("disabled") >= 10, "locked controls are not marked disabled")
require("control-locked" in (DOCS / "styles.css").read_text(encoding="utf-8"), "disabled-control styling is missing")
require("<div id=\"identity-table\" class=\"table-wrap\"></div>" not in identity, "identity still depends on client rendering")
require("<section id=\"ipeds-metrics\" class=\"metric-grid\"></section>" not in ipeds, "IPEDS metrics still depend on client rendering")
require("<section id=\"herd-metrics\" class=\"metric-grid\"></section>" not in herd, "HERD metrics still depend on client rendering")
require("<section id=\"scorecard-metrics\" class=\"metric-grid\"></section>" not in scorecard, "Scorecard metrics still depend on client rendering")
require("<section id=\"nsf-metrics\" class=\"metric-grid\"></section>" not in nsf, "NSF metrics still depend on client rendering")
require("<section id=\"nih-metrics\" class=\"metric-grid\"></section>" not in nih, "NIH metrics still depend on client rendering")
require("<section id=\"usaspending-metrics\" class=\"metric-grid\"></section>" not in usaspending, "USAspending metrics still depend on client rendering")
require("<section id=\"openalex-metrics\" class=\"metric-grid\"></section>" not in openalex, "OpenAlex metrics still depend on client rendering")
require(scorecard.count("collegescorecard.ed.gov/school/") >= 31, "Scorecard peer identifiers are not fully linked")
require(nsf.count("api.nsf.gov/services/v1/awards/") >= 20, "NSF award identifiers are not fully linked")
require(nih.count("reporter.nih.gov/project-details/") >= 20, "NIH application identifiers are not fully linked")
require(usaspending.count("usaspending.gov/award/") >= 20, "USAspending award identifiers are not fully linked")
require("api.openalex.org/institutions/I86501945" in openalex and "ror.org/01sbq1a82" in openalex, "OpenAlex institution identifiers are not fully linked")
require(trials.count("clinicaltrials.gov/study/NCT") >= 25, "ClinicalTrials.gov identifiers are not fully linked")
require("carnegieclassifications.acenet.edu/institution/university-of-delaware" in carnegie, "Carnegie UNITID evidence link is missing")
require('id="peer-control" disabled' in nsf and "UEI crosswalk not loaded for peers" in nsf, "NSF peer control is not visibly unavailable")
require('id="peer-control" disabled' in nih and "NIH organization crosswalk not loaded for peers" in nih, "NIH peer control is not visibly unavailable")
require('id="peer-control" disabled' in usaspending and "Recipient UEI crosswalk not loaded for peers" in usaspending, "USAspending peer control is not visibly unavailable")
require('id="peer-control" disabled' in openalex and "Peer institution boundaries not reviewed" in openalex, "OpenAlex peer control is not visibly unavailable")
require('id="peer-control" disabled' in gss and "NCSES profile crosswalk not loaded for peers" in gss, "GSS peer control is not visibly unavailable")
require('id="peer-control" disabled' in sed and "NCSES profile crosswalk not loaded for peers" in sed, "SED peer control is not visibly unavailable")
require('id="peer-control" disabled' in facilities and "NCSES profile crosswalk not loaded for peers" in facilities, "Facilities peer control is not visibly unavailable")
require('id="peer-control" disabled' in trials and "Stable institution identifiers are unavailable" in trials, "ClinicalTrials.gov peer control is not visibly unavailable")
require('id="peer-control" disabled' in carnegie and "Classification labels are not peer metrics" in carnegie, "Carnegie peer control is not visibly unavailable")
require("official peer group" not in all_html.lower(), "banned peer wording is present")

summary = {
    "status": "failed" if failures else "passed",
    "html_pages": 15,
    "static_ipeds_values": 5,
    "static_herd_values": 10,
    "static_scorecard_values": 11,
    "static_nsf_summary_values": 4,
    "static_nih_summary_values": 4,
    "static_usaspending_summary_values": 4,
    "static_openalex_summary_values": 4,
    "static_gss_summary_values": 4,
    "static_sed_summary_values": 4,
    "static_facilities_summary_values": 4,
    "static_clinical_trials_summary_values": 4,
    "static_carnegie_summary_values": 4,
    "confirmed_identifier_rows": len([row for row in atlas["identifiers"] if row["status"] == "confirmed"]),
    "peer_records": len(atlas["peerModes"]["DFR_SUBMITTED"]["unitids"]),
    "failures": failures,
}
print(json.dumps(summary, indent=2))
sys.exit(2 if failures else 0)
