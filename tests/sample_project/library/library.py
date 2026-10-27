"""The Library orchestrator that ties members, books, and loans together."""

from .book import Book, BookType
from .member import Member
from .loan import Loan


class Library:
    """Central registry that enforces the library's lending rules.

    The Library is the only place that creates loans, which keeps the
    business rules (borrowing limit, age restriction, availability) in one
    consistent place.
    """

    def __init__(self):
        self.books: dict = {}     # book_id -> Book
        self.members: dict = {}   # member_id -> Member
        self.loans: list = []

    def add_book(self, book: Book) -> None:
        """Register a new book title in the catalogue."""
        if book.book_id in self.books:
            raise ValueError(f"Book id '{book.book_id}' already exists.")
        self.books[book.book_id] = book

    def register_member(self, member: Member) -> None:
        """Register a new library member."""
        if member.member_id in self.members:
            raise ValueError(f"Member id '{member.member_id}' already exists.")
        self.members[member.member_id] = member

    def issue_loan(self, member_id: str, book_id: str, book_type: str = BookType.CIRCULATING):
        """Issue a new loan, enforcing every lending rule.

        Raises:
            KeyError: if the member or book is unknown.
            ValueError: if copies are unavailable, the member has hit the
                borrowing limit, or a minor is borrowing a reference book.
        """
        member = self.members.get(member_id)
        if member is None:
            raise KeyError(f"Unknown member '{member_id}'.")
        book = self.books.get(book_id)
        if book is None:
            raise KeyError(f"Unknown book '{book_id}'.")

        # business rule: book must have an available copy
        if not book.is_available():
            raise ValueError(f"'{book.title}' has no available copies.")

        # business rule: member must be under the active-loan limit
        if not member.can_borrow_more():
            raise ValueError(f"Member '{member.name}' has reached the loan limit.")

        loan = Loan(member, book, book_type=book_type)
        book.check_out()
        member.register_loan(loan)
        self.loans.append(loan)
        return loan

    def return_loan(self, loan: Loan) -> float:
        """Return a loan and collect any overdue fine."""
        return loan.return_book()

    def total_outstanding_fines(self, as_of=None) -> float:
        """Sum of fines across all still-active overdue loans."""
        return round(
            sum(loan.calculate_fine(as_of) for loan in self.loans if not loan.returned_on),
            2,
        )

    def __repr__(self) -> str:
        return f"Library(books={len(self.books)}, members={len(self.members)}, loans={len(self.loans)})"
