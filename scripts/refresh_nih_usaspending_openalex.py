import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TODAY = date.today().isoformat()
FISCAL_YEARS = list(range(date.today().year - 4, date.today().year + 1))
START_DATE = f"{FISCAL_YEARS[0] - 1}-10-01"
END_DATE = f"{FISCAL_YEARS[-1]}-09-30"
UEI = "T72NHKM259N3"
NIH_ORG_NAME = "UNIVERSITY OF DELAWARE"
NIH_IPF = "2076701"
OPENALEX_ID = "I86501945"
ROR = "https://ror.org/01sbq1a82"
USER_AGENT = "InstitutionAtlas/1.0 (https://nilkamal11.github.io/institution-atlas/)"


def request_json(url, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def write_json(name, payload):
    (DATA / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_nih_record(row):
    organization = row.get("organization") or {}
    admin = row.get("agency_ic_admin") or {}
    investigators = row.get("principal_investigators") or []
    return {
        "appl_id": row.get("appl_id"),
        "fiscal_year": row.get("fiscal_year"),
        "project_num": row.get("project_num"),
        "core_project_num": row.get("core_project_num"),
        "project_title": row.get("project_title"),
        "activity_code": row.get("activity_code"),
        "award_amount": row.get("award_amount"),
        "award_notice_date": row.get("award_notice_date"),
        "project_start_date": row.get("project_start_date"),
        "project_end_date": row.get("project_end_date"),
        "admin_ic_code": admin.get("code"),
        "admin_ic_name": admin.get("name"),
        "principal_investigators": [person.get("full_name") for person in investigators if person.get("full_name")],
        "org_name": organization.get("org_name"),
        "org_ipf_code": str(organization.get("org_ipf_code") or ""),
        "primary_uei": organization.get("primary_uei"),
        "primary_duns": organization.get("primary_duns"),
        "official_record_url": f'https://reporter.nih.gov/project-details/{row.get("appl_id")}',
    }


def fetch_nih():
    endpoint = "https://api.reporter.nih.gov/v2/projects/search"
    fields = [
        "ApplId", "FiscalYear", "ProjectNum", "CoreProjectNum", "ProjectTitle",
        "AwardAmount", "Organization", "PrincipalInvestigators", "AgencyIcAdmin",
        "ActivityCode", "ProjectStartDate", "ProjectEndDate", "AwardNoticeDate",
    ]
    records = []
    offset = 0
    total = None
    search_url = None
    while total is None or offset < total:
        response = request_json(endpoint, {
            "criteria": {"org_names_exact_match": [NIH_ORG_NAME], "fiscal_years": FISCAL_YEARS},
            "include_fields": fields,
            "offset": offset,
            "limit": 500,
            "sort_field": "fiscal_year",
            "sort_order": "desc",
        })
        meta = response["meta"]
        total = int(meta["total"])
        raw_search_url = (meta.get("properties") or {}).get("URL")
        if raw_search_url:
            search_url = raw_search_url.replace("https:/reporter", "https://reporter")
        batch = [normalize_nih_record(row) for row in response.get("results", [])]
        records.extend(batch)
        offset += len(batch)
        if not batch:
            break
    if len(records) != total:
        raise RuntimeError(f"NIH RePORTER pagination returned {len(records)} of {total} records")
    mismatches = [row for row in records if row["org_name"] != NIH_ORG_NAME or row["org_ipf_code"] != NIH_IPF or row["primary_uei"] != UEI]
    if mismatches:
        raise RuntimeError(f"NIH identifier mismatch in {len(mismatches)} records")

    by_year = []
    for year in FISCAL_YEARS:
        rows = [row for row in records if row["fiscal_year"] == year]
        by_year.append({
            "fiscal_year": year,
            "application_records": len(rows),
            "award_amount": sum(row["award_amount"] or 0 for row in rows),
            "core_projects": len({row["core_project_num"] for row in rows if row["core_project_num"]}),
        })
    admin_totals = defaultdict(lambda: {"application_records": 0, "award_amount": 0})
    for row in records:
        key = row["admin_ic_name"] or row["admin_ic_code"] or "Not reported"
        admin_totals[key]["application_records"] += 1
        admin_totals[key]["award_amount"] += row["award_amount"] or 0
    admin_summary = [
        {"admin_ic": key, **value}
        for key, value in sorted(admin_totals.items(), key=lambda item: item[1]["award_amount"], reverse=True)
    ]
    recent = sorted(records, key=lambda row: (row["award_notice_date"] or "", row["appl_id"] or 0), reverse=True)[:20]
    return {
        "source_id": "NIH_REPORTER",
        "retrieved_at": TODAY,
        "organization": NIH_ORG_NAME,
        "org_ipf_code": NIH_IPF,
        "uei": UEI,
        "duns": "059007500",
        "fiscal_years": FISCAL_YEARS,
        "record_grain": "one funded application record by appl_id and fiscal year",
        "record_count": len(records),
        "distinct_core_projects": len({row["core_project_num"] for row in records if row["core_project_num"]}),
        "award_amount": sum(row["award_amount"] or 0 for row in records),
        "year_summary": by_year,
        "admin_ic_summary": admin_summary,
        "recent_records": recent,
        "records": records,
        "query_urls": {
            "api": endpoint,
            "search_results": search_url or "https://reporter.nih.gov/advanced-search",
            "documentation": "https://api.reporter.nih.gov/",
        },
    }


AWARD_TYPES = ["A", "B", "C", "D", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "-1", "F001", "F002", "F003", "F004", "F005", "F006", "F007", "F008", "F009", "F010"]
AWARD_GROUPS = {
    "contracts": ["A", "B", "C", "D"],
    "grants": ["02", "03", "04", "05", "F001", "F002"],
}


def usaspending_filters(types=None):
    return {
        "recipient_search_text": [UEI],
        "time_period": [{"start_date": START_DATE, "end_date": END_DATE}],
        "award_type_codes": types or AWARD_TYPES,
    }


def fetch_usaspending():
    base = "https://api.usaspending.gov/api/v2"
    recipient = request_json(f"{base}/recipient/", {
        "keyword": UEI, "award_type": "all", "limit": 20, "page": 1, "sort": "amount", "order": "desc"
    })
    matches = [row for row in recipient["results"] if row.get("uei") == UEI and row.get("name") == NIH_ORG_NAME and row.get("recipient_level") == "R"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one exact USAspending recipient, found {len(matches)}")
    recipient_record = matches[0]

    over_time = request_json(f"{base}/search/spending_over_time/", {
        "group": "fiscal_year", "filters": usaspending_filters()
    })
    year_rows = []
    for row in over_time["results"]:
        year_rows.append({
            "fiscal_year": int(row["time_period"]["fiscal_year"]),
            "obligations": row["aggregated_amount"],
            "contract_obligations": row["Contract_Obligations"],
            "direct_obligations": row["Direct_Obligations"],
            "grant_obligations": row["Grant_Obligations"],
            "loan_obligations": row["Loan_Obligations"],
            "other_obligations": row["Other_Obligations"],
        })
    year_rows.sort(key=lambda row: row["fiscal_year"])
    if [row["fiscal_year"] for row in year_rows] != FISCAL_YEARS:
        raise RuntimeError("USAspending fiscal-year coverage differs from the requested window")

    counts = request_json(f"{base}/search/spending_by_award_count/", {"filters": usaspending_filters()})["results"]
    agencies = request_json(f"{base}/search/spending_by_category/awarding_agency/", {
        "filters": usaspending_filters(), "category": "awarding_agency", "limit": 25, "page": 1
    })["results"]

    selected_awards = []
    fields = ["Award ID", "Recipient Name", "Recipient UEI", "Awarding Agency", "Awarding Sub Agency", "Start Date", "End Date", "Award Amount", "Total Outlays", "Description", "generated_internal_id"]
    for group, types in AWARD_GROUPS.items():
        response = request_json(f"{base}/search/spending_by_award/", {
            "filters": usaspending_filters(types),
            "fields": fields,
            "page": 1,
            "limit": 100,
            "sort": "Award Amount",
            "order": "desc",
            "spending_level": "awards",
        })
        for row in response["results"]:
            if row.get("Recipient UEI") != UEI:
                raise RuntimeError(f"USAspending recipient mismatch on {row.get('Award ID')}")
            internal = row.get("generated_internal_id")
            selected_awards.append({
                "award_group": group,
                "award_id": row.get("Award ID"),
                "recipient_name": row.get("Recipient Name"),
                "recipient_uei": row.get("Recipient UEI"),
                "awarding_agency": row.get("Awarding Agency"),
                "awarding_sub_agency": row.get("Awarding Sub Agency"),
                "start_date": row.get("Start Date"),
                "end_date": row.get("End Date"),
                "award_amount": row.get("Award Amount"),
                "total_outlays": row.get("Total Outlays"),
                "description": row.get("Description"),
                "generated_internal_id": internal,
                "official_record_url": f"https://www.usaspending.gov/award/{internal}/latest" if internal else None,
            })
    selected_awards.sort(key=lambda row: row["award_amount"] or 0, reverse=True)
    top_awards = selected_awards[:20]
    type_totals = Counter()
    for row in year_rows:
        type_totals["Contracts"] += row["contract_obligations"] or 0
        type_totals["Direct payments"] += row["direct_obligations"] or 0
        type_totals["Grants"] += row["grant_obligations"] or 0
        type_totals["Loans"] += row["loan_obligations"] or 0
        type_totals["Other"] += row["other_obligations"] or 0
    profile_url = f'https://www.usaspending.gov/recipient/{recipient_record["id"]}/latest'
    return {
        "source_id": "USASPENDING",
        "retrieved_at": TODAY,
        "recipient_name": NIH_ORG_NAME,
        "uei": UEI,
        "duns": recipient_record.get("duns"),
        "recipient_id": recipient_record["id"],
        "fiscal_years": FISCAL_YEARS,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "record_grain": "obligation trends are transaction aggregates; award counts and listed records are prime-award grain",
        "year_summary": year_rows,
        "five_year_obligations": sum(row["obligations"] or 0 for row in year_rows),
        "type_obligations": [{"award_type": label, "obligations": amount} for label, amount in type_totals.most_common()],
        "award_counts": counts,
        "prime_award_count": sum(counts.values()),
        "awarding_agencies": agencies,
        "largest_prime_awards": top_awards,
        "query_urls": {
            "recipient_profile": profile_url,
            "api_documentation": "https://api.usaspending.gov/docs/endpoints",
            "recipient_api": f"{base}/recipient/",
            "spending_over_time_api": f"{base}/search/spending_over_time/",
        },
    }


def openalex_group(filter_value, group_by):
    query = urlencode({"filter": filter_value, "group_by": group_by, "per_page": 200})
    return request_json(f"https://api.openalex.org/works?{query}")


def fetch_openalex():
    institution = request_json(f"https://api.openalex.org/institutions/{OPENALEX_ID}")
    if institution.get("ror") != ROR or institution.get("display_name") != "University of Delaware":
        raise RuntimeError("OpenAlex institution record does not match the reviewed ROR")
    start_year, end_year = 2021, 2025
    filter_value = f"authorships.institutions.id:{OPENALEX_ID},from_publication_date:{start_year}-01-01,to_publication_date:{end_year}-12-31"
    groups = {
        "year_summary": openalex_group(filter_value, "publication_year"),
        "open_access_summary": openalex_group(filter_value, "open_access.oa_status"),
        "type_summary": openalex_group(filter_value, "type"),
        "domain_summary": openalex_group(filter_value, "primary_topic.domain.id"),
        "field_summary": openalex_group(filter_value, "primary_topic.field.id"),
    }
    counts = {name: response["meta"]["count"] for name, response in groups.items()}
    if len(set(counts.values())) != 1:
        raise RuntimeError(f"OpenAlex grouped counts disagree: {counts}")
    total = next(iter(counts.values()))
    oa_count = sum(row["count"] for row in groups["open_access_summary"]["group_by"] if row["key_display_name"] != "closed")
    topic_count = sum(row["count"] for row in groups["domain_summary"]["group_by"])

    def cleaned(response, limit=None):
        rows = [{"id": row["key"].replace("https://openalex.org/", "https://api.openalex.org/"), "label": row["key_display_name"], "works": row["count"]} for row in response["group_by"]]
        return rows if limit is None else rows[:limit]

    api_query = "https://api.openalex.org/works?" + urlencode({"filter": filter_value, "group_by": "publication_year", "per_page": 200})
    return {
        "source_id": "OPENALEX",
        "retrieved_at": TODAY,
        "institution_name": institution["display_name"],
        "openalex_id": OPENALEX_ID,
        "ror": ROR,
        "record_grain": "one OpenAlex work with at least one authorship linked to the exact OpenAlex institution record",
        "window_start": f"{start_year}-01-01",
        "window_end": f"{end_year}-12-31",
        "works_count": total,
        "open_access_works": oa_count,
        "topic_classified_works": topic_count,
        "year_summary": sorted(cleaned(groups["year_summary"]), key=lambda row: int(row["label"])),
        "open_access_summary": cleaned(groups["open_access_summary"]),
        "type_summary": cleaned(groups["type_summary"], 12),
        "domain_summary": cleaned(groups["domain_summary"]),
        "field_summary": cleaned(groups["field_summary"], 12),
        "institution_profile": {
            "works_count": institution.get("works_count"),
            "cited_by_count": institution.get("cited_by_count"),
            "updated_date": institution.get("updated_date"),
        },
        "boundary_note": "Exact OpenAlex institution I86501945 only. ROR child and related organizations are not rolled into these counts.",
        "query_urls": {
            "institution": f"https://api.openalex.org/institutions/{OPENALEX_ID}",
            "institution_api": f"https://api.openalex.org/institutions/{OPENALEX_ID}",
            "works_api": api_query,
            "documentation": "https://docs.openalex.org/",
            "ror": ROR,
        },
    }


def update_review_metadata():
    contracts_path = DATA / "source-contracts.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8-sig"))
    for row in contracts:
        if row["source_id"] in {"NIH_REPORTER", "USASPENDING", "OPENALEX"}:
            row["last_verified_date"] = TODAY
            row["last_verified_by"] = "Nil Shah"
    contracts_path.write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    maintenance_path = DATA / "maintenance-log.json"
    maintenance = json.loads(maintenance_path.read_text(encoding="utf-8-sig"))
    maintenance["last_completed_review"] = {
        "date": TODAY,
        "date_display": date.today().strftime("%d %b %Y"),
        "result": "NIH RePORTER, USAspending, and OpenAlex snapshots refreshed and validated",
    }
    maintenance["history"].insert(0, {
        "date": TODAY,
        "type": "Source-page expansion",
        "owner": "Nil Shah",
        "result": "Completed",
        "details": "Refreshed exact-identifier NIH RePORTER, USAspending, and OpenAlex snapshots and rebuilt source pages.",
    })
    maintenance_path.write_text(json.dumps(maintenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Refresh NIH RePORTER, USAspending, and OpenAlex atlas snapshots.")
    parser.add_argument("--record-review", action="store_true", help="Update review dates and maintenance history.")
    args = parser.parse_args()

    nih = fetch_nih()
    usaspending = fetch_usaspending()
    openalex = fetch_openalex()
    write_json("nih-reporter.json", nih)
    write_json("usaspending.json", usaspending)
    write_json("openalex.json", openalex)
    if args.record_review:
        update_review_metadata()
    print(json.dumps({
        "status": "refreshed",
        "retrieved_at": TODAY,
        "nih_application_records": nih["record_count"],
        "usaspending_prime_awards": usaspending["prime_award_count"],
        "openalex_works_2021_2025": openalex["works_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
