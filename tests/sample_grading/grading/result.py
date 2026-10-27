"""Result model: maps a score to a grade point and computes distinction status."""

from .course import Course


class Result:
    """A single exam result linking a student, a course, and a score.

    Grade points follow a 10-point scale (business rule):
        A -> 10, B -> 8, C -> 6, D -> 4, F -> 0.
    A GPA of 8.5 or above earns a distinction.
    """

    GRADE_POINTS = {"A": 10, "B": 8, "C": 6, "D": 4, "F": 0}
    DISTINCTION_GPA = 8.5

    def __init__(self, student, course: Course, score: float):
        if not student.is_eligible_for_exam():
            raise ValueError(
                f"Student '{student.name}' is not eligible to take exams "
                f"(attendance below the 75% minimum)."
            )
        self.student = student
        self.course = course
        self.score = score
        self.grade = course.get_grade(score)

    def grade_point(self) -> int:
        """Return the 10-point-scale grade point for this result."""
        if self.grade not in Result.GRADE_POINTS:
            raise KeyError(f"Unknown grade '{self.grade}'.")
        return Result.GRADE_POINTS[self.grade]

    def is_distinction(self) -> bool:
        """A single result counts toward distinction if its grade point is high."""
        return self.grade_point() >= 9

    def __repr__(self) -> str:
        return f"Result({self.student.name}, {self.course.name}, score={self.score}, grade={self.grade})"
