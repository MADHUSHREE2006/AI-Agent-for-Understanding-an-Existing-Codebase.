# Mini Library Management System

A small but realistic Python project used as the default target for the
**Codebase Understanding Agent**. It is intentionally rich in business rules so
the agent has something meaningful to discover and explain.

## Domain rules (what the agent should find)

- A member may hold at most **5 active loans** (`member.py`).
- The standard **loan period is 14 days** (`loan.py`).
- Overdue fines are **$0.50 per day** past the due date (`loan.py`).
- **Minors (under 18) cannot borrow reference books** (`loan.py`).
- A book copy must be **available** before it can be loaned (`book.py`).
- Returning more copies than exist is **rejected** (`book.py`).

## Layout

```
sample_project/
├── main.py            # demo entry point
└── library/
    ├── __init__.py    # package exports
    ├── book.py        # Book / BookType
    ├── member.py      # Member (age, loan limit)
    ├── loan.py        # Loan (due date, fines, age gating)
    └── library.py     # Library orchestrator (issues/returns loans)
```

Run it standalone:

```bash
python tests/sample_project/main.py
```
