"""Report card: aggregates a student's results into GPA, pass/fail, and probation status."""

from .result import Result


class ReportCard:
    """Collects a student's results and computes overall academic standing.

    Business rules:
    * The student passes only if every course is passed.
    * The GPA is the average of the individual grade points (10-point scale).
    * A class with a pass rate below 60% is placed on probation.
    * Distinction requires an overall GPA of at least 8.5.
    """

    PROBATION_PASS_RATE = 60  # business rule: below this pass rate -> probation

    def __init__(self, student, results: list = None):
        self.student = student
        self.results: list = results or []

    def add_result(self, result: Result) -> None:
        """Append an exam result to the report card."""
        self.results.append(result)

    def overall_gpa(self) -> float:
        """Average grade point across all results (0 if no results)."""
        if not self.results:
            return 0.0
        total = sum(r.grade_point() for r in self.results)
        return round(total / len(self.results), 2)

    def is_pass(self) -> bool:
        """True only if every course result is a pass."""
        if not self.results:
            return False
        return all(r.course.is_passed(r.score) for r in self.results)

    def pass_rate(self) -> float:
        """Percentage of courses passed (0 if no results)."""
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.course.is_passed(r.score))
        return round((passed / len(self.results)) * 100, 2)

    def is_on_probation(self) -> bool:
        """True if the pass rate is below the probation threshold."""
        return self.pass_rate() < ReportCard.PROBATION_PASS_RATE

    def has_distinction(self) -> bool:
        """True if the overall GPA meets the distinction threshold."""
        return self.overall_gpa() >= Result.DISTINCTION_GPA

    def summary(self) -> str:
        """Return a human-readable academic summary."""
        status = "PASS" if self.is_pass() else "FAIL"
        distinction = " with Distinction" if self.has_distinction() else ""
        probation = " [ON PROBATION]" if self.is_on_probation() else ""
        return (
            f"{self.student.name}: GPA {self.overall_gpa()}, "
            f"Pass rate {self.pass_rate()}%, {status}{distinction}{probation}"
        )

    def __repr__(self) -> str:
        return f"ReportCard({self.student.name}, results={len(self.results)})"
