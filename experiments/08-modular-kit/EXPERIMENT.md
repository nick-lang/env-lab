# E08 — A modular kit with sockets, and the solver

*Started 2026-09-02. Layers L2 + L3. First piece of the tower.*

## Hypothesis

A kit of exact-dimension stone pieces with a socket on every face, plus a socket-based 3D wave-function
collapse solver, can fill a 20×20×3 building with zero gaps, zero clipping and every socket matched, and the
result reads as one material language. Pass: the automated check reports zero of each; you read it as a
building. Kill: if image-to-3D can't hold a grid spec, pieces become procedural shells with generated materials.

**Decision taken up front:** the kill path is the right path. Exact snapping geometry is what a grid needs and
what image-to-3D will never give reliably, so the kit is procedural shells dressed with the E07 generated
materials. Image-to-3D stays for ornaments (later). Everything is still ours.

## What was built

| Piece | Tool |
|---|---|
| Kit (9 pieces) | `tools/blender/gen_kit.py` + `kit_spec.json`: Floor, Ceiling, Wall, WallWindow, WallDoor, WallAlcove, Pillar, Stair, Parapet. 4 × 4 × 3.5 m cell, level pitch 3.8 m (wall + floor slab), planar world-aligned UVs at 2 m so tiles line up across pieces, four material slots (Floor, Wall, Trim, Ceil). Exports bounds for the validator. |
| Solver | `tools/layout/wfc.py`: tiles are cell types with six sockets and a piece list; rotations generated; `compatible()` is a rule, not equality: `in:w`/`in:a`/`in:p` subtypes never touch their own kind (no two windows side by side, pillars never adjacent), a wall's `out` face only touches `ext`, stairs demand a `hole` cell above them. Min-entropy collapse, arc-consistent propagation, restart on contradiction. |
| Structure node | `tools/layout/structure.py`: doors and stairs are pins; the exterior ring is forced; top-level cells get a ceiling and parapets on their outward faces; pieces become HISM layers with the cell recorded per instance. Validator: socket check over every adjacent pair, AABB overlap check across cells with the exported bounds, floor coverage. |
| World | `world_hall.json`: flat meadow, ember-dusk look, one 20×20×3 hall with two doors and two stairs. `run_e5.py --world … --out … --compile --build --snap --tag E8`. |
| Materials | `stone_wall` tile added to E07's set; kit slots map to `M_Gen_stone_wall`, `M_Gen_flagstone`, `M_Gen_wood_planks`, `M_Gen_plaster` in Unreal (`tools/ue/ue_import_kit.py`). |

## Gate results

Validator on the solved hall (seed 3): **socket mismatches 0, cross-cell overlaps 0, uncovered cells 0**; 1200
cells, 1976 pieces; corners 12, walls 216 (137 plain, 46 window, 31 alcove, 2 door), pillars 57, stairs 2 with
their holes above. Those counts match the geometry exactly (4 corners and 72 wall cells per level).

First solve had two real bugs the validator caught: wall backs matched each other (`ext`↔`ext`), so the solver
built double walls through the interior, and walls 3.5 m tall intersected the 0.3 m floor slab above (1253
overlaps). Fixed with an `out` socket that only touches the exterior, and a level pitch of wall + slab.

## Stills — awaiting your judgment

`build/snaps/e8/E8_*.png`: exterior, door, hall floor, stair, window row, roof.

Claude's read: it is unmistakably one building — corners, window rhythm, parapet, doors. Tells: the interior is an
empty warehouse (no rooms yet: that is E09's mission graph), windows are square holes without frames, and the
ember sun turns the whole facade orange.

## User verdict on the kit hall

"It looks like it worked, but it looks really bad. ... just applying patterns to things is the worst something can
look. The gate ... is the best thing this project has made so far." Logged in `critic/CRITIQUES.md`. The validator
gate passed; the *look* gate failed. Direction change below.

## E08b — build like the gate (started the same day)

Geometry over texture. The kit keeps its exact envelopes and sockets, but every visible surface is assembled from
sculpted blocks made by the asset factory (the pipeline that made the gate):

| Piece | Tool |
|---|---|
| Block library | `tools/asset/library.py` + `blocks.json`: 4 classes (large/medium/small blocks, flagstone slabs) × 6 variants each, concept → TRELLIS.2 → cleanup to class dims, manifest with dims |
| Assembler | `tools/layout/masonry.py`: coursed running bond, mixed block classes, 2.5 cm recessed joints, ±1° tilt jitter, 5% proud blocks, 2% missing, openings clipped, lintels; slab floors on a jittered grid; stacked-block pillars |
| Cores | kit gains mortar-dark core slabs (`SM_Kit_WallCore*`, `FloorCore`, `ParapetCore`) behind the blocks so joints never see through |
| Weathering v1 | `tools/ue/ue_import_library.py`: per-block material with crevice dirt from the baked AO (glTF ORM red channel), moss from up-facing × low-in-world × occlusion × noise, per-instance brightness jitter; Nanite on |
| Look | hall world switched to neutral daylight for judging architecture |
| Measurement pack | `tools/measure.py`: spectral slope, detail per octave, tiling repeat score, value groups, local contrast, saturation — printed per still, guard numbers only |

### Measurement baseline (before blocks)

| still | slope | repeat | shadow/mid/light | local contrast |
|---|---|---|---|---|
| E8 door (painted kit) | -2.63 | **0.63** | 0.45/0.35/0.20 | 0.25 |
| E8 exterior | -2.44 | **0.61** | 0.34/0.66/0.00 | 0.11 |
| E8 window row | -1.17 | **0.60** | 0.26/0.68/0.06 | 0.29 |
| E7 wide (Barrow) | -2.49 | 0.05 | 0.28/0.70/0.02 | 0.18 |
| E3 gate | -2.72 | 0.19 | 0.42/0.42/0.15 | 0.17 |
| LR10 player (old baseline) | -2.97 | **0.73** | 0.38/0.57/0.04 | 0.05 |

The repeat score alone separates "pattern on a box" (≥0.6) from the Barrow (≤0.25); the old baseline was both the
flattest (steepest slope, lowest local contrast) and the most repetitive. These become guard numbers for E08b.

### E08b rounds (2026-09-02/03)

1. Library: 24 blocks (6 large, 6 medium, 6 small, 6 slabs) generated in 77 min on TRELLIS.2, each 9–24k tris.
   The first cleanup squashed blocks whose long axis came out along Y; cleanup now aligns the long axis to X first
   (`--align`). Blocks read as sculpted stone in turntables (`build/library/blocks/_sheet.png`).
2. Daylight exposed a rendering fact: instanced meshes that are not Nanite get no Lumen sky light and go black in
   shadow. Kit and library are Nanite now. `new_level` also refuses to leave a dirty level unattended; the builder
   loads the saved package instead.
3. First block hall: 53k instances, validator clean. Missing blocks showed the black mortar core as holes; the
   terrain's roll poked through the ground-floor slabs; interior wall faces were bare cores.
4. Wall cores are plaster (interior finish) with openings cut 6 cm larger so their cut faces hide behind block ends;
   floor beds stay dark; fewer missing blocks; structure lifted 25 cm; sun moved to the camera side; exposure bias +0.8.
5. Quoin stacks at every corner (rotated with the corner tile); block albedo lifted 1.35× in the weathered material.
6. The corner seam was z-fighting: each wall core ran the full cell width, so its end face lay on the perpendicular
   wall's block faces. Cores now stop 10 cm short of the cell edge and are two layers: plaster inside, dark mortar
   behind the joints. Lamps dimmed so the interior stops blowing out through the windows.

### Measurements, painted kit vs blocks (same daylight, same cameras)

| still | repeat: kit → blocks | local contrast: kit → blocks | slope: kit → blocks |
|---|---|---|---|
| door | 0.69 → **0.54** | 0.18 → **0.26** | -2.50 → -1.88 |
| roof | 0.45 → **0.21** | 0.24 → 0.14 | -2.82 → -1.83 |
| hall floor | 0.34 → 0.41 | 0.04 → **0.13** | -3.46 → -2.32 |
| exterior | 0.68 → 0.68 | 0.11 → 0.09 | -1.79 → -1.84 |

Reading: close and mid shots gained real multi-scale detail (slopes moved from "flat surface" toward the natural
-2 and the repeat fell where blocks fill the frame). The exterior's repeat is unchanged because it comes from the
building's own rhythm — identical floors, evenly spaced windows, a straight parapet — not from any texture. That is
the massing grammar's job (E09/E10), and the metric says so without a critic.

### Claude's read of the block hall

The door shot is masonry: individual blocks with cracks and chips, running bond, joints, a lintel. The roof corner
reads as a built thing. Tells left: blocks lean brown under this grade; the interior is over-lit by the lamps; the
floor slabs sit proud with a dark bed; windows are bare openings; the exterior is a shoebox. None of those is a
texture problem any more.

## Open items

1. Interior partitions: the solver has no interior wall tile yet; E09 pins rooms from the mission graph.
2. Window and door dressing (frames, shutters, sills as separate ornaments) — image-to-3D territory.
3. Procedural assembly for the flagstone/planks tiles (E07 open item) would make the floors seamless.
4. A daylight look for judging architecture; the ember grade fights it.
