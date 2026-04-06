"""Multi-wall path loss model (ITU-R P.1238 / Motley-Keenan)."""
import math
from buildingspacegen.core.device import Device
from buildingspacegen.core.model import Building
from buildingspacegen.core.links import LinkResult
from buildingspacegen.core.geometry import Point2D
from .base import PathLossModel
from ..geometry import find_intersected_walls


class MultiWallPathLossModel(PathLossModel):
    """Multi-wall path loss model combining free-space path loss and wall attenuation."""

    def __init__(self, material_db):
        """Initialize with a material RF database."""
        self.material_db = material_db

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

        # 3D distance (use z coordinates)
        dx = tx_device.position.x - rx_device.position.x
        dy = tx_device.position.y - rx_device.position.y
        dz = tx_device.position.z - rx_device.position.z
        distance_m = math.sqrt(dx*dx + dy*dy + dz*dz)
        if distance_m < 0.01:
            distance_m = 0.01  # avoid log(0)

        # Free-space path loss (Friis formula)
        # FSPL(dB) = 20*log10(d) + 20*log10(f) - 147.55
        fspl_db = 20*math.log10(distance_m) + 20*math.log10(frequency_hz) - 147.55

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
        rx_power_dbm = (tx_profile.tx_power_dbm
                        + tx_profile.tx_antenna_gain_dbi
                        + rx_profile.rx_antenna_gain_dbi
                        - path_loss_db)

        link_viable = rx_power_dbm >= rx_profile.rx_sensitivity_dbm
        link_margin_db = rx_power_dbm - rx_profile.rx_sensitivity_dbm

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
