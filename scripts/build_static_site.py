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
reconciliation = load_csv("reconciliation.csv")
vintage_diff = load_csv("vintage-diff.csv")
atlas["identifiers"] = load_csv("DELAWARE_IDENTITY_REGISTRY.csv")
atlas["aliases"] = load_csv("DELAWARE_ALIAS_REGISTRY.csv")
atlas["relatedOrganizations"] = load_csv("DELAWARE_RELATED_ORGANIZATIONS.csv")
atlas["sourceCoverage"] = load_csv("SOURCE_COVERAGE_MATRIX.csv")
identifiers = [row for row in atlas["identifiers"] if row["status"] == "confirmed"]
focal = atlas["records"][atlas["institution"]["unitid"]]
default_mode = atlas["peerModes"]["DFR_SUBMITTED"]
default_peers = [atlas["records"][unitid] for unitid in default_mode["unitids"]]
contract_by_id = {row["source_id"]: row for row in contracts}


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def fmt_int(value):
    return "—" if value is None else f"{round(value):,}"


def fmt_money(value):
    return "—" if value is None else f"${value / 1000:,.1f}M"


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
        ("herd", "herd.html", "03", "Research · HERD"),
        ("maintenance", "maintenance.html", "04", "Maintenance"),
    ]
    links = []
    for key, href, number, label in items:
        attrs = ' class="active" aria-current="page"' if key == active else ""
        links.append(f'<a{attrs} href="{href}"><span>{number}</span> {esc(label)}</a>')
    return '<nav class="page-nav" aria-label="Atlas sections">' + "".join(links) + "</nav>"


def controls(page):
    peer_options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == "DFR_SUBMITTED" else ""}>{esc(value["label"])}</option>'
        for key, value in atlas["peerModes"].items()
    )
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
    else:
        year = '<select id="year-control" disabled><option>Source-specific</option></select><span class="control-status">Not applicable</span>'
        vintage = '<select id="vintage-control" disabled><option>Latest verified</option></select><span class="control-status">Not applicable</span>'
    return f'''<section class="control-rail" aria-label="Persistent atlas controls">
  <label class="control-locked">Institution<select id="institution-control" disabled><option>{esc(atlas["institution"]["name"])}</option></select><span class="control-status">Fixed pilot</span></label>
  <label class="control-limited">Reporting boundary<select id="boundary-control" aria-describedby="boundary-control-note">{boundary_options}</select><span id="boundary-control-note" class="control-status">Core is the only reviewed boundary</span></label>
  <label>Peer group<select id="peer-control">{peer_options}</select></label>
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


def comparison_svg(series, value_formatter, title):
    max_value = max(max(row[1] or 0, row[2] or 0) for row in series) or 1
    width, left, plot = 920, 190, 650
    height = 58 * len(series) + 48
    elements = [f'<svg class="static-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title"><title id="chart-title">{esc(title)}</title>', '<g class="svg-legend"><rect x="190" y="10" width="12" height="12" rx="2"/><text x="208" y="21">University of Delaware</text><rect class="peer" x="390" y="10" width="12" height="12" rx="2"/><text x="408" y="21">Peer median</text></g>']
    for index, (label, focal_value, peer_value) in enumerate(series):
        y = 44 + index * 58
        focal_width = (focal_value or 0) / max_value * plot
        peer_width = (peer_value or 0) / max_value * plot
        elements.append(f'<text class="svg-label" x="0" y="{y + 18}">{esc(label)}</text><rect class="svg-track" x="{left}" y="{y}" width="{plot}" height="18" rx="4"/><rect class="svg-bar" x="{left}" y="{y}" width="{focal_width:.2f}" height="18" rx="4"/><text class="svg-value" x="{left + 8}" y="{y + 14}">{esc(value_formatter(focal_value))}</text><rect class="svg-track" x="{left}" y="{y + 23}" width="{plot}" height="18" rx="4"/><rect class="svg-bar peer" x="{left}" y="{y + 23}" width="{peer_width:.2f}" height="18" rx="4"/><text class="svg-value" x="{left + 8}" y="{y + 37}">{esc(value_formatter(peer_value))}</text>')
    elements.append("</svg>")
    table_rows = "".join(f'<tr><th>{esc(label)}</th><td>{esc(value_formatter(focal_value))}</td><td>{esc(value_formatter(peer_value))}</td></tr>' for label, focal_value, peer_value in series)
    elements.append(f'<div class="table-wrap chart-table"><table><thead><tr><th>Measure</th><th>University of Delaware</th><th>Peer median</th></tr></thead><tbody>{table_rows}</tbody></table></div>')
    return "".join(elements)


def single_series_svg(series, value_formatter, title):
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
    elements.append(f'<div class="table-wrap chart-table"><table><thead><tr><th>Funding source</th><th>University of Delaware</th></tr></thead><tbody>{table_rows}</tbody></table></div>')
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
    return f'''{page_head("Evidence | Institution Atlas", "Identifier and value reconciliation evidence for the University of Delaware Institution Atlas.")}
<body data-page="evidence">{site_header()}{navigation("")}
<main id="main" class="page-shell evidence-page"><section class="source-header"><div><p class="eyebrow">Evidence register</p><h1>How each identifier and value was checked</h1><p>Official records, exact releases, and source-row locators used in the delivered pages.</p></div></section>
  <section class="panel data-table-panel" id="identity-evidence"><div class="panel-heading"><div><p class="section-kicker">Identity</p><h2>Identifier evidence</h2></div></div><div class="table-wrap"><table><thead><tr><th>Identifier</th><th>Value</th><th>Official evidence</th><th>Note</th><th>Checked</th></tr></thead><tbody>{identity_rows}</tbody></table></div></section>
  <section class="panel data-table-panel" id="ipeds-reconciliation"><div class="panel-heading"><div><p class="section-kicker">IPEDS Fall Enrollment</p><h2>Reconciliation record</h2><p class="provenance">Every displayed value below matched the exact public-use-file row.</p></div></div><div class="citation-grid"><article><span>Browser-facing records</span>{link("Fall 2022 reported data", unitid_url("130943", "2022"))}<br>{link("Fall 2023 reported data", unitid_url("130943", "2023"))}</article><article><span>Exact bulk releases</span>{link("EF2022A.zip", "https://nces.ed.gov/ipeds/datacenter/data/EF2022A.zip")}<br>{link("EF2023A.zip", "https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip")}</article><article><span>Institution key</span>{link("UNITID 130943", unitid_url("130943", "2023"))}</article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact source-row locator</th><th>Result</th></tr></thead><tbody>{"".join(ipeds_rows)}</tbody></table></div></section>
  <section class="panel data-table-panel" id="herd-reconciliation"><div class="panel-heading"><div><p class="section-kicker">NCSES HERD FY2024</p><h2>Reconciliation record</h2><p class="provenance">Values were checked against the FY2024 public-use file at the NCSES reporting-entity grain.</p></div></div><div class="citation-grid"><article><span>Browser-facing profile</span>{link("U. Delaware · U3284001", ncses_url("U3284001"))}</article><article><span>Exact bulk release</span>{link("higher_education_r_and_d_2024.zip", contract_by_id["NCSES_HERD"]["data_access_url"])}</article><article><span>Join rule</span><code>ncses_inst_id=U3284001 + questionnaire_no + row + column</code></article></div><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Displayed value</th><th>Exact source-row locator</th><th>Result</th></tr></thead><tbody>{"".join(herd_rows)}</tbody></table></div></section>
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
  <section class="panel definition-strip"><div><p class="section-kicker">Published records</p><h2>Machine-readable maintenance files</h2></div><p>{local_link("Maintenance log JSON", "data/maintenance-log.json")} · {local_link("Source contracts JSON", "data/source-contracts.json")} · {local_link("Reconciliation CSV", "data/reconciliation.csv")} · {local_link("IPEDS vintage diff CSV", "data/vintage-diff.csv")}</p></section>
</main>{footer()}</body></html>'''


pages = {
    "index.html": identity_page(),
    "ipeds.html": ipeds_page(),
    "herd.html": herd_page(),
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
    ]:
        shutil.copy2(DATA / source_name, export_dir / export_name)
    if (DATA / "link-check.json").exists():
        shutil.copy2(DATA / "link-check.json", export_dir / "link-check.json")

print(json.dumps({"status": "built", "pages": list(pages), "default_peer_count": len(default_peers), "output": [str(path) for path in OUTPUTS]}, indent=2))
