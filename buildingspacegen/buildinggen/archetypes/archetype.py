"""Building archetype data model and loading."""
from dataclasses import dataclass
from typing import Optional
import yaml

try:
    from core.enums import RoomType, WallMaterial
except ImportError:
    from ...core.enums import RoomType, WallMaterial


@dataclass
class RoomProgram:
    """Room type with target properties."""
    room_type: RoomType
    area_fraction: float  # Fraction of floor area
    min_area_sqm: float
    max_area_sqm: float


@dataclass
class Archetype:
    """Building archetype from YAML."""
    building_type_str: str
    description: str
    footprint_aspect_ratio_min: float
    footprint_aspect_ratio_max: float
    footprint_shapes: list[str]
    floor_ceiling_height_m: float
    floor_corridor_width_m: float
    room_program: list[RoomProgram]
    wall_exterior: str
    wall_interior_default: str
    wall_overrides: dict[str, str]  # room_type -> material

    @classmethod
    def from_yaml_file(cls, filepath: str) -> "Archetype":
        """Load archetype from YAML file."""
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Archetype":
        """Load archetype from dict."""
        footprint = data.get("footprint", {})
        floor = data.get("floor", {})
        wall_construction = data.get("wall_construction", {})

        room_program = []
        for rp_dict in data.get("room_program", []):
            rt = RoomType(rp_dict["room_type"])
            room_program.append(
                RoomProgram(
                    room_type=rt,
                    area_fraction=rp_dict["area_fraction"],
                    min_area_sqm=rp_dict["min_area_sqm"],
                    max_area_sqm=rp_dict["max_area_sqm"],
                )
            )

        return cls(
            building_type_str=data.get("building_type", "unknown"),
            description=data.get("description", ""),
            footprint_aspect_ratio_min=footprint.get("aspect_ratio_range", [1.0, 2.0])[0],
            footprint_aspect_ratio_max=footprint.get("aspect_ratio_range", [1.0, 2.0])[1],
            footprint_shapes=footprint.get("shapes", ["rectangle"]),
            floor_ceiling_height_m=floor.get("ceiling_height_m", 3.0),
            floor_corridor_width_m=floor.get("corridor_width_m", 1.8),
            room_program=room_program,
            wall_exterior=wall_construction.get("exterior", "reinforced_concrete"),
            wall_interior_default=wall_construction.get("interior_default", "gypsum_double"),
            wall_overrides=wall_construction.get("overrides", {}),
        )

    def validate(self) -> None:
        """Validate archetype consistency."""
        total_fraction = sum(rp.area_fraction for rp in self.room_program)
        if abs(total_fraction - 1.0) > 0.05:
            raise ValueError(f"Room program fractions sum to {total_fraction}, not ~1.0")
