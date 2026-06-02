"""Confidence value object representing the model's certainty about an extracted value."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Confidence:
    """A normalised certainty score in [0.0, 1.0] attached to an extracted field.

    A score of 0.0 means the model has no evidence for the value (typically
    paired with value=None and an abstain_reason). A score of 1.0 means the
    model found unambiguous, recent evidence.

    Attributes:
        score: Certainty in the range [0.0, 1.0].

    Raises:
        ValueError: If score is outside [0.0, 1.0].
    """

    score: float

    def __post_init__(self) -> None:
        """Validate that score is within [0.0, 1.0]."""
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"confidence score must be in [0, 1], got {self.score}")

    def is_reliable(self, threshold: float = 0.5) -> bool:
        """Return True if the score meets or exceeds the given threshold.

        Args:
            threshold: Minimum acceptable confidence. Defaults to 0.5.
        """
        return self.score >= threshold
