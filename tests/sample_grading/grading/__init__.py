"""Student Grading & Result Management System.

A second sample target for the codebase understanding agent. It models
students, courses, and exam results, and encodes several academic business
rules (attendance eligibility, grade boundaries, GPA, pass/fail, probation).
"""

from .student import Student
from .course import Course
from .result import Result
from .report import ReportCard

__all__ = ["Student", "Course", "Result", "ReportCard"]
