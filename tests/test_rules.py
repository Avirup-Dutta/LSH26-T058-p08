"""Every rule gets a test. Change a rule, a test tells you what moved."""

from app.rules import Component, SubjectEntry, evaluate_student, evaluate_subject


def plain(code, name, mark, optional=False):
    return SubjectEntry(code, name, optional, [Component("theory", 100, 33, mark)])


def split(code, name, theory, practical, optional=False):
    return SubjectEntry(
        code, name, optional,
        [Component("theory", 75, 25, theory), Component("practical", 25, 8, practical)],
    )


def six(mark=70):
    return [
        plain("BAN", "Bangla", mark),
        plain("ENG", "English", mark),
        plain("MATH", "Mathematics", mark),
        split("PHY", "Physics", mark * 0.75, mark * 0.25),
        split("CHEM", "Chemistry", mark * 0.75, mark * 0.25),
        split("BIO", "Biology", mark * 0.75, mark * 0.25),
    ]


def run(entries):
    return evaluate_student(1, "R-1", "Test Student", "Class 10", entries)


# --- subject level ---------------------------------------------------------

def test_band_boundaries():
    assert evaluate_subject(plain("X", "X", 80)).grade_point == 5.0
    assert evaluate_subject(plain("X", "X", 79)).grade_point == 4.0
    assert evaluate_subject(plain("X", "X", 33)).grade_point == 1.0
    assert evaluate_subject(plain("X", "X", 32)).grade_point == 0.0


def test_practical_fail_beats_a_passing_total():
    r = evaluate_subject(split("PHY", "Physics", 58, 5))
    assert r.mark_used == 63 and r.grade_point == 0.0
    assert r.rule_code == "R3_PRACTICAL_FAIL" and r.component_failed == "practical"


def test_theory_fail_beats_a_strong_practical():
    r = evaluate_subject(split("BIO", "Biology", 22, 24))
    assert r.mark_used == 46 and r.grade_point == 0.0
    assert r.rule_code == "R2_THEORY_FAIL"


def test_components_exactly_on_the_pass_mark_pass():
    r = evaluate_subject(split("PHY", "Physics", 25, 8))
    assert r.passed and r.grade_point == 1.0 and r.rule_code == "R5_BAND"


def test_absent_is_a_fail_and_has_no_mark():
    r = evaluate_subject(split("CHEM", "Chemistry", None, 20))
    assert r.is_absent and r.mark_used is None and r.rule_code == "R1_ABSENT"


def test_single_paper_subject_reports_a_total_fail_not_a_component_fail():
    assert evaluate_subject(plain("MATH", "Mathematics", 30)).rule_code == "R4_TOTAL_FAIL"


# --- student level ---------------------------------------------------------

def test_one_failed_subject_zeroes_a_strong_average():
    entries = six(80)
    entries[2] = plain("MATH", "Mathematics", 30)
    r = run(entries)
    assert r.gpa == 0.0 and r.letter == "F" and not r.passed
    assert r.failing_subjects == ["Mathematics"]
    assert r.compulsory_average_mark >= 60
    assert "FAILED_DESPITE_HIGH_AVERAGE" in r.flags


def test_optional_at_or_below_two_adds_nothing():
    r = run(six(70) + [split("HM", "Higher Mathematics", 36, 13, optional=True)])
    assert r.optional_bonus == 0.0
    assert r.gpa == r.gpa_without_optional
    assert "OPTIONAL_NO_EFFECT" in r.flags
    assert "G4_OPTIONAL_IGNORED" in r.gpa_rule_codes


def test_optional_above_two_lifts_the_gpa():
    r = run(six(70) + [split("HM", "Higher Mathematics", 68, 24, optional=True)])
    assert r.optional_bonus == 3.0
    assert r.gpa > r.gpa_without_optional
    assert "G3_OPTIONAL_APPLIED" in r.gpa_rule_codes


def test_a_failed_optional_never_sinks_the_student():
    r = run(six(70) + [split("HM", "Higher Mathematics", 10, 4, optional=True)])
    assert r.passed and r.gpa > 0
    assert "OPTIONAL_FAILED_NOT_COUNTED" in r.flags


def test_absent_optional_does_not_fail_the_student():
    r = run(six(70) + [split("HM", "Higher Mathematics", 50, None, optional=True)])
    assert r.passed and "LIST_ABSENT" in r.flags


def test_gpa_is_capped_at_five():
    r = run(six(90) + [split("HM", "Higher Mathematics", 70, 23, optional=True)])
    assert r.gpa == 5.0 and r.letter == "A+"
    assert "G5_CAPPED" in r.gpa_rule_codes


def test_every_subject_carries_a_rule():
    r = run(six(70) + [split("HM", "Higher Mathematics", 50, 16, optional=True)])
    assert len(r.subjects) == 7
    assert all(s.rule_code and s.rule_text for s in r.subjects)


# --- the published clarifications, one test per rule id ---------------------

def test_R11_failing_either_part_fails_the_subject():
    assert evaluate_subject(split("PHY", "Physics", 24, 20)).grade_point == 0.0
    assert evaluate_subject(split("PHY", "Physics", 60, 7)).grade_point == 0.0
    assert evaluate_subject(split("PHY", "Physics", 25, 8)).passed


def test_R12_absent_compulsory_is_zero_and_overall_F():
    entries = six(70)
    entries[4] = SubjectEntry("CHE", "Chemistry", False,
                              [Component("theory", 75, 25, None),
                               Component("practical", 25, 8, None)])
    r = run(entries)
    assert r.subjects[4].grade_point == 0.0 and r.subjects[4].is_absent
    assert r.gpa == 0.0 and r.letter == "F"
    assert "LIST_ABSENT" in r.flags


def test_R12_absent_optional_contributes_zero_and_lists_the_student():
    r = run(six(70) + [SubjectEntry("HMT", "Higher Mathematics", True,
                                    [Component("theory", 75, 25, None),
                                     Component("practical", 25, 8, None)])])
    assert r.passed and r.optional_bonus == 0.0
    assert "LIST_OPTIONAL" in r.flags and "LIST_ABSENT" in r.flags


def test_R13_gpa_formula_and_cap():
    r = run(six(70) + [split("HMT", "Higher Mathematics", 68, 24, optional=True)])
    # six A grades = 24.00, optional A+ = 5.00 so it carries 3.00
    assert r.total_points == 27.0 and r.gpa == 4.5
    assert run(six(90) + [split("HMT", "H", 70, 23, optional=True)]).gpa == 5.0


def test_R13_uncancelled_average_survives_a_compulsory_failure():
    entries = six(80)
    entries[2] = plain("MAT", "Mathematics", 30)
    r = run(entries)
    assert r.gpa == 0.0 and r.letter == "F"
    assert r.uncancelled_gpa > 0            # still visible in the trace
    assert any("uncancelled" in n for n in r.gpa_rule_notes)


def test_R29_three_lists_and_a_student_can_be_on_more_than_one():
    entries = six(70)
    entries[3] = split("PHY", "Physics", 58, 5)        # practical fail
    entries[4] = SubjectEntry("CHE", "Chemistry", False,
                              [Component("theory", 75, 25, None),
                               Component("practical", 25, 8, None)])   # absent
    r = run(entries + [split("HMT", "H", 30, 10, optional=True)])      # optional 2.0
    assert {"LIST_OPTIONAL", "LIST_PRACTICAL_FAIL", "LIST_ABSENT"} <= set(r.flags)


def test_R29_optional_list_is_grade_point_not_effect():
    # optional grade point exactly 2.00 belongs on the list
    r = run(six(70) + [split("HMT", "H", 35, 14, optional=True)])
    assert r.subjects[-1].grade_point == 2.0 and "LIST_OPTIONAL" in r.flags
    # above 2.00 does not
    r2 = run(six(70) + [split("HMT", "H", 40, 15, optional=True)])
    assert r2.subjects[-1].grade_point > 2.0 and "LIST_OPTIONAL" not in r2.flags
