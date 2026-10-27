"""
main.py – FastAPI application for ClinGuide AI.
Serves the REST API and the static frontend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json

from app import db, agents

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialise the database and seed data on first run."""
    db.init_db()
    yield


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="ClinGuide AI", version="1.0.0", lifespan=lifespan)

# Allow all origins for development / educational use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Static files ──────────────────────────────────────────────────────────────

# Mount static assets (CSS, JS) under /static.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    """Serve the single-page frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/cases")
def list_cases():
    """Return a summary list of all fictional cases."""
    return db.fetch_all_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """Return the full data for one case."""
    case = db.fetch_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/analyze")
def analyze_case(case_id: str):
    """
    Run the full agent pipeline for a case.
    Creates and stores a new report; returns it.
    """
    case = db.fetch_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        report = agents.run_pipeline(case_id)
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/cases/{case_id}/report")
def get_report(case_id: str):
    """Return the most recent pipeline report for a case."""
    report = db.fetch_latest_report(case_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report found – run /analyze first")
    return report


class ReviewPayload(BaseModel):
    decision: str   # 'approve' or 'request_changes'
    comment: str = ""


@app.post("/api/cases/{case_id}/review")
def submit_review(case_id: str, payload: ReviewPayload):
    """
    Submit a clinician review decision for the latest report.
    Validates the decision value before saving.
    """
    valid_decisions = {"approve", "request_changes"}
    if payload.decision not in valid_decisions:
        raise HTTPException(
            status_code=422,
            detail=f"decision must be one of: {valid_decisions}",
        )

    report = db.fetch_latest_report(case_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report found for this case")

    db.save_review(case_id, report["report_id"], payload.decision, payload.comment)
    db.log_audit(
        case_id, "HumanReview", "ok",
        f"decision={payload.decision}"
    )
    return {"status": "saved", "decision": payload.decision}


# ── Required keys every uploaded case must contain ───────────────────────────
_REQUIRED_CASE_KEYS = {"id", "title", "age", "sex", "symptoms", "ai_guide"}


@app.post("/api/cases/upload")
async def upload_case(file: UploadFile = File(...)):
    """
    Accept a JSON file upload and insert it as a new case.
    Validates required fields; rejects duplicate IDs.
    The file must be fictional/educational data only.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    raw = await file.read()
    try:
        case = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    # Basic field validation
    missing = _REQUIRED_CASE_KEYS - set(case.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required fields: {sorted(missing)}",
        )

    if not isinstance(case.get("ai_guide"), list) or len(case["ai_guide"]) == 0:
        raise HTTPException(
            status_code=422,
            detail="ai_guide must be a non-empty list of {dx, text} objects",
        )

    for item in case["ai_guide"]:
        if "dx" not in item or "text" not in item:
            raise HTTPException(
                status_code=422,
                detail="Each ai_guide item must have 'dx' and 'text' keys",
            )

    # Fill optional fields with safe defaults so agents never crash
    case.setdefault("history", "")
    case.setdefault("vitals", {"bp": None, "hr": None, "temp": None, "spo2": None})
    case.setdefault("tests", [])
    case.setdefault("medications", [])

    try:
        db.insert_case(case)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.log_audit(case["id"], "Upload", "ok", f"Uploaded by user: {file.filename}")
    return {"status": "created", "id": case["id"], "title": case["title"]}


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str):
    """
    Delete a case and all its associated reports, reviews, and audit rows.
    Seeded cases (CASE-001, CASE-002, CASE-003) can also be deleted.
    """
    found = db.delete_case(case_id)
    if not found:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"status": "deleted", "id": case_id}


@app.get("/api/audit")
def get_audit(case_id: str | None = None):
    """Return the audit log, optionally filtered by case_id."""
    return db.fetch_audit_log(case_id)


@app.get("/api/stats")
def get_stats():
    """Return aggregate statistics for the dashboard overview."""
    return db.fetch_stats()
