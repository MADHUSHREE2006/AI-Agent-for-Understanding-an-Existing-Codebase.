"""Entry point for the Student Grading & Result Management System.

A short demo that exercises the main business rules:
attendance eligibility, grade boundaries, GPA, pass/fail, and probation.
"""

from grading import Student, Course, Result, ReportCard


def main() -> None:
    # Two students: one eligible, one not (attendance below 75%).
    alice = Student("S001", "Alice", attendance=92)
    bob = Student("S002", "Bob", attendance=60)  # below 75% -> not eligible

    math = Course("C001", "Mathematics")
    physics = Course("C002", "Physics")

    alice.enroll(math)
    alice.enroll(physics)

    # Alice sits exams and scores well -> high GPA, distinction.
    alice_card = ReportCard(alice)
    alice_card.add_result(Result(alice, math, 95))   # A
    alice_card.add_result(Result(alice, physics, 82))  # B
    print(alice_card.summary())

    # Bob is blocked from exams (attendance rule).
    try:
        Result(bob, math, 50)
    except ValueError as exc:
        print(f"Blocked: {exc}")

    # A class with a low pass rate goes on probation.
    carol = Student("S003", "Carol", attendance=80)
    carol.enroll(math)
    carol_card = ReportCard(carol)
    carol_card.add_result(Result(carol, math, 35))  # F (fail)
    print(carol_card.summary())  # shows FAIL and ON PROBATION


if __name__ == "__main__":
    main()
