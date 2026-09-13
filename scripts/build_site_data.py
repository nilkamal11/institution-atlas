import csv
import json
import math
import statistics
import os
from collections import defaultdict
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("AAGENERAL_ROOT", SITE.parent.parent)).resolve()
STUDY = ROOT / "outputs" / "institution-atlas-identity-coverage-study"
DIST = SITE / "dist"
DIST.mkdir(parents=True, exist_ok=True)


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in {"", "NULL", "PrivacySuppressed", "NA"}:
        return None
    return value


def number(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def integer(value):
    value = number(value)
    return int(value) if value is not None else None


with (STUDY / "DELAWARE_DFR_PEER_COVERAGE.csv").open(encoding="utf-8-sig", newline="") as f:
    institutions = list(csv.DictReader(f))

unitids = {r["unitid"] for r in institutions}
peer_unitids = [r["unitid"] for r in institutions if r["peer_mode"] == "DFR_SUBMITTED"]
institution_by_unitid = {r["unitid"]: r for r in institutions}

hd_path = next((ROOT / ".work" / "mit_identity_coverage" / "hd2024_extract").glob("*.csv"))
hd = {}
with hd_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        if row["UNITID"].strip() in unitids:
            hd[row["UNITID"].strip()] = row

def load_enrollment(path):
    output = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            unitid = row["UNITID"].strip()
            if unitid in unitids and row["EFALEVEL"].strip() in {"1", "2", "12", "21", "41"}:
                output[unitid][row["EFALEVEL"].strip()] = row
    return output


ef_by_vintage = {
    "IPEDS_EF2022A": load_enrollment(
        ROOT / ".work" / "institution_atlas" / "ipeds" / "EF2022A" / "ef2022a.csv"
    ),
    "IPEDS_EF2023A": load_enrollment(
        ROOT / ".work" / "institution_atlas" / "ipeds" / "EF2023A" / "ef2023a.csv"
    ),
}
ef = ef_by_vintage["IPEDS_EF2023A"]

scorecard_path = ROOT / ".work" / "institution_atlas" / "scorecard" / "Most-Recent-Cohorts-Institution.csv"
scorecard = {}
with scorecard_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        unitid = row["UNITID"].strip()
        if unitid in unitids:
            scorecard[unitid] = row

completion_path = ROOT / ".work" / "institution_atlas" / "ipeds" / "C2024_A" / "C2024_a.csv"
completions = defaultdict(lambda: defaultdict(int))
with completion_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        unitid = row["UNITID"].strip()
        if unitid not in unitids or row["MAJORNUM"].strip() != "1":
            continue
        value = integer(row["CTOTALT"])
        if value is not None:
            completions[unitid][row["AWLEVEL"].strip()] += value

herd_path = ROOT / ".work" / "public_higher_ed" / "funding_samples" / "herd_2024" / "herd2024.csv"
ncses_ids = {r["herd_ncses_inst_id"] for r in institutions if r["herd_ncses_inst_id"]}
herd = defaultdict(lambda: {"sources": {}, "personnel": {}, "fte": {}})
with herd_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        ncses_id = row["ncses_inst_id"].strip()
        if ncses_id not in ncses_ids:
            continue
        value = integer(row["data"])
        q = row["questionnaire_no"].strip()
        label = row["row"].strip()
        if q in {"01.a", "01.b", "01.c", "01.d", "01.e", "01.f", "01.g"}:
            herd[ncses_id]["sources"][label] = value
        elif q == "15" and label == "Total":
            herd[ncses_id]["personnel"][row["column"].strip()] = value
        elif q == "16" and label == "Total":
            herd[ncses_id]["fte"][row["column"].strip()] = value

records = {}
for unitid in ["130943", *peer_unitids]:
    peer = institution_by_unitid[unitid]
    directory = hd.get(unitid, {})
    sc = scorecard.get(unitid, {})
    enrollment_rows = ef.get(unitid, {})
    awards = completions.get(unitid, {})
    ncses_id = peer.get("herd_ncses_inst_id", "")
    herd_row = herd.get(ncses_id, {"sources": {}, "personnel": {}, "fte": {}})

    def enrollment(level, rows=enrollment_rows):
        row = rows.get(level)
        return integer(row.get("EFTOTLT")) if row else None

    ipeds_history = {}
    for vintage, vintage_rows in ef_by_vintage.items():
        rows = vintage_rows.get(unitid, {})
        year = "2022" if vintage == "IPEDS_EF2022A" else "2023"
        values = {
            "totalEnrollment": enrollment("1", rows),
            "undergraduate": enrollment("2", rows),
            "graduate": enrollment("12", rows),
            "fullTime": enrollment("21", rows),
            "partTime": enrollment("41", rows),
            "responseStatus": rows.get("1", {}).get("XEFTOTLT"),
            "dataYear": f"Fall {year}",
            "releaseVintage": vintage,
        }
        ipeds_history[vintage] = values

    total = enrollment("1")
    undergraduate = enrollment("2")
    graduate = enrollment("12")
    full_time = enrollment("21")
    part_time = enrollment("41")
    degree_counts = {
        "bachelors": awards.get("5", 0),
        "masters": awards.get("7", 0),
        "researchDoctorates": awards.get("17", 0),
        "professionalDoctorates": awards.get("18", 0),
        "otherDoctorates": awards.get("19", 0),
    }
    degree_total = sum(degree_counts.values())
    student_faculty_ratio = number(sc.get("STUFACR"))
    estimated_faculty = (
        total / student_faculty_ratio
        if total is not None and student_faculty_ratio not in {None, 0}
        else None
    )
    herd_total = herd_row["sources"].get("Total")

    records[unitid] = {
        "institutionKey": f"IPEDS-{unitid}",
        "unitid": unitid,
        "name": peer["institution_name"],
        "location": peer["location"],
        "control": integer(directory.get("CONTROL")),
        "sector": integer(directory.get("SECTOR")),
        "opeid8": clean(directory.get("OPEID")),
        "ipeds": {
            "totalEnrollment": total,
            "undergraduate": undergraduate,
            "graduate": graduate,
            "fullTime": full_time,
            "partTime": part_time,
            "responseStatus": enrollment_rows.get("1", {}).get("XEFTOTLT"),
            "dataYear": "Fall 2023",
            "releaseVintage": "IPEDS_EF2023A",
        },
        "ipedsHistory": ipeds_history,
        "degrees": degree_counts,
        "herd": {
            "ncsesId": ncses_id,
            "instId": peer.get("herd_inst_id", ""),
            "reportedName": peer.get("herd_reported_name", ""),
            "coverage": peer["herd_fy2024_coverage"],
            "total": herd_total,
            "sources": herd_row["sources"],
            "personnel": herd_row["personnel"],
            "fte": herd_row["fte"],
            "dataYear": "FY2024",
            "releaseVintage": "NCSES_HERD_FY2024",
        },
        "similarityInputs": {
            "researchSpending": herd_total,
            "researchDoctorates": degree_counts["researchDoctorates"],
            "totalEnrollment": total,
            "graduateShare": graduate / total if graduate is not None and total else None,
            "bachelorsShare": degree_counts["bachelors"] / degree_total if degree_total else None,
            "mastersShare": degree_counts["masters"] / degree_total if degree_total else None,
            "doctorateShare": (
                degree_counts["researchDoctorates"]
                + degree_counts["professionalDoctorates"]
                + degree_counts["otherDoctorates"]
            )
            / degree_total
            if degree_total
            else None,
            "estimatedFacultyScale": estimated_faculty,
            "financialScale": number(sc.get("ENDOWEND")),
            "control": integer(directory.get("CONTROL")),
        },
    }

feature_specs = [
    ("researchSpending", "Research spending", 1.5, True),
    ("researchDoctorates", "Research doctorates", 1.25, True),
    ("totalEnrollment", "Enrollment", 1.0, True),
    ("graduateShare", "Graduate share", 1.0, False),
    ("bachelorsShare", "Bachelor's degree share", 0.75, False),
    ("mastersShare", "Master's degree share", 0.75, False),
    ("doctorateShare", "Doctoral degree share", 0.75, False),
    ("estimatedFacultyScale", "Estimated faculty scale", 0.75, True),
    ("financialScale", "Endowment scale", 0.75, True),
]

population = [records["130943"], *[records[u] for u in peer_unitids]]
stats = {}
for key, _, _, log_transform in feature_specs:
    values = []
    for row in population:
        value = row["similarityInputs"][key]
        if value is not None:
            values.append(math.log1p(value) if log_transform else value)
    median = statistics.median(values)
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) or 1.0
    stats[key] = {"median": median, "mean": mean, "sd": sd, "log": log_transform}


def standardized(row, key):
    raw = row["similarityInputs"][key]
    spec = stats[key]
    value = spec["median"] if raw is None else (math.log1p(raw) if spec["log"] else raw)
    return (value - spec["mean"]) / spec["sd"], raw is None


focal = records["130943"]
ranked = []
for unitid in peer_unitids:
    candidate = records[unitid]
    contributions = []
    total_distance = 0.0
    for key, label, weight, _ in feature_specs:
        focal_z, focal_missing = standardized(focal, key)
        candidate_z, candidate_missing = standardized(candidate, key)
        delta = abs(candidate_z - focal_z)
        component = weight * delta * delta
        if candidate_missing or focal_missing:
            component += 0.35
        total_distance += component
        contributions.append({"key": key, "label": label, "delta": round(delta, 3)})
    if candidate["control"] != focal["control"]:
        total_distance += 1.5
    factors = [x["label"] for x in sorted(contributions, key=lambda x: x["delta"])[:3]]
    ranked.append(
        {
            "unitid": unitid,
            "distance": round(math.sqrt(total_distance), 3),
            "factors": factors,
            "controlMatch": candidate["control"] == focal["control"],
        }
    )

ranked.sort(key=lambda row: (row["distance"], row["unitid"]))
analytical = ranked[:10]


def read_csv(name):
    with (STUDY / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


data = {
    "generatedAt": "2026-09-13",
    "institution": {
        "unitid": "130943",
        "name": "University of Delaware",
        "location": "Newark, Delaware",
        "boundary": "CORE",
    },
    "ipedsVintages": [
        {"id": "IPEDS_EF2023A", "label": "Fall 2023", "dataYear": "2023", "isDefault": True},
        {"id": "IPEDS_EF2022A", "label": "Fall 2022", "dataYear": "2022", "isDefault": False},
    ],
    "records": records,
    "peerModes": {
        "DFR_SUBMITTED": {
            "label": "Submitted DFR group",
            "provenance": "Institution-submitted comparison group in the 2025 IPEDS Data Feedback Report",
            "vintage": "IPEDS_DFR_2025",
            "unitids": peer_unitids,
        },
        "DFR_DEFAULT": {
            "label": "NCES default group",
            "provenance": "Unavailable because the 2025 report contains an institution-submitted group",
            "vintage": "IPEDS_DFR_2025",
            "unitids": [],
        },
        "ANALYTICAL": {
            "label": "Analytical peers",
            "provenance": "Ten nearest institutions within the submitted DFR candidate pool using the documented 2026-09-13 model",
            "vintage": "ATLAS_ANALYTICAL_2026-09-13",
            "unitids": [row["unitid"] for row in analytical],
            "ranking": analytical,
        },
        "CUSTOM": {
            "label": "Custom peers",
            "provenance": "User-selected from the submitted DFR candidate pool on this device",
            "vintage": "USER_SELECTION",
            "unitids": [row["unitid"] for row in analytical[:5]],
        },
    },
    "method": {
        "candidatePool": "The 30 institutions in Delaware's 2025 submitted DFR comparison group.",
        "distance": "Weighted Euclidean distance after z-score standardization. Spending, enrollment, faculty scale, and endowment use log1p transforms. Missing values use the candidate-pool median plus a 0.35 penalty. A control mismatch adds 1.5 before the square root.",
        "featureWeights": [
            {"feature": label, "weight": weight, "transform": "log1p" if log_transform else "none"}
            for _, label, weight, log_transform in feature_specs
        ],
        "staffingProxy": "Estimated faculty scale equals fall enrollment divided by the Scorecard student-faculty ratio. It is used for ranking only and is not displayed as an observed faculty count.",
        "classificationRule": "Carnegie labels are display metadata and are not used in the distance calculation.",
    },
    "identifiers": read_csv("DELAWARE_IDENTITY_REGISTRY.csv"),
    "aliases": read_csv("DELAWARE_ALIAS_REGISTRY.csv"),
    "relatedOrganizations": read_csv("DELAWARE_RELATED_ORGANIZATIONS.csv"),
    "sourceCoverage": read_csv("SOURCE_COVERAGE_MATRIX.csv"),
}

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
(DIST / "atlas-data.js").write_text(f"window.ATLAS_DATA={payload};\n", encoding="utf-8")
(SITE / "analytical-peer-model.json").write_text(
    json.dumps({"method": data["method"], "ranking": ranked}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "records": len(records),
            "analyticalPeers": [records[row["unitid"]]["name"] for row in analytical],
            "ipedsFocal": records["130943"]["ipeds"],
            "herdFocal": records["130943"]["herd"],
            "output": str(DIST / "atlas-data.js"),
        },
        indent=2,
    )
)
