"""FastAPI server for BuildingSpaceGenerator Visualizer."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json
import os
from typing import Optional, Union

app = FastAPI(title="BuildingSpaceGenerator Visualizer", version="1.0.0")

# In-memory scene store
_current_scene: Optional[dict] = None
_scene_lock = None  # Could add threading lock if needed for multi-threaded access


class GenerateRequest(BaseModel):
    """Request body for /api/generate endpoint."""
    building_type: str
    total_sqft: float
    seed: int
    frequencies_hz: list[float]


def _normalize_links_payload(links_data: Optional[Union[dict, list]], freq: Optional[float] = None) -> dict:
    """Return frontend-compatible links payload from either supported scene shape."""
    if links_data is None:
        return {"entries": [], "frequency_hz": freq}

    if isinstance(links_data, dict):
        entries = links_data.get("entries", [])
    elif isinstance(links_data, list):
        entries = links_data
    else:
        raise TypeError(f"Unsupported links payload type: {type(links_data).__name__}")

    if freq is not None:
        entries = [
            link for link in entries
            if link.get("frequency_hz") == freq
        ]

    return {"entries": entries, "frequency_hz": freq}


def get_scene() -> dict:
    """Load or return current scene."""
    global _current_scene
    if _current_scene is None:
        # Load fixture on startup
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "data", "fixtures", "sample_scene.json"
        )
        if os.path.exists(fixture_path):
            with open(fixture_path) as f:
                _current_scene = json.load(f)
        else:
            raise RuntimeError(f"Fixture not found at {fixture_path}")
    return _current_scene


def set_scene(scene: dict) -> None:
    """Update current scene."""
    global _current_scene
    _current_scene = scene


# API Routes


@app.get("/")
async def root():
    """Serve root HTML."""
    frontend_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "index.html"
    )
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "BuildingSpaceGenerator Visualizer API"}


@app.get("/api/scene")
async def get_full_scene():
    """Return complete scene JSON."""
    try:
        return get_scene()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/building")
async def get_building():
    """Return building geometry."""
    try:
        scene = get_scene()
        return scene.get("building")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices")
async def get_devices():
    """Return devices and radio profiles."""
    try:
        scene = get_scene()
        return {
            "devices": scene.get("devices", []),
            "radio_profiles": scene.get("radio_profiles", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/links")
async def get_links(freq: Optional[float] = None):
    """Return links, optionally filtered by frequency."""
    try:
        scene = get_scene()
        links_data = scene.get("links")
        return _normalize_links_payload(links_data, freq)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate_scene(req: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate a new scene using the full pipeline."""
    try:
        # Try to import the pipeline
        from buildingspacegen.buildinggen.api import generate_building
        from buildingspacegen.sensorplacer.api import place_sensors as place_devices
        from buildingspacegen.pathloss.api import compute_path_loss
        from buildingspacegen.core.serialization import serialize_building_scene
        from buildingspacegen.core.enums import BuildingType

        # Convert building_type string to enum
        try:
            btype = BuildingType(req.building_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid building_type: {req.building_type}"
            )

        # Generate building
        building = generate_building(btype, req.total_sqft, seed=req.seed)

        # Place devices
        devices = place_devices(building)

        # Compute path loss (returns PathLossGraph)
        links = compute_path_loss(building, devices, req.frequencies_hz)

        # Get radio profiles from devices
        radio_profiles = {}
        if devices and devices.devices:
            seen_profiles = set()
            for device in devices.devices:
                profile_name = device.radio_profile.name
                if profile_name not in seen_profiles:
                    radio_profiles[profile_name] = device.radio_profile

        # Serialize to JSON
        scene = serialize_building_scene(building, devices, links, radio_profiles)

        scene["links"] = _normalize_links_payload(
            scene.get("links"),
            req.frequencies_hz[0] if req.frequencies_hz else None,
        )

        # Store in memory
        set_scene(scene)

        return scene

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Pipeline modules not available. Make sure buildinggen, sensorplacer, and pathloss are installed."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


def _compute_link_stats(scene: dict) -> dict:
    """Compute per-frequency link statistics from a scene dict.

    For each frequency band present in the links, computes:
    - sensors_with_viable_connection: sensors that have >= 1 viable link
    - total_sensors: total sensor count in scene
    - distance_97pct_m: distance where cumulative viability rate first drops to 97%
    - distance_70pct_m: distance where cumulative viability rate first drops to 70%

    Viability survival function S(d):
      S(d) = (# viable links with distance <= d) / (# total links with distance <= d)
    Starts near 100% at short range and decreases as farther non-viable links accumulate.
    """
    links_data = scene.get("links")
    if isinstance(links_data, dict):
        all_links = links_data.get("entries", [])
    elif isinstance(links_data, list):
        all_links = links_data
    else:
        all_links = []

    if not all_links:
        return {}

    devices = scene.get("devices") or []
    sensor_ids = {d["id"] for d in devices if d.get("device_type") == "sensor"}

    # Group links by frequency
    freq_links: dict = {}
    for link in all_links:
        freq = link.get("frequency_hz")
        if freq is not None:
            freq_links.setdefault(freq, []).append(link)

    result = {}
    for freq, links in freq_links.items():
        viable = [l for l in links if l.get("link_viable")]

        # Sensors with at least one viable connection
        sensors_connected: set = set()
        for l in viable:
            if l.get("tx_device_id") in sensor_ids:
                sensors_connected.add(l["tx_device_id"])
            if l.get("rx_device_id") in sensor_ids:
                sensors_connected.add(l["rx_device_id"])

        # Walk links sorted by distance, tracking cumulative viability rate
        sorted_links = sorted(links, key=lambda l: l.get("distance_m", 0))
        dist_97: Optional[float] = None
        dist_70: Optional[float] = None
        viable_count = 0

        for i, link in enumerate(sorted_links):
            if link.get("link_viable"):
                viable_count += 1
            rate = viable_count / (i + 1)
            d = link.get("distance_m", 0)
            if dist_97 is None and rate <= 0.97:
                dist_97 = d
            if dist_70 is None and rate <= 0.70:
                dist_70 = d

        result[int(freq)] = {
            "sensors_with_viable_connection": len(sensors_connected),
            "total_sensors": len(sensor_ids),
            "distance_97pct_m": round(dist_97, 1) if dist_97 is not None else None,
            "distance_70pct_m": round(dist_70, 1) if dist_70 is not None else None,
        }

    return result


@app.get("/api/stats")
async def get_stats():
    """Return per-frequency link statistics for the current scene."""
    try:
        scene = get_scene()
        return _compute_link_stats(scene)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files (frontend)
frontend_dir = os.path.join(
    os.path.dirname(__file__), "..", "frontend"
)
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
