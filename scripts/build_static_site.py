import csv
import html
import json
import shutil
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
OUTPUTS = [ROOT / "docs", ROOT / "dist"]
BASE_URL = "https://nilkamal11.github.io/institution-atlas/"


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8-sig"))


def load_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


atlas = load_json("atlas.json")
contracts = load_json("source-contracts.json")
maintenance = load_json("maintenance-log.json")
scorecard = load_json("scorecard.json")
nsf_awards = load_json("nsf-awards.json")
nih_reporter = load_json("nih-reporter.json")
usaspending = load_json("usaspending.json")
openalex = load_json("openalex.json")
reconciliation = load_csv("reconciliation.csv")
vintage_diff = load_csv("vintage-diff.csv")
atlas["identifiers"] = load_csv("DELAWARE_IDENTITY_REGISTRY.csv")
atlas["aliases"] = load_csv("DELAWARE_ALIAS_REGISTRY.csv")
atlas["relatedOrganizations"] = load_csv("DELAWARE_RELATED_ORGANIZATIONS.csv")
atlas["sourceCoverage"] = load_csv("SOURCE_COVERAGE_MATRIX.csv")
atlas["scorecard"] = scorecard
atlas["nsfAwards"] = nsf_awards
identifiers = [row for row in atlas["identifiers"] if row["status"] == "confirmed"]
focal = atlas["records"][atlas["institution"]["unitid"]]
default_mode = atlas["peerModes"]["DFR_SUBMITTED"]
default_peers = [atlas["records"][unitid] for unitid in default_mode["unitids"]]
contract_by_id = {row["source_id"]: row for row in contracts}
scorecard_by_unitid = {row["unitid"]: row for row in scorecard["records"]}
scorecard_focal = scorecard_by_unitid[atlas["institution"]["unitid"]]
scorecard_peers = [scorecard_by_unitid[unitid] for unitid in default_mode["unitids"] if unitid in scorecard_by_unitid]


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def fmt_int(value):
    return "—" if value is None else f"{round(value):,}"


def fmt_money(value):
    return "—" if value is None else f"${value / 1000:,.1f}M"


def fmt_currency(value):
    return "—" if value is None else f"${round(value):,}"


def fmt_dollars_millions(value):
    return "—" if value is None else f"${value / 1_000_000:,.1f}M"


def fmt_dollars_compact(value):
    if value is None:
        return "—"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"
    return fmt_dollars_millions(value)


def fmt_pct(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def link(label, url, class_name=""):
    class_attr = f' class="{esc(class_name)}"' if class_name else ""
    return f'<a{class_attr} href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)} <span aria-hidden="true">↗</span></a>'


def local_link(label, url, class_name=""):
    class_attr = f' class="{esc(class_name)}"' if class_name else ""
    return f'<a{class_attr} href="{esc(url)}">{esc(label)}</a>'


def unitid_url(unitid, year="2023"):
    return f"https://nces.ed.gov/ipeds/reported-data/html/{unitid}?surveyNumber=15&viewMode=print&year={year}"


def ncses_url(ncses_id):
    return f"https://ncsesdata.nsf.gov/profiles/site?method=view&tin={ncses_id}"


def scorecard_url(unitid, name=""):
    slug = "-".join("".join(character if character.isalnum() else " " for character in name).split())
    return f"https://collegescorecard.ed.gov/school/?{unitid}-{slug}" if slug else f"https://collegescorecard.ed.gov/school/?{unitid}"


def nsf_award_url(award_id):
    return f"https://api.nsf.gov/services/v1/awards/{award_id}.json"


def page_head(title, description):
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%2308233b'/%3E%3Cpath d='M32 8 45 32 32 56 19 32Z' fill='%2300a6a6'/%3E%3Ccircle cx='32' cy='32' r='8' fill='white'/%3E%3C/svg%3E">
  <link rel="stylesheet" href="styles.css">
</head>'''


def site_header():
    last = maintenance["last_completed_review"]
    return f'''<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header">
  <a class="brand" href="index.html" aria-label="Institution Atlas home"><span class="brand-mark" aria-hidden="true"><i></i></span><span><strong>Institution Atlas</strong><small>Public records, one institution at a time</small></span></a>
  <div class="header-meta"><span class="status-dot"></span> Reviewed {esc(last["date_display"])} · Owner: {esc(maintenance["owner"])}</div>
</header>'''


def navigation(active):
    items = [
        ("identity", "index.html", "01", "Identity & peers"),
        ("ipeds", "ipeds.html", "02", "IPEDS core"),
        ("scorecard", "scorecard.html", "03", "College Scorecard"),
        ("herd", "herd.html", "04", "Research · HERD"),
        ("nsf", "nsf-awards.html", "05", "NSF awards"),
        ("nih", "nih-reporter.html", "06", "NIH projects"),
        ("usaspending", "usaspending.html", "07", "Federal awards"),
        ("openalex", "openalex.html", "08", "Publications"),
        ("maintenance", "maintenance.html", "09", "Maintenance"),
    ]
    links = []
    for key, href, number, label in items:
        attrs = ' class="active" aria-current="page"' if key == active else ""
        links.append(f'<a{attrs} href="{href}"><span>{number}</span> {esc(label)}</a>')
    return '<nav class="page-nav" aria-label="Atlas sections">' + "".join(links) + "</nav>"


def controls(page):
    peer_lock_reasons = {
        "nsf": "UEI crosswalk not loaded for peers",
        "nih": "NIH organization crosswalk not loaded for peers",
        "usaspending": "Recipient UEI crosswalk not loaded for peers",
        "openalex": "Peer institution boundaries not reviewed",
    }
    if page in peer_lock_reasons:
        peer_options = '<option selected>Not available for this source</option>'
        peer_control = f'<label class="control-locked">Peer group<select id="peer-control" disabled>{peer_options}</select><span class="control-status">{esc(peer_lock_reasons[page])}</span></label>'
    else:
        peer_options = "".join(
            f'<option value="{esc(key)}"{" selected" if key == "DFR_SUBMITTED" else ""}>{esc(value["label"])}</option>'
            for key, value in atlas["peerModes"].items()
        )
        peer_control = f'<label>Peer group<select id="peer-control">{peer_options}</select></label>'
    boundary_options = '''<option value="CORE" selected>Core campus</option>
      <option value="CORE_FFRDC" disabled>Core + FFRDC — unavailable</option>
      <option value="CORE_AFFIL" disabled>Core + affiliates — not reviewed</option>
      <option value="CORE_HEALTH" disabled>Core + health system — not reviewed</option>
      <option value="SYSTEM" disabled>System — no reporting entity</option>'''
    if page == "ipeds":
        year = '<select id="year-control"><option value="IPEDS_EF2023A" selected>Fall 2023</option><option value="IPEDS_EF2022A">Fall 2022</option></select>'
        vintage = '<select id="vintage-control"><option value="IPEDS_EF2023A" selected>IPEDS_EF2023A</option><option value="IPEDS_EF2022A">IPEDS_EF2022A</option></select>'
    elif page == "herd":
        year = '<select id="year-control" disabled><option>FY2024</option></select><span class="control-status">Only loaded year</span>'
        vintage = '<select id="vintage-control" disabled><option>NCSES_HERD_FY2024</option></select><span class="control-status">Only loaded release</span>'
    elif page == "scorecard":
        year = f'<select id="year-control" disabled><option>{esc(scorecard["institution_year"])} institution file</option></select><span class="control-status">Selected common year</span>'
        vintage = f'<select id="vintage-control" disabled><option>Snapshot {esc(scorecard["retrieved_at"])}</option></select><span class="control-status">API snapshot</span>'
    elif page == "nsf":
        year = f'<select id="year-control" disabled><option>2022–{esc(nsf_awards["recent_period_end"][:4])}</option></select><span class="control-status">Recent award-date window</span>'
        vintage = f'<select id="vintage-control" disabled><option>Snapshot {esc(nsf_awards["retrieved_at"])}</option></select><span class="control-status">API snapshot</span>'
    elif page == "nih":
        year = f'<select id="year-control" disabled><option>FY{nih_reporter["fiscal_years"][0]}–FY{nih_reporter["fiscal_years"][-1]}</option></select><span class="control-status">Federal fiscal years</span>'
        vintage = f'<select id="vintage-control" disabled><option>Snapshot {esc(nih_reporter["retrieved_at"])}</option></select><span class="control-status">API snapshot</span>'
    elif page == "usaspending":
        year = f'<select id="year-control" disabled><option>FY{usaspending["fiscal_years"][0]}–FY{usaspending["fiscal_years"][-1]}</option></select><span class="control-status">Federal fiscal years</span>'
        vintage = f'<select id="vintage-control" disabled><option>Snapshot {esc(usaspending["retrieved_at"])}</option></select><span class="control-status">API snapshot</span>'
    elif page == "openalex":
        year = f'<select id="year-control" disabled><option>{esc(openalex["window_start"][:4])}–{esc(openalex["window_end"][:4])}</option></select><span class="control-status">Publication years</span>'
        vintage = f'<select id="vintage-control" disabled><option>Snapshot {esc(openalex["retrieved_at"])}</option></select><span class="control-status">API snapshot</span>'
    else:
        year = '<select id="year-control" disabled><option>Source-specific</option></select><span class="control-status">Not applicable</span>'
        vintage = '<select id="vintage-control" disabled><option>Latest verified</option></select><span class="control-status">Not applicable</span>'
    return f'''<section class="control-rail" aria-label="Persistent atlas controls">
  <label class="control-locked">Institution<select id="institution-control" disabled><option>{esc(atlas["institution"]["name"])}</option></select><span class="control-status">Fixed pilot</span></label>
  <label class="control-limited">Reporting boundary<select id="boundary-control" aria-describedby="boundary-control-note">{boundary_options}</select><span id="boundary-control-note" class="control-status">Core is the only reviewed boundary</span></label>
  {peer_control}
  <label class="control-locked">Data year{year}</label>
  <label class="control-locked">Release vintage{vintage}</label>
</section>'''


def footer():
    return f'''<footer><span>Institution Atlas prototype</span><span>Monthly review owner: {esc(maintenance["owner"])} · {local_link("Maintenance record", "maintenance.html")}</span></footer>'''


def scripts():
    return '<script src="atlas-data.js"></script><script src="app.js"></script>'


def identifier_link(row, class_name="id-link"):
    target = row["source_url"]
    if row["identifier_type"] in {"UNITID", "OPEID8"}:
        target = unitid_url("130943")
    elif row["identifier_type"] == "NCSES_INST_ID":
        target = ncses_url(row["identifier_value"])
    return link(row["identifier_value"], target, class_name)


def peer_items(peers):
    return "".join(
        f'''<div class="peer-item"><strong title="{esc(row["name"])}">{esc(row["name"])}</strong><span>{esc(row["location"])} · {link("UNITID " + row["unitid"], unitid_url(row["unitid"]), "inline-evidence")}</span></div>'''
        for row in peers
    )


def identity_page():
    by_type = {row["identifier_type"]: row for row in identifiers}
    ribbon_types = ["UNITID", "OPEID8", "NCSES_INST_ID", "ROR", "UEI"]
    ribbon = "".join(
        f'<div><span>{esc(kind.replace("NCSES_INST_ID", "NCSES").replace("OPEID8", "OPEID"))}</span><strong>{identifier_link(by_type[kind])}</strong></div>'
        for kind in ribbon_types
    )
    rows = "".join(
        f'''<tr id="identifier-{esc(row["identifier_type"].lower())}"><td>{esc(row["identifier_type"].replace("_", " "))}</td><td class="id-value">{identifier_link(row)}</td><td>{link(row["source"], row["source_url"], "source-evidence")}</td><td><span class="confirm-badge">Confirmed</span></td></tr>'''
        for row in identifiers
    )
    exact = sum(1 for row in default_peers if row["herd"]["coverage"] == "present_exact_unitid")
    conditional = sum(1 for row in default_peers if row["herd"]["coverage"] == "conditional_boundary_match")
    related = "".join(
        f'''<div class="related-row"><strong>{esc(row["related_name"])}</strong><span>{esc(row["relationship"])} · {link("ROR " + row["related_identifier"].rsplit("/", 1)[-1], row["related_identifier"], "inline-evidence")}</span><span class="disposition">{esc(row["proposed_disposition"].replace("_", " "))}</span></div>'''
        for row in atlas["relatedOrganizations"]
    )
    weights = "".join(f'<li><span>{esc(row["feature"])}</span><strong>{esc(row["weight"])} · {esc(row["transform"])}</strong></li>' for row in atlas["method"]["featureWeights"])
    return f'''{page_head("Identity and peers | Institution Atlas", "A source-traceable institutional profile for the University of Delaware.")}
<body data-page="identity">{site_header()}{navigation("identity")}{controls("identity")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="institution-banner"><div><p class="eyebrow">Public research university · {esc(atlas["institution"]["location"])}</p><h1>{esc(atlas["institution"]["name"])}</h1><p class="lede">One reviewed identity connects education, research, awards, and publication sources while keeping their reporting boundaries visible.</p></div><div class="readiness-card"><span class="readiness-label">Pilot gate</span><strong>Tier 0 confirmed</strong><ul><li>One IPEDS institution</li><li>Exact HERD crosswalk</li><li>No administered FFRDC</li></ul></div></section>
  <section class="id-ribbon" aria-label="Core identifiers">{ribbon}</section>
  <section class="dashboard-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Reviewed crosswalk</p><h2>Institution identity</h2></div><button class="quiet-button" data-download="identity">Download rows</button></div><div id="identity-table" class="table-wrap"><table><thead><tr><th>Identifier</th><th>Value</th><th>Evidence</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div><p class="evidence-note">Every identifier links to the official record or source file used to confirm it. {local_link("See the full evidence record", "evidence.html#identity-evidence")}.</p></article>
  <aside class="panel source-note"><p class="section-kicker">Boundary in use</p><h2 id="boundary-title">Core campus</h2><p id="boundary-copy">The degree-granting institution reported to IPEDS under {link("UNITID 130943", unitid_url("130943"), "inline-evidence")}.</p><dl><div><dt>IPEDS</dt><dd>Exact</dd></div><div><dt>HERD</dt><dd>Exact</dd></div><div><dt>OpenAlex</dt><dd>Review children</dd></div></dl>{link("Open Fall 2023 reported data", unitid_url("130943"), "source-link")}</aside></section>
  <section class="panel peer-panel"><div class="panel-heading peer-heading"><div><p class="section-kicker">Comparison set</p><h2 id="peer-title">{esc(default_mode["label"])}</h2><p id="peer-provenance" class="provenance">{esc(default_mode["provenance"])}. Vintage: {esc(default_mode["vintage"])}.</p></div><div class="peer-stat"><strong id="peer-count">{len(default_peers)}</strong><span>institutions</span></div></div><div id="coverage-strip" class="coverage-strip"><span class="coverage-chip">IPEDS {len(default_peers)}/{len(default_peers)}</span><span class="coverage-chip">Scorecard {len(default_peers)}/{len(default_peers)}</span><span class="coverage-chip">HERD exact {exact}/{len(default_peers)}</span><span class="coverage-chip warning">HERD boundary review {conditional}</span></div><div id="custom-editor" class="custom-editor" hidden></div><div id="peer-list" class="peer-list">{peer_items(default_peers)}</div></section>
  <section class="dashboard-grid lower-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Research organization boundary</p><h2>Related organizations</h2></div><span class="review-pill">{len(atlas["relatedOrganizations"])} review decisions</span></div><p class="panel-intro">ROR lists six child organizations and one related hospital. Proposed dispositions remain visible until reviewed.</p><div id="related-list" class="related-list">{related}</div></article><aside class="panel method-card"><p class="section-kicker">Analytical peers</p><h2>Transparent by design</h2><p>The model uses spending, doctorates, enrollment, degree mix, staffing scale, financial scale, and control. Carnegie labels are display metadata.</p><button class="primary-button" data-open-method>View method</button></aside></section>
</main>{footer()}<dialog id="method-dialog" class="method-dialog"><form method="dialog"><button aria-label="Close methodology">×</button></form><p class="section-kicker">Analytical peer method</p><h2>How similarity is calculated</h2><div id="method-content"><p><strong>Candidate pool:</strong> {esc(atlas["method"]["candidatePool"])}</p><p>{esc(atlas["method"]["distance"])}</p><ul class="weight-list">{weights}</ul><p>{esc(atlas["method"]["staffingProxy"])}</p><p>{esc(atlas["method"]["classificationRule"])}</p></div></dialog>{scripts()}</body></html>'''


def metric_card(label, value, note, tone=""):
    return f'<article class="metric-card {tone}"><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>'


def comparison_svg(series, value_formatter, title, title_id="chart-title"):
    max_value = max(max(row[1] or 0, row[2] or 0) for row in series) or 1
    width, left, plot = 920, 190, 650
    height = 58 * len(series) + 48
    elements = [f'<svg class="static-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{esc(title_id)}"><title id="{esc(title_id)}">{esc(title)}</title>', '<g class="svg-legend"><rect x="190" y="10" width="12" height="12" rx="2"/><text x="208" y="21">University of Delaware</text><rect class="peer" x="390" y="10" width="12" height="12" rx="2"/><text x="408" y="21">Peer median</text></g>']
    for index, (label, focal_value, peer_value) in enumerate(series):
        y = 44 + index * 58
        focal_width = (focal_value or 0) / max_value * plot
        peer_width = (peer_value or 0) / max_value * plot
        elements.append(f'<text class="svg-label" x="0" y="{y + 18}">{esc(label)}</text><rect class="svg-track" x="{left}" y="{y}" width="{plot}" height="18" rx="4"/><rect class="svg-bar" x="{left}" y="{y}" width="{focal_width:.2f}" height="18" rx="4"/><text class="svg-value" x="{left + 8}" y="{y + 14}">{esc(value_formatter(focal_value))}</text><rect class="svg-track" x="{left}" y="{y + 23}" width="{plot}" height="18" rx="4"/><rect class="svg-bar peer" x="{left}" y="{y + 23}" width="{peer_width:.2f}" height="18" rx="4"/><text class="svg-value" x="{left + 8}" y="{y + 37}">{esc(value_formatter(peer_value))}</text>')
    elements.append("</svg>")
    table_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value_formatter(focal_value))}</td><td>{esc(value_formatter(peer_value))}</td></tr>' for label, focal_value, peer_value in series)
    elements.append(f'<div class="table-wrap chart-table"><table><thead><tr><th>Measure</th><th>University of Delaware</th><th>Peer median</th></tr></thead><tbody>{table_rows}</tbody></table></div>')
    return "".join(elements)


def single_series_svg(series, value_formatter, title, label_header="Funding source"):
    max_value = max((row[1] or 0) for row in series) or 1
    width, left, plot = 920, 190, 650
    height = 42 * len(series) + 30
    elements = [f'<svg class="static-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="source-chart-title"><title id="source-chart-title">{esc(title)}</title>']
    for index, (label, value) in enumerate(series):
        y = 12 + index * 42
        bar_width = (value or 0) / max_value * plot
        elements.append(f'<text class="svg-label" x="0" y="{y + 18}">{esc(label)}</text><rect class="svg-track" x="{left}" y="{y}" width="{plot}" height="22" rx="4"/><rect class="svg-bar" x="{left}" y="{y}" width="{bar_width:.2f}" height="22" rx="4"/><text class="svg-value" x="{left + 8}" y="{y + 16}">{esc(value_formatter(value))}</text>')
    elements.append("</svg>")
    table_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value_formatter(value))}</td></tr>' for label, value in series)
    elements.append(f'<div class="table-wrap chart-table"><table><thead><tr><th>{esc(label_header)}</th><th>University of Delaware</th></tr></thead><tbody>{table_rows}</tbody></table></div>')
    return "".join(elements)


def ipeds_peer_table(peers, vintage="IPEDS_EF2023A"):
    focal_value = focal["ipedsHistory"][vintage]["totalEnrollment"]
    rows = []
    for row in peers:
        values = row["ipedsHistory"][vintage]
        difference = values["totalEnrollment"] - focal_value
        rows.append(f'<tr><td><strong>{esc(row["name"])}</strong><br><span class="table-sub">{link("UNITID " + row["unitid"], unitid_url(row["unitid"], values["dataYear"].split()[-1]), "inline-evidence")}</span></td><td>{fmt_int(values["totalEnrollment"])}</td><td>{fmt_int(values["undergraduate"])}</td><td>{fmt_int(values["graduate"])}</td><td class="{"difference-positive" if difference >= 0 else "difference-negative"}">{"+" if difference >= 0 else ""}{fmt_int(difference)}</td><td><span class="boundary-status">Exact</span></td></tr>')
    return '<table><thead><tr><th>Institution</th><th>Total</th><th>Undergraduate</th><th>Graduate</th><th>Difference from Delaware</th><th>Status</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def what_changed():
    before = focal["ipedsHistory"]["IPEDS_EF2022A"]
    after = focal["ipedsHistory"]["IPEDS_EF2023A"]
    fields = [
        ("Total enrollment", "totalEnrollment", "1", "EFTOTLT"),
        ("Undergraduate", "undergraduate", "2", "EFTOTLT"),
        ("Graduate", "graduate", "12", "EFTOTLT"),
        ("Full-time", "fullTime", "21", "EFTOTLT"),
        ("Part-time", "partTime", "41", "EFTOTLT"),
    ]
    rows = []
    for label, key, level, field in fields:
        delta = after[key] - before[key]
        pct = delta / before[key] * 100 if before[key] else None
        rows.append(f'''<tr><th>{esc(label)}</th><td>{fmt_int(before[key])}</td><td>{fmt_int(after[key])}</td><td class="{"difference-positive" if delta >= 0 else "difference-negative"}">{"+" if delta >= 0 else ""}{fmt_int(delta)} ({pct:+.1f}%)</td><td><code>UNITID=130943 · EFALEVEL={level} · {field}</code></td></tr>''')
    return "".join(rows)


def ipeds_page():
    current = focal["ipedsHistory"]["IPEDS_EF2023A"]
    peers = [row["ipedsHistory"]["IPEDS_EF2023A"] for row in default_peers]
    series = [
        ("Total enrollment", current["totalEnrollment"], median(row["totalEnrollment"] for row in peers)),
        ("Undergraduate", current["undergraduate"], median(row["undergraduate"] for row in peers)),
        ("Graduate", current["graduate"], median(row["graduate"] for row in peers)),
        ("Full-time", current["fullTime"], median(row["fullTime"] for row in peers)),
    ]
    full_time_share = current["fullTime"] / current["totalEnrollment"] * 100
    metric_html = "".join([
        metric_card("Total enrollment", fmt_int(current["totalEnrollment"]), "Students · Fall 2023"),
        metric_card("Undergraduate", fmt_int(current["undergraduate"]), f'{current["undergraduate"] / current["totalEnrollment"] * 100:.1f}% of enrollment'),
        metric_card("Graduate", fmt_int(current["graduate"]), f'{current["graduate"] / current["totalEnrollment"] * 100:.1f}% of enrollment', "teal"),
        metric_card("Full-time share", f"{full_time_share:.1f}%", "Fall enrollment", "teal"),
    ])
    profile_2023 = unitid_url("130943", "2023")
    profile_2022 = unitid_url("130943", "2022")
    bulk_2023 = "https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip"
    bulk_2022 = "https://nces.ed.gov/ipeds/datacenter/data/EF2022A.zip"
    return f'''{page_head("IPEDS core | Institution Atlas", "University of Delaware Fall 2023 and Fall 2022 enrollment from IPEDS.")}
<body data-page="ipeds">{site_header()}{navigation("ipeds")}{controls("ipeds")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header"><div><p class="eyebrow">IPEDS · Enrollment component</p><h1>IPEDS core</h1><p>Enrollment at the degree-granting institution reported under {link("UNITID 130943", profile_2023, "header-link")}.</p></div><div class="source-actions">{link("Fall 2023 reported data", profile_2023, "official-button")}{link("EF2023A bulk file", bulk_2023, "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>NCES IPEDS</strong></div><div><span>Period</span><strong id="ipeds-period-label">Fall 2023</strong></div><div><span>Vintage</span><strong id="ipeds-vintage-label">IPEDS_EF2023A</strong></div><div><span>Unit</span><strong>Students</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#ipeds-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="ipeds-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid chart-layout"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Fall enrollment</p><h2>Institution and active peer median</h2><p id="ipeds-peer-note" class="provenance">{esc(default_mode["label"])} · {len(default_peers)} institutions · {esc(default_mode["vintage"])}</p></div><button class="quiet-button" data-download="ipeds">Download chart data</button></div><div id="ipeds-chart" class="comparison-chart">{comparison_svg(series, fmt_int, "Fall 2023 enrollment at University of Delaware and the submitted DFR peer median")}</div><div class="chart-footer"><span>Unit: students</span><span id="ipeds-chart-period">Reporting period: Fall 2023</span><span id="ipeds-chart-vintage">Release: IPEDS_EF2023A</span></div></article>
  <aside class="panel definition-card"><p class="section-kicker">What this includes</p><h2>IPEDS reporting institution</h2><p>Counts cover students reported by University of Delaware for this component and vintage. Fall and 12-month enrollment are separate reporting periods; this page uses fall enrollment only.</p><dl><div><dt>UNITID</dt><dd>{link("130943", profile_2023, "inline-evidence")}</dd></div><div><dt>OPEID8</dt><dd>{link(focal["opeid8"], "https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip", "inline-evidence")}</dd></div><div><dt>Response flag</dt><dd id="response-flag">R · Reported</dd></div></dl></aside></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Peer coverage</p><h2>Enrollment records</h2></div><span id="ipeds-coverage-pill" class="review-pill">{len(default_peers)}/{len(default_peers)} present</span></div><div id="ipeds-table" class="table-wrap">{ipeds_peer_table(default_peers)}</div></section>
  <section class="panel change-panel" id="what-changed"><div class="panel-heading"><div><p class="section-kicker">Retained vintages</p><h2>What changed?</h2><p class="provenance">University of Delaware · Fall 2022 to Fall 2023 · same EF A-file grain</p></div>{local_link("Full reconciliation", "evidence.html#ipeds-reconciliation", "record-link")}</div><div class="table-wrap"><table><thead><tr><th>Measure</th><th>Fall 2022</th><th>Fall 2023</th><th>Change</th><th>Source-row locator in both files</th></tr></thead><tbody>{what_changed()}</tbody></table></div><div class="citation-grid"><article><span>Interactive reported data</span>{link("Fall 2022", profile_2022)} · {link("Fall 2023", profile_2023)}</article><article><span>Exact bulk releases</span>{link("EF2022A.zip", bulk_2022)} · {link("EF2023A.zip", bulk_2023)}</article><article><span>Row rule</span><code>UNITID=130943 + EFALEVEL + EFTOTLT</code></article></div></section>
  <section class="panel state-check"><div><p class="section-kicker">Display rule check</p><h2>Zero, missing, and suppressed stay distinct</h2><p>This is an interface test, not an institutional statistic. Suppressed and missing cells are excluded from calculations.</p></div><div class="state-samples"><span><b>0</b> Reported zero</span><span><b>—</b> Missing</span><span class="suppressed"><b>S</b> Suppressed</span></div></section></div>
</main>{footer()}<dialog id="method-dialog" class="method-dialog"><form method="dialog"><button aria-label="Close methodology">×</button></form><div id="method-content"></div></dialog>{scripts()}</body></html>'''


def scorecard_peer_table(peers):
    rows = []
    for row in peers:
        rows.append(f'''<tr><td><strong>{esc(row["name"])}</strong><br><span class="table-sub">{link("UNITID " + row["unitid"], scorecard_url(row["unitid"], row["name"]), "inline-evidence")}</span></td><td>{fmt_currency(row["average_net_price"])}</td><td>{fmt_pct(row["completion_rate_150"])}</td><td>{fmt_pct(row["retention_rate_full_time"])}</td><td>{fmt_pct(row["pell_grant_rate"])}</td><td>{fmt_pct(row["federal_loan_rate"])}</td></tr>''')
    return '<table><thead><tr><th>Institution</th><th>Average net price</th><th>Completion within 150%</th><th>Full-time retention</th><th>Pell Grant rate</th><th>Federal loan rate</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def scorecard_page():
    price_series = [
        ("Average net price", scorecard_focal["average_net_price"], median(row["average_net_price"] for row in scorecard_peers if row["average_net_price"] is not None)),
        ("Median debt · completers", scorecard_focal["median_debt_completers"], median(row["median_debt_completers"] for row in scorecard_peers if row["median_debt_completers"] is not None)),
    ]
    outcome_series = [
        ("Completion within 150%", scorecard_focal["completion_rate_150"], median(row["completion_rate_150"] for row in scorecard_peers if row["completion_rate_150"] is not None)),
        ("Full-time retention", scorecard_focal["retention_rate_full_time"], median(row["retention_rate_full_time"] for row in scorecard_peers if row["retention_rate_full_time"] is not None)),
        ("Pell Grant rate", scorecard_focal["pell_grant_rate"], median(row["pell_grant_rate"] for row in scorecard_peers if row["pell_grant_rate"] is not None)),
        ("Federal loan rate", scorecard_focal["federal_loan_rate"], median(row["federal_loan_rate"] for row in scorecard_peers if row["federal_loan_rate"] is not None)),
    ]
    metric_html = "".join([
        metric_card("Average net price", fmt_currency(scorecard_focal["average_net_price"]), f'{scorecard["institution_year"]} institution file'),
        metric_card("Completion within 150%", fmt_pct(scorecard_focal["completion_rate_150"]), "Four-year institution cohort"),
        metric_card("Full-time retention", fmt_pct(scorecard_focal["retention_rate_full_time"]), "First-time students", "teal"),
        metric_card("Median earnings", fmt_currency(scorecard_focal["median_earnings_10_year"]), f'10 years after entry · {scorecard["outcomes_cohort_file_year"]} file', "teal"),
    ])
    profile = scorecard["official_profile_url"]
    return f'''{page_head("College Scorecard | Institution Atlas", "University of Delaware cost, aid, access, completion, retention, debt, and earnings from College Scorecard.")}
<body data-page="scorecard">{site_header()}{navigation("scorecard")}{controls("scorecard")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header scorecard-header"><div><p class="eyebrow">U.S. Department of Education · College Scorecard</p><h1>College Scorecard</h1><p>Costs, aid, access, and outcomes for {link("UNITID 130943", profile, "header-link")} and its submitted DFR comparison group.</p></div><div class="source-actions">{link("Official institution profile", profile, "official-button")}{link("Data downloads", scorecard["data_url"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>College Scorecard</strong></div><div><span>Institution year</span><strong>{esc(scorecard["institution_year"])}</strong></div><div><span>Snapshot</span><strong>{esc(scorecard["retrieved_at"])}</strong></div><div><span>Unit</span><strong>Dollars and rates</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#scorecard-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="scorecard-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Price and borrowing</p><h2>Institution and active peer median</h2><p id="scorecard-peer-note" class="provenance">{esc(default_mode["label"])} · {len(scorecard_peers)} institutions · {esc(scorecard["institution_year"])} institution file</p></div><button class="quiet-button" data-download="scorecard">Download comparison data</button></div><div id="scorecard-price-comparison" class="comparison-chart">{comparison_svg(price_series, fmt_currency, "College Scorecard price and debt measures for University of Delaware and its submitted DFR peer median", "scorecard-price-title")}</div><div class="chart-footer"><span>Net price year: {esc(scorecard["institution_year"])}</span><span>Debt cohort file: {esc(scorecard["outcomes_cohort_file_year"])}</span></div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Access and outcomes</p><h2>Rates and peer medians</h2></div></div><div id="scorecard-outcome-comparison" class="comparison-chart">{comparison_svg(outcome_series, fmt_pct, "College Scorecard rates for University of Delaware and its submitted DFR peer median", "scorecard-outcome-title")}</div><div class="chart-footer"><span>Rates shown as percentages</span><span>Institution year: {esc(scorecard["institution_year"])}</span></div></article></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Focal details</p><h2>{link("OPEID6 001431", profile, "inline-evidence")}</h2></div><p>Published in-state tuition is <strong>{fmt_currency(scorecard_focal["in_state_tuition"])}</strong>; out-of-state tuition is <strong>{fmt_currency(scorecard_focal["out_of_state_tuition"])}</strong>; the admission rate is <strong>{fmt_pct(scorecard_focal["admission_rate"])}</strong>; and the federal loan rate is <strong>{fmt_pct(scorecard_focal["federal_loan_rate"])}</strong>. Earnings and debt cover federally aided cohorts defined by College Scorecard and use a different cohort year from the {esc(scorecard["institution_year"])} institution measures.</p></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Peer coverage</p><h2>Scorecard institution records</h2></div><span id="scorecard-coverage-pill" class="review-pill">{len(scorecard_peers)}/{len(default_peers)} present</span></div><div id="scorecard-table" class="table-wrap">{scorecard_peer_table(scorecard_peers)}</div></section></div>
</main>{footer()}<dialog id="method-dialog" class="method-dialog"><form method="dialog"><button aria-label="Close methodology">×</button></form><div id="method-content"></div></dialog>{scripts()}</body></html>'''


def herd_peer_table(peers):
    rows = []
    for row in peers:
        herd = row["herd"]
        exact = herd["coverage"] == "present_exact_unitid"
        unitid = link("UNITID " + row["unitid"], unitid_url(row["unitid"]), "inline-evidence")
        ncses = link(herd["ncsesId"], ncses_url(herd["ncsesId"]), "inline-evidence") if herd.get("ncsesId") else "—"
        rows.append(f'<tr><td><strong>{esc(row["name"])}</strong><br><span class="table-sub">{unitid}</span></td><td>{esc(herd.get("reportedName") or "Not resolved")}</td><td class="id-value">{ncses}</td><td>{fmt_money(herd["total"]) if exact else "Not compared"}</td><td><span class="boundary-status{" conditional" if not exact else ""}">{"Exact UNITID" if exact else "Review boundary"}</span></td></tr>')
    return '<table><thead><tr><th>IPEDS comparison institution</th><th>HERD reporting entity</th><th>NCSES ID</th><th>Total R&amp;D</th><th>Boundary status</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def herd_page():
    herd = focal["herd"]
    exact_peers = [row for row in default_peers if row["herd"]["coverage"] == "present_exact_unitid" and row["herd"]["total"] is not None]
    conditional_peers = [row for row in default_peers if row["herd"]["coverage"] == "conditional_boundary_match"]
    peer_median = median(row["herd"]["total"] for row in exact_peers)
    source_order = ["Federal government", "Institution funds", "State and local government", "All other sources", "Nonprofit organizations", "Business"]
    source_series = [(label, herd["sources"][label]) for label in source_order]
    metric_html = "".join([
        metric_card("Total R&D expenditures", fmt_money(herd["total"]), "Institutional FY2024"),
        metric_card("Federal government", fmt_money(herd["sources"]["Federal government"]), f'{herd["sources"]["Federal government"] / herd["total"] * 100:.1f}% of total'),
        metric_card("Institution funds", fmt_money(herd["sources"]["Institution funds"]), f'{herd["sources"]["Institution funds"] / herd["total"] * 100:.1f}% of total', "teal"),
        metric_card("R&D personnel", fmt_int(herd["personnel"]["Total"]), f'{fmt_int(herd["fte"]["Total"])} reported FTEs', "teal"),
    ])
    delta = herd["total"] - peer_median
    return f'''{page_head("Research · HERD | Institution Atlas", "University of Delaware FY2024 research expenditures from NCSES HERD.")}
<body data-page="herd">{site_header()}{navigation("herd")}{controls("herd")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header herd-header"><div><p class="eyebrow">NCSES · Higher Education Research and Development Survey</p><h1>Research · HERD</h1><p>Separately accounted R&amp;D expenditures reported for the institutional fiscal year under {link("NCSES ID " + herd["ncsesId"], ncses_url(herd["ncsesId"]), "header-link")}.</p></div><div class="source-actions">{link("Academic Institution Profile", ncses_url(herd["ncsesId"]), "official-button")}{link("FY2024 bulk file", contract_by_id["NCSES_HERD"]["data_access_url"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>NCSES HERD</strong></div><div><span>Period</span><strong>FY2024</strong></div><div><span>Vintage</span><strong>NCSES_HERD_FY2024</strong></div><div><span>Unit</span><strong>Thousands of dollars</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#herd-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="herd-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Funding sources</p><h2>R&amp;D expenditures by source</h2></div><button class="quiet-button" data-download="herd">Download chart data</button></div><div id="herd-source-chart" class="source-bars">{single_series_svg(source_series, fmt_money, "University of Delaware FY2024 research and development expenditures by funding source")}</div><div class="chart-footer"><span>Unit: thousands of dollars</span><span>Reporting period: institutional FY2024</span><span>Release: NCSES_HERD_FY2024</span></div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Peer position</p><h2>Boundary-verified comparison</h2><p id="herd-peer-note" class="provenance">{esc(default_mode["label"])} · {len(exact_peers)} boundary-verified of {len(default_peers)}</p></div></div><div id="herd-comparison" class="comparison-focus"><div class="focus-values"><div class="focus-value primary"><span>University of Delaware</span><strong>{fmt_money(herd["total"])}</strong></div><div class="focus-vs">versus</div><div class="focus-value"><span>Peer median · N={len(exact_peers)}</span><strong>{fmt_money(peer_median)}</strong></div></div><div class="focus-delta">Delaware is {fmt_money(abs(delta))} {"above" if delta >= 0 else "below"} the boundary-verified peer median.</div></div></article></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Peer coverage</p><h2>HERD reporting entities</h2></div><span id="herd-coverage-pill" class="review-pill">{len(exact_peers)} exact · {len(conditional_peers)} review</span></div><div id="herd-table" class="table-wrap">{herd_peer_table(default_peers)}</div></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Source boundary</p><h2>{link("U. Delaware · " + herd["ncsesId"], ncses_url(herd["ncsesId"]), "inline-evidence")}</h2></div><p>The FY2024 HERD row maps exactly to {link("IPEDS UNITID 130943", unitid_url("130943"), "inline-evidence")}. Four comparison institutions remain outside the median because their HERD reporting entities have broader or unresolved boundaries. {local_link("Open reconciliation evidence", "evidence.html#herd-reconciliation")}.</p></section></div>
</main>{footer()}<dialog id="method-dialog" class="method-dialog"><form method="dialog"><button aria-label="Close methodology">×</button></form><div id="method-content"></div></dialog>{scripts()}</body></html>'''


def nsf_awards_table():
    rows = []
    for row in nsf_awards["recent_awards"]:
        rows.append(f'''<tr><td>{link(row["award_id"], row["official_record_url"], "inline-evidence")}</td><td><strong>{esc(row["title"])}</strong><br><span class="table-sub">{esc(row["program"] or "Program not reported")}</span></td><td>{esc(row["award_date"])}</td><td>{fmt_currency(row["estimated_total_amount"])}</td><td>{esc(row["directorate"] or "Not reported")}</td><td><span class="boundary-status{' conditional' if not row['active'] else ''}">{'Active' if row['active'] else 'Not active'}</span></td></tr>''')
    return '<table><thead><tr><th>Award</th><th>Title and program</th><th>Award date</th><th>Estimated total</th><th>NSF organization</th><th>Status at snapshot</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def nsf_page():
    year_series = [(row["year"], row["award_count"]) for row in nsf_awards["year_summary"]]
    directorate_rows = "".join(f'<tr><th>{esc(row["directorate"])}</th><td>{fmt_int(row["award_count"])}</td><td>{fmt_dollars_millions(row["estimated_total_amount"])}</td></tr>' for row in nsf_awards["active_directorates"])
    metric_html = "".join([
        metric_card("All-time matching records", fmt_int(nsf_awards["all_time_record_count"]), "Exact UEI query · API history"),
        metric_card("Active award records", fmt_int(nsf_awards["active_award_count"]), f'As retrieved {nsf_awards["retrieved_at"]}'),
        metric_card("Active estimated total", fmt_dollars_millions(nsf_awards["active_estimated_total_amount"]), "Sum across active award records", "teal"),
        metric_card("Recent award records", fmt_int(nsf_awards["recent_award_count"]), f'{nsf_awards["recent_period_start"][:4]}–{nsf_awards["recent_period_end"][:4]} award dates', "teal"),
    ])
    return f'''{page_head("NSF awards | Institution Atlas", "University of Delaware National Science Foundation award records joined by exact UEI.")}
<body data-page="nsf">{site_header()}{navigation("nsf")}{controls("nsf")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header nsf-header"><div><p class="eyebrow">U.S. National Science Foundation · Awards API</p><h1>NSF awards</h1><p>Award records returned for the University of Delaware’s exact federal identifier, {link("UEI " + nsf_awards["focal_uei"], nsf_awards["query_urls"]["all"], "header-link")}.</p></div><div class="source-actions">{link("Exact UEI query", nsf_awards["query_urls"]["all"], "official-button")}{link("API documentation", nsf_awards["query_urls"]["documentation"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>NSF Awards API</strong></div><div><span>Recent window</span><strong>{esc(nsf_awards["recent_period_start"])} to {esc(nsf_awards["recent_period_end"])}</strong></div><div><span>Snapshot</span><strong>{esc(nsf_awards["retrieved_at"])}</strong></div><div><span>Unit</span><strong>Award records and dollars</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#nsf-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="nsf-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Initial award dates</p><h2>Recent award records by year</h2><p class="provenance">Exact UEI · {esc(nsf_awards["recent_period_start"])} through {esc(nsf_awards["recent_period_end"])}</p></div>{local_link("Download JSON", "data/nsf-awards.json", "record-link")}</div><div class="source-bars">{single_series_svg(year_series, fmt_int, "University of Delaware NSF award records by initial award year", "Award year")}</div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Active portfolio</p><h2>Records by NSF directorate</h2><p class="provenance">Status and amounts as returned in the {esc(nsf_awards["retrieved_at"])} snapshot.</p></div></div><div class="table-wrap"><table><thead><tr><th>Directorate</th><th>Active records</th><th>Estimated total</th></tr></thead><tbody>{directorate_rows}</tbody></table></div></article></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Measure boundary</p><h2>{link("UEI " + nsf_awards["focal_uei"], nsf_awards["query_urls"]["active"], "inline-evidence")}</h2></div><p>Counts describe NSF award records matched to the University’s UEI. Estimated total and obligated amounts are award-record fields. They are not HERD expenditures, annual spending, or a fiscal-year flow. Multi-year awards remain one award record.</p></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Most recent records</p><h2>Twenty latest awards in the review window</h2></div><span class="review-pill">{len(nsf_awards["recent_awards"])} displayed of {fmt_int(nsf_awards["recent_award_count"])}</span></div><div class="table-wrap">{nsf_awards_table()}</div></section></div>
</main>{footer()}</body></html>'''


def nih_records_table():
    rows = []
    for row in nih_reporter["recent_records"]:
        investigators = ", ".join(row["principal_investigators"]) or "Not reported"
        notice_date = (row["award_notice_date"] or "")[:10] or "Not reported"
        rows.append(f'''<tr><td>{link(str(row["appl_id"]), row["official_record_url"], "inline-evidence")}</td><td><strong>{esc(row["project_title"] or "Title not reported")}</strong><br><span class="table-sub">{esc(row["project_num"] or row["core_project_num"] or "Project number not reported")}</span></td><td>FY{esc(row["fiscal_year"])}</td><td>{fmt_currency(row["award_amount"])}</td><td>{esc(row["admin_ic_code"] or "—")}</td><td>{esc(investigators)}</td><td>{esc(notice_date)}</td></tr>''')
    return '<table><thead><tr><th>Application ID</th><th>Project</th><th>Fiscal year</th><th>Award amount</th><th>Admin IC</th><th>Principal investigator(s)</th><th>Notice date</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def nih_page():
    current = nih_reporter["year_summary"][-1]
    year_series = [(f'FY{row["fiscal_year"]}', row["application_records"]) for row in nih_reporter["year_summary"]]
    admin_rows = "".join(
        f'<tr><th>{esc(row["admin_ic"])}</th><td>{fmt_int(row["application_records"])}</td><td>{fmt_dollars_millions(row["award_amount"])}</td></tr>'
        for row in nih_reporter["admin_ic_summary"][:10]
    )
    metric_html = "".join([
        metric_card(f'FY{current["fiscal_year"]} application records', fmt_int(current["application_records"]), "One row per funded application ID"),
        metric_card(f'FY{current["fiscal_year"]} award amount', fmt_dollars_millions(current["award_amount"]), "Sum of application-record award amounts"),
        metric_card("Five-year application records", fmt_int(nih_reporter["record_count"]), f'FY{nih_reporter["fiscal_years"][0]}–FY{nih_reporter["fiscal_years"][-1]}', "teal"),
        metric_card("Distinct core projects", fmt_int(nih_reporter["distinct_core_projects"]), "Core project numbers across the window", "teal"),
    ])
    return f'''{page_head("NIH RePORTER | Institution Atlas", "University of Delaware NIH RePORTER funded application records joined by exact organization identifiers.")}
<body data-page="nih">{site_header()}{navigation("nih")}{controls("nih")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header nih-header"><div><p class="eyebrow">National Institutes of Health · RePORTER</p><h1>NIH projects</h1><p>Funded application records matched to organization IPF {link(nih_reporter["org_ipf_code"], nih_reporter["query_urls"]["search_results"], "header-link")} and verified against UEI {link(nih_reporter["uei"], nih_reporter["query_urls"]["search_results"], "header-link")}.</p></div><div class="source-actions">{link("Search results", nih_reporter["query_urls"]["search_results"], "official-button")}{link("API documentation", nih_reporter["query_urls"]["documentation"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>NIH RePORTER</strong></div><div><span>Period</span><strong>FY{nih_reporter["fiscal_years"][0]}–FY{nih_reporter["fiscal_years"][-1]}</strong></div><div><span>Snapshot</span><strong>{esc(nih_reporter["retrieved_at"])}</strong></div><div><span>Unit</span><strong>Applications and dollars</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#nih-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="nih-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Funded applications</p><h2>Application records by federal fiscal year</h2><p class="provenance">Exact organization name, IPF, and UEI required on every retained record.</p></div>{local_link("Download JSON", "data/nih-reporter.json", "record-link")}</div><div class="source-bars">{single_series_svg(year_series, fmt_int, "University of Delaware NIH RePORTER application records by federal fiscal year", "Federal fiscal year")}</div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Administering institutes</p><h2>Ten largest by application-record amount</h2><p class="provenance">Summed across the selected fiscal-year application records.</p></div></div><div class="table-wrap"><table><thead><tr><th>Administering institute or center</th><th>Application records</th><th>Award amount</th></tr></thead><tbody>{admin_rows}</tbody></table></div></article></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Record grain</p><h2>{link("Organization IPF " + nih_reporter["org_ipf_code"], nih_reporter["query_urls"]["search_results"], "inline-evidence")}</h2></div><p>Each row is a funded application record for one federal fiscal year. The same core project can appear in several years. Award amount is the amount reported on that application record; it is not a unique-project lifetime total, a USAspending obligation flow, or HERD expenditure.</p></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Latest notices</p><h2>Twenty latest application records</h2></div><span class="review-pill">20 displayed of {fmt_int(nih_reporter["record_count"])}</span></div><div class="table-wrap">{nih_records_table()}</div></section></div>
</main>{footer()}</body></html>'''


def usaspending_awards_table():
    rows = []
    for row in usaspending["largest_prime_awards"]:
        award_label = row["award_id"] or row["generated_internal_id"] or "Award record"
        award_link = link(award_label, row["official_record_url"], "inline-evidence") if row["official_record_url"] else esc(award_label)
        rows.append(f'''<tr><td>{award_link}<br><span class="table-sub">{esc(row["award_group"].title())}</span></td><td><strong>{esc(row["description"] or "Description not reported")}</strong></td><td>{fmt_dollars_millions(row["award_amount"])}</td><td>{esc(row["awarding_agency"] or "Not reported")}</td><td>{esc(row["start_date"] or "—")} to {esc(row["end_date"] or "—")}</td></tr>''')
    return '<table><thead><tr><th>Prime award</th><th>Description</th><th>Current award amount</th><th>Awarding agency</th><th>Award period</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def usaspending_page():
    current = usaspending["year_summary"][-1]
    grant_total = next(row["obligations"] for row in usaspending["type_obligations"] if row["award_type"] == "Grants")
    grant_share = grant_total / usaspending["five_year_obligations"]
    year_series = [(f'FY{row["fiscal_year"]}', row["obligations"]) for row in usaspending["year_summary"]]
    type_rows = "".join(f'<tr><th>{esc(row["award_type"])}</th><td>{fmt_dollars_millions(row["obligations"])}</td><td>{fmt_pct(row["obligations"] / usaspending["five_year_obligations"])}</td></tr>' for row in usaspending["type_obligations"])
    agency_rows = "".join(f'<tr><th>{esc(row["name"])}</th><td>{esc(row["code"])}</td><td>{fmt_dollars_millions(row["amount"])}</td></tr>' for row in usaspending["awarding_agencies"][:10])
    metric_html = "".join([
        metric_card(f'FY{current["fiscal_year"]} obligations', fmt_dollars_millions(current["obligations"]), "Transaction-level federal obligations"),
        metric_card("Five-year obligations", fmt_dollars_compact(usaspending["five_year_obligations"]), f'FY{usaspending["fiscal_years"][0]}–FY{usaspending["fiscal_years"][-1]}'),
        metric_card("Prime award records", fmt_int(usaspending["prime_award_count"]), "Awards with activity in the selected window", "teal"),
        metric_card("Grant share", fmt_pct(grant_share), "Share of five-year obligations", "teal"),
    ])
    return f'''{page_head("USAspending | Institution Atlas", "University of Delaware federal prime awards and obligation trends from USAspending.")}
<body data-page="usaspending">{site_header()}{navigation("usaspending")}{controls("usaspending")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header usaspending-header"><div><p class="eyebrow">U.S. Department of the Treasury · USAspending</p><h1>Federal awards</h1><p>Prime awards and transaction-level obligations matched to direct recipient UEI {link(usaspending["uei"], usaspending["query_urls"]["recipient_profile"], "header-link")}.</p></div><div class="source-actions">{link("Recipient profile", usaspending["query_urls"]["recipient_profile"], "official-button")}{link("API documentation", usaspending["query_urls"]["api_documentation"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>USAspending</strong></div><div><span>Period</span><strong>FY{usaspending["fiscal_years"][0]}–FY{usaspending["fiscal_years"][-1]}</strong></div><div><span>Snapshot</span><strong>{esc(usaspending["retrieved_at"])}</strong></div><div><span>Unit</span><strong>Obligations and awards</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#usaspending-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="usaspending-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Transaction flow</p><h2>Federal obligations by fiscal year</h2><p class="provenance">Direct recipient UEI · prime-award transactions.</p></div>{local_link("Download JSON", "data/usaspending.json", "record-link")}</div><div class="source-bars">{single_series_svg(year_series, fmt_dollars_millions, "University of Delaware federal obligations by fiscal year", "Federal fiscal year")}</div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Award types</p><h2>Five-year obligations by type</h2><p class="provenance">Shares use transaction-level obligations.</p></div></div><div class="table-wrap"><table><thead><tr><th>Award type</th><th>Obligations</th><th>Share</th></tr></thead><tbody>{type_rows}</tbody></table></div></article></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Awarding agencies</p><h2>Largest obligation totals in the selected window</h2></div></div><div class="table-wrap"><table><thead><tr><th>Awarding agency</th><th>Code</th><th>Obligations</th></tr></thead><tbody>{agency_rows}</tbody></table></div></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Grain boundary</p><h2>{link("Recipient UEI " + usaspending["uei"], usaspending["query_urls"]["recipient_profile"], "inline-evidence")}</h2></div><p>Annual values are sums of transaction obligations. The award count and list below are prime-award records with activity in the period. Current award amount can span several years. Outlays, subawards, parent-recipient rollups, and awards to related organizations are not included in the displayed totals.</p></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Largest records</p><h2>Twenty largest grants and contracts</h2></div><span class="review-pill">Current award amounts</span></div><div class="table-wrap">{usaspending_awards_table()}</div></section></div>
</main>{footer()}</body></html>'''


def openalex_page():
    latest = next(row for row in openalex["year_summary"] if row["label"] == openalex["window_end"][:4])
    oa_share = openalex["open_access_works"] / openalex["works_count"]
    topic_share = openalex["topic_classified_works"] / openalex["works_count"]
    year_series = [(row["label"], row["works"]) for row in openalex["year_summary"]]
    domain_rows = "".join(f'<tr><th>{esc(row["label"])}</th><td>{fmt_int(row["works"])}</td><td>{fmt_pct(row["works"] / openalex["works_count"])}</td></tr>' for row in openalex["domain_summary"])
    oa_rows = "".join(f'<tr><th>{esc(row["label"].title())}</th><td>{fmt_int(row["works"])}</td><td>{fmt_pct(row["works"] / openalex["works_count"])}</td></tr>' for row in openalex["open_access_summary"])
    field_rows = "".join(f'<tr><th>{esc(row["label"])}</th><td>{fmt_int(row["works"])}</td><td>{fmt_pct(row["works"] / openalex["works_count"])}</td></tr>' for row in openalex["field_summary"])
    metric_html = "".join([
        metric_card("Works in selected years", fmt_int(openalex["works_count"]), f'{openalex["window_start"][:4]}–{openalex["window_end"][:4]} publication years'),
        metric_card(f'{latest["label"]} works', fmt_int(latest["works"]), "Latest complete calendar year"),
        metric_card("Open access", fmt_pct(oa_share), f'{fmt_int(openalex["open_access_works"])} works', "teal"),
        metric_card("Primary-topic coverage", fmt_pct(topic_share), f'{fmt_int(openalex["topic_classified_works"])} works', "teal"),
    ])
    return f'''{page_head("OpenAlex | Institution Atlas", "University of Delaware scholarly works linked to the exact OpenAlex institution record.")}
<body data-page="openalex">{site_header()}{navigation("openalex")}{controls("openalex")}
<main id="main" class="page-shell"><div id="boundary-alert" class="boundary-alert" hidden></div>
  <section class="source-header openalex-header"><div><p class="eyebrow">OurResearch · OpenAlex research graph</p><h1>Publications and works</h1><p>Indexed works with at least one authorship linked to {link(openalex["openalex_id"], openalex["query_urls"]["institution"], "header-link")}, matched through {link("ROR 01sbq1a82", openalex["query_urls"]["ror"], "header-link")}.</p></div><div class="source-actions">{link("Institution record", openalex["query_urls"]["institution"], "official-button")}{link("API documentation", openalex["query_urls"]["documentation"], "official-button")}</div></section>
  <section class="provenance-bar"><div><span>Source</span><strong>OpenAlex</strong></div><div><span>Period</span><strong>{esc(openalex["window_start"][:4])}–{esc(openalex["window_end"][:4])}</strong></div><div><span>Snapshot</span><strong>{esc(openalex["retrieved_at"])}</strong></div><div><span>Unit</span><strong>Indexed works</strong></div><div><span>Verification</span><strong>{local_link("Reconciled", "evidence.html#openalex-reconciliation", "verified-text")}</strong></div></section>
  <div class="requires-core"><section id="openalex-metrics" class="metric-grid">{metric_html}</section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Publication years</p><h2>Indexed works by year</h2><p class="provenance">Exact OpenAlex institution ID; publication year assigned by OpenAlex.</p></div>{local_link("Download JSON", "data/openalex.json", "record-link")}</div><div class="source-bars">{single_series_svg(year_series, fmt_int, "University of Delaware OpenAlex works by publication year", "Publication year")}</div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Primary topics</p><h2>Works by broad domain</h2><p class="provenance">One primary topic domain per classified work.</p></div></div><div class="table-wrap"><table><thead><tr><th>Domain</th><th>Works</th><th>Share of all works</th></tr></thead><tbody>{domain_rows}</tbody></table></div></article></section>
  <section class="dashboard-grid equal-grid"><article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Access status</p><h2>Open-access categories</h2></div></div><div class="table-wrap"><table><thead><tr><th>Status</th><th>Works</th><th>Share</th></tr></thead><tbody>{oa_rows}</tbody></table></div></article>
  <article class="panel panel-wide"><div class="panel-heading"><div><p class="section-kicker">Primary fields</p><h2>Twelve largest fields</h2></div></div><div class="table-wrap"><table><thead><tr><th>Field</th><th>Works</th><th>Share</th></tr></thead><tbody>{field_rows}</tbody></table></div></article></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Institution boundary</p><h2>{link(openalex["openalex_id"], openalex["query_urls"]["institution_api"], "inline-evidence")}</h2></div><p>{esc(openalex["boundary_note"])} These counts describe the indexed research graph and can change as works, affiliations, open-access status, and topic assignments are updated. Work types include articles, preprints, conference papers, datasets, and other objects.</p></section></div>
</main>{footer()}</body></html>'''


def evidence_page():
    identity_rows = "".join(f'<tr id="evidence-{esc(row["identifier_type"].lower())}"><th>{esc(row["identifier_type"].replace("_", " "))}</th><td>{identifier_link(row)}</td><td>{link(row["source"], row["source_url"])}</td><td>{esc(row["note"])}</td><td>{esc(row["verified_date"])}</td></tr>' for row in identifiers)
    ipeds_rows = []
    herd_rows = []
    level_by_variable = {"totalEnrollment": "1", "undergraduate": "2", "graduate": "12", "fullTime": "21", "partTime": "41"}
    for row in reconciliation:
        cells = f'<tr><th>{esc(row["variable"])}</th><td>{esc(row["display_data_value"])} {esc(row["unit"])}</td><td><code>{esc(row["source_locator"])}</code></td><td><span class="confirm-badge">{esc(row["result"].title())}</span></td></tr>'
        if row["page"] == "IPEDS core":
            ipeds_rows.append(cells)
        else:
            herd_rows.append(cells)
    scorecard_fields = [
        ("Undergraduate enrollment", f'{scorecard["institution_year"]}.student.size', fmt_int(scorecard_focal["undergraduate_enrollment"])),
        ("In-state tuition", f'{scorecard["institution_year"]}.cost.tuition.in_state', fmt_currency(scorecard_focal["in_state_tuition"])),
        ("Out-of-state tuition", f'{scorecard["institution_year"]}.cost.tuition.out_of_state', fmt_currency(scorecard_focal["out_of_state_tuition"])),
        ("Average net price", f'{scorecard["institution_year"]}.cost.avg_net_price.overall', fmt_currency(scorecard_focal["average_net_price"])),
        ("Pell Grant rate", f'{scorecard["institution_year"]}.aid.pell_grant_rate', fmt_pct(scorecard_focal["pell_grant_rate"])),
        ("Federal loan rate", f'{scorecard["institution_year"]}.aid.federal_loan_rate', fmt_pct(scorecard_focal["federal_loan_rate"])),
        ("Completion within 150%", f'{scorecard["institution_year"]}.completion.rate_suppressed.four_year', fmt_pct(scorecard_focal["completion_rate_150"])),
        ("Full-time retention", f'{scorecard["institution_year"]}.student.retention_rate.four_year.full_time', fmt_pct(scorecard_focal["retention_rate_full_time"])),
        ("Admission rate", f'{scorecard["institution_year"]}.admissions.admission_rate.overall', fmt_pct(scorecard_focal["admission_rate"])),
        ("Median earnings · 10 years", f'{scorecard["outcomes_cohort_file_year"]}.earnings.10_yrs_after_entry.median', fmt_currency(scorecard_focal["median_earnings_10_year"])),
        ("Median debt · completers", f'{scorecard["outcomes_cohort_file_year"]}.aid.median_debt.completers.overall', fmt_currency(scorecard_focal["median_debt_completers"])),
    ]
    scorecard_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td><td><code>id=130943 · {esc(field)}</code></td><td><span class="confirm-badge">Matched</span></td></tr>' for label, field, value in scorecard_fields)
    nsf_fields = [
        ("All-time matching records", "query=ueiNumber; metadata.totalCount", fmt_int(nsf_awards["all_time_record_count"])),
        ("Active award records", "query=ueiNumber+ActiveAwards; metadata.totalCount", fmt_int(nsf_awards["active_award_count"])),
        ("Active estimated total", "sum(active award.estimatedTotalAmt)", fmt_dollars_millions(nsf_awards["active_estimated_total_amount"])),
        ("Recent award records", "query=ueiNumber+dateStart+dateEnd; metadata.totalCount", fmt_int(nsf_awards["recent_award_count"])),
    ]
    nsf_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td><td><code>UEI={esc(nsf_awards["focal_uei"])} · {esc(locator)}</code></td><td><span class="confirm-badge">Matched</span></td></tr>' for label, locator, value in nsf_fields)
    nih_current = nih_reporter["year_summary"][-1]
    nih_fields = [
        (f'FY{nih_current["fiscal_year"]} application records', "count(appl_id) where fiscal_year=current", fmt_int(nih_current["application_records"])),
        (f'FY{nih_current["fiscal_year"]} award amount', "sum(award_amount) where fiscal_year=current", fmt_dollars_millions(nih_current["award_amount"])),
        ("Five-year application records", "count(appl_id) across selected fiscal years", fmt_int(nih_reporter["record_count"])),
        ("Distinct core projects", "count(distinct core_project_num)", fmt_int(nih_reporter["distinct_core_projects"])),
    ]
    nih_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td><td><code>org_ipf_code={esc(nih_reporter["org_ipf_code"])} · {esc(locator)}</code></td><td><span class="confirm-badge">Matched</span></td></tr>' for label, locator, value in nih_fields)
    usa_current = usaspending["year_summary"][-1]
    usa_fields = [
        (f'FY{usa_current["fiscal_year"]} obligations', "spending_over_time.aggregated_amount", fmt_dollars_millions(usa_current["obligations"])),
        ("Five-year obligations", "sum(fiscal-year aggregated_amount)", fmt_dollars_compact(usaspending["five_year_obligations"])),
        ("Prime award records", "sum(spending_by_award_count results)", fmt_int(usaspending["prime_award_count"])),
    ]
    usa_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td><td><code>recipient_uei={esc(usaspending["uei"])} · {esc(locator)}</code></td><td><span class="confirm-badge">Matched</span></td></tr>' for label, locator, value in usa_fields)
    openalex_fields = [
        ("Works in selected years", "group_by=publication_year; meta.count", fmt_int(openalex["works_count"])),
        ("Open-access works", "group_by=open_access.oa_status; sum(non-closed)", fmt_int(openalex["open_access_works"])),
        ("Primary-topic classified works", "group_by=primary_topic.domain.id; sum(count)", fmt_int(openalex["topic_classified_works"])),
    ]
    openalex_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td><td><code>institution={esc(openalex["openalex_id"])} · {esc(locator)}</code></td><td><span class="confirm-badge">Matched</span></td></tr>' for label, locator, value in openalex_fields)
    return f'''{page_head("Evidence | Institution Atlas", "Identifier and value reconciliation evidence for the University of Delaware Institution Atlas.")}
<body data-page="evidence">{site_header()}{navigation("")}
<main id="main" class="page-shell evidence-page"><section class="source-header"><div><p class="eyebrow">Evidence register</p><h1>How each identifier and value was checked</h1><p>Official records, exact releases, and source-row locators used in the delivered pages.</p></div></section>
  <section class="panel data-table-panel" id="identity-evidence"><div class="panel-heading"><div><p class="section-kicker">Identity</p><h2>Identifier evidence</h2></div></div><div class="table-wrap"><table><thead><tr><th>Identifier</th><th>Value</th><th>Official evidence</th><th>Note</th><th>Checked</th></tr></thead><tbody>{identity_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="ipeds-reconciliation"><div class="panel-heading"><div><p class="section-kicker">IPEDS Fall Enrollment</p><h2>Reconciliation record</h2><p class="provenance">Every displayed value below matched the exact public-use-file row.</p></div></div><div class="citation-grid"><article><span>Browser-facing records</span>{link("Fall 2022 reported data", unitid_url("130943", "2022"))}<br>{link("Fall 2023 reported data", unitid_url("130943", "2023"))}</article><article><span>Exact bulk releases</span>{link("EF2022A.zip", "https://nces.ed.gov/ipeds/datacenter/data/EF2022A.zip")}<br>{link("EF2023A.zip", "https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip")}</article><article><span>Institution key</span>{link("UNITID 130943", unitid_url("130943", "2023"))}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact source-row locator</th><th>Result</th></tr></thead><tbody>{"".join(ipeds_rows)}</tbody></table></div></section>
  <section class="panel data-table-panel" id="herd-reconciliation"><div class="panel-heading"><div><p class="section-kicker">NCSES HERD FY2024</p><h2>Reconciliation record</h2><p class="provenance">Values were checked against the FY2024 public-use file at the NCSES reporting-entity grain.</p></div></div><div class="citation-grid"><article><span>Browser-facing profile</span>{link("U. Delaware · U3284001", ncses_url("U3284001"))}</article><article><span>Exact bulk release</span>{link("higher_education_r_and_d_2024.zip", contract_by_id["NCSES_HERD"]["data_access_url"])}</article><article><span>Join rule</span><code>ncses_inst_id=U3284001 + questionnaire_no + row + column</code></article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact source-row locator</th><th>Result</th></tr></thead><tbody>{"".join(herd_rows)}</tbody></table></div></section>
  <section class="panel data-table-panel" id="scorecard-reconciliation"><div class="panel-heading"><div><p class="section-kicker">College Scorecard</p><h2>Reconciliation record</h2><p class="provenance">Displayed values match the official API response stored on {esc(scorecard["retrieved_at"])}. Each metric retains its API field and file year.</p></div></div><div class="citation-grid"><article><span>Institution profile</span>{link("University of Delaware · UNITID 130943", scorecard["official_profile_url"])}</article><article><span>Documentation and data</span>{link("Institution documentation", scorecard["documentation_url"])}<br>{link("Official data downloads", scorecard["data_url"])}</article><article><span>Published snapshot</span>{local_link("scorecard.json", "data/scorecard.json")}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact API locator</th><th>Result</th></tr></thead><tbody>{scorecard_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="nsf-reconciliation"><div class="panel-heading"><div><p class="section-kicker">NSF Awards API</p><h2>Reconciliation record</h2><p class="provenance">Counts and aggregates were rebuilt from exact-UEI API results retrieved {esc(nsf_awards["retrieved_at"])}.</p></div></div><div class="citation-grid"><article><span>Exact source query</span>{link("UEI " + nsf_awards["focal_uei"], nsf_awards["query_urls"]["all"])}</article><article><span>API documentation</span>{link("NSF Awards API", nsf_awards["query_urls"]["documentation"])}</article><article><span>Published snapshot</span>{local_link("nsf-awards.json", "data/nsf-awards.json")}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact API locator</th><th>Result</th></tr></thead><tbody>{nsf_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="nih-reconciliation"><div class="panel-heading"><div><p class="section-kicker">NIH RePORTER</p><h2>Reconciliation record</h2><p class="provenance">All retained application records matched the exact organization name, IPF, and UEI in the {esc(nih_reporter["retrieved_at"])} API snapshot.</p></div></div><div class="citation-grid"><article><span>Search results</span>{link("Organization IPF " + nih_reporter["org_ipf_code"], nih_reporter["query_urls"]["search_results"])}</article><article><span>API documentation</span>{link("NIH RePORTER API", nih_reporter["query_urls"]["documentation"])}</article><article><span>Published snapshot</span>{local_link("nih-reporter.json", "data/nih-reporter.json")}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact API locator</th><th>Result</th></tr></thead><tbody>{nih_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="usaspending-reconciliation"><div class="panel-heading"><div><p class="section-kicker">USAspending</p><h2>Reconciliation record</h2><p class="provenance">Transaction aggregates and prime-award counts use direct recipient UEI {esc(usaspending["uei"])} in the {esc(usaspending["retrieved_at"])} snapshot.</p></div></div><div class="citation-grid"><article><span>Recipient profile</span>{link("University of Delaware · " + usaspending["uei"], usaspending["query_urls"]["recipient_profile"])}</article><article><span>API documentation</span>{link("USAspending endpoints", usaspending["query_urls"]["api_documentation"])}</article><article><span>Published snapshot</span>{local_link("usaspending.json", "data/usaspending.json")}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact API locator</th><th>Result</th></tr></thead><tbody>{usa_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="openalex-reconciliation"><div class="panel-heading"><div><p class="section-kicker">OpenAlex</p><h2>Reconciliation record</h2><p class="provenance">Grouped counts use the exact institution record {esc(openalex["openalex_id"])} and exclude child and related organizations.</p></div></div><div class="citation-grid"><article><span>Institution record</span>{link(openalex["openalex_id"] + " · ROR 01sbq1a82", openalex["query_urls"]["institution"])}</article><article><span>Exact grouped query</span>{link("Publication-year query", openalex["query_urls"]["works_api"])}</article><article><span>Published snapshot</span>{local_link("openalex.json", "data/openalex.json")}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact API locator</th><th>Result</th></tr></thead><tbody>{openalex_rows}</tbody></table></div></section>
</main>{footer()}</body></html>'''


def maintenance_page():
    log_rows = "".join(f'<tr><td>{esc(row["date"])}</td><td>{esc(row["type"])}</td><td>{esc(row["owner"])}</td><td>{esc(row["result"])}</td><td>{esc(row["details"])}</td></tr>' for row in maintenance["history"])
    source_rows = "".join(f'<tr><th>{esc(row["display_name"])}</th><td>{esc(row["owner"])}</td><td>{esc(row["check_cadence"])}</td><td>{esc(row["last_verified_date"])}</td><td>{link("Documentation", row["documentation_url"])} · {link("Data", row["data_access_url"])}</td></tr>' for row in contracts)
    latest = maintenance["last_completed_review"]
    return f'''{page_head("Maintenance | Institution Atlas", "Monthly review ownership, source checks, and revision history for Institution Atlas.")}
<body data-page="maintenance">{site_header()}{navigation("maintenance")}
<main id="main" class="page-shell"><section class="source-header"><div><p class="eyebrow">Maintenance record</p><h1>Who checks the atlas, and when</h1><p>The record separates a completed source review from planned work and keeps each source contract assigned.</p></div></section>
  <section class="maintenance-cards"><article><span>Review owner</span><strong>{esc(maintenance["owner"])}</strong><p>{esc(maintenance["owner_role"])}</p></article><article><span>Cadence</span><strong>{esc(maintenance["cadence"])}</strong><p>{esc(maintenance["schedule"])}</p></article><article><span>Last completed</span><strong>{esc(latest["date_display"])}</strong><p>{esc(latest["result"])}</p></article><article><span>Next review</span><strong>{esc(maintenance["next_review"])}</strong><p>Review automated link results and source changes.</p></article></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Visible history</p><h2>Maintenance log</h2></div>{link("GitHub workflow", maintenance["workflow_url"], "record-link")}</div><div class="table-wrap"><table><thead><tr><th>Date</th><th>Review type</th><th>Owner</th><th>Result</th><th>Details</th></tr></thead><tbody>{log_rows}</tbody></table></div></section>
  <section class="panel data-table-panel"><div class="panel-heading"><div><p class="section-kicker">Assigned contracts</p><h2>Source review ownership</h2></div></div><div class="table-wrap"><table><thead><tr><th>Source</th><th>Owner</th><th>Cadence</th><th>Last verified</th><th>Official links</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
  <section class="panel definition-strip"><div><p class="section-kicker">Published records</p><h2>Machine-readable maintenance files</h2></div><p>{local_link("Maintenance log JSON", "data/maintenance-log.json")} · {local_link("Source contracts JSON", "data/source-contracts.json")} · {local_link("Reconciliation CSV", "data/reconciliation.csv")} · {local_link("IPEDS vintage diff CSV", "data/vintage-diff.csv")} · {local_link("College Scorecard JSON", "data/scorecard.json")} · {local_link("NSF awards JSON", "data/nsf-awards.json")} · {local_link("NIH RePORTER JSON", "data/nih-reporter.json")} · {local_link("USAspending JSON", "data/usaspending.json")} · {local_link("OpenAlex JSON", "data/openalex.json")}</p></section>
</main>{footer()}</body></html>'''


pages = {
    "index.html": identity_page(),
    "ipeds.html": ipeds_page(),
    "scorecard.html": scorecard_page(),
    "herd.html": herd_page(),
    "nsf-awards.html": nsf_page(),
    "nih-reporter.html": nih_page(),
    "usaspending.html": usaspending_page(),
    "openalex.html": openalex_page(),
    "evidence.html": evidence_page(),
    "maintenance.html": maintenance_page(),
}


(DATA / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


for output in OUTPUTS:
    output.mkdir(parents=True, exist_ok=True)
    for name, content in pages.items():
        (output / name).write_text(content.rstrip() + "\n", encoding="utf-8")
    shutil.copy2(ASSETS / "styles.css", output / "styles.css")
    shutil.copy2(ASSETS / "app.js", output / "app.js")
    (output / "atlas-data.js").write_text("window.ATLAS_DATA=" + json.dumps(atlas, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    export_dir = output / "data"
    export_dir.mkdir(exist_ok=True)
    for source_name, export_name in [
        ("atlas.json", "atlas.json"),
        ("source-contracts.json", "source-contracts.json"),
        ("maintenance-log.json", "maintenance-log.json"),
        ("DELAWARE_IDENTITY_REGISTRY.csv", "identity-registry.csv"),
        ("reconciliation.csv", "reconciliation.csv"),
        ("vintage-diff.csv", "vintage-diff.csv"),
        ("scorecard.json", "scorecard.json"),
        ("nsf-awards.json", "nsf-awards.json"),
        ("nih-reporter.json", "nih-reporter.json"),
        ("usaspending.json", "usaspending.json"),
        ("openalex.json", "openalex.json"),
    ]:
        shutil.copy2(DATA / source_name, export_dir / export_name)
    if (DATA / "link-check.json").exists():
        shutil.copy2(DATA / "link-check.json", export_dir / "link-check.json")

print(json.dumps({"status": "built", "pages": list(pages), "default_peer_count": len(default_peers), "output": [str(path) for path in OUTPUTS]}, indent=2))
