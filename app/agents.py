"""
agents.py – Nine plain-function agents for the ClinGuide AI pipeline.
Each agent receives a case dict and (optionally) prior agent outputs,
then returns a plain dict.  run_pipeline() chains them, logs every step
to audit_log, and saves the final report.
"""

import re
from app import db, rag
from app.granite import explain as granite_explain

# Words that signal overconfidence in an AI-generated claim.
OVERCONFIDENT_WORDS = [
    "definitely", "confirmed", "confirm", "pathognomonic",
    "certainly", "certain", "proves", "proof",
]

# Phrases that signal an absolute / exclusionary statement.
ABSOLUTE_PHRASES = [
    "ruled out", "no further tests", "not required",
    "not needed", "not necessary", "completely ruled out",
    "definitively excluded", "no possibility",
]


# ── Agent 1: Case Analysis ────────────────────────────────────────────────────

def agent_case_analysis(case: dict) -> dict:
    """
    Organise the key clinical facts and list anything that is missing
    (history gaps, missing vitals, absent tests, no medication list).
    """
    vitals = case.get("vitals", {})
    missing = []

    # Check each vital sign
    for field in ["bp", "hr", "temp", "spo2"]:
        if not vitals.get(field):
            missing.append(f"Vital sign missing: {field.upper()}")

    # Flag absent tests
    if not case.get("tests"):
        missing.append("No diagnostic tests documented")

    # Flag absent medication list (None vs empty list differs in meaning)
    if case.get("medications") is None:
        missing.append("Medication history not documented")

    # Flag absent narrative history
    if not case.get("history", "").strip():
        missing.append("Clinical history not documented")

    facts = {
        "age": case.get("age"),
        "sex": case.get("sex"),
        "symptoms": case.get("symptoms", []),
        "history": case.get("history", ""),
        "vitals": vitals,
        "tests": case.get("tests", []),
        "medications": case.get("medications", []),
    }

    return {"facts": facts, "missing_info": missing}


# ── Agent 2: Differential Review ─────────────────────────────────────────────

def agent_differential_review(case: dict) -> dict:
    """
    Extract the list of possibilities from the AI guide.
    Re-labels them as 'possibilities', never as confirmed diagnoses.
    """
    guide = case.get("ai_guide", [])
    possibilities = [
        {
            "possibility": item["dx"],   # renamed from 'dx' to avoid diagnosis framing
            "claim": item["text"],
        }
        for item in guide
    ]
    return {
        "possibilities": possibilities,
        "note": (
            "These are possibilities for educational review only. "
            "None represents a confirmed diagnosis."
        ),
    }


# ── Agent 3: Evidence Retrieval ───────────────────────────────────────────────

def agent_evidence_retrieval(case: dict, differential: dict) -> dict:
    """
    Build a query from the case symptoms and each possibility,
    then run a RAG word-overlap search to find relevant reference IDs.
    """
    symptoms = " ".join(case.get("symptoms", []))
    dx_labels = " ".join(
        p["possibility"] for p in differential.get("possibilities", [])
    )
    query = f"{symptoms} {dx_labels} {case.get('history', '')}"

    hits = rag.search(query, top_k=8)
    source_ids = [h["id"] for h in hits]

    return {"source_ids": source_ids, "retrieved_refs": hits}


# ── Agent 4: Evidence Validation ─────────────────────────────────────────────

def agent_evidence_validation(differential: dict, evidence: dict) -> dict:
    """
    For each claim in the differential, assign a validation status:
      Supported   – no overconfident/absolute language, has a supporting ref
      Partial     – overconfident language found (e.g. 'definitely', 'confirmed')
      Unsupported – absolute exclusion ('ruled out') or no reference found
    """
    ref_texts = " ".join(r["text"] for r in evidence.get("retrieved_refs", []))
    source_ids = evidence.get("source_ids", [])

    validated = []
    for item in differential.get("possibilities", []):
        claim = item["claim"].lower()
        status = "Supported"
        flags = []

        # Check for absolute / exclusionary phrases first (strongest signal)
        for phrase in ABSOLUTE_PHRASES:
            if phrase in claim:
                status = "Unsupported"
                flags.append(f"absolute statement: '{phrase}'")

        # Check for overconfident language
        for word in OVERCONFIDENT_WORDS:
            if re.search(rf"\b{word}\b", claim):
                if status != "Unsupported":
                    status = "Partial"
                flags.append(f"overconfident word: '{word}'")

        # Downgrade to Unsupported if no reference overlaps with this possibility
        if not source_ids:
            status = "Unsupported"
            flags.append("no supporting reference found")

        validated.append(
            {
                "possibility": item["possibility"],
                "claim": item["claim"],
                "status": status,
                "flags": flags,
                "source_ids": source_ids,
            }
        )

    return {"validated": validated}


# ── Agent 5: Gap Detection ────────────────────────────────────────────────────

def agent_gap_detection(case_analysis: dict, differential: dict, validation: dict) -> dict:
    """
    Identify:
      - missing information (from case analysis)
      - overconfident language in any claim
      - absolute exclusion statements
      - anchoring bias (only a single possibility listed)
    """
    gaps = []

    # Carry forward missing info
    for m in case_analysis.get("missing_info", []):
        gaps.append({"type": "missing_info", "detail": m})

    # Scan each validated claim for flags
    for item in validation.get("validated", []):
        for flag in item.get("flags", []):
            gaps.append(
                {
                    "type": "language_issue",
                    "possibility": item["possibility"],
                    "detail": flag,
                }
            )

    # Anchoring bias: warn if only one possibility is considered
    n = len(differential.get("possibilities", []))
    if n == 1:
        gaps.append(
            {
                "type": "anchoring_bias",
                "detail": (
                    "Only one possibility is listed; premature closure risk. "
                    "A broader differential should be considered."
                ),
            }
        )

    return {"gaps": gaps}


# ── Agent 6: Guidance Refinement ─────────────────────────────────────────────

def agent_guidance_refinement(case: dict, case_analysis: dict,
                               differential: dict, validation: dict,
                               gaps: dict) -> dict:
    """
    Produce a structured revised guide with four sections:
      Facts | Possibilities | Limitations | Open questions
    """
    facts_section = case_analysis.get("facts", {})

    # Possibilities – use validated items, stripping overconfident language.
    possibilities_section = []
    for item in validation.get("validated", []):
        clean_claim = item["claim"]
        # Soft-redact the most egregious overconfident words.
        for word in OVERCONFIDENT_WORDS:
            clean_claim = re.sub(
                rf"\b{word}\b", f"[possibly {word} – review required]",
                clean_claim, flags=re.IGNORECASE
            )
        possibilities_section.append(
            {
                "possibility": item["possibility"],
                "revised_claim": clean_claim,
                "status": item["status"],
                "source_ids": item["source_ids"],
            }
        )

    # Limitations – language issues and missing info.
    limitations = [g["detail"] for g in gaps.get("gaps", [])]

    # Open questions – derive from missing vitals / tests.
    open_questions = [
        m for m in case_analysis.get("missing_info", [])
    ]
    if not open_questions:
        open_questions = ["Are all relevant investigations complete?"]

    return {
        "facts": facts_section,
        "possibilities": possibilities_section,
        "limitations": limitations,
        "open_questions": open_questions,
    }


# ── Agent 7: Escalation Review ───────────────────────────────────────────────

def agent_escalation_review(case: dict, evidence: dict) -> dict:
    """
    Match warning-type references against the case symptoms and history.
    Returns a list of escalation alerts sourced only from 'warning' refs.
    """
    symptoms_text = (
        " ".join(case.get("symptoms", []))
        + " "
        + case.get("history", "")
        + " "
        + " ".join(case.get("tests", []))
    ).lower()

    alerts = []
    for ref in evidence.get("retrieved_refs", []):
        if ref.get("type") != "warning":
            continue
        # Check if any keyword from this warning ref appears in the case text.
        for kw in ref.get("keywords", []):
            if kw.lower() in symptoms_text:
                alerts.append(
                    {
                        "ref_id": ref["id"],
                        "alert": ref["text"],
                    }
                )
                break  # one match is enough to raise the alert

    return {
        "alerts": alerts,
        "alert_count": len(alerts),
    }


# ── Agent 8: Human Review (placeholder) ──────────────────────────────────────

def agent_human_review() -> dict:
    """
    Placeholder for the clinician review step.
    The actual decision is submitted via the POST /api/cases/{id}/review endpoint.
    This agent records that human sign-off is pending.
    """
    return {
        "status": "pending",
        "instruction": (
            "A qualified clinician must review this guide before any clinical use. "
            "Use the Review Form below to Approve or Request Changes."
        ),
    }


# ── Agent 9: Audit Report ─────────────────────────────────────────────────────

def agent_audit_report(case: dict, case_analysis: dict, validation: dict,
                        gaps: dict, escalation: dict) -> dict:
    """
    Build an audit report with:
      - evidence table (possibility + status + source IDs)
      - missing-info log
      - corrections applied (overconfident language flags)
      - clinician checklist
    """
    evidence_table = [
        {
            "possibility": v["possibility"],
            "status": v["status"],
            "flags": v["flags"],
            "source_ids": v["source_ids"],
        }
        for v in validation.get("validated", [])
    ]

    missing_info_log = [
        g["detail"]
        for g in gaps.get("gaps", [])
        if g["type"] == "missing_info"
    ]

    correction_history = [
        {
            "possibility": g["possibility"],
            "correction": g["detail"],
        }
        for g in gaps.get("gaps", [])
        if g["type"] == "language_issue"
    ]

    checklist = [
        "All missing investigations have been considered.",
        "Overconfident language has been reviewed and adjusted.",
        "Warning-sign alerts have been assessed.",
        "The differential remains open pending further work-up.",
        "A qualified clinician has reviewed and signed off this guide.",
    ]

    return {
        "evidence_table": evidence_table,
        "missing_info_log": missing_info_log,
        "correction_history": correction_history,
        "clinician_checklist": checklist,
    }


# ── Pipeline orchestrator ─────────────────────────────────────────────────────

def run_pipeline(case_id: str) -> dict:
    """
    Run all agents in order for the given case, log each step, and
    persist the assembled report.  Returns the full report dict.
    """
    case = db.fetch_case(case_id)
    if not case:
        raise ValueError(f"Case not found: {case_id}")

    steps = {}

    def _run(name: str, fn, *args):
        """Run one agent, log result, and store output in steps."""
        try:
            result = fn(*args)
            db.log_audit(case_id, name, "ok", "")
            steps[name] = result
            return result
        except Exception as exc:
            db.log_audit(case_id, name, "error", str(exc))
            raise

    # Agent 1
    ca = _run("CaseAnalysis", agent_case_analysis, case)

    # Agent 2
    dr = _run("DifferentialReview", agent_differential_review, case)

    # Agent 3
    er = _run("EvidenceRetrieval", agent_evidence_retrieval, case, dr)

    # Agent 4
    ev = _run("EvidenceValidation", agent_evidence_validation, dr, er)

    # Agent 5
    gd = _run("GapDetection", agent_gap_detection, ca, dr, ev)

    # Agent 6
    gr = _run("GuidanceRefinement", agent_guidance_refinement, case, ca, dr, ev, gd)

    # Agent 7
    esc = _run("EscalationReview", agent_escalation_review, case, er)

    # Agent 8
    hr = _run("HumanReview", agent_human_review)

    # Agent 9
    ar = _run("AuditReport", agent_audit_report, case, ca, ev, gd, esc)

    # Ask Granite for a plain-English summary (graceful fallback built-in).
    summary_input = (
        f"Case: {case.get('title')} | "
        f"Possibilities: {[p['possibility'] for p in dr['possibilities']]} | "
        f"Gaps: {[g['detail'] for g in gd['gaps']]} | "
        f"Alerts: {esc['alert_count']} warning(s)"
    )
    granite_text, granite_source = granite_explain(summary_input)

    report = {
        "case_id": case_id,
        "case_title": case.get("title"),
        "agents": steps,
        "guidance": gr,
        "escalation": esc,
        "human_review": hr,
        "audit": ar,
        "granite_summary": granite_text,
        "granite_source": granite_source,
    }

    report_id = db.save_report(case_id, report)
    report["report_id"] = report_id
    db.log_audit(case_id, "Pipeline", "ok", f"Report {report_id} saved")
    return report
