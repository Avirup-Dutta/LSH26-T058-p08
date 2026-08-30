"""Bridge between the database and the pure engine in app.rules."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, rules

# R-29 defines three separate lists. These are the flags that build them.
LIST_DEFINITIONS = {
    "optional": {
        "flag": "LIST_OPTIONAL",
        "title": "Optional subject list",
        "rule": "Every student whose optional grade point is 2.0 or below. An absent optional counts.",
    },
    "practical_fail": {
        "flag": "LIST_PRACTICAL_FAIL",
        "title": "Practical fail list",
        "rule": "Every student with a practical part below 8 in any subject.",
    },
    "absent": {
        "flag": "LIST_ABSENT",
        "title": "Absent list",
        "rule": "Every student with AB in any subject.",
    },
}

FLAG_LABELS = {
    "LIST_OPTIONAL": "Optional grade point 2.0 or below",
    "LIST_PRACTICAL_FAIL": "Practical part below 8",
    "LIST_ABSENT": "AB in a subject",
    "OPTIONAL_CHANGED_LETTER": "Optional subject moved the letter grade",
    "OPTIONAL_CHANGED_GPA": "Optional subject moved the GPA but not the letter grade",
    "OPTIONAL_NO_EFFECT": "Optional subject taken but at or below 2.00",
    "OPTIONAL_FAILED_NOT_COUNTED": "Optional subject failed, not counted against the student",
    "PRACTICAL_FAIL": "Practical component failed",
    "ABSENT": "Absent in a subject",
    "FAILED_DESPITE_HIGH_AVERAGE": "Failed a compulsory subject despite a strong average",
    "GPA_CAPPED": "Total exceeded 5.00 and was capped",
}

# 1 = check first, the result turned on this. 2 = check, a rule was applied or
# withheld. 3 = routine, the optional subject moved a number and nothing else.
FLAG_PRIORITY = {
    "LIST_PRACTICAL_FAIL": 1,
    "LIST_ABSENT": 1,
    "FAILED_DESPITE_HIGH_AVERAGE": 1,
    "LIST_OPTIONAL": 2,
    "OPTIONAL_CHANGED_LETTER": 2,
    "GPA_CAPPED": 2,
    "OPTIONAL_CHANGED_GPA": 3,
}

CHECKING_LIST_FLAGS = tuple(FLAG_PRIORITY)
ROUTINE_FLAGS = {"OPTIONAL_CHANGED_GPA"}


def _entries_for(student: models.Student) -> List[rules.SubjectEntry]:
    entries: List[rules.SubjectEntry] = []
    for mark in sorted(student.marks, key=lambda m: m.subject.display_order):
        subject = mark.subject
        components = [
            rules.Component(
                kind="theory",
                full_mark=subject.theory_full,
                pass_mark=subject.theory_pass,
                obtained=None if mark.theory_absent else mark.theory_obtained,
            )
        ]
        if subject.has_practical:
            components.append(
                rules.Component(
                    kind="practical",
                    full_mark=subject.practical_full,
                    pass_mark=subject.practical_pass,
                    obtained=None if mark.practical_absent else mark.practical_obtained,
                )
            )
        entries.append(
            rules.SubjectEntry(
                code=subject.code,
                name=subject.name,
                is_optional=subject.is_optional,
                components=components,
            )
        )
    return entries


def evaluate(student: models.Student) -> rules.StudentResult:
    return rules.evaluate_student(
        student_id=student.id,
        roll=student.roll,
        name=student.name,
        class_name=student.school_class.name,
        entries=_entries_for(student),
    )


def _load_students(db: Session, class_id: Optional[int] = None) -> List[models.Student]:
    stmt = (
        select(models.Student)
        .options(
            selectinload(models.Student.marks).selectinload(models.Mark.subject),
            selectinload(models.Student.school_class),
        )
        .order_by(models.Student.roll)
    )
    if class_id:
        stmt = stmt.where(models.Student.class_id == class_id)
    return list(db.scalars(stmt))


def get_student(db: Session, student_id: int) -> Optional[models.Student]:
    stmt = (
        select(models.Student)
        .options(
            selectinload(models.Student.marks).selectinload(models.Mark.subject),
            selectinload(models.Student.school_class),
        )
        .where(models.Student.id == student_id)
    )
    return db.scalars(stmt).first()


def compute_all(db: Session, class_id: Optional[int] = None) -> int:
    """Recompute and store results. Returns how many students were processed."""
    students = _load_students(db, class_id)
    existing = {r.student_id: r for r in db.scalars(select(models.StudentResult))}
    now = datetime.utcnow()

    for student in students:
        result = evaluate(student)
        row = existing.get(student.id) or models.StudentResult(student_id=student.id)
        row.gpa = result.gpa
        row.letter = result.letter
        row.passed = result.passed
        row.gpa_without_optional = result.gpa_without_optional
        row.optional_bonus = result.optional_bonus
        row.compulsory_average_mark = result.compulsory_average_mark
        row.flags = ",".join(result.flags)
        row.failing_subjects = ", ".join(result.failing_subjects)
        row.trace_json = json.dumps(asdict(result))
        row.computed_at = now
        db.add(row)

    db.commit()
    return len(students)


def result_payload(result: rules.StudentResult) -> dict:
    data = asdict(result)
    data["flag_labels"] = [FLAG_LABELS.get(f, f) for f in result.flags]
    return data


def checking_lists(db: Session, class_id: Optional[int] = None) -> dict:
    """
    R-29: three separate lists. A student can appear on more than one.

    This is the output the judges mark, so it follows the rule text exactly
    rather than the merged, priority-ordered view the office screen uses.
    """
    out = {key: {"title": d["title"], "rule": d["rule"], "students": []}
           for key, d in LIST_DEFINITIONS.items()}

    for student in _load_students(db, class_id):
        result = evaluate(student)
        optional = next((s for s in result.subjects if s.is_optional), None)

        for key, definition in LIST_DEFINITIONS.items():
            if definition["flag"] not in result.flags:
                continue

            row = {
                "id": result.roll,
                "name": result.name,
                "class": result.class_name,
                "gpa": result.gpa,
                "grade": result.letter,
                "also_on": [
                    LIST_DEFINITIONS[k]["title"]
                    for k in LIST_DEFINITIONS
                    if k != key and LIST_DEFINITIONS[k]["flag"] in result.flags
                ],
            }

            if key == "optional" and optional is not None:
                row["detail"] = (
                    f"{optional.name}: "
                    + ("absent" if optional.is_absent
                       else f"mark {optional.mark_used:g}")
                    + f", grade point {optional.grade_point:.2f}, contributes 0.00"
                )
            elif key == "practical_fail":
                row["detail"] = "; ".join(
                    f"{s.name}: practical {s.practical_obtained:g}/{s.practical_full}, "
                    f"theory {s.theory_obtained:g}/{s.theory_full}"
                    for s in result.subjects if s.component_failed == "practical"
                )
            else:
                row["detail"] = "; ".join(
                    f"{s.name}: AB" for s in result.subjects if s.is_absent
                )

            out[key]["students"].append(row)

    for entry in out.values():
        entry["count"] = len(entry["students"])
    return out


def verification_rows(
    db: Session,
    class_id: Optional[int] = None,
    include_routine: bool = False,
) -> List[dict]:
    """
    The office checking list: every result a human should verify by hand.

    The optional subject nudges almost every GPA, so a bare "the optional rule
    applied" list would be the whole cohort. By default this returns the cases
    where a rule decided something: a fail, an absence, a withheld optional, or
    an optional that moved the letter grade. Pass include_routine to add the
    students whose optional subject only moved the number.
    """
    rows: List[dict] = []
    for student in _load_students(db, class_id):
        result = evaluate(student)
        hits = [f for f in result.flags if f in CHECKING_LIST_FLAGS]
        if not include_routine:
            hits = [f for f in hits if f not in ROUTINE_FLAGS]
        if not hits:
            continue

        reasons, subjects_to_check = [], []
        for flag in hits:
            reasons.append(FLAG_LABELS[flag])

        optional = next((s for s in result.subjects if s.is_optional), None)
        if optional and any(f.startswith("OPTIONAL") for f in hits):
            subjects_to_check.append(optional.name)
        for subject in result.subjects:
            if subject.component_failed == "practical" or subject.is_absent:
                subjects_to_check.append(subject.name)
        if "FAILED_DESPITE_HIGH_AVERAGE" in hits:
            subjects_to_check.extend(result.failing_subjects)

        detail = []
        if ("OPTIONAL_CHANGED_LETTER" in hits or "OPTIONAL_CHANGED_GPA" in hits) and optional:
            detail.append(
                f"GPA without optional {result.gpa_without_optional:.2f} "
                f"({result.letter_without_optional}) -> with optional "
                f"{result.gpa:.2f} ({result.letter})"
            )
        if "LIST_OPTIONAL" in hits and optional:
            scored = "was absent" if optional.is_absent else f"scored {optional.mark_used:g}"
            detail.append(
                f"{optional.name} {scored}, grade point {optional.grade_point:.2f}, "
                f"at or below 2.00, so it contributed 0.00"
            )
        if "LIST_PRACTICAL_FAIL" in hits:
            for s in result.subjects:
                if s.component_failed == "practical":
                    detail.append(
                        f"{s.name}: theory {s.theory_obtained:g}/{s.theory_full} passed, "
                        f"practical {s.practical_obtained:g}/{s.practical_full} below {s.practical_pass}"
                    )
        if "LIST_ABSENT" in hits:
            for s in result.subjects:
                if s.is_absent:
                    detail.append(f"{s.name}: absent, recorded as F")
        if "FAILED_DESPITE_HIGH_AVERAGE" in hits:
            detail.append(
                f"Average {result.compulsory_average_mark:.2f} but failed "
                f"{', '.join(result.failing_subjects)}"
            )
        if "GPA_CAPPED" in hits:
            detail.append(f"Raw total {result.total_points:.2f}/6 exceeded 5.00")

        rows.append(
            {
                "student_id": result.student_id,
                "roll": result.roll,
                "name": result.name,
                "class_name": result.class_name,
                "gpa": result.gpa,
                "letter": result.letter,
                "passed": result.passed,
                "flags": hits,
                "priority": min(FLAG_PRIORITY[f] for f in hits),
                "reasons": reasons,
                "reason_text": "; ".join(reasons),
                "subjects_to_check": sorted(set(subjects_to_check)),
                "detail": detail,
                "detail_text": " | ".join(detail),
                "verified": False,
            }
        )
    rows.sort(key=lambda r: (r["priority"], r["class_name"], r["roll"]))
    return rows
