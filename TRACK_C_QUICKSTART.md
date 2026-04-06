# Track C Quick Start Guide

## What Was Implemented

A complete **2D interactive web-based visualizer** for BuildingSpaceGenerator with:
- FastAPI backend serving building geometry, devices, RF links
- React-style Canvas renderer with pan/zoom/hover/click interactions
- Dark-themed single-page app with sidebar controls
- Matplotlib 2D renderer for static floor plan exports
- 15 realistic devices and 22 RF links in fixture

## Files Created

### Backend (Python)
```
buildingspacegen/buildingviz/server/app.py          (187 lines) - FastAPI server
buildingspacegen/buildingviz/renderers/matplotlib_2d.py (280 lines) - Matplotlib renderer
```

### Frontend (JavaScript + HTML)
```
buildingspacegen/buildingviz/frontend/index.html    (230 lines) - Main SPA
buildingspacegen/buildingviz/frontend/src/
  ├── colormap.js       (71 lines)  - Color utilities
  ├── floorplan.js      (130 lines) - Room/wall/door renderer
  ├── devices.js        (111 lines) - Device marker renderer
  ├── links.js          (138 lines) - RF link line renderer
  ├── interaction.js    (230 lines) - Pan/zoom/hover/click
  ├── filters.js        (158 lines) - UI control wiring
  └── main.js           (160 lines) - App initialization
```

### Fixture Data
```
data/fixtures/sample_scene.json  (27 KB)
  - 8 rooms (open office, private office, conference, corridor, etc.)
  - 15 devices (1 main controller, 3 secondary, 11 sensors)
  - 22 RF links (900 MHz + 2.4 GHz, viable + non-viable)
```

### Tests
```
tests/test_buildingviz/test_server.py     (16 tests) - API endpoints
tests/test_buildingviz/test_matplotlib.py (8 tests)  - Rendering
```

## Quick Start

### 1. Install Dependencies
```bash
cd buildingspacegen
pip install fastapi uvicorn httpx matplotlib pytest
```

### 2. Start the Server
```bash
python -m uvicorn buildingviz.server.app:app --reload --port 8000
```

### 3. Open in Browser
```
http://localhost:8000
```

### 4. Interact with Visualization
- **Pan**: Click and drag on canvas
- **Zoom**: Mouse wheel scroll (centered at cursor)
- **Click Device**: Shows gold highlight, highlights connected links
- **Hover Device**: Tooltip with ID, position, radio profile, frequencies
- **Hover Link**: Tooltip with TX/RX IDs, distance, path loss, RX power, viability
- **Frequency Switch**: Select 900 MHz or 2.4 GHz (links re-fetch)
- **Power Filter**: Min/Max RX power sliders filter visible links
- **Device Visibility**: Checkboxes toggle sensors, secondary controllers, main controllers
- **Room Labels**: Checkbox toggles room type and area labels
- **Generate Scene**: Fill in building type, sqft, seed → POST to `/api/generate`

## API Endpoints

### GET /api/scene
Returns complete scene JSON (building + devices + links)
```bash
curl http://localhost:8000/api/scene | jq '.' | head -100
```

### GET /api/building
Returns building geometry only
```bash
curl http://localhost:8000/api/building | jq '.building_type'
# Output: "medium_office"
```

### GET /api/devices
Returns devices + radio profiles
```bash
curl http://localhost:8000/api/devices | jq '.devices | length'
# Output: 15
```

### GET /api/links?freq=900000000
Returns links filtered by frequency
```bash
curl http://localhost:8000/api/links?freq=900000000 | jq '.entries | length'
# Output: 10
```

### POST /api/generate
Generate new scene using full pipeline
```bash
curl -X POST http://localhost:8000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "building_type": "medium_office",
    "total_sqft": 20000,
    "seed": 99,
    "frequencies_hz": [900000000, 2400000000]
  }' | jq '.building.building_type'
```

Returns 200 if Track A/B pipeline is available, 503 if not (fixture loads instead).

## Testing

### Run All Tests
```bash
pytest tests/test_buildingviz/ -v
```

### Run Server Tests Only
```bash
pytest tests/test_buildingviz/test_server.py -v
```

### Run Matplotlib Tests Only
```bash
pytest tests/test_buildingviz/test_matplotlib.py -v
```

## Key Features

### Frontend
- **Dark Theme**: Modern engineering tool aesthetic
- **Responsive Layout**: Sidebar (260px) + canvas (responsive)
- **Interactive Canvas**: Pan, zoom, hover, click with no page reloads
- **Real-time Filtering**: Links filtered by frequency, power range, viability status
- **Device Selection**: Click device → gold highlight + link highlighting
- **Statistics Panel**: Device counts, link viability, building info
- **Room Legend**: Color-coded room types from scene

### Backend
- **RESTful API**: 6 endpoints following REST principles
- **P.3 Schema Compliant**: Exact JSON schema from serialization.py
- **Graceful Degradation**: Falls back to fixture if Track A/B unavailable
- **In-Memory Caching**: Scenes cached for fast access
- **Static File Serving**: Frontend served alongside API

### Matplotlib Renderer
- **Full Building Rendering**: Rooms, walls, doors, devices, links
- **Color-Coded Styling**: Room types, wall materials, RX power gradient
- **Export to PNG/PDF**: `save_path` parameter for static reports
- **Label Support**: Optional room names + area (sqft)

## Fixture Data Details

**Building**: Medium office, 60m × 40m, 1 floor

**Rooms** (8 total):
| Room | Type | Area (sqft) | Purpose |
|------|------|-----------|---------|
| room_001 | Open Office | 3,987 | Main workspace |
| room_002 | Private Office | 1,076 | Manager office |
| room_003 | Private Office | 1,076 | Manager office |
| room_004 | Conference | 1,076 | Meeting room |
| room_005 | Corridor | 1,614 | Main circulation |
| room_006 | Restroom | 752 | Facilities |
| room_007 | Kitchen/Break | 860 | Break room |
| room_008 | Mechanical | 1,614 | HVAC/utilities |

**Devices** (15 total):
| ID | Type | Room | Position (x,y,z) | Profile |
|----|------|------|-----------------|---------|
| dev_001 | Main Controller | room_001 | (13.5, 19.0, 2.5) | main_controller |
| dev_002-004 | Secondary Controller | various | distributed | secondary_controller |
| dev_005-015 | Sensor | various | distributed | gen1_sensor |

**RF Links** (22 total):
- 10 @ 900 MHz (6 viable, 4 non-viable)
- 12 @ 2.4 GHz (8 viable, 4 non-viable)
- Distances: 1.5m to 16.2m
- RX power: -34.8 dBm (excellent) to -83.0 dBm (very weak)

## Architecture Highlights

### Phase 2 Upgrade Ready
The code is structured for easy Three.js integration:
- `colormap.js` — Pure data functions (no Canvas) ✓ Reusable
- `interaction.js` — Works with abstract coordinates ✓ Reusable
- `filters.js` — UI logic only ✓ Reusable
- Only `floorplan.js` and `devices.js` reference Canvas 2D context (replaceable)

### Separation of Concerns
1. **colormap.js** — What colors to use
2. **floorplan.js** — How to draw rooms/walls/doors
3. **devices.js** — How to draw device markers
4. **links.js** — How to draw RF links
5. **interaction.js** — How to handle user input (camera, hit tests, tooltips)
6. **filters.js** — How to wire UI controls to renderer state
7. **main.js** — Application orchestration

## Troubleshooting

### "Port 8000 already in use"
```bash
# Kill existing process
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or use different port
python -m uvicorn buildingviz.server.app:app --port 8001
```

### "Module not found: fastapi"
```bash
pip install fastapi uvicorn
```

### "Cannot import buildingspacegen"
```bash
# Make sure you're in the right directory
cd buildingspacegen
export PYTHONPATH=$(pwd):$PYTHONPATH
```

### Fixture not loading
```bash
# Verify fixture exists
ls -l data/fixtures/sample_scene.json

# Verify JSON is valid
python -c "import json; json.load(open('data/fixtures/sample_scene.json'))"
```

### /api/generate returns 503
This is expected if Track A/B pipeline is not installed. The fixture will load instead, and you can still visualize it. If you want to generate new scenes, install Track A and B:
```bash
pip install buildingspacegen[all]
```

## Next Steps

1. **Run Tests**: `pytest tests/test_buildingviz/ -v`
2. **Start Server**: `python -m uvicorn buildingviz.server.app:app --reload`
3. **Open Browser**: `http://localhost:8000`
4. **Explore Visualization**: Pan, zoom, click devices, filter links
5. **Generate Scenes**: Click "Generate" button (if Track A/B available)
6. **Export Reports**: Use matplotlib renderer for static PNG exports

## File Locations

- **Backend**: `buildingspacegen/buildingviz/server/app.py`
- **Frontend**: `buildingspacegen/buildingviz/frontend/`
- **Renderer**: `buildingspacegen/buildingviz/renderers/matplotlib_2d.py`
- **Tests**: `tests/test_buildingviz/`
- **Fixture**: `data/fixtures/sample_scene.json`

---

**Track C is complete and ready for production use!**
