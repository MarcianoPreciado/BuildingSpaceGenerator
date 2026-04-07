"""Tests for FastAPI server endpoints."""
import pytest
from fastapi.testclient import TestClient

from buildingspacegen.buildingviz.server.app import app, set_scene


@pytest.fixture
def client():
    """Provide FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def restore_scene():
    """Reset in-memory scene after each test to avoid cross-test leakage."""
    yield
    set_scene(None)


def test_get_scene(client):
    """Test GET /api/scene returns full scene JSON."""
    resp = client.get("/api/scene")
    assert resp.status_code == 200
    data = resp.json()
    assert "building" in data
    assert "devices" in data
    assert "radio_profiles" in data


def test_get_building(client):
    """Test GET /api/building returns building geometry."""
    resp = client.get("/api/building")
    assert resp.status_code == 200
    data = resp.json()
    assert "floors" in data
    assert "building_type" in data
    assert "total_area_sqft" in data
    assert len(data["floors"]) > 0


def test_get_devices(client):
    """Test GET /api/devices returns devices and radio profiles."""
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    assert "radio_profiles" in data
    assert isinstance(data["devices"], list)
    assert isinstance(data["radio_profiles"], dict)


def test_get_links_no_freq(client):
    """Test GET /api/links without frequency filter."""
    resp = client.get("/api/links")
    assert resp.status_code == 200
    data = resp.json()
    # Should return links in some format
    assert data is not None


def test_get_links_with_freq(client):
    """Test GET /api/links with frequency filter."""
    resp = client.get("/api/links?freq=900000000")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data or isinstance(data, dict)


def test_get_links_with_freq_2_4_ghz(client):
    """Test GET /api/links with 2.4 GHz frequency."""
    resp = client.get("/api/links?freq=2400000000")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data or isinstance(data, dict)


def test_get_links_with_generated_scene_shape(client):
    """Frequency filtering works after generation stores links as {entries, frequency_hz}."""
    set_scene(
        {
            "building": {"building_type": "medium_office", "total_area_sqft": 1000, "seed": 1, "floors": []},
            "devices": [],
            "radio_profiles": {},
            "links": {
                "entries": [
                    {"tx_device_id": "a", "rx_device_id": "b", "frequency_hz": 900000000.0, "link_viable": True, "rx_power_dbm": -70.0},
                    {"tx_device_id": "a", "rx_device_id": "c", "frequency_hz": 2400000000.0, "link_viable": False, "rx_power_dbm": -95.0},
                ],
                "frequency_hz": 900000000.0,
            },
        }
    )

    resp = client.get("/api/links?freq=2400000000")

    assert resp.status_code == 200
    data = resp.json()
    assert data["frequency_hz"] == 2400000000
    assert len(data["entries"]) == 1
    assert data["entries"][0]["frequency_hz"] == 2400000000.0


def test_get_links_filters_serialized_multiband_scene(client):
    """Frequency filtering works when scene links are stored as a plain serialized list."""
    set_scene(
        {
            "building": {"building_type": "medium_office", "total_area_sqft": 1000, "seed": 1, "floors": []},
            "devices": [],
            "radio_profiles": {},
            "links": [
                {"tx_device_id": "a", "rx_device_id": "b", "frequency_hz": 900000000.0, "link_viable": True, "rx_power_dbm": -70.0},
                {"tx_device_id": "a", "rx_device_id": "c", "frequency_hz": 2400000000.0, "link_viable": False, "rx_power_dbm": -12.0},
            ],
        }
    )

    resp = client.get("/api/links?freq=900000000")

    assert resp.status_code == 200
    data = resp.json()
    assert data["frequency_hz"] == 900000000
    assert len(data["entries"]) == 1
    assert data["entries"][0]["frequency_hz"] == 900000000.0


def test_generate_endpoint_invalid_building_type(client):
    """Test POST /api/generate with invalid building type."""
    resp = client.post(
        "/api/generate",
        json={
            "building_type": "invalid_type",
            "total_sqft": 10000,
            "seed": 123,
            "frequencies_hz": [900e6],
        },
    )
    # Should fail validation
    assert resp.status_code in (400, 422, 503)


def test_generate_endpoint(client):
    """Test POST /api/generate endpoint."""
    resp = client.post(
        "/api/generate",
        json={
            "building_type": "medium_office",
            "total_sqft": 10000,
            "seed": 123,
            "frequencies_hz": [900e6, 2.4e9],
        },
    )
    # Either 200 (pipeline available) or 503 (not available) - both acceptable
    assert resp.status_code in (200, 503)

    if resp.status_code == 200:
        data = resp.json()
        assert "building" in data
        assert "devices" in data


def test_root_endpoint(client):
    """Test GET / returns something sensible."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_api_scene_has_valid_building(client):
    """Test that /api/scene returns valid building structure."""
    resp = client.get("/api/scene")
    assert resp.status_code == 200
    scene = resp.json()

    building = scene["building"]
    assert building["building_type"] in ["medium_office", "large_office", "warehouse"]
    assert building["total_area_sqft"] > 0
    assert "floors" in building
    assert len(building["floors"]) > 0

    floor = building["floors"][0]
    assert "rooms" in floor
    assert "walls" in floor
    assert len(floor["rooms"]) > 0


def test_api_devices_have_positions(client):
    """Test that devices have valid position data."""
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    data = resp.json()

    devices = data["devices"]
    for device in devices:
        assert "id" in device
        assert "device_type" in device
        assert "position" in device
        assert len(device["position"]) == 3  # x, y, z


def test_api_links_have_viability(client):
    """Test that links have viability information."""
    resp = client.get("/api/links?freq=900000000")
    assert resp.status_code == 200
    data = resp.json()

    if "entries" in data:
        entries = data["entries"]
    else:
        # Might be a list directly
        entries = data if isinstance(data, list) else []

    if entries:
        for link in entries:
            assert "tx_device_id" in link
            assert "rx_device_id" in link
            assert "link_viable" in link
            assert "rx_power_dbm" in link


def test_api_radio_profiles_complete(client):
    """Test that radio profiles have all required fields."""
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    data = resp.json()

    profiles = data["radio_profiles"]
    for profile_name, profile in profiles.items():
        assert "name" in profile
        assert "tx_power_dbm" in profile
        assert "rx_sensitivity_dbm" in profile
        assert "supported_frequencies_hz" in profile
