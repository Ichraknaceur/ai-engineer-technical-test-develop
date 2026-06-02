"""Domain exceptions for the quarry extraction pipeline.

All exceptions raised by business logic inherit from DomainError so that
infrastructure layers can catch them without importing specific subclasses.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class ValidationError(DomainError):
    """Raised when a quarry record fails JSON Schema v2.0.0 validation."""


class BudgetExceededError(DomainError):
    """Raised when the next LLM call would exceed the job's max_usd_cost cap."""


class InvalidCoordinatesError(DomainError):
    """Raised when latitude, longitude, or radius_km values are out of their valid range."""


class ScrapingNotAllowedError(DomainError):
    """Raised when robots.txt disallows fetching a given URL."""
