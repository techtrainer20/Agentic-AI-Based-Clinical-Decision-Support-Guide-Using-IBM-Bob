"""
db.py – SQLite helpers for ClinGuide AI.
All tables are created here; seed data is loaded from data/.
"""

import json
import os
import sqlite3
from pathlib import Path

# Default database path; overridden by tests via DB_PATH env var.
DB_PATH = os.environ.get("DB_PATH", "clinguide.db")

# Locate the data directory relative to this file.
DATA_DIR = Path(__file__).parent.parent / "data"


def get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables and seed them if empty."""
    conn = get_conn()
    with conn:
        # Table: cases – one row per fictional clinical case.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id      TEXT PRIMARY KEY,
                title   TEXT NOT NULL,
                data    TEXT NOT NULL   -- full case JSON
            )
        """)

        # Table: reports – agent pipeline output for a case.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                data        TEXT NOT NULL   -- full report JSON
            )
        """)

        # Table: reviews – clinician decisions on a report.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     TEXT NOT NULL,
                report_id   INTEGER NOT NULL,
                decision    TEXT NOT NULL,  -- 'approve' or 'request_changes'
                comment     TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # Table: audit_log – one row per agent step or event.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     TEXT NOT NULL,
                step        TEXT NOT NULL,
                status      TEXT NOT NULL,  -- 'ok' or 'error'
                detail      TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # Table: references – approved evidence snippets.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refs (
                id       TEXT PRIMARY KEY,
                type     TEXT NOT NULL,
                keywords TEXT NOT NULL,  -- JSON array stored as text
                text     TEXT NOT NULL
            )
        """)

    _seed(conn)
    conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    """Insert cases and references from JSON files if tables are empty."""
    # Seed cases
    if conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0:
        cases = json.loads((DATA_DIR / "cases.json").read_text(encoding="utf-8"))
        for case in cases:
            conn.execute(
                "INSERT INTO cases (id, title, data) VALUES (?, ?, ?)",
                (case["id"], case["title"], json.dumps(case)),
            )

    # Seed references
    if conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0] == 0:
        refs = json.loads((DATA_DIR / "references.json").read_text(encoding="utf-8"))
        for ref in refs:
            conn.execute(
                "INSERT INTO refs (id, type, keywords, text) VALUES (?, ?, ?, ?)",
                (ref["id"], ref["type"], json.dumps(ref["keywords"]), ref["text"]),
            )
    conn.commit()


# ── Convenience query helpers ──────────────────────────────────────────────────

def fetch_all_cases() -> list[dict]:
    """Return all cases as plain dicts (id, title)."""
    conn = get_conn()
    rows = conn.execute("SELECT id, title FROM cases ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_case(case_id: str) -> dict | None:
    """Return a full case dict or None."""
    conn = get_conn()
    row = conn.execute("SELECT data FROM cases WHERE id = ?", (case_id,)).fetchone()
    conn.close()
    return json.loads(row["data"]) if row else None


def fetch_all_refs() -> list[dict]:
    """Return all reference snippets as plain dicts."""
    conn = get_conn()
    rows = conn.execute("SELECT id, type, keywords, text FROM refs").fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "keywords": json.loads(r["keywords"]),
            "text": r["text"],
        }
        for r in rows
    ]


def save_report(case_id: str, data: dict) -> int:
    """Persist a pipeline report; return the new row id."""
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO reports (case_id, data) VALUES (?, ?)",
            (case_id, json.dumps(data)),
        )
        report_id = cur.lastrowid
    conn.close()
    return report_id


def fetch_latest_report(case_id: str) -> dict | None:
    """Return the most recent report dict for a case, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, data FROM reports WHERE case_id = ? ORDER BY id DESC LIMIT 1",
        (case_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    report = json.loads(row["data"])
    report["report_id"] = row["id"]
    return report


def save_review(case_id: str, report_id: int, decision: str, comment: str) -> None:
    """Persist a clinician review."""
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO reviews (case_id, report_id, decision, comment) VALUES (?, ?, ?, ?)",
            (case_id, report_id, decision, comment),
        )
    conn.close()


def log_audit(case_id: str, step: str, status: str, detail: str = "") -> None:
    """Write one row to audit_log."""
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO audit_log (case_id, step, status, detail) VALUES (?, ?, ?, ?)",
            (case_id, step, status, detail),
        )
    conn.close()


def fetch_audit_log(case_id: str | None = None) -> list[dict]:
    """Return audit log rows, optionally filtered by case_id."""
    conn = get_conn()
    if case_id:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY id DESC",
            (case_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT 200"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_case(case: dict) -> None:
    """Insert a new case. Raises ValueError if the id already exists."""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM cases WHERE id = ?", (case["id"],)
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Case id '{case['id']}' already exists")
    with conn:
        conn.execute(
            "INSERT INTO cases (id, title, data) VALUES (?, ?, ?)",
            (case["id"], case["title"], json.dumps(case)),
        )
    conn.close()


def delete_case(case_id: str) -> bool:
    """Delete a case and its reports/reviews/audit rows. Returns True if found."""
    conn = get_conn()
    exists = conn.execute(
        "SELECT id FROM cases WHERE id = ?", (case_id,)
    ).fetchone()
    if not exists:
        conn.close()
        return False
    with conn:
        conn.execute("DELETE FROM cases     WHERE id = ?",      (case_id,))
        conn.execute("DELETE FROM reports   WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM reviews   WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM audit_log WHERE case_id = ?", (case_id,))
    conn.close()
    return True


def fetch_stats() -> dict:
    """Return simple aggregate statistics."""
    conn = get_conn()
    n_cases = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    n_reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    n_reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    n_approved = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE decision = 'approve'"
    ).fetchone()[0]
    conn.close()
    return {
        "cases": n_cases,
        "reports_generated": n_reports,
        "reviews_submitted": n_reviews,
        "approved": n_approved,
    }
