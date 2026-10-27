"""Course model with scoring and grade-boundary rules."""


class Course:
    """A course that awards marks out of a maximum and assigns letter grades.

    Grade boundaries (business rule):
        A >= 90, B >= 75, C >= 60, D >= 40, F < 40.
    A score of at least ``passing_marks`` (default 40) is a pass.
    """

    PASSING_MARKS = 40
    MAX_MARKS = 100

    def __init__(self, course_id: str, name: str, max_marks: int = MAX_MARKS):
        if max_marks <= 0:
            raise ValueError("Maximum marks must be positive.")
        self.course_id = course_id
        self.name = name
        self.max_marks = max_marks

    def is_passed(self, score: float) -> bool:
        """A score at or above the passing threshold passes the course."""
        self._validate(score)
        return score >= Course.PASSING_MARKS

    def get_grade(self, score: float) -> str:
        """Return the letter grade for a score (A/B/C/D/F)."""
        self._validate(score)
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= Course.PASSING_MARKS:
            return "D"
        return "F"

    def _validate(self, score: float) -> None:
        """Guard against invalid scores (negative or above the maximum)."""
        if score < 0:
            raise ValueError("Score cannot be negative.")
        if score > self.max_marks:
            raise ValueError(f"Score {score} exceeds maximum marks {self.max_marks}.")

    def __repr__(self) -> str:
        return f"Course({self.course_id}, '{self.name}', max={self.max_marks})"
