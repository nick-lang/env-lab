# E01 — Barrow density

*Started 2026-09-02.*

## Diagnosis this experiment tests

The AttunementDemo look-rounds (LR1–LR10) tuned lighting on a scene made of a flat plane,
sphere hills, tapered-cube megaliths and ~100 grass tufts, and the final stills read as a
blockout with nice light. Four content failures, none of them lighting:

1. **Assets were primitives with noise.** Rocks from tapered cubes, hills from spheres.
2. **The scene was empty.** ~10 objects on a plane; no mid-scale dressing, no ground clutter.
3. **The critic had no taste.** "LR10 self-judged: the look has arrived" was the model grading itself.
4. **The bar was unreachable.** Arcane. Reachable: Firewatch / Sable / Journey / Tunic.

## Hypothesis

Holding lighting, cameras, materials and the gate composition fixed, swapping the ground for
a real heightmap and adding a displaced-icosphere kit plus rules-based scatter at three
scales moves the stills from "blockout" to "scene". If it does, content sourcing and density
were the bottleneck and the asset/density factories get built properly. If not, we learned
that for a day's work.

## What changes (and only this)

| Axis | Baseline (Barrow / LR10) | E01 (Barrow_E1) |
|---|---|---|
| Terrain | 450×520 m plane + 5 scaled spheres/ridges | 512 m heightmap: gate dome, valley bowls, 8 ridges, fBm, droplet erosion; path corridor kept smooth (`terrain.json`) |
| Rocks | tapered cubes (dolmen kept as-is) | 3 boulders, 3 rocks, 3 pebbles — icosphere + 3-layer global displacement, faceted (`gen_rocks.py`) |
| Vegetation | 107 hand-placed grass tufts | + rules-scatter grass (path-band, clumped), shrubs, 3 tree types (`scatter_rules.json`) |
| Placement | per-object | 6 rule layers: region, path distance band, gate exclusion, slope band, clump noise, sink, slope-align |
| Lighting / fog / grade / materials / cameras | LR9–LR10 | **unchanged** |

Dressing actors (path slabs, wanderer, dolmen, ward, grass) are reseated at their old height
above ground, so composition survives the new terrain.

## Shots (fixed, ground-relative z)

`shots.json`: player, hero, path_low, gate, stone (same as LR10/LR9B) + one new `wide`.
Baseline copies in `build/snaps/baseline/`, E01 output in `build/snaps/e1/`.

## Judging protocol

1. You look at pairs (baseline vs E01) per shot. Rate 1–10 in `critic/ratings.csv`, note the first fix.
2. Claude scores both sets with `critic/RUBRIC.md` **only if** `references/` has frames; otherwise
   Claude lists tells and density per scale, no score.
3. Sign-off means: "the density leg is proven, move to E02 (look) and E03 (assets)". No stills
   from E01 are canonized.

## Status (2026-09-02, end of day 1)

- **Pipeline proven end to end.** `py -3 tools/run_e1.py --all` regenerates terrain, kit, map, scatter
  and the 7-shot set in ~4 minutes. `Barrow_E1` is saved in the AttunementDemo project; `Barrow` is untouched.
- **Stills: `build/snaps/e1/`, side-by-side sheet `build/snaps/E01_contact_sheet.png`. Awaiting the user's judgment.**
  Claude's read (not a score — no reference board yet): the scene moved from blockout to
  populated hillside; three scales of clutter exist; the gate crowns the hill against sky. Tells that
  remain: icosphere shrubs and lollipop trees read as low-poly kit, not art; the LR path slabs are still
  flat rectangles; the ground reads brick red (see open items).
- Instances: 2742 (pebbles 186, rocks 215, boulders 41, grass 1409, shrubs 784, trees 114).

## Open items

1. **Ground colour — RESOLVED in E05.** The terrain had no material at all after the first run: the setup script
   copied it from the ground plane, which only existed on run 1. Every later still rendered Unreal's default grey grid
   under the ember light. Not a material problem. See `experiments/05-world-file/EXPERIMENT.md`.
2. **Kit quality.** Rocks are fine at distance; shrubs/trees are placeholders for the asset factory (E03).
3. **Trunk material** renders orange under the ember grade; bark colour needs a grade-aware pick.

## Log

- 2026-09-02 — First UE run crashed the editor: `duplicate_asset` + `load_level` of the copy
  trips a world-leak assert. Switched to `EditorLoadingAndSavingUtils.save_map` (Save As).
- `save_map(world, dst)` writes a copy but the editor stays on the source package; the first run
  therefore saved E1 edits into `Barrow.umap`. Restored from the pristine `Barrow_E1` copy via
  save_map back to `/Game/Maps/Barrow` (timestamps verified), and the setup script now refuses to
  edit unless the loaded package is the target.
- Round 1: terrain too tall/steep, gate buried against a hill wall, trees rejected by slope. Round 2:
  far ridges lowered/pushed back, bowl behind the gate, trees allowed near the corridor. Found a
  checkerboard from 8 m UV tiles on the ground material → UVs now 0..1 over the mesh.
- Round 3: dashed lines in the sky traced (hide-and-capture) to the scatter; trees were 20–60 m
  wide: `primitive_cylinder_add(location=…)` keeps location as an object transform in Blender 5.2
  (cubes bake it), so the taper math sheared trunk tops. Fixed by `transform_apply` after every primitive.
- Round 4: terrain lowered 4.6 m so the valley sits in the ground material's green band. Result: the
  stills above. HISM components attach via `SubobjectDataSubsystem` (`add_component_by_class` is not
  exposed to Python on Actor).
