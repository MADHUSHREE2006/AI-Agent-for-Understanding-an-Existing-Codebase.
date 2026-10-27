"""Book and copy model."""


class BookType:
    """Categories a book copy can belong to."""
    CIRCULATING = "circulating"  # can be borrowed
    REFERENCE = "reference"      # in-library use only, never borrowed


class Book:
    """A logical title that may have one or more physical copies."""

    def __init__(self, book_id: str, title: str, author: str, copies: int = 1):
        self.book_id = book_id
        self.title = title
        self.author = author
        self.total_copies = copies
        # circulating copies available to loan right now
        self.available_copies = copies

    def is_available(self) -> bool:
        """At least one circulating copy is on the shelf."""
        return self.available_copies > 0

    def check_out(self) -> None:
        """Mark one copy as loaned out.

        Raises a ValueError if no copies are available — a business rule
        that prevents over-loaning a title.
        """
        if not self.is_available():
            raise ValueError(f"No copies of '{self.title}' are available.")
        self.available_copies -= 1

    def return_copy(self) -> None:
        """Return one copy to the shelf.

        Raises a ValueError if this would exceed the total copy count —
        a guard against bad data inflating availability.
        """
        if self.available_copies >= self.total_copies:
            raise ValueError("Cannot return more copies than exist.")
        self.available_copies += 1

    def __repr__(self) -> str:
        return f"Book({self.book_id}, '{self.title}', {self.available_copies}/{self.total_copies})"
