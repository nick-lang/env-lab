"""Image → textured 3D mesh (GLB) with ComfyUI's native Pixal3D / TRELLIS.2 pipeline.

  py -3 tools/asset/generate3d.py --image build/concepts/x.png --name x [--backend pixal3d|trellis2]
                                 [--seed 42] [--tex 2048] [--tris 200000]

Drives the official template `3d_pixal3d_trellis2_image_to_model.json` headlessly (see comfy.py),
with the bf16 weights, and copies the resulting GLB to build/gen3d/<name>.glb.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "build", "gen3d")
TEMPLATE = "3d_pixal3d_trellis2_image_to_model.json"

# node ids in the template (verified 2026-09-02 against comfyui-workflow-templates 0.11.54)
N_LOAD_IMAGE = 122
N_UNET_TRELLIS = 40
N_UNET_PIXAL = 319
N_SWITCH_BACKEND = 316      # PrimitiveBoolean: true = TRELLIS.2, false = Pixal3D
N_TEX_RES = 288             # PrimitiveInt texture resolution
N_DECIMATE = 186
N_SAVE = 322                # Save3DAdvanced (textured)
N_KS_STRUCT, N_KS_SHAPE, N_KS_UP, N_KS_TEX = 3, 18, 23, 12
N_REMOVE_BG_SWITCH = 248


def build_prompt(image_name, backend, seed, tex, tris, remove_bg=True):
    wf = json.load(open(comfy.template_path(TEMPLATE), encoding="utf-8"))
    info = comfy.object_info()
    ov = {
        N_LOAD_IMAGE: {"image": image_name},
        N_UNET_TRELLIS: {"unet_name": "trellis_2_bf16.safetensors"},
        N_UNET_PIXAL: {"unet_name": "pixal3d_bf16.safetensors"},
        N_SWITCH_BACKEND: {"value": backend == "trellis2"},
        N_TEX_RES: {"value": tex},
        N_DECIMATE: {"target_face_count": tris} if tris else {},
        N_SAVE: {"filename_prefix": "3d/envlab/asset"},
        N_REMOVE_BG_SWITCH: {"switch": remove_bg},
    }
    for k in (N_KS_STRUCT, N_KS_SHAPE, N_KS_UP, N_KS_TEX):
        ov[k] = {"seed": seed}
    api = comfy.ui_to_api(wf, info, keep_outputs=[N_SAVE], overrides=ov)
    # sanity: input names we override must exist on those nodes
    for nid, kv in ov.items():
        node = api.get(str(nid))
        if node is None:
            continue
        for key in kv:
            if key not in node["inputs"]:
                print(f"  WARN override {key} not an input of node {nid} ({node['class_type']}); inputs={list(node['inputs'])}")
    return api


def generate(image, name, backend="pixal3d", seed=42, tex=2048, tris=200000, log=print):
    os.makedirs(OUT, exist_ok=True)
    if not comfy.alive():
        raise SystemExit("ComfyUI is not running on " + comfy.BASE)
    up = comfy.upload_image(image)
    log(f"UPLOADED {up}")
    api = build_prompt(up, backend, seed, tex, tris)
    with open(os.path.join(OUT, f"{name}.prompt.json"), "w", encoding="utf-8") as f:
        json.dump(api, f, indent=1)
    t0 = time.time()
    pid = comfy.queue(api)
    entry = comfy.wait(pid, log=log)
    files = comfy.output_files(entry)
    glbs = [f for f in files if f.lower().endswith(".glb")]
    if not glbs:
        # Save3DAdvanced may not report through history; fall back to newest file under output/3d/envlab
        cands = sorted(glob.glob(os.path.join(comfy.COMFY_DIR, "output", "3d", "envlab", "*.glb")), key=os.path.getmtime)
        glbs = cands[-1:]
    if not glbs:
        raise RuntimeError(f"no GLB produced; outputs={files}")
    dst = os.path.join(OUT, f"{name}.glb")
    shutil.copyfile(glbs[-1], dst)
    log(f"GLB {dst} ({os.path.getsize(dst)/1e6:.1f} MB) in {time.time()-t0:.0f}s via {backend}")
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--backend", default="pixal3d", choices=["pixal3d", "trellis2"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--tris", type=int, default=200000)
    a = ap.parse_args()
    generate(a.image, a.name, a.backend, a.seed, a.tex, a.tris)


if __name__ == "__main__":
    main()
