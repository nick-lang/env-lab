"""Experiment 03 orchestrator: concept image → Pixal3D/TRELLIS.2 → Blender cleanup → Unreal swap → snaps.

  py -3 tools/run_e3.py --gen [--backend pixal3d|trellis2] [--only NAME]   # image→GLB for each asset in e3.json
  py -3 tools/run_e3.py --clean                                            # GLB→FBX (dims/origin)
  py -3 tools/run_e3.py --swap --scatter --snap                            # Unreal side
  py -3 tools/run_e3.py --restore                                          # put E01 meshes back
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "03-asset-factory")
BUILD = os.path.join(ROOT, "build")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
REMOTE = os.path.join(ROOT, "tools", "ue", "remote.py")
sys.path.insert(0, os.path.join(ROOT, "tools", "asset"))


def run(cmd, must=None):
    print(">>", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    keep = [l for l in out.splitlines() if l.strip() and not l.startswith("[Info]   ")]
    print("\n".join(keep[-30:]))
    if p.returncode != 0 or (must and must not in out):
        print(f"STEP FAILED (rc={p.returncode}, expected '{must}')")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    for f in ("gen", "clean", "swap", "scatter", "snap", "restore"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--backend", default="pixal3d")
    ap.add_argument("--only")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--tris", type=int, default=120000)
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(EXP, "e3.json"), encoding="utf-8"))
    assets = [x for x in cfg["assets"] if not a.only or x["name"] == a.only]

    if a.gen:
        import generate3d
        for x in assets:
            img = os.path.join(BUILD, "concepts", x["concept"] + ".png")
            generate3d.generate(img, x["name"], a.backend, a.seed, a.tex, a.tris)
    if a.clean:
        for x in assets:
            src = os.path.join(BUILD, "gen3d", x["name"] + ".glb")
            dst = os.path.join(BUILD, "gen3d", "fbx", x["name"] + ".fbx")
            args = [BLENDER, "--background", "--python", os.path.join(ROOT, "tools", "blender", "clean_glb.py"), "--", src, dst]
            if "dims" in x:
                args += ["--dims"] + [str(v) for v in x["dims"]]
            if "height" in x:
                args += ["--height", str(x["height"])]
            if x.get("center"):
                args += ["--center"]
            if x.get("fit") == "uniform":
                args += ["--uniform"]
            run(args, must="CLEAN_DONE")
    if a.restore or a.swap:
        cfg2 = dict(cfg)
        cfg2["restore"] = bool(a.restore)
        json.dump(cfg2, open(os.path.join(EXP, "e3.json"), "w", encoding="utf-8"), indent=2)
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e3_swap.py")], must="E3_SWAP_DONE")
        cfg2["restore"] = False
        json.dump(cfg2, open(os.path.join(EXP, "e3.json"), "w", encoding="utf-8"), indent=2)
    if a.scatter:
        open(os.path.join(BUILD, "active_rules.txt"), "w").write(os.path.join(EXP, "scatter_rules.json").replace("\\", "/"))
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_scatter.py")], must="SCATTER_DONE")
        os.remove(os.path.join(BUILD, "active_rules.txt"))
    if a.snap:
        open(os.path.join(BUILD, "active_shots.txt"), "w").write(os.path.join(EXP, "shots.json").replace("\\", "/"))
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_snap.py")], must="SNAP_DONE")
        os.remove(os.path.join(BUILD, "active_shots.txt"))
    print("RUN_E3_OK")


if __name__ == "__main__":
    main()
