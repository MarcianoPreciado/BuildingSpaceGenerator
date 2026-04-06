"""Base path loss model interface."""
from abc import ABC, abstractmethod
from buildingspacegen.core.device import Device
from buildingspacegen.core.model import Building
from buildingspacegen.core.links import LinkResult


class PathLossModel(ABC):
    """Abstract base class for path loss models."""

    @abstractmethod
    def compute_link(
        self,
        tx_device: Device,
        rx_device: Device,
        building: Building,
        wall_attenuations: dict[str, float],
        frequency_hz: float,
    ) -> LinkResult:
        """
        Compute path loss link budget between two devices.

        Args:
            tx_device: Transmitting device
            rx_device: Receiving device
            building: Building model
            wall_attenuations: Pre-sampled wall attenuations: {wall_id: attenuation_db}
            frequency_hz: RF frequency in Hz

        Returns:
            LinkResult with computed path loss and link viability
        """
        pass
