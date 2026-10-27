# ClinGuide AI

> ## ⚠️ Safety Notice (Read First)
> **Educational use only.** Every case, symptom, test result, and clinical detail in this project is **fictional**.
> This application is a classroom simulation to help students practice critical thinking about AI-generated clinical text.
> It is **not** a medical device, **not** a diagnosis tool, and **must never be used for real patient care or real medical decisions**.
> Final decisions always belong to a licensed clinician in real-world settings.

ClinGuide AI is a student-friendly web app that shows how an AI-written clinical guide can be checked, corrected, and reviewed in a safe simulation.

In simple terms, the app takes a fictional case and:
1. Reviews the draft clinical guide in small steps,
2. Checks whether claims are supported by approved reference text,
3. Flags overconfident wording and missing information,
4. Produces a revised report for clinician review and sign-off.

What you can learn with this project:
- How structured review steps improve AI-generated clinical writing,
- How evidence tracking and audit trails support responsible AI,
- Why human review is required before accepting AI output.

What this app does **not** do:
- It does not diagnose real patients,
- It does not replace clinicians,
- It does not use real patient records,
- It does not provide medical advice.

---

## What you will see in the app

Use this section as a visual tour before you click anything.

### 1) Overview dashboard (home page)
![image3](image3)

**What to notice:**
- Summary cards with key counts (for example, cases, analyses, and reviews),
- A quick snapshot of activity so you can understand the project state at a glance,
- A starting point for moving to case analysis.

### 2) Fictional Cases page
![image2](image2)

**What to notice:**
- A list of fictional cases you can open,
- Each case includes a draft AI guide that intentionally contains issues for learning,
- Controls to run an analysis and generate a structured report.

### 3) Audit Log page
![image1](image1)

**What to notice:**
- A timeline/table of what happened during analysis,
- Traceability details showing why a claim was flagged or revised,
- Review/sign-off records that demonstrate human oversight.

---

## Quick Start (beginner-friendly)

### 1. Prerequisites
You need:
- **Python 3.10+** (download from [python.org](https://www.python.org/downloads/))
- A terminal:
  - **Windows:** PowerShell
  - **macOS/Linux:** Terminal

Tip: while installing Python on Windows, enable **“Add Python to PATH”**.

### 2. Open the project folder in your terminal

Use the cloned repository path:

`/home/runner/work/Agentic-AI-Based-Clinical-Decision-Support-Guide-Using-IBM-Bob/Agentic-AI-Based-Clinical-Decision-Support-Guide-Using-IBM-Bob`

### 3. Create and activate a virtual environment
A virtual environment is an isolated Python workspace for this project.

```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies
Dependencies are required Python packages listed in `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 5. Run the application server
A server is the local process that hosts the app in your browser.

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

---

## How to use the application (step by step)

1. **Start the server** using the `uvicorn` command above.
2. **Open the browser** at `http://127.0.0.1:8000`.
3. Go to **Fictional Cases** and choose one case.
4. Click the control to **run analysis**.
   - The app runs a multi-step pipeline using software “agents” (small software tasks).
5. Open the generated **report** and read:
   - Identified possibilities,
   - Evidence support status,
   - Missing information and safety notes,
   - Refined guidance text.
6. Record a **clinician review** (human sign-off):
   - Approve or request changes,
   - Add review notes.
7. Visit **Audit Log** to see what was done and when.

---

## Troubleshooting (common beginner issues)

### Python is not found
- Try `python --version` (Windows) or `python3 --version` (macOS/Linux).
- If command fails, reinstall Python and ensure PATH is enabled.

### Windows PowerShell blocks activation
You may see an execution policy error for `Activate.ps1`.
Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then run:

```powershell
.venv\Scripts\Activate.ps1
```

### Port 8000 is already in use
Start on another port:

```bash
uvicorn app.main:app --reload --port 8001
```

Then open `http://127.0.0.1:8001`.

### Dependency installation errors
- Upgrade packaging tools:
  ```bash
  python -m pip install --upgrade pip setuptools wheel
  ```
- Re-run:
  ```bash
  pip install -r requirements.txt
  ```
- If needed, delete and recreate `.venv`, then reinstall.

---

## Optional: IBM Granite AI Summaries

ClinGuide AI can call IBM Granite (via [watsonx.ai](https://www.ibm.com/watsonx)) to generate plain-English summaries of each analysis.
If credentials are not set, the app still runs and shows a template summary.

Set these environment variables **before** starting the server:

```bash
# Windows PowerShell
$env:WATSONX_API_KEY    = "your-api-key"
$env:WATSONX_PROJECT_ID = "your-project-id"
# Optional – defaults to us-south
$env:WATSONX_URL        = "https://us-south.ml.cloud.ibm.com"

# macOS / Linux
export WATSONX_API_KEY="your-api-key"
export WATSONX_PROJECT_ID="your-project-id"
```

---

## Project Structure

```
clinguide-ai/
├── app/
│   ├── __init__.py     # Package marker
│   ├── main.py         # FastAPI app, routes, CORS, static serving
│   ├── db.py           # SQLite helpers, table creation, seed data
│   ├── agents.py       # Nine agent functions + run_pipeline()
│   ├── rag.py          # Word-overlap retrieval (no ML libraries)
│   └── granite.py      # IBM Granite / watsonx.ai integration
├── data/
│   ├── cases.json      # 3 fictional clinical cases
│   └── references.json # 12 approved reference snippets (REF-001…REF-012)
├── static/
│   ├── index.html      # Single-page frontend shell
│   ├── style.css       # Hospital dashboard styles (blue/white/teal)
│   └── app.js          # Vanilla JS, hash routing, XSS-safe DOM updates
├── tests/
│   └── test_app.py     # pytest suite (RAG, agents, pipeline, API routes)
├── requirements.txt
└── README.md
```

---

## Nine-agent workflow (plain language)

In this project, an **agent** means a small software task that does one specific review step.
It is **not** a human and **not** an autonomous clinician.

1. **Case Analysis** – Organizes case facts and marks missing details.
2. **Differential Review** – Lists possible explanations, not final diagnoses.
3. **Evidence Retrieval (RAG)** – Finds relevant approved reference snippets.
4. **Evidence Validation** – Marks claims as supported, partial, or unsupported.
5. **Gap Detection** – Flags missing data, risky wording, and bias patterns.
6. **Guidance Refinement** – Rewrites output into a safer structured format.
7. **Escalation Review** – Checks for warning signs needing urgent attention.
8. **Human Review** – Clinician approves or requests changes.
9. **Audit Report** – Stores traceable results and review outcomes.

```mermaid
flowchart TD
    A[Case Data\nfrom SQLite] --> B[1 CaseAnalysis\nOrganise facts, list missing info]
    B --> C[2 DifferentialReview\nList possibilities, never diagnoses]
    C --> D[3 EvidenceRetrieval\nRAG word-overlap search → source IDs]
    D --> E[4 EvidenceValidation\nSupported / Partial / Unsupported]
    E --> F[5 GapDetection\nMissing info, overconfidence, anchoring bias]
    F --> G[6 GuidanceRefinement\nFacts | Possibilities | Limitations | Questions]
    D --> H[7 EscalationReview\nWarning-sign refs matched to case]
    G --> I[8 HumanReview\nClinician Approve / Request Changes]
    H --> I
    I --> J[9 AuditReport\nEvidence table, corrections, checklist]
    J --> K[(SQLite Report\n+ Audit Log)]
    K --> L[IBM Granite Summary\ngraceful fallback]
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cases` | List all fictional cases |
| GET | `/api/cases/{id}` | Full case data |
| POST | `/api/cases/{id}/analyze` | Run the nine-agent pipeline |
| GET | `/api/cases/{id}/report` | Most recent report |
| POST | `/api/cases/{id}/review` | Submit clinician review |
| GET | `/api/audit` | Full audit log (optional `?case_id=`) |
| GET | `/api/stats` | Dashboard statistics |

---

## Glossary (key terms)

- **Fictional case**: A made-up patient scenario used only for learning.
- **Differential diagnosis**: A list of possible explanations for symptoms.
- **Evidence retrieval (RAG)**: Pulling relevant reference text to support or challenge claims.
- **Audit log**: A history of what steps were run, what changed, and who reviewed it.
- **Human review / sign-off**: A clinician checks the report and approves or requests revisions.
- **IBM Granite summary**: Optional plain-language summary generated through IBM watsonx.ai.

---

## Responsible AI

ClinGuide AI was designed with the following Responsible AI principles:

| Principle | Implementation |
|-----------|----------------|
| **Transparency** | Every claim is traced to a source ID. The Granite source is always labelled ("granite" or "template"). |
| **Uncertainty** | The app never states a confirmed diagnosis. Overconfident language is flagged and soft-redacted. |
| **Human oversight** | A clinician must review and sign off every report before it is considered complete. |
| **Explainability** | The evidence table, gap detection, and audit report show exactly why each claim was flagged. |
| **Non-maleficence** | Warning-sign references trigger explicit escalation alerts. Missing investigations are listed. |
| **Fictional data only** | No real patient data is ever used. An "Educational use only" banner is shown on every page. |
| **Auditability** | Every agent step and clinician decision is logged in the `audit_log` table. |

---

## Notes for Students

- The **original AI guide** in each case includes intentional flaws (for example overconfident wording or missing information) so you can practice review.
- The **RAG retrieval** in this project uses simple word overlap (not neural embeddings).
- The **database** is a local SQLite file (`clinguide.db`) created automatically on first run.
- You can delete `clinguide.db` at any time to reset to a clean state.

---

## Test command (optional for contributors)

```bash
pytest tests/ -v
```
