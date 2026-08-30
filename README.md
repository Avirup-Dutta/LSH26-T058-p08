# School Result Processing and GPA Engine

- **Team ID:** `LSH26-T058`
- **Problem ID:** `P08`
- **Repository Name:** `Avirup-Dutta-LSH26-T058-p08`
- **Live URL:** `https://result-engine-vercel.vercel.app`

---

## Problem-Solving Method Statement

Our solution implements a modular, pure-Python deterministic rule engine (`app/rules.py`) decoupled completely from database layers, web frameworks, and third-party dependencies. This architecture ensures 100% auditable, transparent, and reproducible grading calculations that can be verified offline via CLI tools, unit tests, and public fixture test harnesses.

The engine implements official secondary education board standards:
1. Six compulsory subjects plus one optional (4th) subject per student.
2. Distinct theory (75 max / 25 pass) and practical (25 max / 8 pass) components where applicable, enforcing that component failure causes subject failure regardless of combined totals.
3. Strict compulsory pass requirement (any compulsory subject fail results in GPA 0.00 / F).
4. Optional 4th subject bonus mechanism where only grade points earned in excess of 2.00 contribute to the GPA total (capped at 5.00), preventing an optional subject from ever penalizing a student.
5. Multi-tiered verification checking lists (R-29) categorizing students by audit risk (Priority 1: Outcome-determining edge cases, Priority 2: Rule application / withholding, Priority 3: Routine adjustments).

---

## Team Members and Contributions

| Registered Name | GitHub Username | Major Contribution | Evidence Paths / Commits |
|---|---|---|---|
| Avirup Dutta | `Avirup-Dutta` | Core rule engine (`app/rules.py`), FastAPI backend (`app/main.py`), checking list service (`app/services.py`), Ext JS frontend integration (`web/app.js`), test suites (`tests/test_rules.py`), test harness (`harness.py`), and CLI reporting (`report.py`). | `app/rules.py`, `app/services.py`, `app/main.py`, `web/app.js`, `tests/test_rules.py`, `harness.py`, `report.py` |
| Riyad Haque | `riyad492` | Backend & database schema architecture, edge-case dataset generation, testing, and deployment setup. | `app/models.py`, `seed/seed_data.py`, `DEPLOY.md`, `vercel.json` |

---

## Requirement Proof & Verification

| Requirement ID | Description | Status | Evidence |
|---|---|---|---|
| **R1** | Subject Evaluation, Component Pass Marks & Grade Bands (R1-R5, R11, R12) | **Complete** | [`app/rules.py`](app/rules.py#L183-L232), [`tests/test_rules.py`](tests/test_rules.py#L34-L65) |
| **R2** | Overall Student GPA, 4th Subject Bonus, Cap 5.00 & Fail Rules (G1-G5, R13) | **Complete** | [`app/rules.py`](app/rules.py#L237-L353), [`tests/test_rules.py`](tests/test_rules.py#L69-L159) |
| **R3** | Three R-29 Checking Lists (Optional <= 2.0, Practical Fail < 8, Absent AB) & Tiered Verification | **Complete** | [`app/services.py`](app/services.py#L15-L62), [`report.py`](report.py#L60-L120), [`web/app.js`](web/app.js) |
| **R4** | Interactive UI Dashboard, Per-Subject Rule Trace & Live Compute Endpoint | **Complete** | [`web/index.html`](web/index.html), [`web/app.js`](web/app.js), [`app/main.py`](app/main.py#L57-L175) |

---

## Major Decisions & Architecture

1. **Decoupled Pure-Python Engine (`app/rules.py`):** Zero framework/database dependencies inside the calculation core allows instant unit testing and standalone execution without launching a database server.
2. **Deterministic Audit Trace:** Every decision (subject evaluation, component failure, optional bonus application, GPA calculation) emits human-readable rule codes (`R1_ABSENT`, `R2_THEORY_FAIL`, `R3_PRACTICAL_FAIL`, `R4_TOTAL_FAIL`, `R5_BAND`, `G1_COMPULSORY_FAIL`, `G2_AVERAGE`, `G3_OPTIONAL_APPLIED`, `G4_OPTIONAL_IGNORED`, `G5_CAPPED`) directly into the student result record.
3. **Dual Execution Interfaces:** Rich interactive Ext JS web UI with sortable grids and detailed student trace modals, alongside full-featured CLI tools (`report.py`, `harness.py`) for automated batch processing.
4. **Three Priority Tiers for Office Checklist:** Prioritizes administrative review by separating outcome-altering results (Priority 1) from policy exceptions (Priority 2) and routine calculation shifts (Priority 3).

---

## Known Limitations

- **Vercel Serverless Read-Only SQLite:** When hosted on Vercel without an external PostgreSQL instance, SQLite operates in read-only mode with pre-seeded data. Full write/recompute capabilities run locally or by configuring a PostgreSQL `DATABASE_URL`.

---

## Running Locally

### 1. Setup Environment

```bash
pip install -r requirements.txt
cp .env.example .env

alembic upgrade head          # create database schema
python -m seed.seed_data      # seed 2 classes, 73 students, 13 hand-built edge cases
uvicorn app.main:app --reload # start FastAPI on :8000
```

### 2. Frontend UI

```bash
cd web && python -m http.server 1841   # launch Ext JS on :1841
```
Open `http://localhost:1841` in your browser and click **Run the engine** or navigate the student roster and verification lists.

### 3. CLI Reports & Verification

```bash
python report.py trace 9A-031     # inspect one student's full calculation trace
python report.py trace --edges    # run every seeded edge case
python report.py checklist        # generate the office verification list
pytest tests -q                   # run the automated rule test suite
```

### 4. Running the Organizers' Public Test Fixture

```bash
python harness.py P08_school_results_public.json
python harness.py P08_school_results_public.json --out results.json
```

---

## The Rule Book

Grade points derived from combined 0–100 mark:

| Mark Range | Letter Grade | Grade Point |
|---|---|---|
| 80 – 100 | A+ | 5.0 |
| 70 – 79 | A | 4.0 |
| 60 – 69 | A- | 3.5 |
| 50 – 59 | B | 3.0 |
| 40 – 49 | C | 2.0 |
| 33 – 39 | D | 1.0 |
| 0 – 32 | F | 0.0 |

### Subject Rules (Order of Evaluation)
- `R1_ABSENT`: Absent in any component $\rightarrow$ Fail (F / 0.0), no mark recorded.
- `R2_THEORY_FAIL`: Theory mark below theory pass line in split subject $\rightarrow$ Fail (F / 0.0).
- `R3_PRACTICAL_FAIL`: Practical mark below practical pass line in split subject $\rightarrow$ Fail (F / 0.0).
- `R4_TOTAL_FAIL`: Combined total mark below 33 $\rightarrow$ Fail (F / 0.0).
- `R5_BAND`: Normal lookup according to grade band table.

### Student Rules
- `G1_COMPULSORY_FAIL`: Any compulsory subject failed $\rightarrow$ GPA 0.00, Grade F.
- `G2_AVERAGE`: Sum of 6 compulsory subject grade points divided by 6.
- `G3_OPTIONAL_APPLIED`: Optional subject grade point > 2.00 $\rightarrow$ excess $(GP - 2.00)$ added to total points.
- `G4_OPTIONAL_IGNORED`: Optional subject grade point $\le$ 2.00 $\rightarrow$ adds 0.00, cannot fail student.
- `G5_CAPPED`: Total GPA capped at 5.00.

---

## Project Layout

```
app/rules.py        Pure Python grading engine (zero DB/framework dependencies)
app/models.py       SQLAlchemy ORM models
app/services.py     Database-to-engine mapping & checking list generators
app/main.py         FastAPI REST API endpoints
seed/seed_data.py   Fixed-seed database generator (73 students, 13 edge cases)
tests/test_rules.py Pytest suite covering all grading rules and edge cases
report.py           Terminal CLI reporting tool for traces and checklists
harness.py          Public test fixture batch processor
web/                Ext JS front-end web dashboard
alembic/            Database migrations
```
