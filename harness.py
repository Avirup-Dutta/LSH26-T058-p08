"""
Run the engine over the organisers' test file.

    python harness.py P08_school_results_public.json
    python harness.py P08_school_results_public.json --out results.json
    python harness.py P08_school_results_public.json --case PUB-01 --trace S003

The file carries no expected answers, so this cannot tell you that you match
their reference. What it can do is run every student through the same engine the
API uses, report the shape of the results, and flag anything the engine could not
interpret.

Mapping notes:
  - Subject codes differ from the seed data (MAT not MATH, CHE not CHEM). Codes
    are read from each case's own "subjects" list, so nothing is hardcoded.
  - "optional" names the student's fourth subject and varies per student
    (HMT, AGR or REL). REL has no practical part.
  - "AB" replaces a whole subject's marks and means absent in that subject.
  - Practical subjects are theory out of THEORY_FULL and practical out of
    PRACTICAL_FULL. Their pass marks are the two constants below.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict

from app import rules

# ---------------------------------------------------------------------------
# Component pass marks.
#
# The organisers' format note gives the mark ranges but not the pass marks, so
# these come from the usual board convention: 33 per cent of each component,
# 24.75 rounded to 25 and 8.25 rounded down to 8. If the problem statement names
# different numbers, change them here and rerun. PRACTICAL_PASS is the one worth
# checking: 8 and 9 are both defensible roundings of 8.25 and they disagree for
# any student who scored exactly 8.
# ---------------------------------------------------------------------------
THEORY_FULL, THEORY_PASS = 75, 25
PRACTICAL_FULL, PRACTICAL_PASS = 25, 8
WHOLE_FULL, WHOLE_PASS = 100, 33

ABSENT = "AB"


def build_entries(case: dict, student: dict) -> list:
    """Turn one student's marks into engine input, using the case's own subjects."""
    by_code = {s["code"]: s for s in case["subjects"]}
    compulsory = case["compulsory"]
    optional_code = student["optional"]
    entries = []

    for code in list(compulsory) + [optional_code]:
        subject = by_code[code]
        value = student["marks"][code]
        absent = value == ABSENT

        if subject["practical"]:
            theory = None if absent else value["theory"]
            practical = None if absent else value["practical"]
            components = [
                rules.Component("theory", THEORY_FULL, THEORY_PASS, theory),
                rules.Component("practical", PRACTICAL_FULL, PRACTICAL_PASS, practical),
            ]
        else:
            components = [
                rules.Component("theory", WHOLE_FULL, WHOLE_PASS, None if absent else value)
            ]

        entries.append(
            rules.SubjectEntry(
                code=code,
                name=subject["name"],
                is_optional=(code == optional_code),
                components=components,
            )
        )
    return entries


def run_case(case: dict) -> list:
    results = []
    for index, student in enumerate(case["students"], start=1):
        results.append(
            rules.evaluate_student(
                student_id=index,
                roll=student["id"],
                name=student["name"],
                class_name=student["class"],
                entries=build_entries(case, student),
            )
        )
    return results


LIST_SPECS = [
    ("optional", "LIST_OPTIONAL",
     "optional grade point 2.0 or below, an absent optional counts"),
    ("practical_fail", "LIST_PRACTICAL_FAIL",
     "a practical part below 8 in any subject"),
    ("absent", "LIST_ABSENT", "AB in any subject"),
]


def checking_lists(results) -> dict:
    """R-29: three separate lists, a student may appear on more than one."""
    out = {}
    for key, flag, rule in LIST_SPECS:
        out[key] = {
            "rule": rule,
            "students": [
                {"id": r.roll, "name": r.name, "class": r.class_name,
                 "gpa": round(r.gpa, 2), "grade": r.letter}
                for r in results if flag in r.flags
            ],
        }
        out[key]["count"] = len(out[key]["students"])
    return out


def compact(result) -> dict:
    """One student's answer, trace included."""
    return {
        "id": result.roll,
        "name": result.name,
        "class": result.class_name,
        "gpa": round(result.gpa, 2),
        "grade": result.letter,
        "passed": result.passed,
        "uncancelled_gpa": round(result.uncancelled_gpa, 2),
        "uncancelled_grade": result.uncancelled_letter,
        "gpa_without_optional": round(result.gpa_without_optional, 2),
        "optional_bonus": result.optional_bonus,
        "failing_subjects": result.failing_subjects,
        "flags": result.flags,
        "subjects": [
            {
                "code": s.code,
                "mark_used": s.mark_used,
                "grade_point": s.grade_point,
                "grade": s.letter,
                "rule": s.rule_code,
            }
            for s in result.subjects
        ],
    }


def main() -> None:
    global THEORY_PASS, PRACTICAL_PASS
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", help="write full results to this JSON file")
    ap.add_argument("--case", help="only this case id")
    ap.add_argument("--trace", help="print one student's full trace, needs --case")
    ap.add_argument("--theory-pass", type=int, default=25,
                    help="theory pass mark out of 75 (default 25)")
    ap.add_argument("--practical-pass", type=int, default=8,
                    help="practical pass mark out of 25 (default 8)")
    args = ap.parse_args()

    THEORY_PASS, PRACTICAL_PASS = args.theory_pass, args.practical_pass

    with open(args.path, encoding="utf-8") as fh:
        data = json.load(fh)

    cases = data["cases"]
    if args.case:
        cases = [c for c in cases if c["case_id"] == args.case]
        if not cases:
            sys.exit(f"No case {args.case}")

    print(f"\n{data['problem_id']}  schema {data['schema_version']}  "
          f"{len(cases)} case(s)")
    print(f"pass marks in use: theory {THEORY_PASS}/{THEORY_FULL}, "
          f"practical {PRACTICAL_PASS}/{PRACTICAL_FULL}, "
          f"whole subject {WHOLE_PASS}/{WHOLE_FULL}\n")

    output, totals = {}, Counter()
    print(f"{'case':<9}{'students':>9}{'passed':>8}{'failed':>8}"
          f"{'mean GPA':>10}{'A+':>5}{'opt':>6}{'prac':>6}{'abs':>5}")
    print("-" * 64)

    for case in cases:
        results = run_case(case)
        output[case["case_id"]] = {
            "students": [compact(r) for r in results],
            "checking_lists": checking_lists(results),
        }

        passed = [r for r in results if r.passed]
        mean = sum(r.gpa for r in passed) / len(passed) if passed else 0.0
        lists = checking_lists(results)
        aplus = sum(1 for r in results if r.letter == "A+")

        print(f"{case['case_id']:<9}{len(results):>9}{len(passed):>8}"
              f"{len(results) - len(passed):>8}{mean:>10.2f}{aplus:>5}"
              f"{lists['optional']['count']:>6}{lists['practical_fail']['count']:>6}"
              f"{lists['absent']['count']:>5}")
        for key in ("optional", "practical_fail", "absent"):
            totals["list:" + key] += lists[key]["count"]

        totals["students"] += len(results)
        totals["passed"] += len(passed)
        for r in results:
            for f in r.flags:
                totals[f] += 1
            for s in r.subjects:
                totals["rule:" + s.rule_code] += 1

    print("-" * 64)
    print(f"{'all':<9}{totals['students']:>9}{totals['passed']:>8}"
          f"{totals['students'] - totals['passed']:>8}{'':>10}{'':>5}"
          f"{totals['list:optional']:>6}{totals['list:practical_fail']:>6}"
          f"{totals['list:absent']:>5}\n")
    print("checking lists (R-29), a student may appear on more than one")
    print(f"  optional grade point 2.0 or below  {totals['list:optional']:>7}")
    print(f"  practical part below 8             {totals['list:practical_fail']:>7}")
    print(f"  AB in any subject                  {totals['list:absent']:>7}\n")

    print("subject rules fired")
    for key in sorted(k for k in totals if k.startswith("rule:")):
        print(f"  {key[5:]:<20}{totals[key]:>7}")

    print("\nstudent flags raised")
    for key in sorted(k for k in totals if k.isupper()):
        print(f"  {key:<32}{totals[key]:>7}")

    if args.trace:
        target = next((s for s in cases[0]["students"] if s["id"] == args.trace), None)
        if target is None:
            sys.exit(f"No student {args.trace} in {cases[0]['case_id']}")
        result = rules.evaluate_student(
            0, target["id"], target["name"], target["class"],
            build_entries(cases[0], target)
        )
        print("\n" + "=" * 78)
        print(json.dumps(compact(result), indent=2))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"problem_id": data["problem_id"], "cases": output}, fh, indent=2)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
