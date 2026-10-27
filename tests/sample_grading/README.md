# Student Grading & Result Management System

A second sample project used as an analysis target for the **Codebase
Understanding Agent**. It models students, courses, and exam results, and
encodes several academic business rules so the agent has a different domain to
explore (compared with the library management sample).

## Domain rules (what the agent should find)

- A student needs **>= 75% attendance** to be eligible for exams (`student.py`).
- Grade boundaries: **A >= 90, B >= 75, C >= 60, D >= 40, F < 40** (`course.py`).
- A score of **>= 40** passes a course (`course.py`).
- Grade points follow a **10-point scale**: A=10, B=8, C=6, D=4, F=0 (`result.py`).
- **Distinction** requires an overall GPA of **>= 8.5** (`result.py`, `report.py`).
- A report card passes only if **all** courses are passed (`report.py`).
- A class with a pass rate **below 60%** is placed on probation (`report.py`).

## Layout

```
sample_grading/
├── main.py            # demo entry point
└── grading/
    ├── __init__.py    # package exports
    ├── student.py     # Student (attendance eligibility)
    ├── course.py      # Course (scores, grade boundaries)
    ├── result.py      # Result (grade points, distinction)
    └── report.py      # ReportCard (GPA, pass/fail, probation)
```

Run it standalone:

```bash
python tests/sample_grading/main.py
```
