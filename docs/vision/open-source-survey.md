# Open-Source Project Survey for Building Space Generator

## Purpose
This document catalogs and evaluates open-source projects relevant to building a procedural commercial/industrial floor plan generator and its companion systems (RF propagation modeling, 3D visualization, sensor placement). Each entry includes an assessment of adaptability to our specific use case: generating realistic mid-to-large commercial and industrial building floor plans for wireless sensor network simulation.

---

## Category 1: Procedural Floor Plan Generators

### 1.1 Procedural-Building-Generator (wojtryb)
- **URL:** https://github.com/wojtryb/Procedural-Building-Generator
- **Language:** Python (Blender add-on)
- **License:** GPL (Blender add-on)
- **Algorithm:** Squarified treemaps + grid placement
- **What it does:** Generates multi-story building floor plans inside Blender using treemap-based space partitioning. Rooms are placed as rectangles within a building footprint. Outputs 3D Blender geometry with walls, floors, ceilings.
- **Adaptation potential:** HIGH. The core treemap algorithm is separable from Blender. Could extract the partitioning logic and drive it with our own room-type distributions for commercial/industrial buildings. The treemap approach naturally produces rectangular room layouts typical of commercial buildings.
- **Limitations:** Designed for residential/apartment layouts. Would need new room-type vocabularies (open office, conference room, server room, warehouse bay, loading dock, mechanical room, etc.). Blender dependency is heavy if we only need the algorithm.
- **Verdict:** FORK the partitioning algorithm, discard Blender dependency, rewrap as a pure Python library.

### 1.2 Graph2Plan
- **URL:** https://github.com/HanHan55/Graph2plan
- **Language:** Python (PyTorch)
- **License:** Research/academic
- **Algorithm:** Graph neural network — takes room adjacency graph + building boundary as input, outputs floor plan
- **What it does:** Published at ICCV. Translates a graph of room relationships into a spatial floor plan that respects connectivity and sizing constraints. Trained on the RPLAN dataset (80k residential plans).
- **Adaptation potential:** MEDIUM. Architecturally elegant — you specify "these rooms connect to these rooms" and it generates a layout. However, it's trained on residential data. Retraining on commercial/industrial datasets would be necessary, and such datasets are scarce.
- **Limitations:** Requires GPU for inference. Trained only on residential. Retraining needs a commercial building dataset we don't have. Inference time may be too slow for Monte Carlo batches.
- **Verdict:** MONITOR. Interesting approach if a commercial training dataset becomes available. Not viable as a primary path without significant ML investment.

### 1.3 House-GAN / House-GAN++
- **URL:** https://github.com/ennauata/housegan
- **Language:** Python (PyTorch)
- **License:** Research
- **Algorithm:** Relational GAN with graph constraints
- **What it does:** Generates room-level floor plan layouts from bubble diagrams (room connectivity graphs). Outputs room bounding boxes.
- **Adaptation potential:** MEDIUM. Same strengths and weaknesses as Graph2Plan — elegant input/output model but residential-trained.
- **Limitations:** Same dataset dependency problem. GAN outputs can be inconsistent. Not deterministic (bad for reproducible Monte Carlo runs unless seeded carefully).
- **Verdict:** MONITOR alongside Graph2Plan. Not primary path.

### 1.4 BSP / Treemap Generators (Roguelike Heritage)
- **URL:** Various — well-documented algorithm family
- **Language:** Any (trivial to implement)
- **Algorithm:** Binary Space Partitioning, recursive subdivision
- **What it does:** Recursively subdivides a rectangle into rooms. The fundamental algorithm behind most roguelike dungeon generators. Produces axis-aligned rectangular rooms with corridors.
- **Adaptation potential:** HIGH. BSP is the simplest viable approach and the most controllable. We can parameterize split ratios, minimum room sizes, corridor widths, and room-type assignment post-generation. Deterministic given a seed. Fast enough for thousands of Monte Carlo runs.
- **Limitations:** Produces only rectangular rooms on axis-aligned grids. All rooms are rectangles — no L-shaped rooms, no curves. This is actually fine for commercial buildings (most are rectangular grids).
- **Verdict:** STRONG CANDIDATE for primary algorithm. Implement from first principles with commercial/industrial parameterization.

### 1.5 ELOPE (Evolutionary Layout Optimization)
- **URL:** Academic implementations exist
- **Language:** Python
- **Algorithm:** Genetic algorithm for facility layout optimization
- **What it does:** Uses evolutionary optimization to arrange rooms/zones within a footprint, optimizing for adjacency preferences, traffic flow, etc.
- **Adaptation potential:** MEDIUM-HIGH. Good for industrial layouts where zones have specific adjacency requirements (e.g., loading docks near warehouse, offices near lobby). Slower than BSP but produces more realistic industrial layouts.
- **Limitations:** Slower generation time. More complex to parameterize. May need custom fitness functions per building type.
- **Verdict:** CONSIDER as secondary algorithm for industrial building types where adjacency matters.

---

## Category 2: BIM/CAD Programmatic Tools

### 2.1 IfcOpenShell
- **URL:** https://ifcopenshell.org/ / https://github.com/IfcOpenShell/IfcOpenShell
- **Language:** Python (C++ core)
- **License:** LGPL
- **What it does:** Full IFC (Industry Foundation Classes) parser and geometry engine. Python API can create, read, modify IFC building models programmatically. Supports spaces, zones, walls, materials, property sets — the full BIM vocabulary.
- **Adaptation potential:** HIGH for output format. Once we generate a floor plan algorithmically, IfcOpenShell can serialize it as a standards-compliant IFC model with proper wall types, materials, spaces, and zones. This gives us interoperability with every BIM viewer and analysis tool.
- **Limitations:** IFC is complex. Learning curve is steep. Creating valid IFC from scratch requires understanding the schema. Not a generator itself — it's a serialization/deserialization layer.
- **Verdict:** USE as the output serialization layer. Our generator produces an internal model; IfcOpenShell writes it as IFC for visualization and interop.

### 2.2 Homemaker
- **URL:** https://github.com/brunopostle/homemaker-addon
- **Language:** Python
- **What it does:** Converts geometric representations into IFC building models. Bridges the gap between procedural geometry and standards-compliant BIM.
- **Adaptation potential:** MEDIUM. Could simplify our IFC export pipeline — feed it room geometries and get IFC back.
- **Limitations:** Less actively maintained. Designed for a specific workflow (Blender → IFC).
- **Verdict:** EVALUATE as a convenience layer over IfcOpenShell. May save development time for IFC export.

### 2.3 FreeCAD (BIM Workbench)
- **URL:** https://www.freecad.org/
- **Language:** Python scripting API, C++ core
- **License:** LGPL
- **What it does:** Full parametric CAD with a BIM/Arch workbench. Python-scriptable. Can create walls, rooms, floors programmatically. Exports to IFC.
- **Adaptation potential:** LOW-MEDIUM. Overkill for our needs — it's a full CAD application. The scripting API is powerful but we'd be fighting a desktop application framework to use it as a library.
- **Verdict:** SKIP as a dependency. Too heavy. Use IfcOpenShell directly.

---

## Category 3: Energy Simulation / HVAC Zone Models

### 3.1 OpenStudio / EnergyPlus
- **URL:** https://openstudio.net/ / https://energyplus.net/
- **Language:** C++ core, Ruby/Python bindings (OpenStudio), C++ (EnergyPlus)
- **License:** BSD-3 (both DOE projects)
- **What it does:** EnergyPlus is the DOE's building energy simulation engine. OpenStudio is the SDK/front-end. They model buildings as thermal zones with surfaces (walls, floors, ceilings), each surface having construction layers (materials with physical properties). This is very close to what we need: zones = rooms, surfaces = walls, constructions = wall materials.
- **Adaptation potential:** MEDIUM. The zone/surface/construction model maps well to our needs. OpenStudio has a "model articulation" system with "measures" that can programmatically generate building geometry. The DOE Commercial Reference Building models provide realistic templates for office, retail, warehouse, etc.
- **Limitations:** The tools are designed for thermal simulation. Extracting just the geometry/zone model requires careful API work. The Ruby SDK is more mature than the Python bindings. Heavy dependencies.
- **Verdict:** REFERENCE for building archetypes. The DOE Commercial Reference Buildings (16 building types × 19 climate zones) are an excellent source of realistic room/zone distributions, sizes, and wall constructions for commercial buildings. Don't use the simulation engine — mine the building model data.

### 3.2 DOE Commercial Reference Buildings
- **URL:** https://www.energy.gov/eere/buildings/commercial-reference-buildings
- **What they are:** Pre-built EnergyPlus models for 16 commercial building types (small office, medium office, large office, stand-alone retail, strip mall, primary school, secondary school, hospital, outpatient healthcare, small hotel, large hotel, warehouse, quick-service restaurant, full-service restaurant, mid-rise apartment, high-rise apartment). Each model has detailed zone layouts, wall constructions, and material properties.
- **Adaptation potential:** VERY HIGH. These are the authoritative source for "what does a realistic commercial building look like?" We can parse these IDF files to extract room-type distributions, typical room sizes, wall construction stacks (gypsum + insulation + concrete, etc.), and use these as parameters for our procedural generator.
- **Verdict:** MUST USE as the statistical basis for our building archetypes. Parse the IDF files, extract zone/room distributions, and use them to parameterize our generator.

---

## Category 4: RF Propagation / Path Loss Modeling

### 4.1 PyLayers
- **URL:** https://github.com/pylayers/pylayers
- **Language:** Python
- **License:** Open source (academic)
- **What it does:** Site-specific radio propagation simulator. UWB ray tracing, indoor radio coverage prediction, multipath channel modeling. Takes building geometry as input and computes signal propagation between arbitrary points.
- **Adaptation potential:** HIGH. This is the most complete indoor RF propagation tool in Python. Can directly consume our building geometry and compute path loss between sensor pairs.
- **Limitations:** Primarily UWB-focused. Documentation is academic-grade (sparse). May require adaptation for BLE/Zigbee/Sub-GHz frequencies. Complex dependency chain.
- **Verdict:** EVALUATE as the propagation engine. If the frequency model can be adapted, this saves enormous development time vs. building ray tracing from scratch.

### 4.2 Simple Multi-Wall Model (Custom Implementation)
- **Algorithm:** ITU-R P.1238 / Motley-Keenan multi-wall model
- **What it does:** Computes path loss as: free-space loss + sum of wall attenuation factors along the direct path. Each wall contributes a fixed dB loss based on material (e.g., drywall: 3-5 dB, concrete: 10-20 dB, glass: 2-3 dB).
- **Adaptation potential:** VERY HIGH. This is what the user described in intent.md — "a simple model which takes the shortest distance between the two, and the sum of the attenuations of each wall that lie in the path." Trivial to implement given building geometry with wall materials.
- **Implementation:** Line-segment intersection test between two sensor positions against all wall segments. Sum the material attenuation of each intersected wall. Add free-space path loss for the total distance.
- **Verdict:** IMPLEMENT as the primary/default path loss model. Fast, deterministic, sufficient for Monte Carlo. Offer PyLayers as an optional high-fidelity model.

---

## Category 5: 3D Visualization

### 5.1 Three.js (Web-Based)
- **URL:** https://threejs.org/
- **Language:** JavaScript
- **License:** MIT
- **What it does:** The dominant WebGL 3D library. OrbitControls for pan/zoom/rotate. Raycasting for hover/click detection. Supports custom geometry, materials, lines, sprites, tooltips.
- **Adaptation potential:** VERY HIGH. Matches every visualization requirement from intent.md: interactive 3D view, color-coded connections, mouseover tooltips, filtering. Web-based means easy sharing with management.
- **Integration:** Python backend (Flask/FastAPI) generates building + simulation data as JSON. Three.js frontend renders and provides interactivity.
- **Verdict:** PRIMARY CHOICE for the visualization layer. Web-based deployment is ideal for executive demos.

### 5.2 PyVista
- **URL:** https://github.com/pyvista/pyvista
- **Language:** Python
- **License:** MIT
- **What it does:** High-level VTK wrapper. Interactive 3D rendering with widgets, color mapping, picking.
- **Adaptation potential:** HIGH for development/debugging. Can render building geometry, sensors, connections with color mapping. Good for prototyping before the Three.js viewer is ready.
- **Limitations:** Desktop-only. Less polished for executive demos. VTK dependency is heavy.
- **Verdict:** SECONDARY / development tool. Use for quick visualization during development. Three.js for production demos.

### 5.3 Plotly 3D / Dash
- **URL:** https://dash.plotly.com/
- **Language:** Python
- **License:** MIT
- **What it does:** Interactive 3D plots in the browser. Built-in hover tooltips. Color scales. Web deployment via Dash.
- **Adaptation potential:** MEDIUM. Good for quick prototypes and data-heavy visualizations (heatmaps, scatter plots of sensor data). Less suitable for rendering detailed building geometry.
- **Verdict:** CONSIDER for analytics dashboards alongside the Three.js building viewer. Good for showing Monte Carlo result distributions.

---

## Category 6: Sensor Placement

### 6.1 No Existing Tool Found
There is no open-source tool that handles building-aware automated sensor placement with wall-mounting constraints. This must be custom-built.

### 6.2 Recommended Approach
- **Rule-based placement** (primary): Place sensors according to configurable rules — N sensors per room, or 1 per X sq ft, at height H on the wall, with minimum spacing constraints.
- **Optimization-based placement** (secondary): Use scipy.optimize or DEAP genetic algorithms to optimize placement for coverage/connectivity, subject to wall-mounting constraints.
- **NetworkX** for connectivity graph construction and analysis.

---

## Summary: Recommended Technology Stack

| Layer | Primary Choice | Secondary/Fallback | Rationale |
|-------|---------------|-------------------|-----------|
| Floor Plan Generation | Custom BSP/Treemap (Python) | ELOPE genetic for industrial | Deterministic, fast, parameterizable |
| Building Archetypes | DOE Reference Buildings (IDF parsing) | Manual parameterization | Authoritative commercial building data |
| Output Format | IfcOpenShell (IFC) + internal model | Custom JSON | Standards compliance + lightweight option |
| Path Loss Model | Custom multi-wall (ITU-R P.1238) | PyLayers (ray tracing) | Fast default + high-fidelity option |
| 3D Visualization | Three.js (web) | PyVista (desktop/dev) | Web for demos, desktop for dev |
| Sensor Placement | Custom rule-based + optimization | — | No existing tool fits |
| Network Analysis | NetworkX | — | De facto standard |
| Monte Carlo Engine | Custom Python | — | Domain-specific scoring |
