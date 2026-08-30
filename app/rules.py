"""
Grading engine.

Pure Python. No database, no web framework. Everything in here is a function of
its arguments, so the office can unit-test a rule without standing up a server.

Every decision carries a rule code so the trace can name what decided it.

Board convention implemented (NCTB / Bangladesh secondary style):
  - Six compulsory subjects + one optional ("4th") subject.
  - A subject with a practical part has a separate theory mark and practical
    mark, each with its own pass mark. Both must be passed.
  - The grade point comes from the combined mark, but a failed component
    overrides the combined mark.
  - Absent in a subject is a fail in that subject.
  - Fail in any compulsory subject => GPA 0.00, letter F, whatever the average.
  - Optional subject: only the part of its grade point above 2.00 is added to
    the total. It can lift a result; it can never sink one.
  - GPA = (sum of six compulsory grade points + optional bonus) / 6, capped 5.00.

Change the constants below and the whole engine changes with them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# (minimum mark, letter, grade point) - evaluated top down against a 0-100 mark
GRADE_BANDS: tuple = (
    (80, "A+", 5.0),
    (70, "A", 4.0),
    (60, "A-", 3.5),
    (50, "B", 3.0),
    (40, "C", 2.0),
    (33, "D", 1.0),
    (0, "F", 0.0),
)

# (minimum GPA, letter) - evaluated top down
GPA_BANDS: tuple = (
    (5.00, "A+"),
    (4.00, "A"),
    (3.50, "A-"),
    (3.00, "B"),
    (2.00, "C"),
    (1.00, "D"),
    (0.00, "F"),
)

OPTIONAL_THRESHOLD = 2.0   # only grade points above this count
COMPULSORY_COUNT = 6       # the GPA divisor
MAX_GPA = 5.0
HIGH_AVERAGE_MARK = 60     # "strong average" cut-off for the checking list

RULE_TEXT = {
    "R1_ABSENT": "Absent in a component. Absence is a fail in the subject.",
    "R2_THEORY_FAIL": "Theory mark below the theory pass mark. Subject fails even though the combined mark passes.",
    "R3_PRACTICAL_FAIL": "Practical mark below the practical pass mark. Subject fails even though the combined mark passes.",
    "R4_TOTAL_FAIL": "Combined mark below the subject pass mark.",
    "R5_BAND": "Combined mark falls in the grade band.",
    "G1_COMPULSORY_FAIL": "Fail in a compulsory subject. GPA is 0.00 and the letter grade is F.",
    "G2_AVERAGE": "Sum of the six compulsory grade points divided by six.",
    "G3_OPTIONAL_APPLIED": "Optional subject grade point above 2.00. The excess is added to the total.",
    "G4_OPTIONAL_IGNORED": "Optional subject grade point is 2.00 or below. It adds nothing and it cannot fail the student.",
    "G5_CAPPED": "Total would exceed 5.00. GPA capped at 5.00.",
}


def _round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def band_for_mark(mark: float) -> tuple:
    """Return (letter, grade_point) for a 0-100 mark."""
    for minimum, letter, point in GRADE_BANDS:
        if mark >= minimum:
            return letter, point
    return "F", 0.0


def letter_for_gpa(gpa: float) -> str:
    for minimum, letter in GPA_BANDS:
        if gpa >= minimum:
            return letter
    return "F"


# --------------------------------------------------------------------------
# Input shapes
# --------------------------------------------------------------------------

@dataclass
class Component:
    """One examinable part of a subject: theory or practical."""
    kind: str                      # "theory" | "practical"
    full_mark: int
    pass_mark: int
    obtained: Optional[float]      # None means absent

    @property
    def is_absent(self) -> bool:
        return self.obtained is None

    @property
    def is_failed(self) -> bool:
        return self.obtained is not None and self.obtained < self.pass_mark


@dataclass
class SubjectEntry:
    code: str
    name: str
    is_optional: bool
    components: List[Component]

    @property
    def has_practical(self) -> bool:
        return any(c.kind == "practical" for c in self.components)

    def component(self, kind: str) -> Optional[Component]:
        return next((c for c in self.components if c.kind == kind), None)


# --------------------------------------------------------------------------
# Output shapes
# --------------------------------------------------------------------------

@dataclass
class SubjectResult:
    code: str
    name: str
    is_optional: bool
    has_practical: bool
    theory_obtained: Optional[float]
    theory_full: Optional[int]
    theory_pass: Optional[int]
    practical_obtained: Optional[float]
    practical_full: Optional[int]
    practical_pass: Optional[int]
    mark_used: Optional[float]     # combined 0-100 mark, None if absent
    grade_point: float
    letter: str
    passed: bool
    rule_code: str
    rule_text: str
    is_absent: bool = False
    component_failed: Optional[str] = None   # "theory" | "practical" | None


@dataclass
class StudentResult:
    student_id: int
    roll: str
    name: str
    class_name: str
    subjects: List[SubjectResult]
    gpa: float
    letter: str
    passed: bool
    uncancelled_gpa: float          # R-13: what the GPA would have been
    uncancelled_letter: str
    gpa_without_optional: float
    letter_without_optional: str
    optional_bonus: float
    compulsory_average_mark: float
    total_points: float
    gpa_rule_codes: List[str] = field(default_factory=list)
    gpa_rule_notes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    failing_subjects: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Subject level
# --------------------------------------------------------------------------

def evaluate_subject(entry: SubjectEntry) -> SubjectResult:
    theory = entry.component("theory")
    practical = entry.component("practical")

    def out(mark_used, gp, letter, passed, rule, absent=False, comp_failed=None):
        return SubjectResult(
            code=entry.code,
            name=entry.name,
            is_optional=entry.is_optional,
            has_practical=entry.has_practical,
            theory_obtained=theory.obtained if theory else None,
            theory_full=theory.full_mark if theory else None,
            theory_pass=theory.pass_mark if theory else None,
            practical_obtained=practical.obtained if practical else None,
            practical_full=practical.full_mark if practical else None,
            practical_pass=practical.pass_mark if practical else None,
            mark_used=mark_used,
            grade_point=gp,
            letter=letter,
            passed=passed,
            rule_code=rule,
            rule_text=RULE_TEXT[rule],
            is_absent=absent,
            component_failed=comp_failed,
        )

    # R1 - absence beats everything
    if any(c.is_absent for c in entry.components):
        return out(None, 0.0, "F", False, "R1_ABSENT", absent=True)

    total = sum(c.obtained for c in entry.components)

    # R2 / R3 - a failed component beats the combined mark.
    # Only meaningful when the subject is split; a one-paper subject falls to R4.
    if len(entry.components) > 1:
        if theory is not None and theory.is_failed:
            return out(total, 0.0, "F", False, "R2_THEORY_FAIL", comp_failed="theory")
        if practical is not None and practical.is_failed:
            return out(total, 0.0, "F", False, "R3_PRACTICAL_FAIL", comp_failed="practical")

    letter, gp = band_for_mark(total)

    # R4 - combined mark below the pass line
    if gp == 0.0:
        return out(total, 0.0, "F", False, "R4_TOTAL_FAIL")

    # R5 - normal band
    return out(total, gp, letter, True, "R5_BAND")


# --------------------------------------------------------------------------
# Student level
# --------------------------------------------------------------------------

def evaluate_student(
    student_id: int,
    roll: str,
    name: str,
    class_name: str,
    entries: List[SubjectEntry],
) -> StudentResult:
    results = [evaluate_subject(e) for e in entries]
    compulsory = [r for r in results if not r.is_optional]
    optional = next((r for r in results if r.is_optional), None)

    marks = [r.mark_used or 0.0 for r in compulsory]
    average = _round2(sum(marks) / len(marks)) if marks else 0.0

    codes: List[str] = []
    notes: List[str] = []
    flags: List[str] = []

    failing = [r.name for r in compulsory if not r.passed]

    # Bonus is worked out either way, so the trace can show what was forfeited.
    if optional is None:
        bonus = 0.0
    elif optional.grade_point > OPTIONAL_THRESHOLD:
        bonus = _round2(optional.grade_point - OPTIONAL_THRESHOLD)
    else:
        bonus = 0.0

    base_sum = sum(r.grade_point for r in compulsory)
    gpa_wo = min(MAX_GPA, _round2(base_sum / COMPULSORY_COUNT))
    gpa_with = min(MAX_GPA, _round2((base_sum + bonus) / COMPULSORY_COUNT))

    # G1 - one failed compulsory subject ends it
    if failing:
        codes.append("G1_COMPULSORY_FAIL")
        notes.append(
            RULE_TEXT["G1_COMPULSORY_FAIL"] + " Failed: " + ", ".join(failing) + "."
        )
        notes.append(
            f"The uncancelled average stays visible: {gpa_with:.2f} "
            f"({letter_for_gpa(gpa_with)}) before the failure rule cancelled it."
        )
        gpa, gpa_wo_final = 0.0, 0.0
        letter = "F"
        passed = False
    else:
        codes.append("G2_AVERAGE")
        notes.append(RULE_TEXT["G2_AVERAGE"])
        if optional is not None:
            if bonus > 0:
                codes.append("G3_OPTIONAL_APPLIED")
                notes.append(
                    f"{RULE_TEXT['G3_OPTIONAL_APPLIED']} {optional.name}: "
                    f"{optional.grade_point:.2f} - {OPTIONAL_THRESHOLD:.2f} = {bonus:.2f}."
                )
            else:
                codes.append("G4_OPTIONAL_IGNORED")
                notes.append(
                    f"{RULE_TEXT['G4_OPTIONAL_IGNORED']} {optional.name}: "
                    f"{optional.grade_point:.2f}."
                )
        if (base_sum + bonus) / COMPULSORY_COUNT > MAX_GPA:
            codes.append("G5_CAPPED")
            notes.append(RULE_TEXT["G5_CAPPED"])
        gpa, gpa_wo_final = gpa_with, gpa_wo
        letter = letter_for_gpa(gpa)
        passed = True

    letter_wo = letter_for_gpa(gpa_wo_final) if passed else "F"

    # ---- R-29: the three checking lists --------------------------------
    # optional list: optional grade point 2.0 or below, an absent optional counts
    if optional is not None and optional.grade_point <= OPTIONAL_THRESHOLD:
        flags.append("LIST_OPTIONAL")
    # practical fail list: a practical part below its pass mark in any subject
    if any(r.component_failed == "practical" for r in results):
        flags.append("LIST_PRACTICAL_FAIL")
    # absent list: AB in any subject
    if any(r.is_absent for r in results):
        flags.append("LIST_ABSENT")

    # ---- extra detail, not part of the three lists ----------------------
    if optional is not None and passed:
        if bonus > 0 and letter != letter_wo:
            flags.append("OPTIONAL_CHANGED_LETTER")
        elif bonus > 0 and gpa != gpa_wo_final:
            flags.append("OPTIONAL_CHANGED_GPA")
        elif bonus == 0 and optional.passed:
            flags.append("OPTIONAL_NO_EFFECT")
    if optional is not None and not optional.passed:
        flags.append("OPTIONAL_FAILED_NOT_COUNTED")
    if failing and average >= HIGH_AVERAGE_MARK:
        flags.append("FAILED_DESPITE_HIGH_AVERAGE")
    if "G5_CAPPED" in codes:
        flags.append("GPA_CAPPED")

    return StudentResult(
        student_id=student_id,
        roll=roll,
        name=name,
        class_name=class_name,
        subjects=results,
        gpa=gpa,
        letter=letter,
        passed=passed,
        uncancelled_gpa=gpa_with,
        uncancelled_letter=letter_for_gpa(gpa_with),
        gpa_without_optional=gpa_wo_final,
        letter_without_optional=letter_wo,
        optional_bonus=bonus,
        compulsory_average_mark=average,
        total_points=_round2(base_sum + bonus),
        gpa_rule_codes=codes,
        gpa_rule_notes=notes,
        flags=flags,
        failing_subjects=failing,
    )
