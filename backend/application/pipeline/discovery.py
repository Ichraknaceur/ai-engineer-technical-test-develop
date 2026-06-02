"""Discovery pipeline step: find quarry candidates for a given search area."""

from backend.domain.entities.quarry import QuarryCandidate
from backend.domain.value_objects.coordinates import Coordinates
from backend.ports.outbound.discoverer import IDiscoverer


class DiscoveryStep:
    """Wraps the IDiscoverer port and adds pipeline-level logic (logging, fallback).

    Args:
        discoverer: The concrete discovery adapter (e.g. OverpassDiscoverer).
    """

    def __init__(self, discoverer: IDiscoverer) -> None:
        self._discoverer = discoverer

    async def run(self, coordinates: Coordinates) -> list[QuarryCandidate]:
        """Run the discovery step and return a list of quarry candidates.

        Args:
            coordinates: Centre point and radius of the search area.

        Returns:
            A list of QuarryCandidate objects. Empty list if none found.
        """
        raise NotImplementedError
