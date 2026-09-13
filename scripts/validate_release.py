import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
DATA = REPO / "data"
WORKSPACE = Path(os.environ.get("AAGENERAL_ROOT", REPO.parent.parent)).resolve()


def read_atlas():
    text = (DIST / "atlas-data.js").read_text(encoding="utf-8")
    prefix = "window.ATLAS_DATA="
    if not text.startswith(prefix) or not text.rstrip().endswith(";"):
        raise ValueError("atlas-data.js is not a deterministic ATLAS_DATA assignment")
    return json.loads(text[len(prefix):].strip()[:-1])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_vintage_artifacts(atlas):
    metrics = ["totalEnrollment", "undergraduate", "graduate", "fullTime", "partTime"]
    for vintage in ["IPEDS_EF2022A", "IPEDS_EF2023A"]:
        rows = []
        for unitid, record in atlas["records"].items():
            fact = record["ipedsHistory"][vintage]
            rows.append({
                "institution_key": record["institutionKey"],
                "unitid": unitid,
                "boundary_id": "CORE",
                "data_year": fact["dataYear"].replace("Fall ", ""),
                "release_vintage": vintage,
                **{metric: fact.get(metric) for metric in metrics},
                "response_status": fact.get("responseStatus"),
            })
        write_json(DATA / "vintages" / f"{vintage}.json", {"release_vintage": vintage, "facts": rows})

    diff_rows = []
    for unitid, record in atlas["records"].items():
        prior = record["ipedsHistory"]["IPEDS_EF2022A"]
        current = record["ipedsHistory"]["IPEDS_EF2023A"]
        for metric in metrics:
            old, new = prior.get(metric), current.get(metric)
            if old != new:
                diff_rows.append({
                    "institution_key": record["institutionKey"],
                    "unitid": unitid,
                    "variable": metric,
                    "prior_vintage": "IPEDS_EF2022A",
                    "prior_value": old,
                    "current_vintage": "IPEDS_EF2023A",
                    "current_value": new,
                    "absolute_change": "" if old is None or new is None else new - old,
                })
    write_csv(DATA / "vintage-diff.csv", [
        "institution_key", "unitid", "variable", "prior_vintage", "prior_value",
        "current_vintage", "current_value", "absolute_change"
    ], diff_rows)
    return len(diff_rows)


def official_reconciliation(atlas):
    focal = atlas["records"]["130943"]
    rows = []
    ef_path = WORKSPACE / ".work" / "institution_atlas" / "ipeds" / "EF2023A" / "ef2023a.csv"
    ipeds_source = {}
    with ef_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["UNITID"].strip() == "130943" and row["EFALEVEL"].strip() in {"1", "2", "12", "21", "41"}:
                ipeds_source[row["EFALEVEL"].strip()] = int(float(row["EFTOTLT"]))
    ipeds_fields = {
        "totalEnrollment": "1", "undergraduate": "2", "graduate": "12",
        "fullTime": "21", "partTime": "41"
    }
    for field, level in ipeds_fields.items():
        expected = ipeds_source[level]
        actual = focal["ipedsHistory"]["IPEDS_EF2023A"][field]
        rows.append({
            "page": "IPEDS core", "variable": field, "source": "IPEDS EF2023A",
            "source_locator": f"UNITID=130943; EFALEVEL={level}; EFTOTLT",
            "official_value": expected, "display_data_value": actual,
            "unit": "students", "result": "match" if expected == actual else "mismatch"
        })

    herd_path = WORKSPACE / ".work" / "public_higher_ed" / "funding_samples" / "herd_2024" / "herd2024.csv"
    source_values = {}
    personnel = {}
    ftes = {}
    with herd_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ncses_inst_id"].strip() != "U3284001":
                continue
            value = int(float(row["data"])) if row["data"].strip() else None
            q = row["questionnaire_no"].strip()
            if q in {"01.a", "01.b", "01.c", "01.d", "01.e", "01.f", "01.g"}:
                source_values[row["row"].strip()] = value
            elif q == "15" and row["row"].strip() == "Total":
                personnel[row["column"].strip()] = value
            elif q == "16" and row["row"].strip() == "Total":
                ftes[row["column"].strip()] = value
    for label, expected in source_values.items():
        actual = focal["herd"]["sources"].get(label)
        rows.append({
            "page": "Research HERD", "variable": label, "source": "NCSES HERD FY2024",
            "source_locator": f"ncses_inst_id=U3284001; row={label}",
            "official_value": expected, "display_data_value": actual,
            "unit": "thousands of dollars", "result": "match" if expected == actual else "mismatch"
        })
    for kind, values, site_values in [("personnel", personnel, focal["herd"]["personnel"]), ("fte", ftes, focal["herd"]["fte"])]:
        expected = values.get("Total")
        actual = site_values.get("Total")
        rows.append({
            "page": "Research HERD", "variable": f"total_{kind}", "source": "NCSES HERD FY2024",
            "source_locator": f"ncses_inst_id=U3284001; {kind}; column=Total",
            "official_value": expected, "display_data_value": actual,
            "unit": "people" if kind == "personnel" else "FTE", "result": "match" if expected == actual else "mismatch"
        })
    write_csv(DATA / "reconciliation.csv", [
        "page", "variable", "source", "source_locator", "official_value",
        "display_data_value", "unit", "result"
    ], rows)
    return rows


def download_rows(atlas, page):
    fields = ["institution", "unitid", "boundary_id", "peer_provenance", "data_year",
              "release_vintage", "variable", "value", "unit", "reporting_period",
              "suppression_status", "boundary_status"]
    peer_ids = atlas["peerModes"]["DFR_SUBMITTED"]["unitids"]
    records = [atlas["records"]["130943"], *[atlas["records"][unitid] for unitid in peer_ids]]
    rows = []
    if page == "ipeds":
        for record in records:
            fact = record["ipedsHistory"]["IPEDS_EF2023A"]
            for variable, key in [("total_enrollment", "totalEnrollment"), ("undergraduate_enrollment", "undergraduate"), ("graduate_enrollment", "graduate"), ("full_time_enrollment", "fullTime")]:
                value = fact.get(key)
                rows.append({"institution": record["name"], "unitid": record["unitid"], "boundary_id": "CORE", "peer_provenance": "Submitted DFR group", "data_year": "2023", "release_vintage": "IPEDS_EF2023A", "variable": variable, "value": "" if value is None else value, "unit": "students", "reporting_period": "Fall 2023", "suppression_status": "missing" if value is None else "reported", "boundary_status": "exact"})
    else:
        for record in records:
            exact = record["unitid"] == "130943" or record["herd"]["coverage"] == "present_exact_unitid"
            value = record["herd"].get("total") if exact else None
            rows.append({"institution": record["name"], "unitid": record["unitid"], "boundary_id": "CORE", "peer_provenance": "Submitted DFR group", "data_year": "2024", "release_vintage": "NCSES_HERD_FY2024", "variable": "total_r_and_d_expenditures", "value": "" if value is None else value, "unit": "thousands of dollars", "reporting_period": "Institutional fiscal year 2024", "suppression_status": "missing" if record["herd"].get("total") is None else "reported", "boundary_status": "exact" if exact else "conditional_not_compared"})
    write_csv(DATA / "downloads" / f"university-of-delaware-{page}-submitted-dfr.csv", fields, rows)
    return fields, rows


def validate_ratios(invalid=False):
    ratios = [
        {"id": "undergraduate_share", "numerator": {"source": "IPEDS_EF2023A", "boundary": "CORE", "period": "Fall 2023", "population": "all enrolled students"}, "denominator": {"source": "IPEDS_EF2023A", "boundary": "CORE", "period": "Fall 2023", "population": "all enrolled students"}},
        {"id": "federal_research_share", "numerator": {"source": "NCSES_HERD_FY2024", "boundary": "CORE", "period": "Institutional fiscal year 2024", "population": "separately accounted R&D expenditures"}, "denominator": {"source": "NCSES_HERD_FY2024", "boundary": "CORE", "period": "Institutional fiscal year 2024", "population": "separately accounted R&D expenditures"}},
    ]
    if invalid:
        ratios.append({"id": "invalid_research_per_student_fixture", "numerator": {"source": "NCSES_HERD_FY2024", "boundary": "CORE", "period": "Institutional fiscal year 2024", "population": "separately accounted R&D expenditures"}, "denominator": {"source": "IPEDS_EF2023A", "boundary": "CORE", "period": "Fall 2023", "population": "all enrolled students"}})
    write_json(DATA / "metric-definitions.json", {"standard_ratios": ratios[:2], "validation_dimensions": ["source", "boundary", "period", "population"]})
    failures = []
    for ratio in ratios:
        mismatches = [key for key in ["source", "boundary", "period", "population"] if ratio["numerator"][key] != ratio["denominator"][key]]
        if mismatches:
            failures.append({"metric": ratio["id"], "mismatches": mismatches})
    return failures


def validate_static(atlas):
    failures = []
    required = [DIST / name for name in ["index.html", "ipeds.html", "herd.html", "styles.css", "app.js", "atlas-data.js"]]
    failures.extend([f"missing {path.name}" for path in required if not path.exists()])
    search_files = [*DIST.glob("*.html"), DIST / "app.js"]
    banned = "official" + " peer group"
    if any(banned in path.read_text(encoding="utf-8").lower() for path in search_files):
        failures.append("banned peer-label phrase is present")
    app = (DIST / "app.js").read_text(encoding="utf-8")
    ipeds_html = (DIST / "ipeds.html").read_text(encoding="utf-8")
    for token in ["boundary_id", "peer_provenance", "data_year", "release_vintage", "unit", "reporting_period", "suppression_status"]:
        if token not in app:
            failures.append(f"download field missing: {token}")
    for token in ["Reported zero", "Missing", "Suppressed", "excluded from calculations"]:
        if token not in ipeds_html:
            failures.append(f"state display evidence missing: {token}")
    if "boundary-disabled" not in app or "Source panels are disabled" not in app:
        failures.append("boundary disable rule missing")
    if not atlas.get("ipedsVintages") or len(atlas["ipedsVintages"]) < 2:
        failures.append("prior IPEDS vintage is not queryable")
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exercise-invalid-ratio", action="store_true")
    args = parser.parse_args()
    atlas = read_atlas()
    diff_count = build_vintage_artifacts(atlas)
    reconciliation = official_reconciliation(atlas)
    ipeds_fields, ipeds_rows = download_rows(atlas, "ipeds")
    herd_fields, herd_rows = download_rows(atlas, "herd")
    failures = validate_static(atlas)
    failures.extend([f"reconciliation mismatch: {row['page']} {row['variable']}" for row in reconciliation if row["result"] != "match"])
    if diff_count == 0:
        failures.append("new-vintage diff is empty")
    ratio_failures = validate_ratios(args.exercise_invalid_ratio)
    failures.extend([f"ratio {row['metric']} mismatches {', '.join(row['mismatches'])}" for row in ratio_failures])
    summary = {
        "status": "failed" if failures else "passed",
        "atlas_sha256": hashlib.sha256((DIST / "atlas-data.js").read_bytes()).hexdigest(),
        "reconciled_values": len(reconciliation),
        "vintage_diff_rows": diff_count,
        "download_rows": {"ipeds": len(ipeds_rows), "herd": len(herd_rows)},
        "download_fields": ipeds_fields,
        "failures": failures,
    }
    if not args.exercise_invalid_ratio:
        write_json(DATA / "validation-results.json", summary)
    print(json.dumps(summary, indent=2))
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
