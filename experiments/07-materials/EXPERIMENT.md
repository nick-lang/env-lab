# E07 — Materials we made

*Started 2026-09-02. Layer L2. Replaces the last inherited materials in the scene: the ground, the path slabs, the ramp,
and the stone on the procedural rock kit.*

## Hypothesis

A tileable material generator (Flux tile → seam pass → derived normal and roughness) covers ground, stone, plaster and
wood well enough that nothing in the scene needs a downloaded or hand-made texture. Pass: seamless at four tiles; you
prefer it to the flat materials; the brick-red ground is gone (it was: E05). Kill: if seams can't be fixed at 2k, fall
back to triplanar procedural blends with generated detail textures.

## The factory

| Step | Tool |
|---|---|
| Tile | `tools/asset/materials.py make --name X --prompt "..."` → Flux schnell, top-down prompt preamble, "no text/letters/logo" |
| Flatten | remove low-frequency lighting (vignette) so both sides of a seam share a mean |
| Seam | `--seam inpaint` (default): three passes — roll X + repaint the vertical band, roll Y + repaint the horizontal band, roll X + repaint the centre square where the band ends meet; partial denoise 0.55; band colour-matched to the tile. `--seam fade`: roll + cross-fade (for grids). |
| Maps | Normal from tile-aware Sobel on blurred luminance; Roughness from inverted luminance. Both seamless by construction. |
| Score | `seam score` = wrap-edge difference / interior neighbour difference; 1.0 = invisible. Printed per tile. |
| Engine | `tools/ue/ue_import_materials.py`: `M_Gen_<set>` (UV-tiled PBR) per set; `M_Ground_Barrow` = world-aligned UV (300 cm tile), grass→moorland by world Z (250–1000 cm), →rock by slope, plus a 7× macro sample of the grass tile as a 0.75–1.25 multiplier to break the repeat. |
| Scene | `world.json` v2: terrain → `M_Ground_Barrow`; path + ramp → `M_Gen_flagstone`; `materials.rock` → `M_Gen_rock_face` (the compiler passes the slot map to the builder). |

Sets: `ground_grass`, `ground_dry` (moorland turf, toned olive because the ember sun turns anything warm into desert),
`rock_face`, `flagstone`, `wood_planks`, `plaster`. Sheet: `build/materials/_sheet.png` (2×2 tiles each).

## Seam scores (final)

| set | seam mode | score |
|---|---|---|
| ground_grass | inpaint | 1.27 |
| ground_dry | inpaint | 0.98 |
| rock_face | inpaint | 1.22 |
| plaster | inpaint | 1.62 |
| wood_planks | fade | 1.27 |
| flagstone | fade | 5.48 (grid; see open items) |

## Rounds

1. Single cross-band inpaint at full denoise: bands visibly lighter, seams still there.
2. Flatten + partial denoise + feathered blend: better; a naive edge cross-fade made rock worse (it blends in the band).
3. Three-pass inpaint: scores near 1 for organic tiles. **Flux painted lettering into the bands** of the structured tiles
   (flagstone, planks, plaster) — inpainting with a prompt hallucinates objects.
4. "No text" in the prompt, denoise 0.55, colour-matched bands; grids switched to plain cross-fade. Moorland toned olive;
   macro variation added to the ground material; tile 300 cm.

5. **User: the ground was harsh, trypophobic, and showed a second-order grid.** Three causes, all fixed: the grass tile had
   high-contrast dark blotches ("bare earth patches" in the prompt) and the derived normal turned them into pits; the macro
   variation re-sampled the grass tile at 7x, which is itself a regular grid. Now: tiles regenerated with a "no bare patches,
   low contrast" prompt, contrast 0.75, normal strength 0.7; macro variation from world-space gradient noise (about 25 m);
   and a stochastic two-sample blend (the tile rotated 90 degrees and offset, mixed by a two-tile-wide noise mask) so no
   repeat lines up. Seam scores: grass 1.15, moorland 0.99.

## Result — awaiting your judgment

Stills `build/snaps/e7/E7_*.png`; sheet vs E06 `build/snaps/E07_contact_sheet.png`. Claude's read: the ground finally
has surface, the path reads as laid stone, the hero rocks keep their own PBR. Tells: the crest reads orange under the ember sun (the moorland tile is olive on its own); the rock tile carries a faint band; flagstone is blurred at its seam.

## Open items

1. **Structured tiles (flagstone, planks, brick) should be built, not painted.** Generate per-slab / per-plank textures and
   assemble the grid procedurally → seamless by construction. This is the same generator E08's modular kit needs.
2. Inpainting hallucination: even with "no text" the model sometimes writes. A text detector on the band, or a second
   seed on failure, would automate the retry.
3. Cube slabs stretch the flagstone on their side faces; give slabs a world-aligned (triplanar) material.
4. Macro variation uses the grass tile itself; a dedicated low-frequency variation map would look less patterned.
