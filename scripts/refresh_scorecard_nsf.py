import argparse
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ATLAS = json.loads((DATA / "atlas.json").read_text(encoding="utf-8-sig"))
USER_AGENT = "InstitutionAtlas/1.0 (public-data refresh)"
TODAY = date.today()
parser = argparse.ArgumentParser()
parser.add_argument("--record-review", action="store_true", help="Update the visible monthly maintenance record and source contract dates.")
args = parser.parse_args()


def get_json(url, attempts=4):
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def scorecard_snapshot():
    institution_metrics = [
        "student.size",
        "cost.tuition.in_state",
        "cost.tuition.out_of_state",
        "cost.avg_net_price.overall",
        "aid.pell_grant_rate",
        "aid.federal_loan_rate",
        "completion.rate_suppressed.four_year",
        "student.retention_rate.four_year.full_time",
        "admissions.admission_rate.overall",
    ]
    outcome_metrics = ["earnings.10_yrs_after_entry.median", "aid.median_debt.completers.overall"]
    institution_years = range(2024, TODAY.year + 1)
    outcome_years = range(2020, TODAY.year + 1)
    metric_paths = [f"{year}.{metric}" for year in institution_years for metric in institution_metrics]
    metric_paths.extend(f"{year}.{metric}" for year in outcome_years for metric in outcome_metrics)
    field_names = ["id", "school.name", "school.ownership", "ope6_id", "ope8_id", *metric_paths]
    unitids = [ATLAS["institution"]["unitid"], *ATLAS["peerModes"]["DFR_SUBMITTED"]["unitids"]]
    params = {
        "id": ",".join(unitids),
        "fields": ",".join(field_names),
        "per_page": 100,
        "api_key": os.environ.get("COLLEGE_SCORECARD_API_KEY", "DEMO_KEY"),
    }
    url = "https://api.data.gov/ed/collegescorecard/v1/schools.json?" + urllib.parse.urlencode(params)
    payload = get_json(url)
    if payload.get("metadata", {}).get("total") != len(unitids):
        raise RuntimeError(f"Expected {len(unitids)} Scorecard records; received {payload.get('metadata', {}).get('total')}")
    focal_raw = next(row for row in payload["results"] if str(row["id"]) == ATLAS["institution"]["unitid"])
    year = max(year for year in institution_years if all(focal_raw.get(f"{year}.{metric}") is not None for metric in institution_metrics))
    cohort_year = max(year for year in outcome_years if all(focal_raw.get(f"{year}.{metric}") is not None for metric in outcome_metrics))
    records = []
    for row in payload["results"]:
        records.append(
            {
                "unitid": str(row["id"]),
                "name": row["school.name"],
                "ownership": row.get("school.ownership"),
                "opeid6": row.get("ope6_id"),
                "opeid8": row.get("ope8_id"),
                "undergraduate_enrollment": row.get(f"{year}.student.size"),
                "in_state_tuition": row.get(f"{year}.cost.tuition.in_state"),
                "out_of_state_tuition": row.get(f"{year}.cost.tuition.out_of_state"),
                "average_net_price": row.get(f"{year}.cost.avg_net_price.overall"),
                "pell_grant_rate": row.get(f"{year}.aid.pell_grant_rate"),
                "federal_loan_rate": row.get(f"{year}.aid.federal_loan_rate"),
                "completion_rate_150": row.get(f"{year}.completion.rate_suppressed.four_year"),
                "retention_rate_full_time": row.get(f"{year}.student.retention_rate.four_year.full_time"),
                "admission_rate": row.get(f"{year}.admissions.admission_rate.overall"),
                "median_earnings_10_year": row.get(f"{cohort_year}.earnings.10_yrs_after_entry.median"),
                "median_debt_completers": row.get(f"{cohort_year}.aid.median_debt.completers.overall"),
            }
        )
    records.sort(key=lambda row: (row["unitid"] != ATLAS["institution"]["unitid"], row["name"]))
    return {
        "schema_version": "1.0.0",
        "retrieved_at": TODAY.isoformat(),
        "source": "U.S. Department of Education College Scorecard API",
        "institution_year": year,
        "outcomes_cohort_file_year": cohort_year,
        "focal_unitid": ATLAS["institution"]["unitid"],
        "record_count": len(records),
        "fields": field_names,
        "query_without_key": "https://api.data.gov/ed/collegescorecard/v1/schools.json?" + urllib.parse.urlencode({key: value for key, value in params.items() if key != "api_key"}),
        "official_profile_url": "https://collegescorecard.ed.gov/school/?130943-University-of-Delaware",
        "documentation_url": "https://collegescorecard.ed.gov/files/InstitutionDataDocumentation.pdf",
        "data_url": "https://collegescorecard.ed.gov/data/",
        "records": records,
    }


def fetch_nsf_pages(params):
    base = "https://api.nsf.gov/services/v1/awards.json"
    first_params = {**params, "rpp": 25, "offset": 0}
    first = get_json(base + "?" + urllib.parse.urlencode(first_params))
    response = first.get("response", {})
    if response.get("serviceNotification"):
        raise RuntimeError(response["serviceNotification"])
    metadata = response["metadata"]
    rows = list(response.get("award") or [])
    for offset in range(25, int(metadata["totalCount"]), 25):
        page_params = {**params, "rpp": 25, "offset": offset}
        page = get_json(base + "?" + urllib.parse.urlencode(page_params))
        rows.extend(page.get("response", {}).get("award") or [])
    if len(rows) != int(metadata["totalCount"]):
        raise RuntimeError(f"Expected {metadata['totalCount']} NSF records; received {len(rows)}")
    return rows, int(metadata["totalCount"])


def parse_money(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_date(value):
    return datetime.strptime(value, "%m/%d/%Y").date() if value else date.min


def nsf_snapshot():
    uei = "T72NHKM259N3"
    recent_start = "01/01/2022"
    recent_end = TODAY.strftime("%m/%d/%Y")
    active_rows, active_count = fetch_nsf_pages({"ueiNumber": uei, "ActiveAwards": "True"})
    recent_rows, recent_count = fetch_nsf_pages({"ueiNumber": uei, "dateStart": recent_start, "dateEnd": recent_end})
    years = {}
    for row in recent_rows:
        award_date = parse_date(row.get("date"))
        bucket = years.setdefault(str(award_date.year), {"award_count": 0, "estimated_total_amount": 0, "funds_obligated_amount": 0})
        bucket["award_count"] += 1
        bucket["estimated_total_amount"] += parse_money(row.get("estimatedTotalAmt"))
        bucket["funds_obligated_amount"] += parse_money(row.get("fundsObligatedAmt"))
    directorates = {}
    for row in active_rows:
        label = row.get("orgLongName") or row.get("dirAbbr") or "Not reported"
        bucket = directorates.setdefault(label, {"award_count": 0, "estimated_total_amount": 0})
        bucket["award_count"] += 1
        bucket["estimated_total_amount"] += parse_money(row.get("estimatedTotalAmt"))
    recent_rows.sort(key=lambda row: (parse_date(row.get("date")), row.get("id", "")), reverse=True)
    awards = []
    for row in recent_rows[:20]:
        award_id = row.get("id")
        awards.append(
            {
                "award_id": award_id,
                "title": row.get("title"),
                "award_date": row.get("date"),
                "start_date": row.get("startDate"),
                "expiration_date": row.get("expDate"),
                "estimated_total_amount": parse_money(row.get("estimatedTotalAmt")),
                "funds_obligated_amount": parse_money(row.get("fundsObligatedAmt")),
                "directorate": row.get("orgLongName") or row.get("dirAbbr"),
                "division": row.get("orgLongName2") or row.get("divAbbr"),
                "program": row.get("fundProgramName"),
                "transaction_type": row.get("transType"),
                "active": str(row.get("activeAwd", "")).lower() == "true",
                "official_record_url": f"https://api.nsf.gov/services/v1/awards/{award_id}.json",
            }
        )
    return {
        "schema_version": "1.0.0",
        "retrieved_at": TODAY.isoformat(),
        "source": "U.S. National Science Foundation Awards API",
        "focal_uei": uei,
        "all_time_record_count": int(get_json(f"https://api.nsf.gov/services/v1/awards.json?ueiNumber={uei}&rpp=1")["response"]["metadata"]["totalCount"]),
        "active_award_count": active_count,
        "active_estimated_total_amount": sum(parse_money(row.get("estimatedTotalAmt")) for row in active_rows),
        "active_funds_obligated_amount": sum(parse_money(row.get("fundsObligatedAmt")) for row in active_rows),
        "recent_period_start": "2022-01-01",
        "recent_period_end": TODAY.isoformat(),
        "recent_award_count": recent_count,
        "recent_estimated_total_amount": sum(parse_money(row.get("estimatedTotalAmt")) for row in recent_rows),
        "recent_funds_obligated_amount": sum(parse_money(row.get("fundsObligatedAmt")) for row in recent_rows),
        "year_summary": [{"year": year, **values} for year, values in sorted(years.items())],
        "active_directorates": [{"directorate": name, **values} for name, values in sorted(directorates.items(), key=lambda item: (-item[1]["award_count"], item[0]))],
        "recent_awards": awards,
        "query_urls": {
            "all": f"https://api.nsf.gov/services/v1/awards.json?ueiNumber={uei}",
            "active": f"https://api.nsf.gov/services/v1/awards.json?ueiNumber={uei}&ActiveAwards=True",
            "recent": f"https://api.nsf.gov/services/v1/awards.json?ueiNumber={uei}&dateStart={urllib.parse.quote(recent_start)}&dateEnd={urllib.parse.quote(recent_end)}",
            "documentation": "https://resources.research.gov/common/webapi/awardapisearch-v1.htm",
        },
    }


def record_review(scorecard, nsf):
    contracts_path = DATA / "source-contracts.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8-sig"))
    for contract in contracts:
        if contract["source_id"] == "SCORECARD_INSTITUTION":
            contract["last_verified_date"] = TODAY.isoformat()
            contract["vintage_identifier"] = f'SCORECARD_API_{TODAY.isoformat()}'
            contract["reporting_period_definition"] = f'The page uses {scorecard["institution_year"]} institution metrics and the latest common nonmissing {scorecard["outcomes_cohort_file_year"]} file-year earnings and debt measures. The source field and year remain attached to every displayed value.'
        elif contract["source_id"] == "NSF_AWARDS":
            contract["last_verified_date"] = TODAY.isoformat()
            contract["vintage_identifier"] = f'NSF_AWARDS_{TODAY.isoformat()}'
    contracts_path.write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    maintenance_path = DATA / "maintenance-log.json"
    maintenance = json.loads(maintenance_path.read_text(encoding="utf-8-sig"))
    maintenance["last_completed_review"] = {
        "date": TODAY.isoformat(),
        "date_display": TODAY.strftime("%d %b %Y").lstrip("0"),
        "result": "College Scorecard and NSF Awards API snapshots refreshed and validated",
    }
    entry = {
        "date": TODAY.isoformat(),
        "type": "Automated source refresh",
        "owner": maintenance["owner"],
        "result": "Passed",
        "details": f'College Scorecard returned {scorecard["record_count"]} institution records for file year {scorecard["institution_year"]}. NSF returned {nsf["active_award_count"]} active and {nsf["recent_award_count"]} recent exact-UEI award records.',
    }
    maintenance["history"] = [row for row in maintenance["history"] if not (row.get("date") == entry["date"] and row.get("type") == entry["type"])]
    maintenance["history"].insert(0, entry)
    maintenance_path.write_text(json.dumps(maintenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    coverage_path = DATA / "SOURCE_COVERAGE_MATRIX.csv"
    with coverage_path.open(encoding="utf-8-sig", newline="") as handle:
        coverage = list(csv.DictReader(handle))
        fieldnames = list(coverage[0])
    for row in coverage:
        if row["source_id"] == "SCORECARD_INSTITUTION":
            row["verified_date"] = TODAY.isoformat()
            row["reason"] = f'File year {scorecard["institution_year"]} covers Delaware and all {scorecard["record_count"] - 1} submitted DFR peers; focal outcomes retain file year {scorecard["outcomes_cohort_file_year"]}'
        elif row["source_id"] == "NSF_AWARDS":
            row["verified_date"] = TODAY.isoformat()
            row["reason"] = f'Exact-UEI snapshot returned {nsf["all_time_record_count"]} historical records and {nsf["active_award_count"]} active records; counts describe API coverage and current status'
    with coverage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(coverage)


scorecard = scorecard_snapshot()
nsf = nsf_snapshot()
(DATA / "scorecard.json").write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(DATA / "nsf-awards.json").write_text(json.dumps(nsf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if args.record_review:
    record_review(scorecard, nsf)
print(json.dumps({"scorecard_records": scorecard["record_count"], "nsf_all_time": nsf["all_time_record_count"], "nsf_active": nsf["active_award_count"], "nsf_recent": nsf["recent_award_count"], "retrieved_at": TODAY.isoformat()}, indent=2))
