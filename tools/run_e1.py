"""Experiment 01 orchestrator. Runs the factories in order; each step is idempotent.

  py -3 tools/run_e1.py --all
  py -3 tools/run_e1.py --terrain --kit      # regenerate inputs only
  py -3 tools/run_e1.py --setup --scatter --snap
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "01-barrow-density")
BUILD = os.path.join(ROOT, "build")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
REMOTE = os.path.join(ROOT, "tools", "ue", "remote.py")


def run(cmd, must=None):
    print(">>", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    keep = [l for l in out.splitlines() if l.strip() and not l.startswith("[Info]   ")]
    print("\n".join(keep[-40:]))
    if p.returncode != 0 or (must and must not in out):
        print(f"STEP FAILED (rc={p.returncode}, expected '{must}')")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    for f in ("all", "terrain", "kit", "setup", "scatter", "snap"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    do = lambda k: a.all or getattr(a, k)

    if do("terrain"):
        run([sys.executable, os.path.join(ROOT, "tools", "terrain", "heightmap.py"),
             os.path.join(EXP, "terrain.json"), os.path.join(BUILD, "terrain")], must="HEIGHTMAP_DONE")
        run([BLENDER, "--background", "--python", os.path.join(ROOT, "tools", "blender", "gen_terrain.py"),
             "--", os.path.join(BUILD, "terrain")], must="TERRAIN_EXPORTED")
    if do("kit"):
        run([BLENDER, "--background", "--python", os.path.join(ROOT, "tools", "blender", "gen_rocks.py"),
             "--", os.path.join(BUILD, "assets")], must="KIT_DONE")
    if do("setup"):
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_setup.py")], must="E1_SETUP_DONE")
    if do("scatter"):
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_scatter.py")], must="SCATTER_DONE")
    if do("snap"):
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_snap.py")], must="SNAP_DONE")
    print("RUN_E1_OK")


if __name__ == "__main__":
    main()
