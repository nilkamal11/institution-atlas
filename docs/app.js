(() => {
  const data = window.ATLAS_DATA;
  const key = "institution-atlas-state-v1";
  const defaults = {
    boundary: "CORE",
    peerMode: "DFR_SUBMITTED",
    customPeers: data.peerModes.CUSTOM.unitids,
    ipedsVintage: "IPEDS_EF2023A"
  };
  let state;
  try { state = { ...defaults, ...JSON.parse(localStorage.getItem(key) || "{}") }; }
  catch { state = { ...defaults }; }

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const save = () => localStorage.setItem(key, JSON.stringify(state));
  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

  const activePeerIds = () => state.peerMode === "CUSTOM" ? state.customPeers : data.peerModes[state.peerMode].unitids;
  const activeMode = () => data.peerModes[state.peerMode];

  function syncControls() {
    const boundary = $("#boundary-control");
    const peers = $("#peer-control");
    const year = $("#year-control");
    const vintage = $("#vintage-control");
    if (boundary) boundary.value = state.boundary;
    if (peers) peers.value = state.peerMode;
    if (document.body.dataset.page === "ipeds") {
      if (year) year.value = state.ipedsVintage;
      if (vintage) vintage.value = state.ipedsVintage;
      const changeVintage = event => {
        state.ipedsVintage = event.target.value;
        if (year) year.value = state.ipedsVintage;
        if (vintage) vintage.value = state.ipedsVintage;
        save();
        renderPage();
      };
      year?.addEventListener("change", changeVintage);
      vintage?.addEventListener("change", changeVintage);
    }
    boundary?.addEventListener("change", event => {
      state.boundary = event.target.value;
      save();
      updateBoundary();
      renderPage();
    });
    peers?.addEventListener("change", event => {
      state.peerMode = event.target.value;
      save();
      renderPage();
    });
  }

  function updateBoundary() {
    const alert = $("#boundary-alert");
    const supported = state.boundary === "CORE";
    if (alert) {
      alert.hidden = supported;
      alert.textContent = supported ? "" : "No reviewed entity set is available for this boundary. Source panels are disabled until the related organizations are approved.";
    }
    const title = $("#boundary-title");
    const copy = $("#boundary-copy");
    const labels = {
      CORE: ["Core campus", "The degree-granting institution reported to IPEDS under UNITID 130943."],
      CORE_FFRDC: ["Core plus FFRDC", "University of Delaware does not administer an FFRDC in the February 2026 master list."],
      CORE_AFFIL: ["Core plus affiliates", "Related research organizations have proposed dispositions, but none have been approved for rollup."],
      CORE_HEALTH: ["Core plus health system", "No health-system boundary has been reviewed for this pilot."],
      SYSTEM: ["System", "IPEDS HD2024 does not assign University of Delaware to a reporting system."],
    };
    if (title) title.textContent = labels[state.boundary][0];
    if (copy) copy.textContent = labels[state.boundary][1];
    document.body.classList.toggle("boundary-disabled", !supported);
  }

  function renderIdentityTable() {
    const target = $("#identity-table");
    if (!target) return;
    const rows = data.identifiers.filter(row => row.status === "confirmed").slice(0, 14);
    target.innerHTML = `<table><thead><tr><th>Identifier</th><th>Value</th><th>Source</th><th>Status</th></tr></thead><tbody>${rows.map(row => `
      <tr><td>${esc(row.identifier_type.replaceAll("_", " "))}</td><td class="id-value">${esc(row.identifier_value)}</td><td>${esc(row.source)}</td><td><span class="confirm-badge">Confirmed</span></td></tr>`).join("")}</tbody></table>`;
  }

  function renderPeerMode() {
    const mode = activeMode();
    const ids = activePeerIds();
    $("#peer-title").textContent = mode.label;
    $("#peer-provenance").textContent = `${mode.provenance}. Vintage: ${mode.vintage}.`;
    $("#peer-count").textContent = ids.length;

    const coverage = $("#coverage-strip");
    const exactHerd = ids.filter(id => data.records[id]?.herd.coverage === "present_exact_unitid").length;
    const conditionalHerd = ids.filter(id => data.records[id]?.herd.coverage === "conditional_boundary_match").length;
    coverage.innerHTML = `<span class="coverage-chip">IPEDS ${ids.length}/${ids.length || 0}</span><span class="coverage-chip">Scorecard ${ids.length}/${ids.length || 0}</span><span class="coverage-chip">HERD exact ${exactHerd}/${ids.length || 0}</span>${conditionalHerd ? `<span class="coverage-chip warning">HERD boundary review ${conditionalHerd}</span>` : ""}`;

    const custom = $("#custom-editor");
    custom.hidden = state.peerMode !== "CUSTOM";
    if (!custom.hidden) {
      const candidates = data.peerModes.DFR_SUBMITTED.unitids;
      custom.innerHTML = `<p>Select institutions. The same set remains active on every page.</p><div class="custom-checks">${candidates.map(id => `<label><input type="checkbox" value="${id}" ${state.customPeers.includes(id) ? "checked" : ""}><span>${esc(data.records[id].name)}</span></label>`).join("")}</div>`;
      $$("input", custom).forEach(input => input.addEventListener("change", () => {
        state.customPeers = $$("input:checked", custom).map(node => node.value);
        save();
        renderPeerMode();
      }));
    }

    const ranking = Object.fromEntries((data.peerModes.ANALYTICAL.ranking || []).map(row => [row.unitid, row]));
    const target = $("#peer-list");
    if (!ids.length) {
      target.innerHTML = `<div class="empty-state">No NCES default group exists for this DFR vintage because University of Delaware supplied a comparison group. Choose another peer mode to compare institutions.</div>`;
      return;
    }
    target.innerHTML = ids.map(id => {
      const record = data.records[id];
      const rank = ranking[id];
      const factors = state.peerMode === "ANALYTICAL" && rank ? `<small>Closest on ${esc(rank.factors.join(", ").toLowerCase())}</small>` : "";
      return `<div class="peer-item"><strong title="${esc(record.name)}">${esc(record.name)}</strong><span>${esc(record.location)} · UNITID ${id}</span>${factors}</div>`;
    }).join("");
  }

  function renderRelated() {
    const target = $("#related-list");
    if (!target) return;
    target.innerHTML = data.relatedOrganizations.map(row => `<div class="related-row"><strong>${esc(row.related_name)}</strong><span>${esc(row.relationship)} · ${esc(row.related_identifier.replace("https://ror.org/", "ROR "))}</span><span class="disposition">${esc(row.proposed_disposition.replaceAll("_", " "))}</span></div>`).join("");
  }

  function renderMethod() {
    const target = $("#method-content");
    if (!target) return;
    target.innerHTML = `<p><strong>Candidate pool:</strong> ${esc(data.method.candidatePool)}</p><p>${esc(data.method.distance)}</p><ul class="weight-list">${data.method.featureWeights.map(row => `<li><span>${esc(row.feature)}</span><strong>${row.weight} · ${esc(row.transform)}</strong></li>`).join("")}</ul><p>${esc(data.method.staffingProxy)}</p><p>${esc(data.method.classificationRule)}</p>`;
  }

  function downloadRows() {
    const rows = data.identifiers;
    const fields = ["institution_key","boundary_id","identifier_type","identifier_value","source","source_url","verified_date","status","note"];
    const csv = [fields.join(","), ...rows.map(row => fields.map(field => `"${String(row[field] ?? "").replaceAll('"','""')}"`).join(","))].join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv"}));
    link.download = "university-of-delaware-identity-registry.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function renderIdentity() {
    if (document.body.dataset.page !== "identity") return;
    renderIdentityTable();
    renderPeerMode();
    renderRelated();
  }

  const formatInt = value => value == null ? "—" : Math.round(value).toLocaleString("en-US");
  const formatMoney = value => value == null ? "—" : `$${(value / 1000).toLocaleString("en-US", {maximumFractionDigits: 1})}M`;
  const median = values => {
    const sorted = values.filter(value => Number.isFinite(value)).sort((a, b) => a - b);
    if (!sorted.length) return null;
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };

  function metricCard(label, value, note, tone = "") {
    return `<article class="metric-card ${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
  }

  function peerRecords() {
    return activePeerIds().map(id => data.records[id]).filter(Boolean);
  }

  function ipedsRecord(record) {
    return record.ipedsHistory?.[state.ipedsVintage] || record.ipeds;
  }

  function renderIpeds() {
    if (document.body.dataset.page !== "ipeds") return;
    const focal = data.records[data.institution.unitid];
    const peers = peerRecords();
    const focalIpeds = ipedsRecord(focal);
    const vintage = data.ipedsVintages.find(row => row.id === state.ipedsVintage) || data.ipedsVintages[0];
    const fields = [
      ["Total enrollment", "totalEnrollment"],
      ["Undergraduate", "undergraduate"],
      ["Graduate", "graduate"],
      ["Full-time", "fullTime"],
    ];
    const fullTimeShare = focalIpeds.totalEnrollment ? focalIpeds.fullTime / focalIpeds.totalEnrollment : null;
    $("#ipeds-period-label").textContent = vintage.label;
    $("#ipeds-vintage-label").textContent = vintage.id;
    $("#ipeds-chart-period").textContent = `Reporting period: ${vintage.label}`;
    $("#ipeds-chart-vintage").textContent = `Release: ${vintage.id}`;
    $("#ipeds-metrics").innerHTML = [
      metricCard("Total enrollment", formatInt(focalIpeds.totalEnrollment), `Students · ${vintage.label}`),
      metricCard("Undergraduate", formatInt(focalIpeds.undergraduate), `${((focalIpeds.undergraduate / focalIpeds.totalEnrollment) * 100).toFixed(1)}% of enrollment`),
      metricCard("Graduate", formatInt(focalIpeds.graduate), `${((focalIpeds.graduate / focalIpeds.totalEnrollment) * 100).toFixed(1)}% of enrollment`, "teal"),
      metricCard("Full-time share", fullTimeShare == null ? "—" : `${(fullTimeShare * 100).toFixed(1)}%`, "Fall enrollment", "teal"),
    ].join("");
    $("#response-flag").textContent = focalIpeds.responseStatus === "R" ? "R · Reported" : (focalIpeds.responseStatus || "—");

    const mode = activeMode();
    $("#ipeds-peer-note").textContent = peers.length ? `${mode.label} · ${peers.length} institutions · ${mode.vintage}` : mode.provenance;
    const chart = $("#ipeds-chart");
    if (!peers.length) {
      chart.innerHTML = `<div class="empty-state">No comparison values are available for this peer mode.</div>`;
    } else {
      const series = fields.map(([label, field]) => ({label, focal: focalIpeds[field], peer: median(peers.map(row => ipedsRecord(row)[field]))}));
      const max = Math.max(...series.flatMap(row => [row.focal || 0, row.peer || 0]));
      chart.innerHTML = `<div class="bar-legend"><span>University of Delaware</span><span>Peer median</span></div>${series.map(row => `<div class="chart-row"><div class="chart-label">${esc(row.label)}</div><div class="bar-pair"><div class="bar-line"><div class="bar-fill" style="width:${(row.focal / max) * 100}%"></div><span class="bar-value">${formatInt(row.focal)}</span></div><div class="bar-line"><div class="bar-fill peer" style="width:${(row.peer / max) * 100}%"></div><span class="bar-value">${formatInt(row.peer)}</span></div></div></div>`).join("")}`;
    }

    $("#ipeds-coverage-pill").textContent = `${peers.length}/${peers.length || 0} present`;
    const table = $("#ipeds-table");
    if (!peers.length) {
      table.innerHTML = `<div class="empty-state">Select Submitted DFR, Analytical, or Custom peers to view records.</div>`;
    } else {
      table.innerHTML = `<table><thead><tr><th>Institution</th><th>Total</th><th>Undergraduate</th><th>Graduate</th><th>Difference from Delaware</th><th>Status</th></tr></thead><tbody>${peers.map(row => {
        const rowIpeds = ipedsRecord(row);
        const diff = rowIpeds.totalEnrollment - focalIpeds.totalEnrollment;
        return `<tr><td><strong>${esc(row.name)}</strong><br><span class="table-sub">UNITID ${row.unitid}</span></td><td>${formatInt(rowIpeds.totalEnrollment)}</td><td>${formatInt(rowIpeds.undergraduate)}</td><td>${formatInt(rowIpeds.graduate)}</td><td class="${diff >= 0 ? "difference-positive" : "difference-negative"}">${diff >= 0 ? "+" : ""}${formatInt(diff)}</td><td><span class="boundary-status">Exact</span></td></tr>`;
      }).join("")}</tbody></table>`;
    }
  }

  function renderHerd() {
    if (document.body.dataset.page !== "herd") return;
    const focal = data.records[data.institution.unitid];
    const peers = peerRecords();
    const exactPeers = peers.filter(row => row.herd.coverage === "present_exact_unitid" && Number.isFinite(row.herd.total));
    const conditionalPeers = peers.filter(row => row.herd.coverage === "conditional_boundary_match");
    const federal = focal.herd.sources["Federal government"];
    const institutional = focal.herd.sources["Institution funds"];
    const personnel = focal.herd.personnel.Total;
    const fte = focal.herd.fte.Total;
    $("#herd-metrics").innerHTML = [
      metricCard("Total R&D expenditures", formatMoney(focal.herd.total), "Institutional FY2024"),
      metricCard("Federal government", formatMoney(federal), `${((federal / focal.herd.total) * 100).toFixed(1)}% of total`),
      metricCard("Institution funds", formatMoney(institutional), `${((institutional / focal.herd.total) * 100).toFixed(1)}% of total`, "teal"),
      metricCard("R&D personnel", formatInt(personnel), `${formatInt(fte)} reported FTEs`, "teal"),
    ].join("");

    const sourceOrder = ["Federal government", "Institution funds", "State and local government", "All other sources", "Nonprofit organizations", "Business"];
    const labels = {"Federal government":"Federal government","Institution funds":"Institution funds","State and local government":"State & local","All other sources":"All other","Nonprofit organizations":"Nonprofit","Business":"Business"};
    const max = Math.max(...sourceOrder.map(label => focal.herd.sources[label] || 0));
    $("#herd-source-chart").innerHTML = sourceOrder.map(label => {
      const value = focal.herd.sources[label];
      return `<div class="source-bar-row"><span>${esc(labels[label])}</span><div class="source-track"><i style="width:${((value || 0) / max) * 100}%"></i></div><strong>${formatMoney(value)}</strong></div>`;
    }).join("");

    const peerMedian = median(exactPeers.map(row => row.herd.total));
    const mode = activeMode();
    $("#herd-peer-note").textContent = peers.length ? `${mode.label} · ${exactPeers.length} boundary-verified of ${peers.length}` : mode.provenance;
    const comparison = $("#herd-comparison");
    if (!exactPeers.length) {
      comparison.innerHTML = `<div class="empty-state">No boundary-verified comparison values are available for this peer mode.</div>`;
    } else {
      const delta = focal.herd.total - peerMedian;
      comparison.innerHTML = `<div class="focus-values"><div class="focus-value primary"><span>University of Delaware</span><strong>${formatMoney(focal.herd.total)}</strong></div><div class="focus-vs">versus</div><div class="focus-value"><span>Peer median · N=${exactPeers.length}</span><strong>${formatMoney(peerMedian)}</strong></div></div><div class="focus-delta">Delaware is ${formatMoney(Math.abs(delta))} ${delta >= 0 ? "above" : "below"} the boundary-verified peer median.</div>`;
    }

    $("#herd-coverage-pill").textContent = `${exactPeers.length} exact · ${conditionalPeers.length} review`;
    const table = $("#herd-table");
    if (!peers.length) {
      table.innerHTML = `<div class="empty-state">Select Submitted DFR, Analytical, or Custom peers to view HERD coverage.</div>`;
    } else {
      table.innerHTML = `<table><thead><tr><th>IPEDS comparison institution</th><th>HERD reporting entity</th><th>NCSES ID</th><th>Total R&D</th><th>Boundary status</th></tr></thead><tbody>${peers.map(row => {
        const exact = row.herd.coverage === "present_exact_unitid";
        return `<tr><td><strong>${esc(row.name)}</strong><br><span class="table-sub">UNITID ${row.unitid}</span></td><td>${esc(row.herd.reportedName || "Not resolved")}</td><td class="id-value">${esc(row.herd.ncsesId || "—")}</td><td>${exact ? formatMoney(row.herd.total) : "Not compared"}</td><td><span class="boundary-status ${exact ? "" : "conditional"}">${exact ? "Exact UNITID" : "Review boundary"}</span></td></tr>`;
      }).join("")}</tbody></table>`;
    }
  }

  function downloadPageData(page) {
    const mode = activeMode();
    const fields = ["institution","unitid","boundary_id","peer_provenance","data_year","release_vintage","variable","value","unit","reporting_period","suppression_status","boundary_status"];
    const rows = [];
    const add = row => rows.push(row);
    if (page === "ipeds") {
      [data.records[data.institution.unitid], ...peerRecords()].forEach(row => {
        const current = ipedsRecord(row);
        [["total_enrollment",current.totalEnrollment],["undergraduate_enrollment",current.undergraduate],["graduate_enrollment",current.graduate],["full_time_enrollment",current.fullTime]].forEach(([variable,value]) => add({institution:row.name,unitid:row.unitid,boundary_id:state.boundary,peer_provenance:mode.label,data_year:current.dataYear.replace("Fall ", ""),release_vintage:current.releaseVintage,variable,value:value ?? "",unit:"students",reporting_period:current.dataYear,suppression_status:value == null ? "missing" : "reported",boundary_status:"exact"}));
      });
    } else {
      [data.records[data.institution.unitid], ...peerRecords()].forEach(row => {
        const exact = row.unitid === data.institution.unitid || row.herd.coverage === "present_exact_unitid";
        add({institution:row.name,unitid:row.unitid,boundary_id:state.boundary,peer_provenance:mode.label,data_year:"2024",release_vintage:"NCSES_HERD_FY2024",variable:"total_r_and_d_expenditures",value:exact ? (row.herd.total ?? "") : "",unit:"thousands of dollars",reporting_period:"Institutional fiscal year 2024",suppression_status:row.herd.total == null ? "missing" : "reported",boundary_status:exact ? "exact" : "conditional_not_compared"});
      });
    }
    const csv = [fields.join(","), ...rows.map(row => fields.map(field => `"${String(row[field] ?? "").replaceAll('"','""')}"`).join(","))].join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv"}));
    link.download = `university-of-delaware-${page}-${state.peerMode.toLowerCase()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function renderPage() {
    renderIdentity();
    renderIpeds();
    renderHerd();
  }

  syncControls();
  updateBoundary();
  renderPage();
  renderMethod();
  $$('[data-open-method]').forEach(button => button.addEventListener("click", () => $("#method-dialog")?.showModal()));
  $$('[data-download="identity"]').forEach(button => button.addEventListener("click", downloadRows));
  $$('[data-download="ipeds"]').forEach(button => button.addEventListener("click", () => downloadPageData("ipeds")));
  $$('[data-download="herd"]').forEach(button => button.addEventListener("click", () => downloadPageData("herd")));
})();
