# E05 — A world file rebuilds the Barrow

*Started 2026-09-02. Layer L1, the world model and ID spine.*

## Hypothesis

One file can describe the Barrow completely (terrain, look, sites, props, paths, biome rules, player,
shots), a compiler can turn it into a placement plan deterministically, and Unreal can build a fresh
map from that plan with every placed thing addressable back to the rule and intent that put it there.
If so, every later capability (tower floors, gating, "this looks out of place") is an operation on
this file, not on a map.

## What was built

| Piece | File | Role |
|---|---|---|
| Scene export | `tools/ue/ue_export_scene.py` | dumps the live E1/E3 map (transforms, meshes, materials, light/fog/cloud/grade properties) so the first world file is authored from the real scene |
| Author | `tools/world/author_barrow.py` | export + E1 terrain params + E3 scatter rules → `world.json`; every part gets an id, an intent, and a **ground-relative** height sampled from the heightmap |
| Compiler | `tools/world/compile.py` | `world.json` → terrain build → `plan.json` (actors, HISM layers, look, player, shots) + `manifest.json` (id → kind, node, rule, intent, transform) + `hash.txt`. Placement is computed from the heightmap, never from engine traces |
| Builder | `tools/ue/ue_build_world.py` | fresh map from the plan; labels and tags are ids; look properties applied by name; no placement logic |
| Pick | `tools/ue/ue_pick.py` + `run_e5.py --resolve` | random screen rays per shot → hit actor / instance index → manifest lookup |
| Orchestrator | `tools/run_e5.py` | `--author --compile --determinism --build --snap --pick --resolve` |

World file: `experiments/05-world-file/world.json` (67 ids: terrain, 6 look actors, 15 site/prop parts, 2 lights,
26 path stones, 16 scatter layers with 2556 instances, player). Map: `/Game/Maps/Barrow_W`.

## Gates

- **Determinism:** compile twice → identical `hash.txt`, byte-identical `plan.json` and `height.npy`. **PASS**
  (first attempt failed only because the plan embedded the output directory path; paths are relative now).
- **Addressability:** 70 random rays over the 7 shots → 60 hits, **60 of 60 resolved** to id → rule → intent, 10 sky. **PASS**
  Example: `biome.barrow.boulders.1` → scatter → rule `{attempts_per_m2: 0.0009, gate_min: 9 …}` → "a few generated hero boulders on flanks, never on the path".

## What the rebuild exposed

- **The E3 dolmen never showed its textures at the gate** because the actors carried a material override of the old
  stylised stone from the swap script. The world file sets `materials: null` for generated parts (mesh default = PBR),
  so the rebuilt gate shows the generated stone for the first time in the scene.
- **`unreal.Color` is BGRA.** The first rebuild had a blue sun and a midday sky; positional Color construction swapped
  channels. Fixed with keyword args. The old AttunementDemo notes had this gotcha; it bit again through a new path.
- **The E01–E03 terrain never had a ground material.** `ue_e1_setup.py` copied the material from the old ground plane
  on its first run only; on every re-run the plane was already gone, the copy was `None`, and Unreal fell back to
  `WorldGridMaterial` (the engine's grey checker). The E02 "checkerboard", the "brick red" ground and the orange cast in
  every E01/E03 still were that default material under the ember sun and grade. Found by diffing the two maps property by
  property after every light/fog/grade value came back identical. The world file assigns `M_LR6_Ground` explicitly, so the
  rebuilt map is the first time the scene's authored look (green valley, yellow crest, blue-purple dusk) has rendered.

## Status

- Round 1 built, snapped, picked, resolved. Colour-order bug found and fixed; round 2 stills in `build/snaps/e5/`.
- **E05 passes both gates.** Sheet vs E03: `build/snaps/E05_contact_sheet.png`.
- The 107 hand-placed grass tufts and the 3 empty scatter actors from E1 are gone; grass is a rule now.

- **Post-mortem (found during E06):** `new_level` on an existing map does not clear it, so every rebuild after the first
  appended a second copy of every actor (two suns, two grades, doubled scatter). The look diff "matched" because label lookups
  hit one copy. Builder now wipes stale actors; counts are verified after each build. The determinism and addressability
  gates are unaffected (they test the compiler and the manifest), but E05 round-2 stills were lit by two suns.

## Open items

1. Look fidelity: **resolved** — every light, fog, atmosphere, cloud and grade property is identical between the maps
   (`tools/ue/ue_diff_look.py`); the visible difference was E1's missing ground material, above. Barrow_W is now the
   reference map; Barrow_E1 stays as the E01/E03 record.
2. The world file still references AttunementDemo assets by path (meshes, materials, the game mode). An asset manifest
   section should list them so a world can be checked for "everything ours" and for missing assets before compile.
3. Scatter uses the compiler's own noise and RNG, so instances differ from E3's (same rules, different draws). Expected.
