# Architectural Review Brief
## Building Space Generator & Wireless Sensor Network Simulation Platform

**Prepared for:** Mr. Preciado (Master Architect / Reviewer)
**Prepared by:** Your Hand of the King
**Date:** April 5, 2026
**Status:** ✓ APPROVED — Ready for parallel development

---

## Executive Summary

I've completed the initial architectural review for the Building Space Generator project. This brief presents my findings, recommendations, and the key decision points that need your sign-off before we break ground.

The good news: this is a very buildable system. The core building generator can be implemented from first principles using well-understood algorithms (BSP space partitioning), parameterized by real commercial building data from the DOE, with minimal dependencies. The path loss model you described in intent.md maps directly to a standard ITU multi-wall model that's trivial to implement. The visualizer has an obvious technology choice in Three.js. There are no exotic dependencies or risky bets in the critical path.

The nuanced news: I surveyed 60+ open-source projects and the conclusion is that we should build the core generator ourselves rather than fork an existing project. The existing projects fall into two camps — ML-based generators trained on residential data (wrong building types, non-deterministic, heavy dependencies) and game-oriented dungeon generators (too simplistic, wrong abstractions). The right move is a clean Python library built from first principles, informed by the DOE's commercial reference building data for realistic parameterization.

---

## What I Did

1. **Analyzed your intent.md and initial-research.md** to extract the full requirements chain: building generation → sensor placement → path loss computation → protocol simulation → visualization. Identified two workflows: batch Monte Carlo and interactive single-building demo.

2. **Designed the full platform architecture** — five subsystems (building generator, sensor placer, path loss engine, protocol simulator, visualizer) with clean interfaces. The building generator is the foundation; everything else composes on top of it. See `architecture.md` for the complete design.

3. **Surveyed 60+ open-source projects** across six categories: procedural generators, BIM/CAD tools, energy simulation, RF propagation, 3D visualization, and sensor placement. See `open-source-survey.md` for the full catalog with URLs, licenses, and assessments.

4. **Made technology recommendations** for each layer of the stack, with primary and fallback choices justified.

---

## Key Architectural Decisions Needing Your Review

### Decision 1: Build the Generator from Scratch (BSP) vs. Fork an Existing Project

**My recommendation: Build from scratch using BSP space partitioning.**

Rationale: I evaluated every promising open-source floor plan generator and none of them are a good fit as a fork base.

The ML-based generators (Graph2Plan, House-GAN, ArchiGAN) are trained exclusively on residential floor plans. They'd need retraining on commercial data we don't have. They're non-deterministic (problematic for reproducible Monte Carlo). They require GPU inference. They're research code, not production libraries.

The Blender-based generator (wojtryb/Procedural-Building-Generator) uses a good algorithm (squarified treemaps) but is deeply coupled to Blender's data model and API. Extracting the algorithm would mean rewriting it anyway — at which point we might as well write it cleanly from the start.

BSP partitioning is the right choice because it's deterministic (reproducible from seed), fast (sub-second generation for Monte Carlo), produces rectangular room layouts (which is exactly what commercial buildings look like), and is simple enough that we can implement and debug it in a few days. We augment the basic BSP with corridor insertion, door placement, and material assignment as post-processing steps.

I also recommend implementing squarified treemap as a second generator algorithm — it's slightly faster and simpler, good for quick-and-dirty Monte Carlo runs where layout realism matters less.

For industrial buildings (warehouses, factories) where zone adjacency matters more, a genetic/evolutionary algorithm is the right third option, but this can come later.

**Risk:** The BSP approach won't produce architecturally beautiful floor plans. It produces functional, realistic, rectangular layouts. For the purpose of wireless simulation this is perfectly fine — we need plausible wall placements and room distributions, not award-winning architecture.

### Decision 2: DOE Commercial Reference Buildings as the Parameterization Source

**My recommendation: Parse the DOE's 16 commercial reference building EnergyPlus models to extract room-type distributions, sizes, and wall constructions.**

This is potentially the single highest-value move in the project. The DOE has already done the hard work of defining what a realistic medium office, large office, warehouse, retail store, hospital, etc. looks like in terms of zones, room types, sizes, and wall constructions. Their models include material stacks (e.g., "8-inch concrete block + 1-inch rigid insulation + 0.5-inch gypsum board") that we can directly map to RF attenuation values.

We parse these IDF files once, extract statistical distributions (room type percentages, size ranges, wall constructions), and store them as YAML archetype files. The generator then samples from these distributions when creating a building.

**Risk:** The DOE models are simplified thermal zones, not detailed architectural floor plans. A "zone" in EnergyPlus might represent an entire open office area, not individual rooms within it. We'll need to apply judgment in translating thermal zones to rooms. But the proportions, materials, and building-type characteristics are exactly what we need.

### Decision 3: Multi-Wall Path Loss as Default, Ray Tracing as Optional

**My recommendation: Implement the simple multi-wall model you described as the primary engine. Offer PyLayers integration as a high-fidelity option.**

Your description in intent.md — "the shortest distance between the two, and the sum of the attenuations of each wall" — maps directly to the ITU-R P.1238 / Motley-Keenan multi-wall model. This is a well-understood model, trivial to implement (line-segment intersection test + summation), and fast enough for Monte Carlo (all pairwise losses for 500 devices in seconds).

PyLayers is the most capable open-source indoor RF propagation tool I found — it does full ray tracing with multipath, reflections, and diffraction. But it's a heavy dependency, primarily UWB-focused, and orders of magnitude slower. Worth having as an option for validation or high-fidelity single-building analysis, but not for batch runs.

**Risk:** The multi-wall model is conservative — it doesn't account for constructive multipath that can sometimes improve reception, or for diffraction around corners. For a worst-case / conservative simulation (which you mentioned wanting), this is actually a feature, not a bug.

### Decision 4: Phase 1 2D Top-Down Visualizer, Upgradeable to Three.js

**Approved: 2D top-down view for Phase 1 (matplotlib + lightweight browser canvas), with architecture designed for Three.js 3D upgrade in Phase 2.**

The FastAPI backend serves building + device + link data as JSON with full 3D coordinates (x, y, z). Phase 1 frontends render only x, y as a top-down floor plan. When Three.js is added later, the backend API and JSON schema remain unchanged — only the frontend renderer swaps out. This gives us a working interactive visualizer quickly without the JavaScript investment up front.

**Risk:** Minimal. The 2D view is actually sufficient for most floor-plan analysis. The 3D upgrade is additive, not a rewrite.

### Decision 5: Internal Model + JSON as Canonical Format, IFC as Optional Export

**My recommendation: The internal Python dataclass model is the source of truth. JSON serialization is the interchange format. IFC export via IfcOpenShell is available but optional.**

IFC (Industry Foundation Classes) is the BIM standard. Having IFC export gives us interoperability with every architectural tool in existence. But IFC is complex — generating valid IFC models requires careful schema compliance. I recommend implementing it as an optional export, not as the internal representation.

The JSON format serves the visualizer directly and is the simplest interchange format between subsystems. The internal Python dataclass model (Building, Floor, Room, Wall, etc.) is clean, type-safe, and easy to work with.

**Risk:** If we later want to import real building plans (from architect IFC files), we'd need an IFC-to-internal-model importer. This is straightforward with IfcOpenShell but is additional work.

---

## What I Didn't Find (Gaps)

1. **No open-source commercial building floor plan generator exists.** Everything is residential or game-oriented. This confirms that building our own is the right approach.

2. **No open-source building-aware sensor placement tool exists.** We need to build custom placement logic. The rule-based approach (sensors per room, per sqft, at specified wall height) is straightforward.

3. **No dataset of commercial building floor plans exists** in a machine-readable format suitable for training generative models. The DOE reference buildings are the closest thing, but they're thermal zone models, not architectural floor plans. This is why the algorithmic approach (BSP) beats the ML approach for our use case.

---

## Approved Development Tracks (for Parallel Agent Dispatch)

With all architectural decisions resolved, here are the parallel tracks ready for agent dispatch:

**Track A — Core Data Model + Building Generator (Python)**
- Core data model: Building, Floor, Room, Wall, Door, Material dataclasses + geometry primitives
- Enum definitions: BuildingType (medium_office, large_office, warehouse), RoomType, WallMaterial
- BSP partitioning algorithm with seeded RNG
- Archetype system: parse DOE reference building IDF files → YAML configs for room distributions, sizes, wall constructions
- Post-processing: corridor insertion, door placement, material assignment
- JSON export (schema designed for both 2D and future 3D rendering)
- Unit tests for partitioning, room assignment, and model validation

**Track B — Sensor Placer + Path Loss Engine (Python)**
- Device model: MainController, SecondaryController, Sensor with DeviceType enum
- PlacementRules configuration with three-tier rules (main controller density, secondary density, sensor min-per-room + min-per-sqft)
- Rule-based placement engine (controllers first → sensors second)
- RadioProfile dataclass (TX/RX gain, antenna gain, sensitivity, frequency)
- MaterialRFDatabase with frequency-dependent stochastic attenuation (normal distribution, 3σ = published bounds)
- Multi-wall path loss model: Friis FSPL + stochastic wall attenuation + full link budget (TX power + gains - path loss)
- Ray-wall intersection geometry (line segment vs. wall segment)
- Path loss graph construction (NetworkX, edge attrs = LinkResult)
- Dual-band support (900 MHz and 2.4 GHz)
- Unit tests for placement, link budget math, intersection geometry

**Track C — 2D Visualizer (Python + lightweight JS)**
- FastAPI backend: building, device, link, simulation JSON endpoints
- matplotlib 2D renderer for quick dev/Jupyter use
- Browser-based 2D top-down renderer (HTML canvas or Plotly Dash)
- Interactive features: pan/zoom, color-coded connections, mouseover tooltips, signal strength filter slider, device colorization by reachability/power
- JSON schema design (carry x,y,z for future 3D, render x,y for now)

**Track D — Integration + CLI (Python)**
- End-to-end pipeline: generate → place → compute path loss graph → export
- CLI tool: `buildinggen generate --type medium_office --sqft 25000 --seed 42 --radio-profile gen1`
- Batch runner for Monte Carlo: iterate seeds, collect path loss graphs, output summary statistics
- IFC export via IfcOpenShell (optional)
- Integration tests: full pipeline from params → JSON output → visualization

**Parallelism:** Tracks A and B share only the data model interfaces — define those first (day 0), then both tracks proceed independently. Track C needs the JSON schema (also day 0) and can proceed in parallel. Track D starts after A+B produce working code. Realistically, A, B, and C can all launch simultaneously with a shared interface definition preamble.

---

## Files Produced

| File | Description |
|------|-------------|
| `architecture.md` | Full system architecture with subsystem breakdown, data model, generation pipeline, algorithm detail, module structure, and dependency list |
| `open-source-survey.md` | Survey of 60+ projects across 6 categories with URLs, assessments, and recommendations |
| `architectural-review-brief.md` | This document — the "hand of the king" summary for your review |

---

## Resolved Decisions (2026-04-05)

All architectural questions have been answered by the master architect:

| # | Question | Decision |
|---|----------|----------|
| 1 | Building type priority | Medium office, large office, warehouse |
| 2 | Frequency band | Dual-band: 2.4 GHz and 900 MHz |
| 3 | Floor scope | Single-floor only (Phase 1) |
| 4 | Visualizer approach | 2D top-down for Phase 1, upgradeable to Three.js 3D |
| 5 | Controller placement | Three device types: Main Controller (low density/sqft, gravitates center), Secondary Controller (higher density/sqft), Sensor (min per-room AND min per-sqft) |

**Additional architectural requirements from master architect:**
- Material attenuation values must be frequency-dependent (900 MHz propagates better)
- Monte Carlo sampling: wall attenuation uses normal distribution with 3σ = published range bounds
- Radio hardware profiles are configurable per-device-generation (TX/RX gains, sensitivity, etc.) to enable head-to-head comparison of hardware revisions
- Attenuation is sampled once per wall per simulation run (not per ray), reflecting fixed-but-uncertain wall properties

---

**Status: APPROVED for development.** Architecture is locked. Ready for parallel agent dispatch across Tracks A, B, C, D.
