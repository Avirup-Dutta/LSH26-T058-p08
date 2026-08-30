from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, services
from app.config import APP_NAME, CORS_ORIGINS, READ_ONLY
from app.db import get_db
from app.rules import GPA_BANDS, GRADE_BANDS, OPTIONAL_THRESHOLD, RULE_TEXT

app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def envelope(data, total: Optional[int] = None) -> dict:
    """Ext JS stores read {success, total, data}."""
    return {
        "success": True,
        "total": total if total is not None else (len(data) if isinstance(data, list) else 1),
        "data": data,
    }


@app.get("/api/health")
def health():
    return envelope({"status": "ok", "app": APP_NAME, "read_only": READ_ONLY})


@app.get("/api/rules")
def get_rules():
    """The rule book the engine is running, so the office can read it."""
    return envelope(
        {
            "grade_bands": [
                {"min_mark": m, "letter": l, "grade_point": p} for m, l, p in GRADE_BANDS
            ],
            "gpa_bands": [{"min_gpa": g, "letter": l} for g, l in GPA_BANDS],
            "optional_threshold": OPTIONAL_THRESHOLD,
            "rule_text": RULE_TEXT,
        }
    )


@app.get("/api/classes")
def list_classes(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.SchoolClass).order_by(models.SchoolClass.id))
    return envelope(
        [{"id": c.id, "name": c.name, "session_year": c.session_year} for c in rows]
    )


@app.get("/api/subjects")
def list_subjects(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Subject).order_by(models.Subject.display_order))
    return envelope(
        [
            {
                "id": s.id, "code": s.code, "name": s.name,
                "is_optional": s.is_optional, "has_practical": s.has_practical,
                "theory_full": s.theory_full, "theory_pass": s.theory_pass,
                "practical_full": s.practical_full, "practical_pass": s.practical_pass,
            }
            for s in rows
        ]
    )


@app.get("/api/students")
def list_students(
    class_id: Optional[int] = None,
    q: Optional[str] = None,
    start: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(models.Student).order_by(models.Student.roll)
    if class_id:
        stmt = stmt.where(models.Student.class_id == class_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(models.Student.name.ilike(like) | models.Student.roll.ilike(like))

    students = list(db.scalars(stmt))
    total = len(students)
    page = students[start : start + limit]

    stored = {
        r.student_id: r
        for r in db.scalars(
            select(models.StudentResult).where(
                models.StudentResult.student_id.in_([s.id for s in page] or [0])
            )
        )
    }

    data = []
    for s in page:
        r = stored.get(s.id)
        data.append(
            {
                "id": s.id,
                "roll": s.roll,
                "name": s.name,
                "class_id": s.class_id,
                "class_name": s.school_class.name,
                "note": s.note,
                "gpa": r.gpa if r else None,
                "letter": r.letter if r else None,
                "passed": r.passed if r else None,
                "flags": r.flags.split(",") if r and r.flags else [],
                "failing_subjects": r.failing_subjects if r else "",
                "computed": r is not None,
            }
        )
    return envelope(data, total)


@app.get("/api/students/{student_id}/result")
def student_result(student_id: int, db: Session = Depends(get_db)):
    """Item 3: the per student trace."""
    student = services.get_student(db, student_id)
    if student is None:
        raise HTTPException(404, "Student not found")
    return envelope(services.result_payload(services.evaluate(student)))


@app.post("/api/results/compute")
def compute(class_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Item 2: run the engine over everyone and store the snapshot."""
    if READ_ONLY:
        # The deployed database ships already computed and cannot be written to.
        stored = len(list(db.scalars(select(models.StudentResult))))
        return envelope({"processed": stored, "read_only": True})
    count = services.compute_all(db, class_id)
    return envelope({"processed": count, "read_only": False})


@app.get("/api/reports/checking-lists")
def checking_lists(class_id: Optional[int] = None, db: Session = Depends(get_db)):
    """R-29: the three lists exactly as the rules define them."""
    return envelope(services.checking_lists(db, class_id))


@app.get("/api/reports/verification")
def verification(class_id: Optional[int] = None, include_routine: bool = False, db: Session = Depends(get_db)):
    """Item 4: the office checking list."""
    return envelope(services.verification_rows(db, class_id, include_routine))


@app.get("/api/reports/verification.csv")
def verification_csv(class_id: Optional[int] = None, include_routine: bool = False, db: Session = Depends(get_db)):
    rows = services.verification_rows(db, class_id, include_routine)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Priority", "Roll", "Name", "Class", "GPA", "Grade", "Reason", "Subjects to check", "Detail", "Checked by"]
    )
    for r in rows:
        writer.writerow(
            [r["priority"], r["roll"], r["name"], r["class_name"], f"{r['gpa']:.2f}", r["letter"],
             r["reason_text"], ", ".join(r["subjects_to_check"]), r["detail_text"], ""]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="verification-list.csv"'},
    )
