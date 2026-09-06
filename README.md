# env-lab — finding a way to build beautiful game environments with an LLM in the loop

## Thesis

Beauty in an environment is roughly **asset quality × density × lighting**. An LLM is bad at
the first when asked to model, weak at the second when asked to place instances one at a
time, and good at the third. So the tooling never asks the model to make art. It directs
three factories and judges the result through a reference-anchored critic:

| Factory | What the model authors | What produces the pixels |
|---|---|---|
| **Asset** | prompts, picks, dimensions, families | image-gen → image-to-3D → Blender cleanup; kitbash packs; proper procedural generators (displaced icospheres, not tapered cubes) |
| **Density** | terrain design params, biome/scatter *rules* | heightmap + erosion (`tools/terrain`), rules-based scatter into instanced meshes (`tools/ue/ue_e1_scatter.py`) |
| **Look** | lighting, fog, grade, post stack, camera | Unreal (Lumen, PPV) — the look-round method from AttunementDemo, unchanged |

The critic scores stills against a **reference board** you pick (`references/`), on a fixed
checklist (`critic/RUBRIC.md`). Your ratings accumulate in `critic/ratings.csv` so the critic
can be checked against you. **The model never canonizes a look. Only you do.**

## Why this exists

`Documents/AttunementDemo` (UE 5.8) proved the pipeline — remote Python into the editor,
headless Blender, screenshot look-rounds — and produced stills that were still empty planes
with floating slabs. See the diagnosis in `experiments/01-barrow-density/EXPERIMENT.md`.

## Layout

```
experiments/<nn>-<name>/   one hypothesis each: EXPERIMENT.md, params, shot list, results
tools/terrain/             heightmap.py — macro shape + fBm + droplet erosion → npy/png/meta
tools/blender/             headless generators: gen_terrain.py (heightmap→FBX), gen_rocks.py (scatter kit)
tools/ue/                  scripts that run *inside* Unreal via remote.py: setup, scatter, snap
critic/                    RUBRIC.md, ratings.csv (your judgments), scoring notes
references/                your reference board (frames you love) + BOARD.md
build/                     generated: heightmaps, FBX, snaps (not committed)
assets/                    downloaded kits + SOURCES.md with licenses (not committed)
```

## Running experiment 01

Prereqs: UE 5.8 editor open on `AttunementDemo.uproject` (remote execution is on), Blender 5.2,
`py -3` with numpy + Pillow.

```powershell
py -3 tools/run_e1.py --all          # terrain → kit → UE setup → scatter → snaps
py -3 tools/run_e1.py --snap         # just re-capture the fixed shot list
```

Stills land in `build/snaps/e1/`. Compare against `build/snaps/baseline/` (the LR10 set).
