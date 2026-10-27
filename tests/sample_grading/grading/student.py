"""Student model with attendance-based exam eligibility."""


class Student:
    """A student whose attendance percentage gates exam eligibility.

    The 75% attendance threshold is a business rule: a student below it is
    not allowed to sit for exams and therefore cannot be graded.
    """

    MIN_ATTENDANCE = 75  # business rule: minimum attendance to take exams

    def __init__(self, student_id: str, name: str, attendance: float):
        if attendance < 0 or attendance > 100:
            raise ValueError("Attendance must be between 0 and 100.")
        self.student_id = student_id
        self.name = name
        self.attendance = attendance
        self.courses: list = []

    def is_eligible_for_exam(self) -> bool:
        """True if the student meets the minimum attendance requirement."""
        return self.attendance >= Student.MIN_ATTENDANCE

    def enroll(self, course) -> None:
        """Add a course to the student's enrolment list."""
        if course in self.courses:
            raise ValueError(f"Already enrolled in '{course.name}'.")
        self.courses.append(course)

    def __repr__(self) -> str:
        return f"Student({self.student_id}, '{self.name}', attendance={self.attendance}%)"
