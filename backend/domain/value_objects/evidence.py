"""Evidence value object linking an extracted value back to its source text."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    """A verbatim quote from a source document that supports an extracted field value.

    Character offsets refer to positions in the cleaned text of the scraped page,
    allowing the UI to highlight the exact passage that justifies the extraction.

    Attributes:
        source_id:  Identifier of the ScrapedPage this quote comes from.
        char_start: Zero-based start offset of the quote in the cleaned text.
        char_end:   Exclusive end offset of the quote in the cleaned text.
        quote:      The verbatim text slice from char_start to char_end.
    """

    source_id: str
    char_start: int
    char_end: int
    quote: str
