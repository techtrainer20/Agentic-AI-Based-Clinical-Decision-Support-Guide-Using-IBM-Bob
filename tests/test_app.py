"""
tests/test_app.py – pytest suite for ClinGuide AI.
Uses FastAPI TestClient with a temporary SQLite database.
"""

import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Create a TestClient backed by a fresh temp database."""
    # Point the app at a temp db file before importing main.
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    os.environ["DB_PATH"] = db_file.name

    # Import after setting env var so db.py picks up the path.
    from app import db as app_db
    from app.main import app

    app_db.DB_PATH = db_file.name
    app_db.init_db()

    with TestClient(app) as c:
        yield c

    # Cleanup
    os.unlink(db_file.name)


# ── RAG tests ─────────────────────────────────────────────────────────────────

class TestRAG:
    def test_search_returns_results(self):
        from app.rag import search
        results = search("chest tightness ECG troponin")
        assert len(results) > 0

    def test_search_returns_dicts_with_id(self):
        from app.rag import search
        results = search("fever cough pneumonia")
        for r in results:
            assert "id" in r
            assert "text" in r

    def test_search_empty_query_returns_empty(self):
        from app.rag import search
        results = search("")
        assert results == []

    def test_search_by_ids(self):
        from app.rag import search_by_ids
        results = search_by_ids(["REF-001", "REF-012"])
        ids = [r["id"] for r in results]
        assert "REF-001" in ids
        assert "REF-012" in ids

    def test_search_top_k_respected(self):
        from app.rag import search
        results = search("headache migraine nausea photophobia", top_k=2)
        assert len(results) <= 2

    def test_search_warning_refs_included(self):
        from app.rag import search
        results = search("ruled out excluded confirmed definitely")
        types = [r["type"] for r in results]
        assert "warning" in types


# ── Agent unit tests ───────────────────────────────────────────────────────────

class TestAgents:
    @pytest.fixture(autouse=True)
    def load_case(self):
        from app.db import fetch_case
        self.case = fetch_case("CASE-001")
        assert self.case is not None

    def test_case_analysis_facts(self):
        from app.agents import agent_case_analysis
        out = agent_case_analysis(self.case)
        assert "facts" in out
        assert "missing_info" in out
        assert out["facts"]["age"] == 52

    def test_case_analysis_detects_missing_vitals(self):
        from app.agents import agent_case_analysis
        case = {**self.case, "vitals": {"bp": None, "hr": None, "temp": None, "spo2": None}}
        out = agent_case_analysis(case)
        # All four vitals missing → four entries
        assert len([m for m in out["missing_info"] if "Vital" in m]) == 4

    def test_differential_review_labels_possibilities(self):
        from app.agents import agent_differential_review
        out = agent_differential_review(self.case)
        assert "possibilities" in out
        assert len(out["possibilities"]) == 3
        for p in out["possibilities"]:
            assert "possibility" in p
            assert "claim" in p

    def test_evidence_retrieval_returns_source_ids(self):
        from app.agents import agent_differential_review, agent_evidence_retrieval
        dr = agent_differential_review(self.case)
        er = agent_evidence_retrieval(self.case, dr)
        assert "source_ids" in er
        assert isinstance(er["source_ids"], list)
        assert len(er["source_ids"]) > 0

    def test_evidence_validation_unsupported_for_absolute(self):
        from app.agents import agent_evidence_validation
        differential = {
            "possibilities": [
                {"possibility": "Test Dx", "claim": "This has been ruled out. No further tests needed."}
            ]
        }
        evidence = {"source_ids": ["REF-001"], "retrieved_refs": []}
        out = agent_evidence_validation(differential, evidence)
        assert out["validated"][0]["status"] == "Unsupported"

    def test_evidence_validation_partial_for_overconfident(self):
        from app.agents import agent_evidence_validation
        differential = {
            "possibilities": [
                {"possibility": "Test Dx", "claim": "This definitely indicates the condition."}
            ]
        }
        evidence = {"source_ids": ["REF-001"], "retrieved_refs": [{"id": "REF-001", "text": "x", "keywords": []}]}
        out = agent_evidence_validation(differential, evidence)
        assert out["validated"][0]["status"] == "Partial"

    def test_gap_detection_finds_language_issues(self):
        from app.agents import (
            agent_case_analysis, agent_differential_review,
            agent_evidence_retrieval, agent_evidence_validation,
            agent_gap_detection,
        )
        ca = agent_case_analysis(self.case)
        dr = agent_differential_review(self.case)
        er = agent_evidence_retrieval(self.case, dr)
        ev = agent_evidence_validation(dr, er)
        gd = agent_gap_detection(ca, dr, ev)
        types = [g["type"] for g in gd["gaps"]]
        assert "language_issue" in types

    def test_gap_detection_anchoring_bias(self):
        from app.agents import agent_gap_detection
        ca = {"missing_info": []}
        dr = {"possibilities": [{"possibility": "Only one dx", "claim": "claim"}]}
        ev = {"validated": [{"possibility": "Only one dx", "claim": "claim", "flags": [], "status": "Supported", "source_ids": []}]}
        gd = agent_gap_detection(ca, dr, ev)
        types = [g["type"] for g in gd["gaps"]]
        assert "anchoring_bias" in types

    def test_guidance_refinement_structure(self):
        from app.agents import (
            agent_case_analysis, agent_differential_review,
            agent_evidence_retrieval, agent_evidence_validation,
            agent_gap_detection, agent_guidance_refinement,
        )
        ca = agent_case_analysis(self.case)
        dr = agent_differential_review(self.case)
        er = agent_evidence_retrieval(self.case, dr)
        ev = agent_evidence_validation(dr, er)
        gd = agent_gap_detection(ca, dr, ev)
        gr = agent_guidance_refinement(self.case, ca, dr, ev, gd)
        for key in ("facts", "possibilities", "limitations", "open_questions"):
            assert key in gr

    def test_escalation_review_returns_alerts(self):
        from app.agents import agent_evidence_retrieval, agent_differential_review, agent_escalation_review
        dr = agent_differential_review(self.case)
        er = agent_evidence_retrieval(self.case, dr)
        esc = agent_escalation_review(self.case, er)
        assert "alerts" in esc
        assert "alert_count" in esc

    def test_human_review_pending(self):
        from app.agents import agent_human_review
        hr = agent_human_review()
        assert hr["status"] == "pending"

    def test_audit_report_structure(self):
        from app.agents import (
            agent_case_analysis, agent_differential_review,
            agent_evidence_retrieval, agent_evidence_validation,
            agent_gap_detection, agent_escalation_review, agent_audit_report,
        )
        ca = agent_case_analysis(self.case)
        dr = agent_differential_review(self.case)
        er = agent_evidence_retrieval(self.case, dr)
        ev = agent_evidence_validation(dr, er)
        gd = agent_gap_detection(ca, dr, ev)
        esc_ = agent_escalation_review(self.case, er)
        ar = agent_audit_report(self.case, ca, ev, gd, esc_)
        for key in ("evidence_table", "missing_info_log", "correction_history", "clinician_checklist"):
            assert key in ar


# ── Pipeline integration test ──────────────────────────────────────────────────

class TestPipeline:
    def test_run_pipeline_case001(self):
        from app.agents import run_pipeline
        report = run_pipeline("CASE-001")
        assert report["case_id"] == "CASE-001"
        assert "report_id" in report
        assert "agents" in report
        assert "guidance" in report
        assert "escalation" in report
        assert "audit" in report

    def test_run_pipeline_invalid_case(self):
        from app.agents import run_pipeline
        with pytest.raises(ValueError):
            run_pipeline("CASE-NONEXISTENT")

    def test_run_pipeline_all_cases(self):
        from app.agents import run_pipeline
        for case_id in ("CASE-001", "CASE-002", "CASE-003"):
            report = run_pipeline(case_id)
            assert report["case_id"] == case_id


# ── API route tests ────────────────────────────────────────────────────────────

class TestAPIRoutes:
    def test_get_cases(self, client):
        r = client.get("/api/cases")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        assert data[0]["id"] == "CASE-001"

    def test_get_case_valid(self, client):
        r = client.get("/api/cases/CASE-001")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "CASE-001"
        assert data["age"] == 52

    def test_get_case_not_found(self, client):
        r = client.get("/api/cases/CASE-NONE")
        assert r.status_code == 404

    def test_analyze_case(self, client):
        r = client.post("/api/cases/CASE-001/analyze")
        assert r.status_code == 200
        data = r.json()
        assert data["case_id"] == "CASE-001"
        assert "report_id" in data

    def test_analyze_case_not_found(self, client):
        r = client.post("/api/cases/CASE-NONE/analyze")
        assert r.status_code == 404

    def test_get_report_after_analyze(self, client):
        # Ensure there is at least one report.
        client.post("/api/cases/CASE-002/analyze")
        r = client.get("/api/cases/CASE-002/report")
        assert r.status_code == 200
        data = r.json()
        assert data["case_id"] == "CASE-002"

    def test_get_report_not_found(self, client):
        # CASE-003 may not have been analyzed yet; use a definitely absent case.
        r = client.get("/api/cases/CASE-NONE/report")
        assert r.status_code == 404

    def test_submit_review_approve(self, client):
        client.post("/api/cases/CASE-003/analyze")
        r = client.post(
            "/api/cases/CASE-003/review",
            json={"decision": "approve", "comment": "Looks good"},
        )
        assert r.status_code == 200
        assert r.json()["decision"] == "approve"

    def test_submit_review_request_changes(self, client):
        r = client.post(
            "/api/cases/CASE-001/review",
            json={"decision": "request_changes", "comment": "Needs more evidence"},
        )
        assert r.status_code == 200

    def test_submit_review_invalid_decision(self, client):
        r = client.post(
            "/api/cases/CASE-001/review",
            json={"decision": "maybe", "comment": ""},
        )
        assert r.status_code == 422

    def test_submit_review_no_report(self, client):
        # Use a case that definitely has no report stored.
        import tempfile, os
        # A fresh temp db won't have this case.
        r = client.post(
            "/api/cases/CASE-NONE/review",
            json={"decision": "approve", "comment": ""},
        )
        assert r.status_code == 404

    def test_get_audit_log(self, client):
        r = client.get("/api/audit")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_audit_log_filtered(self, client):
        r = client.get("/api/audit?case_id=CASE-001")
        assert r.status_code == 200
        data = r.json()
        for entry in data:
            assert entry["case_id"] == "CASE-001"

    def test_get_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        for key in ("cases", "reports_generated", "reviews_submitted", "approved"):
            assert key in data
        assert data["cases"] == 3

    def test_serve_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "ClinGuide AI" in r.text


# ── Upload & delete tests ──────────────────────────────────────────────────────

# Minimal valid case payload used across upload tests.
_VALID_CASE = {
    "id": "CASE-T01",
    "title": "Test Upload Case",
    "age": 40,
    "sex": "Male",
    "symptoms": ["test symptom"],
    "ai_guide": [{"dx": "Test Dx", "text": "This is definitely the diagnosis."}],
}


class TestUploadDelete:
    def _upload(self, client, case: dict, filename: str = "case.json") -> object:
        """Helper: POST case dict as a .json file upload."""
        content = json.dumps(case).encode()
        return client.post(
            "/api/cases/upload",
            files={"file": (filename, content, "application/json")},
        )

    def test_upload_valid_case(self, client):
        r = self._upload(client, _VALID_CASE)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "created"
        assert data["id"] == "CASE-T01"

    def test_upload_appears_in_list(self, client):
        ids = [c["id"] for c in client.get("/api/cases").json()]
        assert "CASE-T01" in ids

    def test_upload_can_analyze(self, client):
        r = client.post("/api/cases/CASE-T01/analyze")
        assert r.status_code == 200

    def test_upload_duplicate_id_rejected(self, client):
        r = self._upload(client, _VALID_CASE)
        assert r.status_code == 409

    def test_upload_non_json_extension_rejected(self, client):
        content = b"{}"
        r = client.post(
            "/api/cases/upload",
            files={"file": ("case.txt", content, "text/plain")},
        )
        assert r.status_code == 400

    def test_upload_invalid_json_rejected(self, client):
        r = client.post(
            "/api/cases/upload",
            files={"file": ("case.json", b"not json at all", "application/json")},
        )
        assert r.status_code == 400

    def test_upload_missing_required_field(self, client):
        bad = {k: v for k, v in _VALID_CASE.items() if k != "ai_guide"}
        bad["id"] = "CASE-T02"
        r = self._upload(client, bad)
        assert r.status_code == 422

    def test_upload_empty_ai_guide_rejected(self, client):
        bad = {**_VALID_CASE, "id": "CASE-T03", "ai_guide": []}
        r = self._upload(client, bad)
        assert r.status_code == 422

    def test_upload_ai_guide_missing_dx_rejected(self, client):
        bad = {**_VALID_CASE, "id": "CASE-T04", "ai_guide": [{"text": "no dx key"}]}
        r = self._upload(client, bad)
        assert r.status_code == 422

    def test_upload_fills_optional_defaults(self, client):
        minimal = {
            "id": "CASE-T05",
            "title": "Minimal Case",
            "age": 25,
            "sex": "Female",
            "symptoms": ["headache"],
            "ai_guide": [{"dx": "Migraine", "text": "Definitely migraine."}],
        }
        r = self._upload(client, minimal)
        assert r.status_code == 200
        case = client.get("/api/cases/CASE-T05").json()
        assert case["history"] == ""
        assert case["tests"] == []
        assert case["medications"] == []

    def test_delete_uploaded_case(self, client):
        r = client.delete("/api/cases/CASE-T01")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    def test_deleted_case_not_in_list(self, client):
        ids = [c["id"] for c in client.get("/api/cases").json()]
        assert "CASE-T01" not in ids

    def test_delete_nonexistent_case(self, client):
        r = client.delete("/api/cases/CASE-NONE")
        assert r.status_code == 404

    def test_delete_seeded_case(self, client):
        # Seeded cases can also be deleted; stats should decrement.
        before = client.get("/api/stats").json()["cases"]
        r = client.delete("/api/cases/CASE-003")
        assert r.status_code == 200
        after = client.get("/api/stats").json()["cases"]
        assert after == before - 1

    def test_upload_audit_log_entry(self, client):
        # Upload CASE-T05 (already exists); upload CASE-T06 fresh and check log.
        fresh = {**_VALID_CASE, "id": "CASE-T06"}
        self._upload(client, fresh, filename="t06.json")
        log = client.get("/api/audit?case_id=CASE-T06").json()
        steps = [e["step"] for e in log]
        assert "Upload" in steps
