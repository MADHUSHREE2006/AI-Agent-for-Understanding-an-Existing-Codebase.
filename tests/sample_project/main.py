"""Entry point for the Mini Library Management System.

Run a small demo that exercises the main business rules:
borrowing a book, hitting the loan limit, and computing an overdue fine.
"""

from datetime import datetime, timedelta

from library import Library, Book, Member, BookType, Loan


def main() -> None:
    lib = Library()
    lib.add_book(Book("B001", "The Pragmatic Programmer", "Hunt & Thomas", copies=2))
    lib.add_book(Book("B002", "Encyclopaedia of Things", "Various", copies=1))
    lib.register_member(Member("M001", "Ada", age=17))     # minor
    lib.register_member(Member("M002", "Grace", age=30))  # adult

    # A normal loan for the adult member.
    loan = lib.issue_loan("M002", "B001")
    print(f"Issued: {loan}")

    # business rule: minors cannot borrow reference books.
    try:
        lib.issue_loan("M001", "B002", book_type=BookType.REFERENCE)
    except ValueError as exc:
        print(f"Blocked: {exc}")

    # business rule: overdue fine accrues at FINE_PER_DAY.
    late = Loan(lib.members["M002"], lib.books["B001"], issued_on=datetime.now() - timedelta(days=20))
    fine = late.calculate_fine()
    print(f"Late loan fine: {fine}")  # 6 days overdue * 0.50 = 3.00

    print(lib)


if __name__ == "__main__":
    main()
