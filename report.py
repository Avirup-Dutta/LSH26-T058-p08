"""
Print the two office-facing outputs without a browser.

  python report.py trace 9A-031      one student's full trace
  python report.py trace --edges     the trace for every seeded edge case
  python report.py checklist         the office verification list
  python report.py checklist --all   ...including routine optional changes
  python report.py lists             the three R-29 lists the judges mark
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app import services
from app.db import SessionLocal
from app.models import Student


def print_trace(result) -> None:
    status = "PASS" if result.passed else "FAIL"
    print("=" * 108)
    print(f"{result.roll}  {result.name}  |  {result.class_name}")
    cancelled = ("" if result.passed else
                 f"   uncancelled average {result.uncancelled_gpa:.2f} "
                 f"({result.uncancelled_letter})")
    print(f"GPA {result.gpa:.2f} ({result.letter})  {status}{cancelled}   "
          f"compulsory average {result.compulsory_average_mark:.2f}   "
          f"GPA without the optional subject {result.gpa_without_optional:.2f}")
    print("-" * 108)
    print(f"{'Subject':<21}{'Theory':>12}{'Practical':>12}{'Mark':>7}{'Pt':>6}{'Gr':>5}  Rule")
    for s in result.subjects:
        theory = "absent" if s.theory_obtained is None and s.is_absent else (
            f"{s.theory_obtained:g}/{s.theory_full}" if s.theory_obtained is not None else "-"
        )
        practical = "-"
        if s.practical_full:
            practical = (
                f"{s.practical_obtained:g}/{s.practical_full}"
                if s.practical_obtained is not None else "absent"
            )
        mark = "-" if s.mark_used is None else f"{s.mark_used:g}"
        name = s.name + (" *" if s.is_optional else "")
        print(f"{name:<21}{theory:>12}{practical:>12}{mark:>7}"
              f"{s.grade_point:>6.2f}{s.letter:>5}  {s.rule_code}")
        print(f"{'':<63}  {s.rule_text}")
    print("-" * 108)
    for code, note in zip(result.gpa_rule_codes, result.gpa_rule_notes):
        print(f"  {code}: {note}")
    if not result.passed:
        print(f"  Result turned on: {', '.join(result.failing_subjects)}.")
    if result.flags:
        print(f"  Flags: {', '.join(result.flags)}")
    print()


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else "checklist"
    db = SessionLocal()

    if command == "trace":
        if "--edges" in args:
            students = list(
                db.scalars(select(Student).where(Student.note.isnot(None)).order_by(Student.roll))
            )
        else:
            roll = args[1]
            students = list(db.scalars(select(Student).where(Student.roll == roll)))
            if not students:
                sys.exit(f"No student with roll {roll}")
        for student in students:
            if student.note:
                print(f"\n>>> {student.note}")
            print_trace(services.evaluate(services.get_student(db, student.id)))

    elif command == "lists":
        lists = services.checking_lists(db)
        for key in ("optional", "practical_fail", "absent"):
            entry = lists[key]
            print(f"\n{entry['title'].upper()}  -  {entry['count']} students")
            print(f"  rule: {entry['rule']}")
            print("  " + "-" * 100)
            for row in entry["students"]:
                also = f"   also on: {', '.join(row['also_on'])}" if row["also_on"] else ""
                print(f"  {row['id']:<9}{row['name']:<22}{row['gpa']:>5.2f} "
                      f"{row['grade']:<3}{row['detail']}{also}")
            if not entry["students"]:
                print("  (none)")
        print()

    elif command == "checklist":
        rows = services.verification_rows(db, include_routine="--all" in args)
        print(f"\nVERIFICATION LIST  -  {len(rows)} students to check by hand\n")
        for row in rows:
            print(f"[P{row['priority']}] {row['roll']:<9}{row['name']:<22}"
                  f"{row['gpa']:>5.2f} {row['letter']:<3} {row['reason_text']}")
            if row["subjects_to_check"]:
                print(f"        subjects: {', '.join(row['subjects_to_check'])}")
            for detail in row["detail"]:
                print(f"        - {detail}")
            print(f"        checked by: ______________________")
        print()

    else:
        sys.exit(__doc__)

    db.close()


if __name__ == "__main__":
    main()
