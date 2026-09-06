"""Asset library batches: concept → image-to-3D → cleanup for N variants of a class of thing.

  py -3 tools/asset/library.py experiments/08-modular-kit/blocks.json [--only large] [--backend trellis2]

Spec: {"name": "blocks", "out": "build/library/blocks", "classes": [
         {"id": "large", "prompt": "...", "count": 6, "seed": 100, "dims": [0.8, 0.45, 0.4], "tris": 30000, "center": true}]}

Writes <out>/<class>_<i>.glb, <out>/fbx/<class>_<i>.fbx (+ textures) and <out>/manifest.json:
  {"classes": {"large": {"dims": [...], "meshes": ["SM_blocks_large_0", ...]}}, "mesh_root": "/Game/Meshes/<name>"}
Resumable: existing GLB/FBX files are skipped.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "asset"))
import concept  # noqa: E402
import generate3d  # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


def clean(src, dst, dims=None, height=None, center=False, uniform=False, tris=None, align=False):
    args = [BLENDER, "--background", "--python", os.path.join(ROOT, "tools", "blender", "clean_glb.py"), "--", src, dst]
    if dims:
        args += ["--dims"] + [str(v) for v in dims]
    if height:
        args += ["--height", str(height)]
    if center:
        args += ["--center"]
    if uniform:
        args += ["--uniform"]
    if align:
        args += ["--align"]
    if tris:
        args += ["--tris", str(tris)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = "CLEAN_DONE" in (r.stdout or "")
    return ok, [l for l in (r.stdout or "").splitlines() if "CLEAN_DONE" in l or "Error" in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only")
    ap.add_argument("--backend", default="trellis2")
    ap.add_argument("--concepts-only", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    out = os.path.join(ROOT, spec["out"])
    fbx_dir = os.path.join(out, "fbx")
    os.makedirs(fbx_dir, exist_ok=True)
    manifest_path = os.path.join(out, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8")) if os.path.isfile(manifest_path) else {"classes": {}, "mesh_root": f"/Game/Meshes/{spec['name']}"}
    t0 = time.time()
    for cls in spec["classes"]:
        if a.only and cls["id"] != a.only:
            continue
        meshes = []
        for i in range(int(cls["count"])):
            seed = int(cls.get("seed", 1)) + i
            name = f"SM_{spec['name']}_{cls['id']}_{i}"
            png = os.path.join(ROOT, "build", "concepts", f"{spec['name']}_{cls['id']}_{seed}.png")
            if not os.path.isfile(png):
                concept.generate(f"{spec['name']}_{cls['id']}", cls["prompt"], n=1, seed=seed, log=lambda *_: None)
                print(f"CONCEPT {name}")
            if a.concepts_only:
                continue
            glb = os.path.join(out, name + ".glb")
            if not os.path.isfile(glb):
                try:
                    generate3d.generate(png, name, a.backend, seed=42 + i, tex=cls.get("tex", 1024), tris=cls.get("tris", 30000), log=lambda *_: None)
                except Exception as e:
                    print(f"GEN_FAILED {name}: {e}")
                    continue
                src = os.path.join(ROOT, "build", "gen3d", name + ".glb")
                os.replace(src, glb)
                print(f"GLB {name} ({time.time() - t0:.0f}s)")
            fbx = os.path.join(fbx_dir, name + ".fbx")
            if not os.path.isfile(fbx):
                ok, lines = clean(glb, fbx, dims=cls.get("dims"), height=cls.get("height"), center=cls.get("center", False), uniform=cls.get("uniform", False), align=cls.get("align", False))
                print(("CLEAN " if ok else "CLEAN_FAILED ") + name + " " + " ".join(lines)[:120])
                if not ok:
                    continue
            meshes.append(name)
        if not a.concepts_only:
            manifest["classes"][cls["id"]] = {"dims": cls.get("dims"), "height": cls.get("height"), "meshes": meshes}
            json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), indent=1)
    print(f"LIBRARY_DONE {manifest_path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
