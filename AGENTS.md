# BuildingSpaceGenerator

## Project Purpose
Procedural building floor plan generator for wireless sensor network simulation. Part of a larger platform to demonstrate the scalability of a new wireless mesh protocol to engineering leadership via Monte Carlo simulation.

## Key Documents
- `intent.md` — Project goals, big-picture vision, and visualization requirements
- `initial-research.md` — Initial leads on open-source generators
- `architecture.md` — Full system architecture (5 subsystems, data model, algorithms, module structure)
- `open-source-survey.md` — Survey of 60+ open-source projects across 6 categories
- `architectural-review-brief.md` — Architectural review summary with resolved decisions and development tracks
- `track-specs.md` — Parallel dispatch specs for Tracks A/B/C/D with shared interface contracts, JSON schema, and per-track task breakdowns

## Architecture (APPROVED 2026-04-05)
Five subsystems: Building Generator (`buildinggen`), Sensor Placer (`sensorplacer`), Path Loss Engine (`pathloss`), Protocol Simulator (`protosim`), Visualizer (`buildingviz`).

Primary generation algorithm: BSP space partitioning, parameterized by DOE Commercial Reference Building data.

### Approved Scope (Phase 1)
- Building types: medium office, large office, warehouse
- Frequency bands: dual-band 2.4 GHz and 900 MHz
- Floor scope: single-floor only
- Visualizer: 2D top-down (matplotlib + lightweight browser), upgradeable to Three.js
- Devices: Main Controller (low density, gravitates center), Secondary Controller (higher density), Sensor (min per-room AND min per-sqft)
- Path loss: ITU multi-wall with stochastic attenuation (normal distribution, 3σ = published bounds), frequency-dependent
- Radio hardware: configurable RadioProfile per device generation (TX/RX gain, sensitivity, etc.)

## Tech Stack
- Python 3.10+, numpy, shapely, networkx, pyyaml (core)
- matplotlib (Phase 1 visualization), FastAPI (backend API)
- IfcOpenShell (optional IFC export)
- Custom multi-wall path loss model (ITU-R P.1238 / Motley-Keenan)

## Development Tracks (Parallel)
- Track A: Core data model + BSP building generator + archetype system
- Track B: Sensor placer + path loss engine (dual-band, stochastic, radio profiles)
- Track C: 2D visualizer (matplotlib + browser-based)
- Track D: Integration + CLI + batch Monte Carlo runner

## Status
Architecture APPROVED. Ready for parallel development.
