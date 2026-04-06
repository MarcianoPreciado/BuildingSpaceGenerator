"""Radio profile management."""
import yaml
import os
from buildingspacegen.core.device import RadioProfile


class RadioProfileRegistry:
    """Registry of radio profiles loaded from YAML files."""

    def __init__(self, profiles: dict[str, RadioProfile]):
        """Initialize with a dictionary of profiles."""
        self._profiles = profiles

    @classmethod
    def from_directory(cls, directory: str) -> 'RadioProfileRegistry':
        """Load all radio profiles from a directory of YAML files."""
        profiles = {}
        for fname in os.listdir(directory):
            if fname.endswith('.yaml'):
                with open(os.path.join(directory, fname)) as f:
                    data = yaml.safe_load(f)
                profile = RadioProfile(
                    name=data['name'],
                    tx_power_dbm=data['tx_power_dbm'],
                    tx_antenna_gain_dbi=data['tx_antenna_gain_dbi'],
                    rx_antenna_gain_dbi=data['rx_antenna_gain_dbi'],
                    rx_sensitivity_dbm=data['rx_sensitivity_dbm'],
                    supported_frequencies_hz=[float(f) for f in data['supported_frequencies_hz']],
                )
                key = fname.replace('.yaml', '')
                profiles[key] = profile
        return cls(profiles)

    def get(self, name: str) -> RadioProfile:
        """Get a profile by name (without .yaml extension)."""
        return self._profiles[name]

    def all_profiles(self) -> dict[str, RadioProfile]:
        """Get all profiles as a dictionary."""
        return dict(self._profiles)
