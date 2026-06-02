"""Coordinates value object representing the geographic search input."""

from dataclasses import dataclass

from backend.domain.exceptions import InvalidCoordinatesError


@dataclass(frozen=True)
class Coordinates:
    """Immutable geographic search area defined by a centre point and a radius.

    Attributes:
        latitude:  Decimal degrees, range [-90, 90].
        longitude: Decimal degrees, range [-180, 180].
        radius_km: Search radius in kilometres, must be strictly positive.

    Raises:
        InvalidCoordinatesError: If any value falls outside its valid range.
    """

    latitude: float
    longitude: float
    radius_km: float

    def __post_init__(self) -> None:
        """Validate all fields immediately after construction."""
        if not (-90 <= self.latitude <= 90):
            raise InvalidCoordinatesError(f"latitude {self.latitude} out of range [-90, 90]")
        if not (-180 <= self.longitude <= 180):
            raise InvalidCoordinatesError(f"longitude {self.longitude} out of range [-180, 180]")
        if self.radius_km <= 0:
            raise InvalidCoordinatesError(f"radius_km must be > 0, got {self.radius_km}")
