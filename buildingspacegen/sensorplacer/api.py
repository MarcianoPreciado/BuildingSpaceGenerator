"""Public API for sensor placement."""
import os
from buildingspacegen.core.model import Building
from buildingspacegen.core.device import DevicePlacement, PlacementRules, RadioProfile
from buildingspacegen.core.enums import DeviceType
from .placer import place_devices
from .rules import DEFAULT_RULES


def place_sensors(
    building: Building,
    rules: PlacementRules = None,
    radio_profiles: dict[DeviceType, RadioProfile] = None,
) -> DevicePlacement:
    """
    Place sensors and controllers in a building.

    Args:
        building: Building model
        rules: Placement rules (default: DEFAULT_RULES)
        radio_profiles: Radio profiles by device type (default: load from data/)

    Returns:
        DevicePlacement with all placed devices
    """
    if rules is None:
        rules = DEFAULT_RULES
    if radio_profiles is None:
        # Use default profiles from data/radio_profiles/
        from buildingspacegen.pathloss.radio import RadioProfileRegistry
        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'radio_profiles')
        registry = RadioProfileRegistry.from_directory(data_dir)
        radio_profiles = {
            DeviceType.MAIN_CONTROLLER: registry.get('main_controller'),
            DeviceType.SECONDARY_CONTROLLER: registry.get('gen1_sensor'),
            DeviceType.SENSOR: registry.get('gen1_sensor'),
        }
    return place_devices(building, rules, radio_profiles, building.seed)
