"""RF material attenuation database."""
import yaml
import numpy as np
from dataclasses import dataclass


@dataclass
class MaterialRFProperties:
    """RF properties for a material at a specific frequency."""
    frequency_hz: float
    mean_attenuation_db: float
    sigma_attenuation_db: float

    def sample(self, rng: np.random.Generator) -> float:
        """Sample stochastic attenuation using normal distribution, max(0, Normal(μ, σ))."""
        return max(0.0, rng.normal(self.mean_attenuation_db, self.sigma_attenuation_db))


class MaterialRFDatabase:
    """Database of RF attenuation properties for building materials."""

    def __init__(self, entries: dict):
        """Initialize database with entries: {(material_name, frequency_hz): MaterialRFProperties}."""
        self.entries = entries

    @classmethod
    def from_yaml(cls, path: str) -> 'MaterialRFDatabase':
        """Load material database from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        entries = {}
        for mat_name, mat_data in data['materials'].items():
            for freq_hz, band_data in mat_data['bands'].items():
                props = MaterialRFProperties(
                    frequency_hz=float(freq_hz),
                    mean_attenuation_db=band_data['mean_attenuation_db'],
                    sigma_attenuation_db=band_data['sigma_attenuation_db'],
                )
                entries[(mat_name, float(freq_hz))] = props
        return cls(entries)

    def get_attenuation(self, material_name: str, frequency_hz: float, rng: np.random.Generator) -> float:
        """Sample stochastic attenuation for a material at frequency."""
        props = self._find_props(material_name, frequency_hz)
        return props.sample(rng)

    def get_deterministic_attenuation(self, material_name: str, frequency_hz: float) -> float:
        """Return the mean attenuation (deterministic)."""
        props = self._find_props(material_name, frequency_hz)
        return props.mean_attenuation_db

    def _find_props(self, material_name: str, frequency_hz: float) -> MaterialRFProperties:
        """Find properties for material/frequency, with fuzzy matching fallback."""
        key = (material_name, float(frequency_hz))
        if key in self.entries:
            return self.entries[key]

        # Fuzzy match: find closest frequency for this material
        candidates = [(k, v) for k, v in self.entries.items() if k[0] == material_name]
        if not candidates:
            # Unknown material — return zero attenuation
            return MaterialRFProperties(frequency_hz=frequency_hz, mean_attenuation_db=0.0, sigma_attenuation_db=0.0)

        closest = min(candidates, key=lambda x: abs(x[0][1] - frequency_hz))
        return closest[1]
