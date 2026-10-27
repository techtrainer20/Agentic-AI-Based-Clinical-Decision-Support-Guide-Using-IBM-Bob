/**
 * app.js – ClinGuide AI single-page frontend.
 * Hash-based routing: #overview, #cases, #case/CASE-001, #audit
 * All text inserted into the DOM is escaped to prevent XSS.
 */

"use strict";

/* ── Utility helpers ──────────────────────────────────────────────────────── */

/** Escape a value to safe HTML text. */
function esc(val) {
  if (val === null || val === undefined) return "";
  return String(val)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Fetch JSON from the API; throws on non-2xx. */
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

/** Return a coloured badge element string for an evidence status. */
function statusBadge(status) {
  const map = {
    Supported:   "badge-supported",
    Partial:     "badge-partial",
    Unsupported: "badge-unsupported",
  };
  const cls = map[status] || "badge-pending";
  return `<span class="badge ${esc(cls)}">${esc(status)}</span>`;
}

/* ── Router ───────────────────────────────────────────────────────────────── */

function route() {
  const hash = location.hash || "#overview";
  const parts = hash.replace("#", "").split("/");
  const page = parts[0];
  const param = parts[1] || null;

  // Hide all pages, activate the right one.
  document.querySelectorAll(".page").forEach(p => {
    p.classList.remove("active");
    p.style.display = "none";
  });

  // Update nav active state.
  document.querySelectorAll(".nav-link").forEach(a => a.classList.remove("active"));
  const activeLink = document.querySelector(`.nav-link[data-page="${esc(page)}"]`);
  if (activeLink) activeLink.classList.add("active");

  if (page === "overview")  renderOverview();
  else if (page === "cases") renderCases();
  else if (page === "case" && param) renderCaseReview(param);
  else if (page === "audit") renderAudit();
  else renderOverview();
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

/* ── Show a page div ──────────────────────────────────────────────────────── */

function showPage(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = "block";
  el.classList.add("active");
  return el;
}

/* ── Overview page ────────────────────────────────────────────────────────── */

async function renderOverview() {
  const el = showPage("page-overview");
  el.innerHTML = `<div class="loading">Loading stats…</div>`;

  try {
    const stats = await api("/api/stats");
    el.innerHTML = `
      <h1 class="page-title">📊 Overview</h1>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">${esc(stats.cases)}</div>
          <div class="stat-label">Fictional Cases</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${esc(stats.reports_generated)}</div>
          <div class="stat-label">Reports Generated</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${esc(stats.reviews_submitted)}</div>
          <div class="stat-label">Reviews Submitted</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${esc(stats.approved)}</div>
          <div class="stat-label">Approved</div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">About ClinGuide AI</div>
        <p style="font-size:.9rem;line-height:1.7;color:var(--gray-600)">
          ClinGuide AI is an <strong>educational</strong> tool that reviews AI-generated
          differential diagnosis guides for <strong>completely fictional</strong> clinical cases.
          Nine agents analyse each guide for overconfident language, missing information,
          and safety warnings. A clinician must review and sign off every report.
          No real patient data is ever used.
        </p>
        <p style="margin-top:.75rem;font-size:.85rem;color:var(--gray-400)">
          Navigate to <a href="#cases">Cases</a> to run an analysis pipeline.
        </p>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load stats: ${esc(e.message)}</p>`;
  }
}

/* ── Cases list page ──────────────────────────────────────────────────────── */

async function renderCases() {
  const el = showPage("page-cases");
  el.innerHTML = `<div class="loading">Loading cases…</div>`;

  try {
    const cases = await api("/api/cases");

    // Build case list rows
    let rows = "";
    cases.forEach(c => {
      rows += `
        <div class="case-item">
          <div style="cursor:pointer;flex:1" onclick="location.hash='#case/${esc(c.id)}'">
            <div class="case-id">${esc(c.id)}</div>
            <div class="case-title">${esc(c.title)}</div>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <span class="badge badge-info" style="cursor:pointer"
                  onclick="location.hash='#case/${esc(c.id)}'">View →</span>
            <button class="btn btn-sm"
                    style="background:var(--red-100);color:var(--red-600);border:1px solid #fca5a5"
                    onclick="deleteCase('${esc(c.id)}')">🗑</button>
          </div>
        </div>`;
    });

    el.innerHTML = `
      <h1 class="page-title">📋 Fictional Cases</h1>

      <!-- Upload card -->
      <div class="card" style="margin-bottom:1.25rem">
        <div class="card-title">📤 Upload a New Case</div>
        <p style="font-size:.85rem;color:var(--gray-600);margin-bottom:.75rem">
          Upload a <code>.json</code> file following the case template.
          <strong>Fictional / educational data only.</strong>
          Download sample files:
          <a href="/static/samples/case_s01_abdominal_pain.json" download>case_s01_abdominal_pain.json</a> &nbsp;|&nbsp;
          <a href="/static/samples/case_s02_dyspnoea_pregnancy.json" download>case_s02_dyspnoea_pregnancy.json</a>
        </p>
        <div class="upload-area" id="upload-drop"
             ondragover="event.preventDefault();this.classList.add('drag-over')"
             ondragleave="this.classList.remove('drag-over')"
             ondrop="handleDrop(event)">
          <div class="upload-icon">📂</div>
          <div style="font-size:.88rem;color:var(--gray-600)">Drag &amp; drop a <code>.json</code> file here, or</div>
          <label class="btn btn-primary btn-sm" style="margin-top:.5rem;cursor:pointer">
            Browse file
            <input type="file" accept=".json" id="upload-input"
                   style="display:none" onchange="handleFileInput(this)">
          </label>
        </div>
        <div id="upload-status" style="margin-top:.65rem;font-size:.85rem"></div>
      </div>

      <!-- Case list -->
      <div class="case-list" id="case-list">${rows}</div>
    `;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load cases: ${esc(e.message)}</p>`;
  }
}

/* ── Upload helpers ───────────────────────────────────────────────────────── */

function handleDrop(event) {
  event.preventDefault();
  document.getElementById("upload-drop").classList.remove("drag-over");
  const file = event.dataTransfer.files[0];
  if (file) uploadFile(file);
}

function handleFileInput(input) {
  if (input.files[0]) uploadFile(input.files[0]);
}

async function uploadFile(file) {
  const status = document.getElementById("upload-status");
  status.textContent = `Uploading ${file.name}…`;
  status.className = "";

  const form = new FormData();
  form.append("file", file);

  try {
    const result = await fetch("/api/cases/upload", { method: "POST", body: form });
    const body = await result.json();
    if (!result.ok) throw new Error(body.detail || result.statusText);
    status.textContent = `✓ Uploaded: ${body.title} (${body.id})`;
    status.className = "msg-ok";
    // Reload the cases page to show the new row.
    setTimeout(() => renderCases(), 800);
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
    status.className = "msg-error";
  }
}

/* ── Delete case ──────────────────────────────────────────────────────────── */

async function deleteCase(caseId) {
  if (!confirm(`Delete case ${caseId} and all its reports? This cannot be undone.`)) return;

  try {
    await api(`/api/cases/${encodeURIComponent(caseId)}`, { method: "DELETE" });
    renderCases(); // Refresh the list.
  } catch (e) {
    alert(`Could not delete: ${e.message}`);
  }
}

/* ── Case review page ─────────────────────────────────────────────────────── */

async function renderCaseReview(caseId) {
  const el = showPage("page-case-review");
  el.innerHTML = `<div class="loading">Loading case…</div>`;

  try {
    const caseData = await api(`/api/cases/${encodeURIComponent(caseId)}`);
    el.innerHTML = buildCaseHeader(caseData) + `
      <div class="card">
        <div class="card-title">AI-Generated Guide (Original)</div>
        ${buildOriginalGuide(caseData.ai_guide)}
      </div>

      <!-- Run button lives OUTSIDE report-area so renderReport never wipes it -->
      <div style="margin:1rem 0 1.25rem" id="run-bar">
        <button class="btn btn-primary" id="run-btn" onclick="runPipeline('${esc(caseId)}')">
          ▶ Run Analysis Pipeline
        </button>
        <span id="run-status" style="margin-left:1rem;font-size:.85rem"></span>
      </div>

      <!-- Report output is injected here -->
      <div id="report-area"></div>
    `;

    // If a report already exists, show it immediately.
    try {
      const report = await api(`/api/cases/${encodeURIComponent(caseId)}/report`);
      document.getElementById("run-status").textContent = "Showing latest report.";
      document.getElementById("run-status").className = "msg-ok";
      renderReport(caseId, report);
    } catch (_) {
      /* No report yet – that's fine, the run button is ready. */
    }
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load case: ${esc(e.message)}</p>`;
  }
}

function buildCaseHeader(c) {
  const vitals = c.vitals || {};
  const vitalParts = Object.entries(vitals)
    .filter(([, v]) => v)
    .map(([k, v]) => `<span><strong>${esc(k.toUpperCase())}:</strong> ${esc(v)}</span>`)
    .join(" &nbsp;|&nbsp; ");

  return `
    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1.25rem">
      <a href="#cases" style="font-size:.85rem;color:var(--blue-500);text-decoration:none">← Cases</a>
      <h1 class="page-title" style="margin-bottom:0">${esc(c.title)}</h1>
    </div>
    <div class="card" style="margin-bottom:1rem">
      <div class="card-title">Case Summary</div>
      <div style="font-size:.88rem;line-height:1.8;color:var(--gray-600)">
        <strong>Age/Sex:</strong> ${esc(c.age)} · ${esc(c.sex)}<br>
        <strong>Symptoms:</strong> ${esc((c.symptoms || []).join(", "))}<br>
        <strong>History:</strong> ${esc(c.history || "Not documented")}<br>
        <strong>Tests:</strong> ${esc((c.tests || []).join("; ") || "None documented")}<br>
        <strong>Medications:</strong> ${esc((c.medications || []).join(", ") || "None documented")}<br>
        ${vitalParts ? `<strong>Vitals:</strong> ${vitalParts}` : ""}
      </div>
    </div>
  `;
}

function buildOriginalGuide(guide) {
  if (!guide || !guide.length) return `<p class="empty">No guide data.</p>`;
  return guide.map(item => `
    <div style="margin-bottom:.75rem;padding:.75rem;border:1px solid var(--gray-200);border-radius:6px">
      <strong>${esc(item.dx)}</strong>
      <p style="font-size:.86rem;margin-top:.3rem;color:var(--gray-600)">${esc(item.text)}</p>
    </div>
  `).join("");
}

/* ── Run pipeline ─────────────────────────────────────────────────────────── */

async function runPipeline(caseId) {
  const btn    = document.getElementById("run-btn");
  const status = document.getElementById("run-status");
  btn.disabled = true;
  btn.textContent = "⏳ Running…";
  status.textContent = "";
  status.className = "";

  try {
    const report = await api(`/api/cases/${encodeURIComponent(caseId)}/analyze`, { method: "POST" });
    // Render the report first so the DOM is updated, then set the status.
    renderReport(caseId, report);
    // btn / status are still in the DOM (they live outside #report-area).
    btn.textContent = "▶ Re-run Pipeline";
    btn.disabled = false;
    status.textContent = "✓ Pipeline complete.";
    status.className = "msg-ok";
  } catch (e) {
    btn.textContent = "▶ Run Analysis Pipeline";
    btn.disabled = false;
    status.textContent = "Error: " + e.message;
    status.className = "msg-error";
  }
}

/* ── Render a full report ─────────────────────────────────────────────────── */

function renderReport(caseId, report) {
  const area = document.getElementById("report-area");
  if (!area) return;

  const agents = report.agents || {};
  const audit  = report.audit || {};
  const esc_   = report.escalation || {};
  const guide  = report.guidance || {};
  const hr     = report.human_review || {};

  area.innerHTML = `
    <!-- Pipeline steps -->
    <div class="card">
      <div class="card-title">Agent Pipeline</div>
      ${buildPipelineSteps(agents)}
    </div>

    <!-- Granite summary -->
    <div class="card">
      <div class="card-title">AI Summary (IBM Granite)</div>
      <div class="granite-label">Source: ${esc(report.granite_source || "template")}</div>
      <div class="granite-box">${esc(report.granite_summary || "")}</div>
    </div>

    <!-- Escalation alerts -->
    ${buildEscalation(esc_)}

    <!-- Evidence table -->
    <div class="card">
      <div class="card-title">Evidence Validation Table</div>
      ${buildEvidenceTable(audit.evidence_table || [])}
    </div>

    <!-- Gaps -->
    <div class="card">
      <div class="card-title">Gap Detection</div>
      ${buildGaps(agents.GapDetection || {})}
    </div>

    <!-- Revised guide -->
    <div class="card">
      <div class="card-title">Revised Guidance</div>
      ${buildRevisedGuide(guide)}
    </div>

    <!-- Audit checklist -->
    <div class="card">
      <div class="card-title">Audit Checklist</div>
      ${buildChecklist(audit.clinician_checklist || [])}
    </div>

    <!-- Clinician review form -->
    <div class="card" id="review-card">
      <div class="card-title">Clinician Review</div>
      ${hr.status === "pending" ? buildReviewForm(caseId) : `<p class="msg-ok">Review submitted.</p>`}
    </div>
  `;
}

function buildPipelineSteps(agents) {
  const names = [
    "CaseAnalysis","DifferentialReview","EvidenceRetrieval",
    "EvidenceValidation","GapDetection","GuidanceRefinement",
    "EscalationReview","HumanReview","AuditReport"
  ];
  return `<div class="pipeline-steps">` +
    names.map(n => {
      const done = agents[n] !== undefined;
      return `<span class="step-pill ${done ? "done" : ""}">${done ? "✓" : "○"} ${esc(n)}</span>`;
    }).join("") +
    `</div>`;
}

function buildEscalation(esc_) {
  if (!esc_.alerts || !esc_.alerts.length) {
    return `<div class="card"><div class="card-title">⚠️ Escalation Alerts</div><p class="empty">No warning-sign alerts triggered.</p></div>`;
  }
  const alertsHtml = esc_.alerts.map(a => `
    <div class="alert-box">
      <div class="alert-ref">${esc(a.ref_id)}</div>
      ${esc(a.alert)}
    </div>
  `).join("");
  return `<div class="card"><div class="card-title">⚠️ Escalation Alerts (${esc(esc_.alert_count)})</div>${alertsHtml}</div>`;
}

function buildEvidenceTable(rows) {
  if (!rows.length) return `<p class="empty">No evidence data.</p>`;
  const thead = `<tr>
    <th>Possibility</th><th>Status</th><th>Flags</th><th>Sources</th>
  </tr>`;
  const tbody = rows.map(r => `
    <tr>
      <td>${esc(r.possibility)}</td>
      <td>${statusBadge(r.status)}</td>
      <td style="font-size:.8rem;color:var(--gray-600)">${esc((r.flags || []).join("; "))}</td>
      <td style="font-size:.78rem;font-family:monospace">${esc((r.source_ids || []).join(", "))}</td>
    </tr>
  `).join("");
  return `<table class="evidence-table"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
}

function buildGaps(gapData) {
  const gaps = gapData.gaps || [];
  if (!gaps.length) return `<p class="empty">No gaps detected.</p>`;
  return `<ul class="gap-list">` +
    gaps.map(g => `
      <li class="gap-item gap-${esc(g.type)}">
        <strong>${esc(g.type.replace(/_/g, " "))}:</strong>
        ${g.possibility ? `[${esc(g.possibility)}] ` : ""}${esc(g.detail)}
      </li>
    `).join("") +
    `</ul>`;
}

function buildRevisedGuide(guide) {
  const poss = guide.possibilities || [];
  if (!poss.length) return `<p class="empty">No revised guide.</p>`;
  return poss.map(p => `
    <div style="margin-bottom:.85rem;padding:.85rem;border:1px solid var(--gray-200);border-radius:6px">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem">
        <strong>${esc(p.possibility)}</strong>
        ${statusBadge(p.status)}
      </div>
      <p style="font-size:.86rem;color:var(--gray-600);line-height:1.6">${esc(p.revised_claim)}</p>
      <p style="font-size:.76rem;color:var(--gray-400);margin-top:.3rem;font-family:monospace">
        Sources: ${esc((p.source_ids || []).join(", "))}
      </p>
    </div>
  `).join("");
}

function buildChecklist(items) {
  if (!items.length) return `<p class="empty">No checklist.</p>`;
  return `<ul class="checklist">` +
    items.map(i => `<li>${esc(i)}</li>`).join("") +
    `</ul>`;
}

function buildReviewForm(caseId) {
  return `
    <div class="review-form" id="review-form">
      <label>Decision
        <select id="review-decision">
          <option value="approve">Approve</option>
          <option value="request_changes">Request Changes</option>
        </select>
      </label>
      <label>Comment (optional)
        <textarea id="review-comment" placeholder="Add a comment for the audit log…"></textarea>
      </label>
      <div>
        <button class="btn btn-teal" onclick="submitReview('${esc(caseId)}')">Submit Review</button>
        <span id="review-status" style="margin-left:1rem;font-size:.85rem"></span>
      </div>
    </div>
  `;
}

/* ── Submit review ────────────────────────────────────────────────────────── */

async function submitReview(caseId) {
  const decision = document.getElementById("review-decision").value;
  const comment  = document.getElementById("review-comment").value;
  const status   = document.getElementById("review-status");

  status.textContent = "Saving…";
  status.className = "";

  try {
    await api(`/api/cases/${encodeURIComponent(caseId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, comment }),
    });
    status.textContent = "Review saved.";
    status.className = "msg-ok";
    document.getElementById("review-form").innerHTML =
      `<p class="msg-ok">✓ Review submitted: ${esc(decision)}</p>`;
  } catch (e) {
    status.textContent = "Error: " + e.message;
    status.className = "msg-error";
  }
}

/* ── Audit log page ───────────────────────────────────────────────────────── */

async function renderAudit() {
  const el = showPage("page-audit");
  el.innerHTML = `<div class="loading">Loading audit log…</div>`;

  try {
    const rows = await api("/api/audit");
    if (!rows.length) {
      el.innerHTML = `<h1 class="page-title">📝 Audit Log</h1><p class="empty">No entries yet.</p>`;
      return;
    }
    const thead = `<tr>
      <th>#</th><th>Case</th><th>Step</th><th>Status</th><th>Detail</th><th>Time</th>
    </tr>`;
    const tbody = rows.map(r => `
      <tr>
        <td class="mono">${esc(r.id)}</td>
        <td class="mono">${esc(r.case_id)}</td>
        <td>${esc(r.step)}</td>
        <td><span class="badge badge-${esc(r.status)}">${esc(r.status)}</span></td>
        <td style="max-width:300px;word-break:break-word">${esc(r.detail)}</td>
        <td class="mono">${esc(r.created_at)}</td>
      </tr>
    `).join("");
    el.innerHTML = `
      <h1 class="page-title">📝 Audit Log</h1>
      <div class="card" style="overflow-x:auto">
        <table class="audit-table">
          <thead>${thead}</thead>
          <tbody>${tbody}</tbody>
        </table>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load audit log: ${esc(e.message)}</p>`;
  }
}
