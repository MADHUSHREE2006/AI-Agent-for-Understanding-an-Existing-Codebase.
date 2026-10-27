"""Library member model."""


class Member:
    """A registered library member who can borrow books.

    The member's age drives several business rules (borrowing limits and
    access to reference material), so it is stored explicitly.
    """

    MAX_ACTIVE_LOANS = 5  # business rule: a member may hold at most 5 loans

    def __init__(self, member_id: str, name: str, age: int):
        if age < 0:
            raise ValueError("Age cannot be negative.")
        self.member_id = member_id
        self.name = name
        self.age = age
        self.active_loans: list = []

    @property
    def is_minor(self) -> bool:
        """A member is a minor if they are under 18."""
        return self.age < 18

    def can_borrow_more(self) -> bool:
        """True if the member has not hit the active-loan limit."""
        return len(self.active_loans) < Member.MAX_ACTIVE_LOANS

    def register_loan(self, loan) -> None:
        """Attach an active loan to the member, enforcing the borrowing limit."""
        if not self.can_borrow_more():
            raise ValueError(
                f"Member '{self.name}' already has {Member.MAX_ACTIVE_LOANS} "
                f"active loans and cannot borrow more."
            )
        self.active_loans.append(loan)

    def clear_loan(self, loan) -> None:
        """Remove a loan from the member's active list once returned."""
        if loan in self.active_loans:
            self.active_loans.remove(loan)

    def __repr__(self) -> str:
        return f"Member({self.member_id}, '{self.name}', age={self.age}, loans={len(self.active_loans)})"
