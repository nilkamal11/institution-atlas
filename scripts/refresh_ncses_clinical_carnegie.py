"""Refresh NCSES profile, ClinicalTrials.gov, and Carnegie snapshots.

The script deliberately uses only the Python standard library so it can run in
the scheduled GitHub Action without an installation step.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NCSES_ID = "U3284001"
NCSES_PROFILE = f"https://ncsesdata.nsf.gov/profiles/site?method=view&tin={NCSES_ID}"
NCSES_DOWNLOAD = f"https://ncsesdata.nsf.gov/profiles/site?method=download&tin={NCSES_ID}"
CARNEGIE_URL = "https://carnegieclassifications.acenet.edu/institution/university-of-delaware/"
CLINICAL_API = "https://clinicaltrials.gov/api/v2/studies"
USER_AGENT = "institution-atlas/1.0 (public-data refresh; github.com/nilkamal11/institution-atlas)"
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_json(url: str) -> dict:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def write_json(name: str, payload: dict) -> None:
    (DATA / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group(0)
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - 64
    return value - 1


def xlsx_rows(archive: zipfile.ZipFile, member: str) -> list[list[object]]:
    with zipfile.ZipFile(archive.open(member)) as workbook:
        shared = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall(XML_NS + "si"):
                shared.append("".join(node.text or "" for node in item.iter(XML_NS + "t")))
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//" + XML_NS + "row"):
            values: dict[int, object] = {}
            for cell in row.findall(XML_NS + "c"):
                index = column_number(cell.attrib["r"])
                raw = cell.find(XML_NS + "v")
                if raw is None:
                    value = None
                elif cell.attrib.get("t") == "s":
                    value = shared[int(raw.text)]
                else:
                    try:
                        numeric = float(raw.text)
                        value = int(numeric) if numeric.is_integer() else numeric
                    except (TypeError, ValueError):
                        value = raw.text
                values[index] = value
            width = max(values, default=-1) + 1
            rows.append([values.get(index) for index in range(width)])
        return rows


def row_by_label(rows: list[list[object]], label: str) -> list[object]:
    for row in rows:
        if row and str(row[0]).strip() == label:
            return row
    raise KeyError(f"Row not found: {label}")


def time_series(rows: list[list[object]], label: str, alternating: bool = True, header_index: int = 2) -> list[dict]:
    headers = rows[header_index]
    values = row_by_label(rows, label)
    step = 2 if alternating else 1
    result = []
    for index in range(1, min(len(headers), len(values)), step):
        year = headers[index]
        value = values[index]
        if year in (None, "") or value in (None, "", "."):
            continue
        result.append({"year": int(year), "value": int(value)})
    return result


class SummaryTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.cell_attrs = {}
        self.text = []
        self.cells = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "table" and attr.get("id") == "institution_summary":
            self.in_table = True
        elif self.in_table and tag in {"th", "td"}:
            self.in_cell = True
            self.cell_attrs = attr
            self.text = []

    def handle_endtag(self, tag):
        if self.in_table and self.in_cell and tag in {"th", "td"}:
            self.cells.append((self.cell_attrs, " ".join("".join(self.text).split())))
            self.in_cell = False
        elif self.in_table and tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.text.append(data)


def ranking(profile_html: str, year: int, survey: str) -> dict:
    parser = SummaryTableParser()
    parser.feed(profile_html)
    values = {}
    prefix = f"y{year} {survey} "
    for attrs, text in parser.cells:
        headers = attrs.get("headers", "")
        if headers.startswith(prefix):
            values[headers.rsplit(" ", 1)[-1]] = text
    return {
        "year": year,
        "rank": int(values["r1" if survey == "sed" else "r2" if survey == "gss" else "r4"]),
        "percentile": float(values["p1" if survey == "sed" else "p2" if survey == "gss" else "p4"]),
        "institutions_ranked": int(values["n1" if survey == "sed" else "n2" if survey == "gss" else "n4"]),
    }


def refresh_ncses(retrieved: str) -> None:
    profile_html = fetch_bytes(NCSES_PROFILE).decode("utf-8", errors="replace")
    archive_bytes = fetch_bytes(NCSES_DOWNLOAD)
    with tempfile.TemporaryFile() as handle:
        handle.write(archive_bytes)
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            g1 = xlsx_rows(archive, f"{NCSES_ID}.g1.xlsx")
            g2 = xlsx_rows(archive, f"{NCSES_ID}.g2.xlsx")
            g3 = xlsx_rows(archive, f"{NCSES_ID}.g3.xlsx")
            g4 = xlsx_rows(archive, f"{NCSES_ID}.g4.xlsx")
            g5 = xlsx_rows(archive, f"{NCSES_ID}.g5.xlsx")
            g6 = xlsx_rows(archive, f"{NCSES_ID}.g6.xlsx")
            sed = xlsx_rows(archive, f"{NCSES_ID}.s1.xlsx")
            facilities = xlsx_rows(archive, f"{NCSES_ID}.f1.xlsx")

    gss_years = time_series(g4, "All types and sources of support")
    part_time = time_series(g2, "Science and engineering")
    health_part_time = time_series(g2, "Health")
    postdoc_se = time_series(g5, "Science and engineering")
    postdoc_health = time_series(g5, "Health")
    postdocs = [
        {"year": left["year"], "value": left["value"] + right["value"]}
        for left, right in zip(postdoc_se, postdoc_health)
    ]
    gss_fields = [
        "Agricultural and veterinary sciences",
        "Biological and biomedical sciences",
        "Computer and information sciences",
        "Geosciences, atmospheric, and ocean sciences",
        "Mathematics and statistics",
        "Physical sciences",
        "Psychology",
        "Social sciences",
        "Engineering",
        "Health",
    ]
    support_labels = ["Fellowships", "Research assistantships", "Teaching assistantships", "Other types of support"]
    gss_payload = {
        "source_id": "NCSES_GSS",
        "institution": "University of Delaware",
        "ncses_id": NCSES_ID,
        "release_year": 2024,
        "retrieved_at": retrieved,
        "profile_url": NCSES_PROFILE,
        "download_url": NCSES_DOWNLOAD,
        "technical_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=technicalNotes",
        "release_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=releaseNotes",
        "report_urls": {code: f"https://ncsesdata.nsf.gov/profiles/site?method=report&tin={NCSES_ID}&id={code}" for code in ["g1", "g2", "g3", "g4", "g5", "g6"]},
        "full_time_year_summary": gss_years,
        "part_time_year_summary": [
            {"year": left["year"], "value": left["value"] + right["value"]}
            for left, right in zip(part_time, health_part_time)
        ],
        "postdoc_year_summary": postdocs,
        "latest": {
            "full_time_graduate_students": gss_years[0]["value"],
            "part_time_graduate_students": part_time[0]["value"] + health_part_time[0]["value"],
            "postdoctorates": postdocs[0]["value"],
            "federally_supported_full_time_graduate_students": int(row_by_label(g3, "All surveyed fields")[1]),
            "federally_supported_postdoctorates": int(row_by_label(g6, "All surveyed fields")[1]),
        },
        "field_summary": [{"field": field, "full_time_students": int(row_by_label(g1, field)[1])} for field in gss_fields],
        "support_summary": [{"support_type": label, "full_time_students": int(row_by_label(g4, label)[1])} for label in support_labels],
        "ranking": ranking(profile_html, 2024, "gss"),
        "source_locators": {
            "full_time": f"{NCSES_ID}.g4.xlsx · row 4 · column 2024",
            "part_time": f"{NCSES_ID}.g2.xlsx · rows 15 and 39 · column 2024",
            "postdoctorates": f"{NCSES_ID}.g5.xlsx · rows 4 and 28 · column 2024",
            "federal_support": f"{NCSES_ID}.g3.xlsx · row 4 · column 2024",
            "federal_postdocs": f"{NCSES_ID}.g6.xlsx · row 4 · column 2024",
        },
        "boundary_note": "Counts cover the organizational units included by U. Delaware in the GSS. They describe graduate students and postdoctorates in science, engineering, and health fields, not all graduate enrollment and not named academic departments.",
        "comparability_note": "The 2017 GSS redesign changed the field taxonomy. The page emphasizes 2018 forward for trend interpretation while retaining the official ten-year table in the export.",
    }
    write_json("ncses-gss.json", gss_payload)

    sed_series = time_series(sed, "All fields", alternating=False)
    sed_fields = [
        "Agricultural sciences and natural resources",
        "Biological and biomedical sciences",
        "Computer and information sciences",
        "Engineering",
        "Geosciences, atmospheric, and ocean sciences",
        "Health sciences",
        "Mathematics and statistics",
        "Physical sciences",
        "Psychology",
        "Social sciences",
        "Non-science and engineering",
    ]
    sed_payload = {
        "source_id": "NCSES_SED",
        "institution": "University of Delaware",
        "ncses_id": NCSES_ID,
        "release_year": 2025,
        "retrieved_at": retrieved,
        "profile_url": NCSES_PROFILE,
        "download_url": NCSES_DOWNLOAD,
        "technical_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=technicalNotes",
        "release_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=releaseNotes",
        "report_url": f"https://ncsesdata.nsf.gov/profiles/site?method=report&tin={NCSES_ID}&id=s1",
        "year_summary": sed_series,
        "latest": {
            "all_fields": sed_series[0]["value"],
            "science_and_engineering": int(row_by_label(sed, "Science and engineering")[1]),
            "non_science_and_engineering": int(row_by_label(sed, "Non-science and engineering")[1]),
        },
        "field_summary": [{"field": field, "doctorates": int(row_by_label(sed, field)[1]) if row_by_label(sed, field)[1] != "." else None} for field in sed_fields],
        "ranking": ranking(profile_html, 2025, "sed"),
        "source_locators": {
            "all_fields": f"{NCSES_ID}.s1.xlsx · row 4 · column 2025",
            "science_and_engineering": f"{NCSES_ID}.s1.xlsx · row 5 · column 2025",
            "non_science_and_engineering": f"{NCSES_ID}.s1.xlsx · row 61 · column 2025",
        },
        "boundary_note": "SED counts research doctorate recipients on confirmed graduation lists submitted by U. Delaware for the academic year. They are completions, not current enrollment or alumni employment records.",
        "comparability_note": "Beginning in 2021, SED adopted a modified 2020 CIP-based field taxonomy. Field-level values before and after that change require care; the all-fields series remains visible with the source note.",
    }
    write_json("ncses-sed.json", sed_payload)

    facilities_series = time_series(facilities, "All research space", header_index=3)
    facility_rows = []
    for row in facilities[5:17]:
        if row and row[0] and row[1] not in (None, "", "."):
            facility_rows.append({"field": str(row[0]), "nasf_thousands": int(row[1])})
    facilities_payload = {
        "source_id": "NCSES_FACILITIES",
        "institution": "University of Delaware",
        "ncses_id": NCSES_ID,
        "release_year": 2023,
        "retrieved_at": retrieved,
        "profile_url": NCSES_PROFILE,
        "download_url": NCSES_DOWNLOAD,
        "technical_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=technicalNotes",
        "release_notes_url": "https://ncsesdata.nsf.gov/profiles/site?method=releaseNotes",
        "report_url": f"https://ncsesdata.nsf.gov/profiles/site?method=report&tin={NCSES_ID}&id=f1",
        "year_summary": facilities_series,
        "latest": {"research_space_nasf_thousands": facilities_series[0]["value"]},
        "field_summary": facility_rows,
        "ranking": ranking(profile_html, 2023, "fac"),
        "source_locators": {"research_space": f"{NCSES_ID}.f1.xlsx · row 5 · column 2023"},
        "boundary_note": "Research space is net assignable square feet in buildings where science and engineering research occurs. It is a capacity measure, not building gross square footage, expenditures, or the whole campus footprint.",
        "comparability_note": "Facilities is biennial. Blank years do not indicate zero, and the field categories reflect the survey rather than the university's named departments.",
    }
    write_json("ncses-facilities.json", facilities_payload)


def refresh_clinical_trials(retrieved: str) -> None:
    params = urllib.parse.urlencode({"query.spons": "University of Delaware", "pageSize": 1000, "countTotal": "true", "format": "json"})
    query_url = f"{CLINICAL_API}?{params}"
    payload = fetch_json(query_url)
    studies = []
    for study in payload.get("studies", []):
        protocol = study.get("protocolSection", {})
        identity = protocol.get("identificationModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {})
        status = protocol.get("statusModule", {})
        design = protocol.get("designModule", {})
        lead_name = sponsor.get("leadSponsor", {}).get("name", "")
        collaborators = [item.get("name", "") for item in sponsor.get("collaborators", [])]
        exact_lead = lead_name.casefold() == "university of delaware"
        exact_collaborator = any(name.casefold() == "university of delaware" for name in collaborators)
        if not (exact_lead or exact_collaborator):
            continue
        nct_id = identity.get("nctId")
        studies.append({
            "nct_id": nct_id,
            "title": identity.get("briefTitle"),
            "role": "Lead sponsor" if exact_lead else "Collaborator",
            "lead_sponsor": lead_name,
            "overall_status": status.get("overallStatus"),
            "study_type": design.get("studyType"),
            "phases": design.get("phases", []),
            "start_date": status.get("startDateStruct", {}).get("date"),
            "completion_date": status.get("completionDateStruct", {}).get("date"),
            "last_update_posted": status.get("lastUpdatePostDateStruct", {}).get("date"),
            "official_record_url": f"https://clinicaltrials.gov/study/{nct_id}",
        })
    studies.sort(key=lambda row: (row["last_update_posted"] or "", row["nct_id"]), reverse=True)
    roles = Counter(row["role"] for row in studies)
    statuses = Counter(row["overall_status"] or "Not reported" for row in studies)
    types = Counter(row["study_type"] or "Not reported" for row in studies)
    start_years = Counter((row["start_date"] or "")[:4] for row in studies if row["start_date"])
    active_statuses = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"}
    result = {
        "source_id": "CLINICALTRIALS",
        "institution": "University of Delaware",
        "retrieved_at": retrieved,
        "query_url": query_url,
        "documentation_url": "https://clinicaltrials.gov/data-api/api",
        "search_url": "https://clinicaltrials.gov/search?term=University%20of%20Delaware",
        "api_returned_count": int(payload.get("totalCount", len(payload.get("studies", [])))),
        "exact_name_record_count": len(studies),
        "lead_sponsor_count": roles["Lead sponsor"],
        "collaborator_count": roles["Collaborator"],
        "active_record_count": sum(count for key, count in statuses.items() if key in active_statuses),
        "status_summary": [{"status": key, "studies": value} for key, value in statuses.most_common()],
        "study_type_summary": [{"study_type": key, "studies": value} for key, value in types.most_common()],
        "start_year_summary": [{"year": int(key), "studies": start_years[key]} for key in sorted(start_years) if key.isdigit()],
        "recent_studies": studies[:25],
        "source_locator": "protocolSection.sponsorCollaboratorsModule.leadSponsor.name or collaborators[].name equals University of Delaware, case-insensitive",
        "boundary_note": "ClinicalTrials.gov does not supply a stable institution identifier for sponsors or collaborators. This page keeps only records whose lead-sponsor or collaborator name exactly matches University of Delaware after case normalization. It does not infer affiliates, health systems, sites, or investigator affiliations.",
        "measure_note": "Counts describe registered study records and sponsor roles at the retrieval date. They do not measure unique trials funded by the university, participants, publications, or research spending.",
    }
    write_json("clinical-trials.json", result)


def refresh_carnegie(retrieved: str) -> None:
    page = fetch_bytes(CARNEGIE_URL).decode("utf-8", errors="replace")
    match = re.search(r"var ace_carnegie_institution_data = (\{.*?\});\s*//# sourceURL", page, flags=re.S)
    if not match:
        raise RuntimeError("Carnegie institution data object not found")
    source = json.loads(match.group(1))
    meta = source["data"]["post_meta"]

    def label(key):
        return meta.get(key, {}).get("label")

    history = json.loads(label("history"))
    program_mix = []
    for index in range(1, 6):
        name = label(f"apm_name_{index}")
        percent = label(f"apm_percent_{index}")
        if name and percent:
            program_mix.append({"program": name.rstrip(".").title(), "share": float(percent)})
    program_mix.append({"program": "All other programs", "share": float(label("apm_remainder_percent"))})
    result = {
        "source_id": "CARNEGIE_2025",
        "institution": label("name"),
        "unitid": label("unitid"),
        "retrieved_at": retrieved,
        "official_record_url": CARNEGIE_URL,
        "data_center_url": "https://carnegieclassifications.acenet.edu/data-center/",
        "institutional_methodology_url": "https://carnegieclassifications.acenet.edu/carnegie-classification/classification-methodology/2025-institutional-classification/",
        "research_methodology_url": "https://carnegieclassifications.acenet.edu/carnegie-classification/classification-methodology/2025-research-activity-designations/",
        "access_earnings_methodology_url": "https://carnegieclassifications.acenet.edu/carnegie-classification/classification-methodology/2025-student-access-and-earnings-classification/",
        "classifications": {
            "institutional_2025": label("ic2025"),
            "research_2025": label("research2025"),
            "student_access_and_earnings_2025": label("saec2025"),
            "basic_2021": label("basic2021"),
            "community_engagement": label("cce"),
            "land_grant": label("landgrnt"),
            "control": label("control"),
            "campus_setting": label("setting2025"),
            "highest_degree": label("highest_degree_2025"),
        },
        "enrollment_2025": int(label("enrollment_2025").replace(",", "")),
        "award_counts_2025": {
            "associate": int(label("award_associates_2025")),
            "bachelor": int(label("award_bachelors_2025")),
            "master": int(label("award_masters_2025")),
            "doctorate": int(label("award_doctorates_2025")),
        },
        "program_mix": program_mix,
        "classification_history": history,
        "source_locator": "ace_carnegie_institution_data.data.post_meta on the official institution record",
        "boundary_note": "Carnegie classifications are descriptive metadata attached to IPEDS UNITID 130943. They are shown as published and do not enter the atlas peer-distance calculations.",
        "period_note": label("institution-tab-notes"),
    }
    write_json("carnegie.json", result)


def record_review(retrieved: str) -> None:
    path = DATA / "maintenance-log.json"
    log = json.loads(path.read_text(encoding="utf-8-sig"))
    details = "Refreshed NCSES GSS, earned-doctorate, and facilities profile tables; exact-name ClinicalTrials.gov sponsor records; and Carnegie 2025 classifications."
    entry = {"date": retrieved, "type": "Source-page expansion", "owner": log["owner"], "result": "Passed", "details": details}
    if not any(row.get("date") == retrieved and row.get("details") == details for row in log["history"]):
        log["history"].insert(0, entry)
    parsed = date.fromisoformat(retrieved)
    display_date = f"{parsed.day} {parsed.strftime('%b %Y')}"
    log["last_completed_review"] = {"date": retrieved, "date_display": display_date, "result": "Five research and classification sources refreshed and validated"}
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-review", action="store_true")
    args = parser.parse_args()
    retrieved = date.today().isoformat()
    refresh_ncses(retrieved)
    refresh_clinical_trials(retrieved)
    refresh_carnegie(retrieved)
    if args.record_review:
        record_review(retrieved)
    print(json.dumps({"status": "refreshed", "date": retrieved, "files": ["ncses-gss.json", "ncses-sed.json", "ncses-facilities.json", "clinical-trials.json", "carnegie.json"]}, indent=2))


if __name__ == "__main__":
    main()
