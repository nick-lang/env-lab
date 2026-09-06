# env-lab — Claude working notes

Read `README.md` for the thesis, then the current experiment's `EXPERIMENT.md`.

## Rules of the lab

- **Never canonize.** Present stills side by side, say what changed, ask the user to judge.
  A model-judged "the look has arrived" is exactly the failure this lab exists to fix.
- **Score against references, not prose.** Use `critic/RUBRIC.md`; cite the reference frame
  you compared against. If `references/` is empty, say so instead of scoring.
- **Model directs, factories produce.** Don't write vertex math to make an asset look good.
  Change the generator's rules, the scatter rules, the heightmap params, or the lighting.
- **One axis per round.** Terrain, assets, density, lighting, post — change one, snap, compare.
- **Baseline stays untouched.** Experiments run on duplicated maps (`Barrow_E1`), never on
  `/Game/Maps/Barrow`.

## Pipeline

- Unreal must be running on `C:\Users\nickl\Documents\AttunementDemo\AttunementDemo.uproject`.
  Launch: `& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "<uproject>"` (background; ~2 min).
- Drive it: `py -3 tools/ue/remote.py --file tools/ue/<script>.py` (scripts run *inside* UE's Python,
  read their config from absolute paths under `experiments/`). Check output for `FAILED`/tracebacks.
- Blender headless: `& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python <script> -- <args>`.
- Orchestrator: `py -3 tools/run_e1.py --all|--terrain|--kit|--setup|--scatter|--snap`.
- **Asset factory (E03):** ComfyUI at `C:/Users/nickl/Documents/Agents/comfyui/ComfyUI` — start it with the
  `comfyui` launch config (preview_start) or `.venv/Scripts/python.exe main.py --listen 127.0.0.1 --port 8188`.
  `tools/asset/concept.py` (Flux schnell) → `tools/asset/generate3d.py` (native Pixal3D / TRELLIS.2 via the
  official template, converted UI→API by `tools/asset/comfy.py`) → `tools/blender/clean_glb.py` → `tools/ue/ue_e3_swap.py`.
  One command: `py -3 tools/run_e3.py --gen --clean --swap --scatter --snap`. Never edit the template; override node inputs.
- **Materials (E07):** `tools/asset/materials.py make` (Flux tile → 3-pass seam inpaint or `--seam fade` for grids → normal/roughness)
  → `tools/ue/ue_import_materials.py` (`M_Gen_<set>`, world-aligned `M_Ground_Barrow`) → `world.json` `terrain.material`,
  `materials.rock`, path/ramp materials. Flux inpainting writes lettering into repainted bands on structured tiles; grids
  should be assembled procedurally (open item, feeds E08).
- **Kit + solver (E08):** `tools/blender/gen_kit.py` + `experiments/08-modular-kit/kit_spec.json` (9 exact-grid pieces, 4 slots) →
  `tools/ue/ue_import_kit.py`; `tools/layout/wfc.py` (socket WFC, `compatible()` is a rule: `in:*` subtypes never touch their
  own kind, `out` only touches `ext`, stairs need a `hole` above) + `tools/layout/structure.py` (pins, validator: sockets,
  cross-cell AABB overlaps, floor coverage). World node `structures[]`; hall world `experiments/08-modular-kit/world_hall.json`;
  run with `run_e5.py --world ... --out build/world/hall --compile --build --snap --tag E8`. bmesh faces need
  `face.normal_update()` before reading `face.normal` (degenerate UVs otherwise).
- **HISM + Lumen:** instanced meshes that are not Nanite get no Lumen/sky lighting and render black wherever the sun
  doesn't hit (found in E08b under daylight; the ember sun had hidden it). Enable Nanite on every kit/library mesh
  (`nanite_settings.enabled`) — the importers do it now.
- **Block masonry (E08b):** `tools/asset/library.py` (batch concept→3D→clean with `--align`), `tools/layout/masonry.py`
  (coursed blocks, slabs, pillars, quoins), `structure.py` `dressing: blocks`, `tools/ue/ue_import_library.py` (weathered
  material from baked AO + world-space moss + per-instance jitter, Nanite). `tools/measure.py` prints guard metrics per still.
  `LevelEditorSubsystem.new_level` won't leave a dirty level unattended: load the saved package and wipe instead.
- **Vegetation (E06):** `tools/asset/textures.py` (cutout / tile) → `tools/blender/gen_veg.py` + `experiments/06-vegetation/veg_spec.json`
  → `tools/ue/ue_import_veg.py` (masked two-sided foliage materials) → `world.json` layers → `run_e5.py --compile --build --snap --tag E6`.
- Stills: `build/snaps/<exp>/`. Read them with the Read tool and compare to `build/snaps/baseline/`.

## Gotchas (inherit AttunementDemo/CLAUDE.md too)

- Blender → Unreal FBX mirrors Y. `gen_terrain.py` negates Y on export; `ue_e1_setup.py`
  verifies with sample points (`TERRAIN_CHECK`). If it reports MISMATCH, re-export with `--no-flip-y`.
- Terrain mesh collision must be complex-as-simple or traces hit a convex hull. Setup does this.
- `line_trace_single` returns a HitResult; use `.to_dict()`; ground scripts walk down through
  non-ground actors by label so slabs/grass don't count as ground.
- If a scatter layer doesn't survive a save/reload, the HISM attach path is the first suspect.
- PIE blocks editor edits — scripts call `editor_request_end_play()` first.
- `EditorAssetLibrary.duplicate_asset` on a map + `load_level` of the copy **crashes the editor**
  (world leak assert). Use `EditorLoadingAndSavingUtils.save_map(world, dst)` — but it only writes a
  copy; the editor stays on the source package. Always `load_level(dst)` afterwards and check
  `world.get_outer().get_path_name()` before editing (setup script does this).
- `Actor.add_component_by_class` is not exposed; attach HISM via `SubobjectDataSubsystem`
  (`k2_gather_subobject_data_for_instance` → `add_new_subobject` → `k2_find_subobject_data_from_handle` → `get_object`).
- Blender 5.2: `primitive_cube_add(location=…)` bakes location into verts, `primitive_cylinder_add`
  / `ico_sphere_add` do not. Call `transform_apply(location=True, rotation=True, scale=True)` right
  after every primitive before doing any vertex math.
- Never decimate meshes with thin cylinders (branches) — they collapse into spikes.
- `M_LR6_Ground` (the baseline ground material) is height/slope/noise-driven in a way that depends on
  the old 450×-scaled plane; on a real mesh it renders brick red. Treat it as a known unknown, not a bug to fix silently.
- If stills show dashed lines / spikes, hide layers and re-capture (`tools/ue/ue_diag_lines.py` pattern) before guessing.
- **Asset factory gotchas:** ComfyUI v3 dynamic-combo sub-inputs are keyed `parent.child` in API prompts
  (`sign_mode.qef`); `run()` helpers drop `[Info]   `-prefixed lines, so grep raw output when a marker is
  missing; Unreal's FBX import ignores embedded glTF textures and collapses materials — export PNGs from
  Blender and build the material in UE (`ue_e3_swap.py::build_pbr_material`); generated GLBs are
  unit-normalized with arbitrary axis order — fit uniformly on the dominant axis, never stretch to dims.
- **World pipeline (E05):** `experiments/05-world-file/world.json` is the source of truth for the Barrow. `py -3 tools/run_e5.py
  --compile --build --snap` rebuilds `/Game/Maps/Barrow_W` from it. The compiler (`tools/world/compile.py`) owns placement
  (heights from the heightmap, seeded RNG); the builder (`tools/ue/ue_build_world.py`) only spawns what the plan says. Every
  actor label and tag is an id from `build/world/barrow/manifest.json`; HISM instances are `<layer id>:<index>`.
- `LevelEditorSubsystem.new_level(path)` on an EXISTING package keeps its actors. The world builder wipes all actors after
  `new_level` (E06 found five stacked copies of the scene and five suns after four rebuilds). Verify with an actor count.
- `unreal.Color(...)` positional args are **B, G, R, A**. Always construct with keywords (`unreal.Color(r=, g=, b=, a=)`).
- Actor-level material overrides shadow a mesh's default material: the E3 swap left `M_LR3_L_Stone` on the dolmen actors,
  hiding the generated PBR. Set `materials: null` in the world file to use the mesh default.
- **Barrow_W (from world.json) is the current map.** Barrow_E1 is the E01/E03 record and its terrain has NO material
  (engine grey grid): never judge look from E01–E03 stills. Any "copy a property from an existing actor" step must fail
  loudly when the actor is gone — that silent `None` cost three experiments of misread colour.
- The gate's ward light + auto-exposure whites out any light stone; judge assets with `tools/ue/ue_lineup.py`
  (neutral spot) as well as scene shots.
