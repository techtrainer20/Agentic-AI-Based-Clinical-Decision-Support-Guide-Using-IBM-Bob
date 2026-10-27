/**
 * app.js – ClinGuide AI frontend.
 * Hash routing: #overview · #cases · #case/ID · #audit
 * All user content escaped before DOM insertion.
 */
"use strict";

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function esc(val) {
  if (val === null || val === undefined) return "";
  return String(val)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function statusBadge(status) {
  const map = { Supported:"badge-supported", Partial:"badge-partial", Unsupported:"badge-unsupported" };
  const cls = map[status] || "badge-pending";
  return `<span class="badge ${esc(cls)}">${esc(status)}</span>`;
}

// Update the topbar title and clock
function setTopbarTitle(t) {
  const el = document.getElementById("topbar-title");
  if (el) el.textContent = t;
}
function tickClock() {
  const el = document.getElementById("topbar-time");
  if (el) el.textContent = new Date().toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" });
}
setInterval(tickClock, 1000);
tickClock();

/* ── Router ───────────────────────────────────────────────────────────────── */

function route() {
  const hash  = location.hash || "#overview";
  const parts = hash.replace("#", "").split("/");
  const page  = parts[0];
  const param = parts[1] || null;

  document.querySelectorAll(".page").forEach(p => { p.style.display = "none"; p.classList.remove("active"); });
  document.querySelectorAll(".nav-link").forEach(a => a.classList.remove("active"));
  const lnk = document.querySelector(`.nav-link[data-page="${esc(page)}"]`);
  if (lnk) lnk.classList.add("active");

  if (page === "overview")            renderOverview();
  else if (page === "cases")          renderCases();
  else if (page === "case" && param)  renderCaseReview(param);
  else if (page === "audit")          renderAudit();
  else                                renderOverview();
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

function showPage(id) {
  const el = document.getElementById(id);
  if (!el) return el;
  el.style.display = "block";
  el.classList.add("active");
  return el;
}

/* ── Overview ─────────────────────────────────────────────────────────────── */

async function renderOverview() {
  setTopbarTitle("Dashboard");
  const el = showPage("page-overview");
  el.innerHTML = `<div class="loading">Loading stats…</div>`;

  try {
    const s = await api("/api/stats");
    el.innerHTML = `
      <h1 class="page-title">Dashboard</h1>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-card-header">
            <div class="stat-label">Fictional Cases</div>
            <div class="stat-card-icon blue">🗂️</div>
          </div>
          <div class="stat-value">${esc(s.cases)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-header">
            <div class="stat-label">Reports Generated</div>
            <div class="stat-card-icon teal">📄</div>
          </div>
          <div class="stat-value">${esc(s.reports_generated)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-header">
            <div class="stat-label">Reviews Submitted</div>
            <div class="stat-card-icon amber">✍️</div>
          </div>
          <div class="stat-value">${esc(s.reviews_submitted)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card-header">
            <div class="stat-label">Approved</div>
            <div class="stat-card-icon green">✅</div>
          </div>
          <div class="stat-value">${esc(s.approved)}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-title"><span class="card-title-dot"></span>About ClinGuide AI</div>
        <p style="font-size:.88rem;line-height:1.75;color:var(--gray-600);margin-bottom:1rem">
          ClinGuide AI reviews AI-generated differential diagnosis guides for
          <strong>completely fictional</strong> educational cases. Nine agents analyse
          each guide for overconfident language, missing information, and safety warnings.
          A clinician must approve every report. No real patient data is ever used.
        </p>
        <div class="about-grid">
          <div class="about-tile">
            <div class="about-tile-icon">🤖</div>
            <div class="about-tile-title">9-Agent Pipeline</div>
            <div class="about-tile-text">Each agent checks one aspect — from case facts to escalation warnings.</div>
          </div>
          <div class="about-tile">
            <div class="about-tile-icon">🔬</div>
            <div class="about-tile-title">Evidence-Backed</div>
            <div class="about-tile-text">Every claim is linked to a pre-approved reference ID (REF-001…REF-012).</div>
          </div>
          <div class="about-tile">
            <div class="about-tile-icon">👩‍⚕️</div>
            <div class="about-tile-title">Clinician Sign-Off</div>
            <div class="about-tile-text">No guide is final until a clinician reviews and approves it.</div>
          </div>
          <div class="about-tile">
            <div class="about-tile-icon">📋</div>
            <div class="about-tile-title">Full Audit Trail</div>
            <div class="about-tile-text">Every agent step and review decision is timestamped and logged.</div>
          </div>
        </div>
        <p style="margin-top:1rem;font-size:.83rem;color:var(--gray-400)">
          Go to <a href="#cases">Cases</a> to run an analysis pipeline.
        </p>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load stats: ${esc(e.message)}</p>`;
  }
}

/* ── Cases list ───────────────────────────────────────────────────────────── */

const CASE_ICONS = ["🫀","🌡️","🧠","🩺","💊","🔬"];

async function renderCases() {
  setTopbarTitle("Cases");
  const el = showPage("page-cases");
  el.innerHTML = `<div class="loading">Loading cases…</div>`;

  try {
    const cases = await api("/api/cases");
    let rows = "";
    cases.forEach((c, i) => {
      const icon = CASE_ICONS[i % CASE_ICONS.length];
      rows += `
        <div class="case-item">
          <div class="case-item-avatar">${icon}</div>
          <div class="case-item-body" onclick="location.hash='#case/${esc(c.id)}'">
            <div class="case-id-tag">${esc(c.id)}</div>
            <div class="case-title-text">${esc(c.title)}</div>
          </div>
          <div class="case-item-actions">
            <button class="btn btn-ghost btn-sm" onclick="location.hash='#case/${esc(c.id)}'">
              Open →
            </button>
            <button class="btn btn-danger btn-sm" onclick="deleteCase('${esc(c.id)}')">🗑</button>
          </div>
        </div>`;
    });

    el.innerHTML = `
      <h1 class="page-title">Fictional Cases</h1>

      <div class="card" style="margin-bottom:1.25rem">
        <div class="card-title"><span class="card-title-dot"></span>Upload a New Case</div>
        <p style="font-size:.84rem;color:var(--gray-500);margin-bottom:.75rem">
          Upload a <code>.json</code> file following the case template.
          <strong>Fictional / educational data only.</strong>
        </p>
        <div class="sample-links">
          <span style="font-size:.78rem;color:var(--gray-500);align-self:center">Sample files:</span>
          <a class="sample-link" href="/static/samples/case_s01_abdominal_pain.json" download>
            ⬇ case_s01_abdominal_pain.json
          </a>
          <a class="sample-link" href="/static/samples/case_s02_dyspnoea_pregnancy.json" download>
            ⬇ case_s02_dyspnoea_pregnancy.json
          </a>
        </div>
        <div class="upload-zone" id="upload-drop" style="margin-top:.85rem"
             ondragover="event.preventDefault();this.classList.add('drag-over')"
             ondragleave="this.classList.remove('drag-over')"
             ondrop="handleDrop(event)">
          <div class="upload-zone-icon">📂</div>
          <div class="upload-zone-text">Drag &amp; drop a <code>.json</code> file here, or</div>
          <label class="btn btn-primary btn-sm" style="cursor:pointer">
            Browse file
            <input type="file" accept=".json" id="upload-input" style="display:none"
                   onchange="handleFileInput(this)">
          </label>
        </div>
        <div id="upload-status" style="margin-top:.65rem"></div>
      </div>

      <div class="section-divider">All Cases</div>
      <div class="case-list" id="case-list">
        ${rows || `<p class="empty">No cases found. Upload one above.</p>`}
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load cases: ${esc(e.message)}</p>`;
  }
}

/* ── Upload helpers ───────────────────────────────────────────────────────── */

function handleDrop(e) {
  e.preventDefault();
  document.getElementById("upload-drop").classList.remove("drag-over");
  const f = e.dataTransfer.files[0];
  if (f) uploadFile(f);
}
function handleFileInput(input) { if (input.files[0]) uploadFile(input.files[0]); }

async function uploadFile(file) {
  const status = document.getElementById("upload-status");
  status.innerHTML = `<span style="color:var(--gray-500);font-size:.83rem">Uploading ${esc(file.name)}…</span>`;

  const form = new FormData();
  form.append("file", file);
  try {
    const res  = await fetch("/api/cases/upload", { method:"POST", body:form });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);
    status.innerHTML = `<span class="msg-ok">✓ Uploaded: ${esc(body.title)} (${esc(body.id)})</span>`;
    setTimeout(() => renderCases(), 800);
  } catch (e) {
    status.innerHTML = `<span class="msg-error">Error: ${esc(e.message)}</span>`;
  }
}

async function deleteCase(caseId) {
  if (!confirm(`Delete ${caseId} and all its reports? This cannot be undone.`)) return;
  try {
    await api(`/api/cases/${encodeURIComponent(caseId)}`, { method:"DELETE" });
    renderCases();
  } catch (e) {
    alert(`Could not delete: ${e.message}`);
  }
}

/* ── Case Review ──────────────────────────────────────────────────────────── */

async function renderCaseReview(caseId) {
  setTopbarTitle("Case Review");
  const el = showPage("page-case-review");
  el.innerHTML = `<div class="loading">Loading case…</div>`;

  try {
    const c = await api(`/api/cases/${encodeURIComponent(caseId)}`);
    el.innerHTML = buildCaseHero(c) + buildCaseInfoGrid(c) + `
      <div class="card">
        <div class="card-title"><span class="card-title-dot"></span>AI-Generated Guide (Original — unreviewed)</div>
        ${buildOriginalGuide(c.ai_guide)}
      </div>

      <div class="run-bar" id="run-bar">
        <button class="btn btn-primary" id="run-btn" onclick="runPipeline('${esc(caseId)}')">
          ▶ Run Analysis Pipeline
        </button>
        <span class="run-bar-status" id="run-status"></span>
      </div>

      <div id="report-area"></div>
    `;

    try {
      const report = await api(`/api/cases/${encodeURIComponent(caseId)}/report`);
      document.getElementById("run-status").innerHTML =
        `<span class="msg-ok">Showing latest report</span>`;
      renderReport(caseId, report);
    } catch (_) { /* no report yet */ }
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load case: ${esc(e.message)}</p>`;
  }
}

function buildCaseHero(c) {
  const vitals = c.vitals || {};
  const chips  = Object.entries(vitals)
    .filter(([, v]) => v)
    .map(([k, v]) => `<span class="vital-chip"><strong>${esc(k.toUpperCase())}</strong> ${esc(v)}</span>`)
    .join("");
  return `
    <div class="case-hero">
      <a class="case-hero-back" href="#cases">← All Cases</a>
      <div class="case-hero-title">${esc(c.title)}</div>
      ${chips ? `<div class="case-vitals-row">${chips}</div>` : ""}
    </div>
  `;
}

function buildCaseInfoGrid(c) {
  const cells = [
    { label:"Age / Sex",    value:`${esc(c.age)} · ${esc(c.sex)}` },
    { label:"Symptoms",     value:esc((c.symptoms||[]).join(", ")) || "None documented" },
    { label:"History",      value:esc(c.history||"Not documented") },
    { label:"Tests",        value:esc((c.tests||[]).join("; ")||"None documented") },
    { label:"Medications",  value:esc((c.medications||[]).join(", ")||"None documented") },
  ];
  return `<div class="case-info-grid">` +
    cells.map(cell => `
      <div class="case-info-cell">
        <div class="case-info-label">${cell.label}</div>
        <div class="case-info-value">${cell.value}</div>
      </div>`).join("") +
    `</div>`;
}

function buildOriginalGuide(guide) {
  if (!guide || !guide.length) return `<p class="empty">No guide data.</p>`;
  return guide.map(item => `
    <div class="orig-guide-item">
      <div class="orig-guide-title">${esc(item.dx)}</div>
      <div class="orig-guide-text">${esc(item.text)}</div>
    </div>`).join("");
}

/* ── Run pipeline ─────────────────────────────────────────────────────────── */

async function runPipeline(caseId) {
  const btn    = document.getElementById("run-btn");
  const status = document.getElementById("run-status");
  btn.disabled = true;
  btn.textContent = "⏳ Running…";
  status.innerHTML = "";

  try {
    const report = await api(`/api/cases/${encodeURIComponent(caseId)}/analyze`, { method:"POST" });
    renderReport(caseId, report);
    btn.textContent = "▶ Re-run Pipeline";
    btn.disabled = false;
    status.innerHTML = `<span class="msg-ok">✓ Pipeline complete</span>`;
  } catch (e) {
    btn.textContent = "▶ Run Analysis Pipeline";
    btn.disabled = false;
    status.innerHTML = `<span class="msg-error">Error: ${esc(e.message)}</span>`;
  }
}

/* ── Render report ────────────────────────────────────────────────────────── */

function renderReport(caseId, report) {
  const area = document.getElementById("report-area");
  if (!area) return;

  const agentSteps = report.agents  || {};
  const audit      = report.audit   || {};
  const esc_       = report.escalation || {};
  const guide      = report.guidance   || {};
  const hr         = report.human_review || {};

  area.innerHTML = `
    <div class="section-divider">Analysis Report</div>

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>Agent Pipeline</div>
      ${buildPipelineSteps(agentSteps)}
    </div>

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>IBM Granite Summary</div>
      ${buildGraniteSummary(report)}
    </div>

    ${buildEscalationCard(esc_)}

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>Evidence Validation</div>
      ${buildEvidenceTable(audit.evidence_table || [])}
    </div>

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>Gap Detection</div>
      ${buildGaps(agentSteps.GapDetection || {})}
    </div>

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>Revised Guidance</div>
      ${buildRevisedGuide(guide)}
    </div>

    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>Audit Checklist</div>
      ${buildChecklist(audit.clinician_checklist || [])}
    </div>

    <div class="card" id="review-card">
      <div class="card-title"><span class="card-title-dot"></span>Clinician Review</div>
      ${hr.status === "pending" ? buildReviewForm(caseId) : `<p class="msg-ok">✓ Review submitted.</p>`}
    </div>
  `;
}

function buildPipelineSteps(agents) {
  const names = [
    "CaseAnalysis","DifferentialReview","EvidenceRetrieval",
    "EvidenceValidation","GapDetection","GuidanceRefinement",
    "EscalationReview","HumanReview","AuditReport"
  ];
  return `<div class="pipeline-track">` +
    names.map(n => {
      const done = agents[n] !== undefined;
      return `<span class="step-pill ${done?"done":""}">${esc(n)}</span>`;
    }).join("") + `</div>`;
}

function buildGraniteSummary(report) {
  return `
    <div class="granite-wrap">
      <div class="granite-source-badge">
        🤖 Source: ${esc(report.granite_source || "template")}
      </div>
      <div class="granite-text">${esc(report.granite_summary || "")}</div>
    </div>`;
}

function buildEscalationCard(esc_) {
  if (!esc_.alerts || !esc_.alerts.length) {
    return `
      <div class="card">
        <div class="card-title"><span class="card-title-dot"></span>⚠️ Escalation Alerts</div>
        <div class="escalation-none">✅ No warning-sign alerts triggered.</div>
      </div>`;
  }
  const alerts = esc_.alerts.map(a => `
    <div class="alert-box">
      <div class="alert-box-icon">⚠️</div>
      <div class="alert-box-body">
        <div class="alert-ref">${esc(a.ref_id)}</div>
        <div class="alert-text">${esc(a.alert)}</div>
      </div>
    </div>`).join("");
  return `
    <div class="card">
      <div class="card-title"><span class="card-title-dot"></span>
        ⚠️ Escalation Alerts
        <span class="badge badge-unsupported" style="margin-left:auto">${esc(esc_.alert_count)} warning${esc_.alert_count===1?"":"s"}</span>
      </div>
      ${alerts}
    </div>`;
}

function buildEvidenceTable(rows) {
  if (!rows.length) return `<p class="empty">No evidence data.</p>`;
  return `<div style="overflow-x:auto">
    <table class="evidence-table">
      <thead><tr>
        <th>Possibility</th><th>Status</th><th>Flags</th><th>Sources</th>
      </tr></thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            <td style="font-weight:600">${esc(r.possibility)}</td>
            <td>${statusBadge(r.status)}</td>
            <td style="color:var(--gray-500);font-size:.8rem">${esc((r.flags||[]).join("; "))}</td>
            <td class="mono">${esc((r.source_ids||[]).join(", "))}</td>
          </tr>`).join("")}
      </tbody>
    </table></div>`;
}

function buildGaps(gapData) {
  const gaps = gapData.gaps || [];
  if (!gaps.length) return `<p class="empty">No gaps detected.</p>`;
  return `<ul class="gap-list">` +
    gaps.map(g => `
      <li class="gap-item gap-${esc(g.type)}">
        <div class="gap-dot"></div>
        <div>
          <strong>${esc(g.type.replace(/_/g," "))}</strong>
          ${g.possibility ? `<span style="opacity:.7"> [${esc(g.possibility)}]</span>` : ""}
          — ${esc(g.detail)}
        </div>
      </li>`).join("") + `</ul>`;
}

function buildRevisedGuide(guide) {
  const poss = guide.possibilities || [];
  if (!poss.length) return `<p class="empty">No revised guide.</p>`;
  return poss.map(p => `
    <div class="guide-item">
      <div class="guide-item-header">
        <span class="guide-item-title">${esc(p.possibility)}</span>
        ${statusBadge(p.status)}
      </div>
      <div class="guide-item-text">${esc(p.revised_claim)}</div>
      <div class="guide-item-sources">Sources: ${esc((p.source_ids||[]).join(", "))}</div>
    </div>`).join("");
}

function buildChecklist(items) {
  if (!items.length) return `<p class="empty">No checklist.</p>`;
  return `<ul class="checklist">` +
    items.map(i => `
      <li><div class="checklist-box"></div>${esc(i)}</li>`).join("") +
    `</ul>`;
}

function buildReviewForm(caseId) {
  return `
    <div class="review-form" id="review-form">
      <label class="form-label">Decision
        <select class="form-select" id="review-decision">
          <option value="approve">✅ Approve</option>
          <option value="request_changes">🔄 Request Changes</option>
        </select>
      </label>
      <label class="form-label">Comment (optional)
        <textarea class="form-textarea" id="review-comment"
                  placeholder="Add a comment for the audit log…"></textarea>
      </label>
      <div style="display:flex;align-items:center;gap:1rem">
        <button class="btn btn-teal" onclick="submitReview('${esc(caseId)}')">
          Submit Review
        </button>
        <span id="review-status"></span>
      </div>
    </div>`;
}

async function submitReview(caseId) {
  const decision = document.getElementById("review-decision").value;
  const comment  = document.getElementById("review-comment").value;
  const status   = document.getElementById("review-status");
  status.innerHTML = `<span style="color:var(--gray-400);font-size:.83rem">Saving…</span>`;

  try {
    await api(`/api/cases/${encodeURIComponent(caseId)}/review`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({ decision, comment }),
    });
    document.getElementById("review-form").innerHTML =
      `<p class="msg-ok">✓ Review submitted: ${esc(decision)}</p>`;
  } catch (e) {
    status.innerHTML = `<span class="msg-error">Error: ${esc(e.message)}</span>`;
  }
}

/* ── Audit Log ────────────────────────────────────────────────────────────── */

async function renderAudit() {
  setTopbarTitle("Audit Log");
  const el = showPage("page-audit");
  el.innerHTML = `<div class="loading">Loading audit log…</div>`;

  try {
    const rows = await api("/api/audit");
    if (!rows.length) {
      el.innerHTML = `<h1 class="page-title">Audit Log</h1><p class="empty">No entries yet.</p>`;
      return;
    }
    el.innerHTML = `
      <h1 class="page-title">Audit Log</h1>
      <div class="card" style="overflow-x:auto">
        <table class="audit-table">
          <thead><tr>
            <th>#</th><th>Case</th><th>Step</th><th>Status</th><th>Detail</th><th>Time</th>
          </tr></thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td class="mono">${esc(r.id)}</td>
                <td class="mono">${esc(r.case_id)}</td>
                <td style="font-weight:500">${esc(r.step)}</td>
                <td><span class="badge badge-${esc(r.status)}">${esc(r.status)}</span></td>
                <td style="max-width:300px;word-break:break-word;color:var(--gray-500);font-size:.8rem">${esc(r.detail)}</td>
                <td class="mono" style="white-space:nowrap">${esc(r.created_at)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    el.innerHTML = `<p class="msg-error">Failed to load audit log: ${esc(e.message)}</p>`;
  }
}
