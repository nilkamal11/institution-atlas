import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8-sig"))
failures = []


def require(condition, message):
    if not condition:
        failures.append(message)


for name in ["index.html", "ipeds.html", "herd.html", "evidence.html", "maintenance.html", "styles.css", "app.js", "atlas-data.js"]:
    require((DOCS / name).exists(), f"missing generated file: {name}")

identity = (DOCS / "index.html").read_text(encoding="utf-8")
ipeds = (DOCS / "ipeds.html").read_text(encoding="utf-8")
herd = (DOCS / "herd.html").read_text(encoding="utf-8")
evidence = (DOCS / "evidence.html").read_text(encoding="utf-8")
maintenance = (DOCS / "maintenance.html").read_text(encoding="utf-8")
all_html = "\n".join([identity, ipeds, herd, evidence, maintenance])

require("24,221" in ipeds and "19,772" in ipeds and "4,449" in ipeds, "IPEDS focal values are not in delivered HTML")
require("465780" in herd or "$465.8M" in herd, "HERD focal value is not in delivered HTML")
require("24,039" in ipeds and "24,221" in ipeds and "+182" in ipeds, "Fall 2022 to Fall 2023 comparison is incomplete")
require("What changed?" in ipeds, "IPEDS What changed section is missing")
require("EF2022A.zip" in ipeds and "EF2023A.zip" in ipeds, "exact IPEDS bulk release links are missing")
require("UNITID=130943" in ipeds and "EFALEVEL=1" in ipeds, "IPEDS source-row locator is missing")
require('<svg class="static-chart"' in ipeds and '<table>' in ipeds, "IPEDS build-time chart/table fallback is missing")
require('<svg class="static-chart"' in herd and '<table>' in herd, "HERD build-time chart/table fallback is missing")
require('href="evidence.html#ipeds-reconciliation"' in ipeds, "IPEDS Reconciled badge is not linked")
require('href="evidence.html#herd-reconciliation"' in herd, "HERD Reconciled badge is not linked")
require(identity.count('class="id-link"') >= 19, "focal identifier links are incomplete")
require(identity.count("surveyNumber=15") >= 31, "peer UNITID links are incomplete")
require(herd.count("ncsesdata.nsf.gov/profiles") >= 27, "peer NCSES identifier links are incomplete")
require("Nil Shah" in maintenance and "Monthly" in maintenance and "Maintenance log" in maintenance, "maintenance ownership or record is missing")
require(all_html.count("Core + FFRDC — unavailable") >= 3, "unsupported boundary choices are not visibly unavailable")
require(all_html.count("disabled") >= 10, "locked controls are not marked disabled")
require("control-locked" in (DOCS / "styles.css").read_text(encoding="utf-8"), "disabled-control styling is missing")
require("<div id=\"identity-table\" class=\"table-wrap\"></div>" not in identity, "identity still depends on client rendering")
require("<section id=\"ipeds-metrics\" class=\"metric-grid\"></section>" not in ipeds, "IPEDS metrics still depend on client rendering")
require("<section id=\"herd-metrics\" class=\"metric-grid\"></section>" not in herd, "HERD metrics still depend on client rendering")
require("official peer group" not in all_html.lower(), "banned peer wording is present")

summary = {
    "status": "failed" if failures else "passed",
    "html_pages": 5,
    "static_ipeds_values": 5,
    "static_herd_values": 10,
    "confirmed_identifier_rows": len([row for row in atlas["identifiers"] if row["status"] == "confirmed"]),
    "peer_records": len(atlas["peerModes"]["DFR_SUBMITTED"]["unitids"]),
    "failures": failures,
}
print(json.dumps(summary, indent=2))
sys.exit(2 if failures else 0)
