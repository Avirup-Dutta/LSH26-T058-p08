# School Result Processing and GPA Engine

Python REST API (FastAPI) + Ext JS front end. Six compulsory subjects and one
optional fourth subject per student, separate theory and practical marks where a
subject has a practical part, and a per-subject trace showing which rule decided
what.

---

## Your stack questions, answered first

**Do you need Supabase? No.**

Supabase is hosted Postgres with some extras bolted on: auth, storage, row level
security, an auto-generated REST layer. You already decided to write your own
REST layer in Python, so the auto-generated one is dead weight. What is left is
"a Postgres you did not have to install", which is worth something if you have no
server, and worth nothing if you already have one.

This project runs on plain `DATABASE_URL`. Point it at anything:

```bash
# local docker
DATABASE_URL=postgresql+psycopg://postgres:pass@localhost:5432/results

# supabase, if you want it - it is just Postgres
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<pass>@aws-0-<region>.pooler.supabase.com:6543/postgres

# no database at all, for trying the engine out
DATABASE_URL=sqlite:///./results.db
```

Nothing above the connection string changes. If you do use Supabase, use the
**session pooler** port (6543) rather than 5432, keep the service key on the
server, and do not enable row level security on these tables unless you also plan
to move authentication into Supabase. Two auth systems fighting over one database
is the usual way this goes wrong.

One thing that genuinely argues for Supabase on a school project: you get a
managed database, backups, and a web SQL editor without running a server. One
thing that argues against it: marks are the kind of data an examination board
will ask you where it physically lives.

**Do you still write migrations? Yes, either way.**

Supabase does not replace migrations. It has its own migration tooling, but if
your models live in SQLAlchemy then Alembic is the tool that reads them. This
repo has Alembic set up and one migration in `alembic/versions/`. The Supabase
dashboard's table editor is a trap here: change a column there and your Alembic
history no longer describes your database.

```bash
alembic upgrade head                                    # apply
alembic revision --autogenerate -m "add exam term"      # after editing models.py
```

**Ext JS notes.** The API returns `{"success": true, "total": n, "data": [...]}`
on every endpoint because that is the shape `Ext.data.Store` expects with
`rootProperty: 'data'` and `totalProperty: 'total'`. CORS origins are set in
`.env`. Ext JS is served as static files from `web/`, not from FastAPI, so the
two run on different ports in development.

---

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env

alembic upgrade head          # create the schema
python -m seed.seed_data      # 2 classes, 73 students, 13 edge cases
uvicorn app.main:app --reload # API on :8000

cd web && python -m http.server 1841   # Ext JS on :1841
```

Then press **Run the engine**, or hit `POST /api/results/compute`.

Without a browser:

```bash
python report.py trace 9A-031     # one student's full trace
python report.py trace --edges    # every seeded edge case
python report.py checklist        # the office verification list
pytest tests -q                   # 13 tests, one per rule
```

---

## The rules the engine runs

Grade points come from the combined 0-100 mark:

| Mark | 80+ | 70-79 | 60-69 | 50-59 | 40-49 | 33-39 | 0-32 |
|---|---|---|---|---|---|---|---|
| Grade | A+ | A | A- | B | C | D | F |
| Point | 5.0 | 4.0 | 3.5 | 3.0 | 2.0 | 1.0 | 0.0 |

Subject rules, in the order they are applied. The first one that matches wins,
and its code goes into the trace.

| Code | Rule |
|---|---|
| `R1_ABSENT` | Absent in any component. Fail, no mark recorded. |
| `R2_THEORY_FAIL` | Theory below its own pass mark, in a split subject. Fail even if the combined mark passes. |
| `R3_PRACTICAL_FAIL` | Practical below its own pass mark. Same. |
| `R4_TOTAL_FAIL` | Combined mark below 33. |
| `R5_BAND` | Normal band lookup. |

Student rules:

| Code | Rule |
|---|---|
| `G1_COMPULSORY_FAIL` | Any compulsory subject failed, so GPA is 0.00 and the grade is F, whatever the average was. |
| `G2_AVERAGE` | Sum of the six compulsory grade points, divided by six. |
| `G3_OPTIONAL_APPLIED` | Optional grade point above 2.00. The excess is added to the total. |
| `G4_OPTIONAL_IGNORED` | Optional grade point at or below 2.00. Adds nothing, and cannot fail the student. |
| `G5_CAPPED` | Total over 5.00 is capped at 5.00. |

All of it is constants at the top of `app/rules.py`. Change the bands, the
optional threshold, or the divisor, and the engine and its trace follow.

---

## Where the four required items live

| Item | Where |
|---|---|
| 1. 60+ students, two classes, edge cases | `seed/seed_data.py` - 73 students, 13 hand-built edges |
| 2. Grade point, GPA, letter grade | `app/rules.py`, exposed at `POST /api/results/compute` |
| 3. Per student trace | `GET /api/students/{id}/result`, the trace tab in the UI, `report.py trace` |
| 4. Office checking list | `GET /api/reports/verification`, `.csv` for print, `report.py checklist` |

### The 13 edge cases

Every one is marked with a note on the student record and shows as `edge case`
in the grid.

1. One failed subject with a strong average - average 70.83, Mathematics 30, result F
2. Practical fail with a passing theory mark - Physics 58/75 theory, 5/25 practical
3. Theory fail with a strong practical - Biology combined 46, theory 22/75
4. Optional subject below the point where it helps - Higher Maths 45, a 2.00
5. Optional exactly on the boundary - 49, still a 2.00
6. Optional one mark past it - 50, a 3.00, carries 1.00
7. Absent in a compulsory subject - Chemistry theory not sat
8. Absent in the optional subject only - student still passes
9. Optional subject failed outright - does not pull the student down
10. Optional moves the letter grade from A- to A
11. Total exceeds 5.00 and is capped
12. Every boundary sat on exactly - Mathematics 33, Physics practical 8
13. One mark under the line with an ordinary average - Mathematics 32

### The checking list

The optional subject nudges nearly every GPA, so a list of "the optional rule
applied" would be the whole cohort and nobody would read it. The list is graded
instead:

- **Priority 1** - the result turned on this. A practical fail, an absence, or a
  fail behind a strong average.
- **Priority 2** - a rule applied or was withheld. The optional subject moved the
  letter grade, or was ignored, or was failed, or the total was capped.
- **Priority 3** - routine. The optional subject moved the number and nothing
  else. Hidden by default; the checkbox in the toolbar brings it back.

Each row names the student, the reason, the subjects to check, what to verify,
and leaves a blank column for the teacher's signature. `verification.csv`
prints on one page per class.

---

## Layout

```
app/rules.py        the engine. pure python, no db, no framework
app/models.py       tables
app/services.py     db rows -> engine inputs, results -> checking list
app/main.py         REST API
seed/seed_data.py   fixed-seed data with the 13 edge cases
tests/test_rules.py one test per rule
report.py           terminal output for the trace and the checking list
web/                Ext JS front end
alembic/            migrations
```

`app/rules.py` has no imports from the rest of the project. That is deliberate:
when a teacher disputes a grade, the argument is about one file, and that file
can be tested without a database.
