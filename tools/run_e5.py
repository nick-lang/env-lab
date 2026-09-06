"""E05 orchestrator: world.json -> compile -> build in Unreal -> snaps -> addressability test.

  py -3 tools/run_e5.py --author          # bootstrap world.json from the E1/E3 scene export (one time)
  py -3 tools/run_e5.py --compile         # world.json -> build/world/barrow (terrain + plan + manifest + hash)
  py -3 tools/run_e5.py --determinism     # compile twice into two dirs, compare hashes
  py -3 tools/run_e5.py --build --snap --pick
  py -3 tools/run_e5.py --resolve         # picks.json x manifest.json -> id / rule / intent table
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "05-world-file")
BUILD = os.path.join(ROOT, "build")
WORLD = os.path.join(EXP, "world.json")
OUT = os.path.join(BUILD, "world", "barrow")
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
    return out


def main():
    ap = argparse.ArgumentParser()
    for f in ("author", "compile", "determinism", "build", "snap", "pick", "resolve", "measure"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--tag", default="W")
    ap.add_argument("--world")
    ap.add_argument("--out")
    a = ap.parse_args()
    global WORLD, OUT, EXP
    if a.world:
        WORLD = os.path.abspath(a.world)
        EXP = os.path.dirname(WORLD)
    if a.out:
        OUT = os.path.abspath(a.out)

    if a.author:
        run([sys.executable, os.path.join(ROOT, "tools", "world", "author_barrow.py")], must="WORLD_WRITTEN")
    if a.compile:
        run([sys.executable, os.path.join(ROOT, "tools", "world", "compile.py"), WORLD, OUT], must="COMPILE_DONE")
    if a.determinism:
        d1, d2 = OUT + "_run1", OUT + "_run2"
        for d in (d1, d2):
            shutil.rmtree(d, ignore_errors=True)
            run([sys.executable, os.path.join(ROOT, "tools", "world", "compile.py"), WORLD, d], must="COMPILE_DONE")
        h1 = open(os.path.join(d1, "hash.txt")).read().strip()
        h2 = open(os.path.join(d2, "hash.txt")).read().strip()
        same_plan = open(os.path.join(d1, "plan.json"), "rb").read() == open(os.path.join(d2, "plan.json"), "rb").read()
        print(f"DETERMINISM {'PASS' if h1 == h2 and same_plan else 'FAIL'} {h1[:16]} {h2[:16]}")
    if a.build:
        open(os.path.join(BUILD, "active_plan.txt"), "w").write(os.path.join(OUT, "plan.json").replace("\\", "/"))
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_build_world.py")], must="BUILD_WORLD_DONE")
    if a.snap:
        plan = json.load(open(os.path.join(OUT, "plan.json"), encoding="utf-8"))
        shots = {"prefix": f"{a.tag}_", "out": os.path.join(BUILD, "snaps", a.tag.lower()).replace("\\", "/"), "ground_labels": ["terrain"], "shots": plan["shots"]}
        sp = os.path.join(EXP, "shots.json")
        json.dump(shots, open(sp, "w", encoding="utf-8"), indent=1)
        open(os.path.join(BUILD, "active_shots.txt"), "w").write(sp.replace("\\", "/"))
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_e1_snap.py")], must="SNAP_DONE")
        os.remove(os.path.join(BUILD, "active_shots.txt"))
    if a.pick:
        plan = json.load(open(os.path.join(OUT, "plan.json"), encoding="utf-8"))
        cfg = {"seed": 5, "per_shot": 10, "shots": plan["shots"], "out": os.path.join(OUT, "picks.json").replace("\\", "/")}
        json.dump(cfg, open(os.path.join(BUILD, "active_pick.json"), "w", encoding="utf-8"))
        run([sys.executable, REMOTE, "--file", os.path.join(ROOT, "tools", "ue", "ue_pick.py")], must="PICK_DONE")
    if a.resolve:
        manifest = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
        picks = json.load(open(os.path.join(OUT, "picks.json"), encoding="utf-8"))
        ok = miss = sky = 0
        rows = []
        for p in picks:
            h = p["hit"]
            if not h:
                sky += 1
                continue
            lbl = h["label"]
            if lbl in manifest and manifest[lbl]["kind"] == "scatter" and h.get("item") is not None:
                inst_id = f"{lbl}:{h['item']}"
                m = manifest[lbl]
                ok += 1
                rows.append((p["shot"], inst_id, "scatter", str(m["rule"])[:60], m["intent"][:70]))
            elif lbl in manifest:
                m = manifest[lbl]
                ok += 1
                rows.append((p["shot"], lbl, m["kind"], str(m.get("rule"))[:60], str(m["intent"])[:70]))
            else:
                miss += 1
                rows.append((p["shot"], lbl, "UNRESOLVED", "", ""))
        for r in rows:
            print(" | ".join(r))
        print(f"RESOLVE resolved={ok} unresolved={miss} sky={sky} of {len(picks)}")
    if a.measure:
        run([sys.executable, os.path.join(ROOT, "tools", "measure.py"), os.path.join(BUILD, "snaps", a.tag.lower())])
    print("RUN_E5_OK")


if __name__ == "__main__":
    main()
