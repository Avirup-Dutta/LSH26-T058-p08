"""
Seed the database.

Two classes, 73 students, seven subjects each: six compulsory plus one optional
fourth subject. Thirteen students are hand-built to land on a hard edge; the
rest are generated from a fixed seed, so every run produces the same data.

Run:  python -m seed.seed_data
"""

from __future__ import annotations

import random
from typing import Optional

from sqlalchemy import delete, select

from app.db import Base, SessionLocal, engine
from app.models import Mark, SchoolClass, Student, StudentResult, Subject

RNG = random.Random(20260830)

# code, name, optional?, practical?, theory full/pass, practical full/pass, order
SUBJECTS = [
    ("BAN", "Bangla", False, False, 100, 33, 0, 0, 1),
    ("ENG", "English", False, False, 100, 33, 0, 0, 2),
    ("MATH", "Mathematics", False, False, 100, 33, 0, 0, 3),
    ("PHY", "Physics", False, True, 75, 25, 25, 8, 4),
    ("CHEM", "Chemistry", False, True, 75, 25, 25, 8, 5),
    ("BIO", "Biology", False, True, 75, 25, 25, 8, 6),
    ("HMATH", "Higher Mathematics", True, True, 75, 25, 25, 8, 7),
]

FIRST = [
    "Arif", "Nusrat", "Tanvir", "Sadia", "Rakib", "Mim", "Shakil", "Farhana",
    "Imran", "Tasnim", "Sabbir", "Jannat", "Rifat", "Sumaiya", "Hasan", "Nadia",
    "Mahmud", "Anika", "Fahim", "Rumana", "Zahid", "Israt", "Naimul", "Lamia",
    "Sohel", "Sharmin", "Abir", "Tanjila", "Rasel", "Meherun",
]
LAST = [
    "Hossain", "Akter", "Rahman", "Islam", "Chowdhury", "Karim", "Sultana",
    "Mia", "Begum", "Uddin", "Alam", "Siddique", "Haque", "Nahar", "Bhuiyan",
]

# One entry per subject code. Use "ABSENT" for a missing paper.
# Non-practical: a single number. Practical: a (theory, practical) pair.
EDGE_CASES = [
    (
        "One failed subject with a strong average. Average is over 70 but Mathematics is 30.",
        {"BAN": 85, "ENG": 82, "MATH": 30, "PHY": (58, 22), "CHEM": (56, 20),
         "BIO": (54, 18), "HMATH": (55, 18)},
    ),
    (
        "Practical fail with a passing theory mark. Physics theory 58 of 75 passes, practical 5 of 25 does not.",
        {"BAN": 72, "ENG": 68, "MATH": 71, "PHY": (58, 5), "CHEM": (55, 19),
         "BIO": (52, 17), "HMATH": (50, 16)},
    ),
    (
        "Theory fail with a strong practical. Biology combined mark is 46 but the theory paper is below 25.",
        {"BAN": 66, "ENG": 63, "MATH": 60, "PHY": (50, 18), "CHEM": (48, 17),
         "BIO": (22, 24), "HMATH": (52, 17)},
    ),
    (
        "Optional subject below the point where it helps. Higher Mathematics totals 45, a 2.00, so it adds nothing.",
        {"BAN": 63, "ENG": 58, "MATH": 61, "PHY": (46, 15), "CHEM": (44, 14),
         "BIO": (45, 15), "HMATH": (32, 13)},
    ),
    (
        "Optional subject exactly on the boundary. Higher Mathematics totals 49, still a 2.00, still no effect.",
        {"BAN": 59, "ENG": 55, "MATH": 57, "PHY": (44, 14), "CHEM": (43, 13),
         "BIO": (42, 14), "HMATH": (36, 13)},
    ),
    (
        "Optional subject one mark past the boundary. Higher Mathematics totals 50, a 3.00, so 1.00 carries over.",
        {"BAN": 59, "ENG": 55, "MATH": 57, "PHY": (44, 14), "CHEM": (43, 13),
         "BIO": (42, 14), "HMATH": (37, 13)},
    ),
    (
        "Absent in one compulsory subject. Chemistry theory paper was not sat.",
        {"BAN": 78, "ENG": 74, "MATH": 76, "PHY": (60, 21), "CHEM": ("ABSENT", 20),
         "BIO": (58, 20), "HMATH": (57, 19)},
    ),
    (
        "Absent in the optional subject only. The student still passes on the six compulsory subjects.",
        {"BAN": 71, "ENG": 69, "MATH": 73, "PHY": (55, 19), "CHEM": (54, 18),
         "BIO": (53, 18), "HMATH": (50, "ABSENT")},
    ),
    (
        "Optional subject failed outright. It must not pull the student down.",
        {"BAN": 70, "ENG": 66, "MATH": 68, "PHY": (52, 18), "CHEM": (50, 17),
         "BIO": (51, 17), "HMATH": (18, 7)},
    ),
    (
        "Optional subject moves the letter grade from A- to A.",
        {"BAN": 74, "ENG": 72, "MATH": 71, "PHY": (55, 18), "CHEM": (54, 17),
         "BIO": (48, 15), "HMATH": (63, 22)},
    ),
    (
        "Total would exceed 5.00 and is capped. Every subject is A+, including the optional.",
        {"BAN": 92, "ENG": 88, "MATH": 95, "PHY": (68, 23), "CHEM": (66, 22),
         "BIO": (67, 22), "HMATH": (69, 23)},
    ),
    (
        "Every boundary sat on exactly. Mathematics is 33, the Physics practical is 8.",
        {"BAN": 50, "ENG": 40, "MATH": 33, "PHY": (25, 8), "CHEM": (47, 13),
         "BIO": (46, 14), "HMATH": (45, 15)},
    ),
    (
        "One mark under the line with an ordinary average. Mathematics is 32, so the result is F.",
        {"BAN": 55, "ENG": 48, "MATH": 32, "PHY": (40, 12), "CHEM": (38, 11),
         "BIO": (39, 12), "HMATH": (40, 13)},
    ),
]


def _random_marks() -> dict:
    marks = {}
    for code, _n, _o, has_practical, t_full, _tp, p_full, _pp, _ord in SUBJECTS:
        if has_practical:
            theory = min(t_full, max(10, round(RNG.gauss(47, 11))))
            practical = min(p_full, max(4, round(RNG.gauss(18, 4))))
            marks[code] = (theory, practical)
        else:
            marks[code] = min(99, max(15, round(RNG.gauss(64, 16))))
    return marks


def _add_marks(db, student: Student, subjects: dict, marks: dict) -> None:
    for code, value in marks.items():
        subject = subjects[code]
        theory: Optional[float]
        practical: Optional[float]
        theory_absent = practical_absent = False

        if isinstance(value, tuple):
            raw_theory, raw_practical = value
        else:
            raw_theory, raw_practical = value, None

        if raw_theory == "ABSENT":
            theory, theory_absent = None, True
        else:
            theory = float(raw_theory)

        if raw_practical == "ABSENT":
            practical, practical_absent = None, True
        elif raw_practical is None:
            practical = None
        else:
            practical = float(raw_practical)

        db.add(
            Mark(
                student=student,
                subject_id=subject.id,
                theory_obtained=theory,
                practical_obtained=practical,
                theory_absent=theory_absent,
                practical_absent=practical_absent,
            )
        )


def run() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()

    db.execute(delete(StudentResult))
    db.execute(delete(Mark))
    db.execute(delete(Student))
    db.execute(delete(SchoolClass))
    db.execute(delete(Subject))
    db.commit()

    for code, name, optional, practical, tf, tp, pf, pp, order in SUBJECTS:
        db.add(
            Subject(
                code=code, name=name, is_optional=optional, has_practical=practical,
                theory_full=tf, theory_pass=tp, practical_full=pf, practical_pass=pp,
                display_order=order,
            )
        )
    db.commit()
    subjects = {s.code: s for s in db.scalars(select(Subject))}

    class_nine = SchoolClass(name="Class 9 - Section A", session_year="2026")
    class_ten = SchoolClass(name="Class 10 - Section B", session_year="2026")
    db.add_all([class_nine, class_ten])
    db.commit()

    counters = {class_nine.id: 0, class_ten.id: 0}
    prefixes = {class_nine.id: "9A", class_ten.id: "10B"}

    def new_student(school_class: SchoolClass, note: Optional[str] = None) -> Student:
        counters[school_class.id] += 1
        roll = f"{prefixes[school_class.id]}-{counters[school_class.id]:03d}"
        student = Student(
            roll=roll,
            name=f"{RNG.choice(FIRST)} {RNG.choice(LAST)}",
            class_id=school_class.id,
            note=note,
        )
        db.add(student)
        db.flush()
        return student

    # 30 generated students per class
    for school_class in (class_nine, class_ten):
        for _ in range(30):
            student = new_student(school_class)
            _add_marks(db, student, subjects, _random_marks())

    # 13 hand-built edge cases, split across the two classes
    for index, (note, marks) in enumerate(EDGE_CASES):
        school_class = class_nine if index % 2 == 0 else class_ten
        student = new_student(school_class, note=f"EDGE CASE: {note}")
        _add_marks(db, student, subjects, marks)

    db.commit()
    total = len(list(db.scalars(select(Student))))
    print(f"Seeded 2 classes, 7 subjects, {total} students ({len(EDGE_CASES)} edge cases).")
    db.close()


if __name__ == "__main__":
    run()
