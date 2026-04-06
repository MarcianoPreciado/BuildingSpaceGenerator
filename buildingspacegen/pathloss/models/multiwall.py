"""Multi-wall path loss model (ITU-R P.1238 / Motley-Keenan)."""
import math
from buildingspacegen.core.device import Device
from buildingspacegen.core.model import Building
from buildingspacegen.core.links import LinkResult
from .base import PathLossModel
from ..geometry import find_intersected_walls


_LIGHT_SPEED_M_PER_S = 299_792_458.0
_REFERENCE_MISC_LOSS_DB = {
    900_000_000.0: 12.0,
    2_400_000_000.0: 12.0,
}
_PATH_LOSS_EXPONENT = {
    900_000_000.0: 33.0,
    2_400_000_000.0: 30.0,
}


class MultiWallPathLossModel(PathLossModel):
    """Multi-wall path loss model combining indoor baseline loss and wall attenuation."""

    def __init__(self, material_db):
        """Initialize with a material RF database."""
        self.material_db = material_db

    @staticmethod
    def _nearest_supported_frequency(frequency_hz: float, table: dict[float, float]) -> float:
        """Return the nearest supported frequency in a lookup table."""
        return min(table, key=lambda supported_freq: abs(supported_freq - frequency_hz))

    def _path_loss_exponent(self, frequency_hz: float) -> float:
        """Return the indoor path-loss exponent from the model spec."""
        supported_freq = self._nearest_supported_frequency(frequency_hz, _PATH_LOSS_EXPONENT)
        return _PATH_LOSS_EXPONENT[supported_freq]

    def _misc_loss(self, frequency_hz: float) -> float:
        """Return the distance-independent misc loss term L(d0)."""
        supported_freq = self._nearest_supported_frequency(frequency_hz, _REFERENCE_MISC_LOSS_DB)
        return _REFERENCE_MISC_LOSS_DB[supported_freq]

    def compute_link(
        self,
        tx_device: Device,
        rx_device: Device,
        building: Building,
        wall_attenuations: dict[str, float],
        frequency_hz: float,
    ) -> LinkResult:
        """Compute path loss link budget between two devices."""
        tx_pos_2d = tx_device.position.to_2d()
        rx_pos_2d = rx_device.position.to_2d()

        # Phase 1 uses 2D Euclidean distance in the floor plane.
        distance_m = tx_pos_2d.distance_to(rx_pos_2d)
        if distance_m < 0.01:
            distance_m = 0.01  # avoid log(0)

        # README indoor baseline:
        # L_total = 20log10(f) + N_f log10(d) + 20log10(4π/c) + L(d0) + wall_loss
        # We store the non-wall portion in fspl_db to preserve the existing LinkResult shape.
        path_loss_exponent = self._path_loss_exponent(frequency_hz)
        fspl_db = (
            20.0 * math.log10(frequency_hz)
            + path_loss_exponent * math.log10(distance_m)
            + 20.0 * math.log10(4.0 * math.pi / _LIGHT_SPEED_M_PER_S)
            + self._misc_loss(frequency_hz)
        )

        # Find intersected walls
        intersected = find_intersected_walls(tx_pos_2d, rx_pos_2d, building)

        # Sum wall attenuations using pre-sampled values
        wall_loss_db = 0.0
        wall_details = []
        for entry in intersected:
            wall_id = entry['wall_id']
            mat_name = entry['material']
            if wall_id in wall_attenuations:
                atten = wall_attenuations[wall_id]
            else:
                # Fallback to deterministic if not pre-sampled
                atten = self.material_db.get_deterministic_attenuation(mat_name, frequency_hz)
            wall_loss_db += atten
            wall_details.append({
                'wall_id': wall_id,
                'material': mat_name,
                'attenuation_db': atten,
                'is_door': entry['is_door'],
            })

        path_loss_db = fspl_db + wall_loss_db

        tx_profile = tx_device.radio_profile
        rx_profile = rx_device.radio_profile
        rx_power_dbm = 0.0

        link_viable = False
        link_margin_db = 0.0

        return LinkResult(
            tx_device_id=tx_device.id,
            rx_device_id=rx_device.id,
            frequency_hz=frequency_hz,
            distance_m=distance_m,
            fspl_db=fspl_db,
            wall_loss_db=wall_loss_db,
            path_loss_db=path_loss_db,
            rx_power_dbm=rx_power_dbm,
            walls_crossed=len(intersected),
            wall_details=wall_details,
            link_viable=link_viable,
            link_margin_db=link_margin_db,
        )
