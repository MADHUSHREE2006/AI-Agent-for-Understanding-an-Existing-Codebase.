"""Loan model and the core lending rules (fines, due dates, age gating)."""

from datetime import datetime, timedelta


class Loan:
    """A single borrowing event linking a member to a book copy.

    Encodes the key business rules of the lending domain: the loan period,
    the overdue fine rate, and the rule that minors may not borrow
    reference books.
    """

    LOAN_PERIOD_DAYS = 14       # business rule: standard loan length
    FINE_PER_DAY = 0.50         # business rule: overdue fine in currency/day

    def __init__(self, member, book, issued_on: datetime = None, book_type: str = "circulating"):
        # business rule: minors cannot borrow reference books
        if book_type == "reference" and member.is_minor:
            raise ValueError(
                f"Minor member '{member.name}' cannot borrow reference books."
            )
        self.member = member
        self.book = book
        self.issued_on = issued_on or datetime.now()
        self.due_on = self.issued_on + timedelta(days=Loan.LOAN_PERIOD_DAYS)
        self.returned_on = None

    def is_overdue(self, as_of: datetime = None) -> bool:
        """True if the loan is past its due date and not yet returned."""
        if self.returned_on is not None:
            return False
        reference = as_of or datetime.now()
        return reference > self.due_on

    def days_overdue(self, as_of: datetime = None) -> int:
        """Number of days the loan is past due (0 if not overdue)."""
        if not self.is_overdue(as_of):
            return 0
        reference = as_of or datetime.now()
        return (reference - self.due_on).days

    def calculate_fine(self, as_of: datetime = None) -> float:
        """Compute the overdue fine.

        Business rule: the fine is FINE_PER_DAY multiplied by the number of
        days overdue. Loans returned on time accrue no fine.
        """
        days = self.days_overdue(as_of)
        return round(days * Loan.FINE_PER_DAY, 2)

    def return_book(self, returned_on: datetime = None) -> float:
        """Process a return, computing any fine owed."""
        self.returned_on = returned_on or datetime.now()
        fine = self.calculate_fine(self.returned_on)
        self.book.return_copy()
        self.member.clear_loan(self)
        return fine

    def __repr__(self) -> str:
        status = "returned" if self.returned_on else "active"
        return f"Loan({self.member.name}, {self.book.title}, due={self.due_on.date()}, {status})"
