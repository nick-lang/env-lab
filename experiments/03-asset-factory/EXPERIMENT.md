# E03 — Asset factory

*Started 2026-09-02, on top of E01's Barrow_E1 map.*

## Hypothesis

Hero assets made by **concept image → image-to-3D → cleanup** beat the procedural kit on
silhouette, surface read, and "made by a person" feel, without the model ever touching a vertex.
If true, the factory replaces `gen_rocks.py` for anything that matters in frame; the procedural kit
stays for filler.

## The factory (all local, RTX 5090)

| Step | Tool | Where |
|---|---|---|
| Concept | Flux.1 schnell fp8 in ComfyUI, fixed "asset shot" preamble (single object, centered, flat gray bg) | `tools/asset/concept.py` |
| Image → 3D | ComfyUI native **Pixal3D** (default) or **TRELLIS.2**, official template driven headlessly; BiRefNet bg removal, MoGe FOV, remesh → decimate → unwrap → PBR bake (base color, metallic, roughness, AO, normal) | `tools/asset/generate3d.py`, converter in `tools/asset/comfy.py` |
| Cleanup | Blender headless: join, scale to blockout dims / height, origin (center for actor swaps, bottom for scatter), FBX with embedded textures | `tools/blender/clean_glb.py` |
| Engine | swap actor meshes in place (transforms preserved), scatter generated boulders, snap the E01 shot list | `tools/ue/ue_e3_swap.py`, `run_e3.py` |

ComfyUI lives at `C:\Users\nickl\Documents\Agents\comfyui\ComfyUI` (venv torch 2.12 cu128, ComfyUI 0.34).
Weights: `models/diffusion_models/{trellis_2,pixal3d}_bf16`, `models/vae/trellis_2_*`, `models/clip_vision/dino_v3_*`,
`models/background_removal/birefnet`, `models/geometry_estimation/moge_2_*`. Start with the `comfyui` launch config.

## What changes vs E01

Only the four dolmen meshes (+ their material: generated PBR textures) and the two boulder meshes
in the Boulders scatter layer. Terrain, scatter rules, grass, shrubs, trees, lighting, cameras: unchanged.

## Concepts (round 1, Flux schnell, seed 1–3)

`build/concepts/`. Picks: uprights = `dolmen_upright_2` (west) / `dolmen_upright_1` (east),
`dolmen_lintel_2`, `dolmen_fallen_2`, boulders = `boulder_2`, `boulder_3`. Rejected: `dolmen_upright_3`
(rock base baked into the object), `dolmen_fallen_1` (grass halo).

## Judging

Same protocol as E01: pairs E01 vs E03 per shot, your rating + first fix in `critic/ratings.csv`.
Extra question for this one: does the PBR-textured stone sit with the stylized flat materials
around it, or does it need the E02 look pass (or the stylized stone material) to belong?

## Status / log

- 2026-09-02 — ComfyUI updated to 0.34 (native TRELLIS.2/Pixal3D landed 2026-08-22), ~27 GB of weights
  downloaded, concept generator proven (7 stills), template→API converter verified node by node.
- **Factory proven end to end the same day.** Six assets generated on TRELLIS.2 (50–350 s each at
  1536 upsample, 2048 textures, ~118k tris after remesh/decimate), cleaned in Blender, swapped into
  Barrow_E1 with per-mesh PBR materials built by script. Turntables: `build/gen3d/*_sheet*.png`,
  `build/gen3d/_sheet_gen.png`. Scene stills: `build/snaps/e3/`, sheet `build/snaps/E03_contact_sheet.png`,
  neutral kit comparison `build/snaps/e3/lineup_generated.png` vs `lineup_procedural.png`.
- Claude's read (no reference board, so not a score): the generated meshes are unmistakably assets —
  cracked slabs, carved spiral, moss, believable silhouettes — and the first thing in this project that
  would not embarrass a store page. In the scene they still read white-pink because the gate's ward
  light + auto exposure blow out any light stone (a known E01/AttunementDemo issue); the lineup shot
  away from the gate shows the textures. Pixal3D not yet compared (weights are in place; flip
  `--backend pixal3d`).
- Gotchas fixed on the way: ComfyUI dynamic-combo sub-inputs are keyed `parent.child` in API prompts;
  Unreal's FBX importer drops glTF-derived textures and collapses all materials to `Material_0`, so the
  factory exports PNGs from Blender and builds `M_<mesh>` in UE by script; non-uniform fitting to blockout
  dims distorts generated meshes (the lintel's long axis is Y in the GLB) — use `fit: uniform`.

## Open items

1. Gate exposure / ward light swamps the hero assets. Lock EV in the gate shots or tone the ward light
   before the next judging round (E02 territory, but it blocks a fair read of E03).
2. 118k tris per hero mesh is fine for a hero but the boulders scatter 38 instances of it; add a
   `--tris 30000` variant for scatter stock (DecimateMesh target is a script arg already).
3. Concept → mesh fidelity: the spiral and cracks survive; moss becomes green blobs. Try Pixal3D and
   a 2nd seed per asset; pick by turntable, not by scene still.
4. Trees/shrubs via this factory are untested (thin geometry is the known weak spot of image-to-3D).
