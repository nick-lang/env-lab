"""World compiler: world.json -> deterministic placement plan + manifest (+ terrain build).

  py -3 tools/world/compile.py experiments/05-world-file/world.json build/world/barrow [--no-terrain]

Outputs in <out>:
  terrain/            height.npy, meta.json, SM_Terrain.fbx (via tools/terrain + tools/blender)
  plan.json           everything the Unreal builder needs: terrain, actors, hism layers, look, player
  manifest.json       id -> {kind, node, rule, intent, transform, mesh}: the ID spine
  hash.txt            sha256 of plan.json, for the determinism gate

The compiler owns placement. The engine is a renderer. Ground heights come from the heightmap,
never from engine traces, so two compiles of the same file are byte-identical.
"""
import hashlib
import json
import math
import os
import random
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "layout"))
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


# ----------------------------------------------------------------------------- ground
class Ground:
    def __init__(self, tdir):
        meta = json.load(open(os.path.join(tdir, "meta.json"), encoding="utf-8"))
        self.h = np.load(os.path.join(tdir, "height.npy")).astype(np.float64)
        self.x0, self.y0 = meta["origin"]
        self.sp = meta["spacing"]
        self.res = meta["res"]
        gy, gx = np.gradient(self.h, self.sp)
        self.gx, self.gy = gx, gy

    def _cell(self, x_cm, y_cm):
        fx = (x_cm / 100.0 - self.x0) / self.sp
        fy = (y_cm / 100.0 - self.y0) / self.sp
        i = int(np.clip(np.floor(fx), 0, self.res - 2))
        j = int(np.clip(np.floor(fy), 0, self.res - 2))
        u = float(np.clip(fx - i, 0, 1))
        v = float(np.clip(fy - j, 0, 1))
        return i, j, u, v

    def z(self, x_cm, y_cm):
        i, j, u, v = self._cell(x_cm, y_cm)
        h = self.h
        return float(h[j, i] * (1 - u) * (1 - v) + h[j, i + 1] * u * (1 - v) + h[j + 1, i] * (1 - u) * v + h[j + 1, i + 1] * u * v) * 100.0

    def normal(self, x_cm, y_cm):
        i, j, u, v = self._cell(x_cm, y_cm)
        gx = float(self.gx[j, i] * (1 - u) + self.gx[j, i + 1] * u)
        gy = float(self.gy[j, i] * (1 - v) + self.gy[j + 1, i] * v)
        n = np.array([-gx, -gy, 1.0])
        n /= np.linalg.norm(n)
        return n  # meters/meters slope -> unit normal, same in cm

    def slope_deg(self, x_cm, y_cm):
        return math.degrees(math.acos(max(-1.0, min(1.0, float(self.normal(x_cm, y_cm)[2])))))


# ----------------------------------------------------------------------------- noise (matches ue_e1_scatter)
def _h(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 4294967295.0


def vnoise(x, y, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _h(ix, iy, seed), _h(ix + 1, iy, seed)
    c, d = _h(ix, iy + 1, seed), _h(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def clump_noise(x_m, y_m, scale, seed):
    return 0.6 * vnoise(x_m / scale, y_m / scale, seed) + 0.4 * vnoise(x_m / scale * 2.3 + 7, y_m / scale * 2.3 + 3, seed + 1)


def stable_seed(*parts):
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def rot_from_normal(n, yaw_deg):
    """Rotator (pitch, yaw, roll) whose up axis is n, matching Unreal's MakeRotFromZX(n, forward(yaw))."""
    fwd = np.array([math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg)), 0.0])
    z = n / np.linalg.norm(n)
    x = fwd - z * float(np.dot(fwd, z))
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    # Unreal rotator from a rotation matrix with rows X (forward), Y (right), Z (up)
    pitch = math.degrees(math.atan2(x[2], math.hypot(x[0], x[1])))
    yaw = math.degrees(math.atan2(x[1], x[0]))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    syaxis = np.array([-sy, cy, 0.0])
    roll = math.degrees(math.atan2(float(np.dot(z, syaxis)), float(np.dot(y, syaxis))))
    return [round(pitch, 3), round(yaw, 3), round(roll, 3)]


# ----------------------------------------------------------------------------- compile
def compile_world(world, out, build_terrain=True):
    os.makedirs(out, exist_ok=True)
    tdir = os.path.join(out, "terrain")
    seed = int(world["meta"]["seed"])

    if build_terrain:
        params = dict(world["terrain"]["params"])
        params["seed"] = params.get("seed", seed)
        pjson = os.path.join(out, "terrain_params.json")
        json.dump(params, open(pjson, "w", encoding="utf-8"), indent=1)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "terrain", "heightmap.py"), pjson, tdir], capture_output=True, text=True)
        if "HEIGHTMAP_DONE" not in r.stdout:
            raise SystemExit("heightmap failed:\n" + r.stdout + r.stderr)
        r = subprocess.run([BLENDER, "--background", "--python", os.path.join(ROOT, "tools", "blender", "gen_terrain.py"), "--", tdir, "--no-vcol"], capture_output=True, text=True)
        if "TERRAIN_EXPORTED" not in r.stdout:
            raise SystemExit("terrain export failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
        # gen_terrain names the mesh SM_Terrain_E1; keep the name stable for the builder
    g = Ground(tdir)

    manifest = {}
    actors = []
    hism = []

    def place_actor(rec, kind, node, intent, rule=None):
        manifest[rec["id"]] = {"kind": kind, "node": node, "intent": intent, "rule": rule,
                               "transform": {"loc": rec["loc"], "rot": rec.get("rot", [0, 0, 0]), "scale": rec.get("scale", [1, 1, 1])},
                               "mesh": rec.get("mesh")}
        actors.append(rec)

    # terrain actor
    place_actor({"id": "terrain", "class": "StaticMeshActor", "mesh": "$terrain", "materials": [world["terrain"].get("material")],
                 "loc": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1], "collision": "complex"},
                "terrain", "terrain", world["terrain"]["intent"], rule="heightmap")

    # look
    look = world["look"]
    for key in ("sun", "sky", "atmosphere", "fog", "clouds", "grade"):
        if key not in look:
            continue
        L = look[key]
        rec = {"id": f"look.{key}", "class": L["class"], "loc": [0, 0, 1000 if key == "sun" else 0], "rot": L.get("rot", [0, 0, 0]), "scale": [1, 1, 1],
               "props": L.get("props", {}), "settings": L.get("settings"), "unbound": L.get("unbound")}
        place_actor(rec, "look", "look", look["intent"], rule=key)

    # sites + props: parts are ground-relative
    for group_key, kind in (("sites", "site"), ("props", "prop")):
        for node in world.get(group_key, []):
            for p in node.get("parts", []):
                x, y = p["at"]
                rec = {"id": p["id"], "class": "StaticMeshActor", "mesh": p["mesh"], "materials": p.get("materials"),
                       "loc": [x, y, round(g.z(x, y) + p["above_ground"], 2)], "rot": p.get("rot", [0, 0, 0]), "scale": p.get("scale", [1, 1, 1])}
                place_actor(rec, kind, node["id"], p.get("intent", node["intent"]), rule="ground+offset")
            for l in node.get("lights", []):
                x, y = l["at"]
                rec = {"id": l["id"], "class": l["class"], "loc": [x, y, round(g.z(x, y) + l["above_ground"], 2)], "rot": [0, 0, 0], "scale": [1, 1, 1], "props": l.get("props", {})}
                place_actor(rec, kind, node["id"], l.get("intent", node["intent"]), rule="ground+offset")

    # paths
    for path in world.get("paths", []):
        c = path["curve"]
        n = int(path["count"])
        for i in range(n):
            y = c["y0"] + (c["y1"] - c["y0"]) * i / (n - 1)
            x = c["amp"] * math.sin(2.0 * math.pi * (y - c["y0"]) / c["period"])
            dx = c["amp"] * math.sin(2.0 * math.pi * (y + 40 - c["y0"]) / c["period"]) - c["amp"] * math.sin(2.0 * math.pi * (y - 40 - c["y0"]) / c["period"])
            yaw = math.degrees(math.atan2(80.0, -dx)) - 90.0 + path.get("yaw_jitter", 0.0) * math.sin(i * 2.7)
            rec = {"id": f"{path['id']}.{i:02d}", "class": "StaticMeshActor", "mesh": path["mesh"], "materials": path.get("materials"),
                   "loc": [round(x, 2), round(y, 2), round(g.z(x, y) + path["above_ground"], 2)], "rot": [0.0, round(yaw, 3), 0.0], "scale": path["scale"]}
            place_actor(rec, "path", path["id"], path["intent"], rule=f"{path['kind']} on sine curve")

    # biomes: scatter layers -> HISM instances (deterministic)
    for biome in world.get("biomes", []):
        P = biome["path"]
        pts = [(P["amp"] * math.sin(2.0 * math.pi * (y - P["y0"]) / P["period"]), y)
               for y in [P["y0"] + (P["y1"] - P["y0"]) * i / 99.0 for i in range(100)]]
        gate = (biome["gate"]["x"], biome["gate"]["y"])

        def path_dist_m(x, y):
            return math.sqrt(min((x - px) ** 2 + (y - py) ** 2 for px, py in pts)) / 100.0

        for layer in biome["layers"]:
            R = layer["rules"]
            lseed = stable_seed(seed, layer["id"])
            rng = random.Random(lseed)
            meshes = layer["meshes"]
            weights = layer.get("weights") or [1.0] * len(meshes)
            x0, y0, x1, y1 = R["region"]
            attempts = int((x1 - x0) * (y1 - y0) * R["attempts_per_m2"])
            nz = R.get("noise")
            per_mesh = [[] for _ in meshes]
            placed = 0
            max_count = R.get("max_count", 1 << 30)
            for _ in range(attempts):
                if placed >= max_count:
                    break
                xm = rng.uniform(x0, x1)
                ym = rng.uniform(y0, y1)
                xc, yc = xm * 100.0, ym * 100.0
                pdm = path_dist_m(xc, yc)
                if pdm < R.get("path_min", 0.0) or pdm > R.get("path_max", 1e9):
                    continue
                if math.hypot(xc - gate[0], yc - gate[1]) / 100.0 < R.get("gate_min", 0.0):
                    continue
                if nz and clump_noise(xm, ym, nz["scale"], lseed & 0xFFFF) < nz["threshold"]:
                    continue
                slope = g.slope_deg(xc, yc)
                if slope < R.get("slope_min", 0.0) or slope > R.get("slope_max", 90.0):
                    continue
                boost = R.get("slope_boost")
                if boost and slope < boost and rng.random() < 0.5:
                    continue
                idx = rng.choices(range(len(meshes)), weights=weights)[0]
                s = rng.uniform(*R["scale"])
                yaw = rng.uniform(0, 360)
                rot = rot_from_normal(g.normal(xc, yc), yaw) if R.get("align_to_slope") else [0.0, round(yaw, 3), 0.0]
                z = g.z(xc, yc) - R.get("sink", 0.0) * s * 100.0 * layer.get("height_m", 1.0)
                per_mesh[idx].append([[round(xc, 2), round(yc, 2), round(z, 2)], rot, [round(s, 4)] * 3])
                placed += 1
            for mi, m in enumerate(meshes):
                lid = f"{layer['id']}.{mi}"
                hism.append({"id": lid, "mesh": m, "material_slots": layer.get("materials", {}).get("slots", []), "instances": per_mesh[mi]})
                manifest[lid] = {"kind": "scatter", "node": biome["id"], "intent": layer["intent"], "rule": R, "mesh": m,
                                 "count": len(per_mesh[mi]), "instances": per_mesh[mi]}

    # structures (WFC-solved buildings from the modular kit)
    for node in world.get("structures", []):
        import structure as _structure
        ax, ay = node["at"]
        base_z = g.z(ax, ay) + float(node.get("above_ground", 0.0))
        node = dict(node)
        if node.get("kit_bounds") and not os.path.isabs(node["kit_bounds"]):
            node["kit_bounds"] = os.path.join(ROOT, node["kit_bounds"])
        layers, cells, report = _structure.place(node, base_z)
        for mesh, insts in layers.items():
            lid = f"structure.{node['id']}.{mesh.rsplit('/', 1)[-1]}"
            hism.append({"id": lid, "mesh": mesh, "material_slots": [], "instances": [[loc, rot, scl] for loc, rot, scl, _c in insts]})
            manifest[lid] = {"kind": "structure", "node": node["id"], "intent": node.get("intent", ""), "rule": "wfc:" + str(node.get("seed", 1)),
                             "mesh": mesh, "count": len(insts), "cells": [c for _l, _r, _s, c in insts]}
        manifest[f"structure.{node['id']}"] = {"kind": "structure", "node": node["id"], "intent": node.get("intent", ""), "rule": {k: v for k, v in node.items() if k != "kit_bounds"}, "report": report}

    # player
    pl = world["player"]
    x, y = pl["at"]
    actors.append({"id": pl["id"], "class": "PlayerStart", "loc": [x, y, round(g.z(x, y) + pl["above_ground"], 2)], "rot": [0, pl.get("yaw", 0), 0], "scale": [1, 1, 1]})
    manifest[pl["id"]] = {"kind": "player", "node": "player", "intent": "where the walk begins", "rule": "ground+offset"}

    plan = {"meta": world["meta"], "terrain": {"fbx": "terrain/SM_Terrain_E1.fbx", "mesh_name": "SM_Terrain_E1"}, "materials": world.get("materials", {}),
            "actors": actors, "hism": hism, "game_mode": pl.get("game_mode"), "shots": world.get("shots", [])}
    plan_json = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        f.write(plan_json)
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=0, sort_keys=True)
    digest = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
    with open(os.path.join(out, "hash.txt"), "w", encoding="utf-8") as f:
        f.write(digest + "\n")
    n_inst = sum(len(l["instances"]) for l in hism)
    print(f"COMPILE_DONE actors={len(actors)} hism_layers={len(hism)} instances={n_inst} ids={len(manifest)} hash={digest[:16]}")
    return digest


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    build_terrain = "--no-terrain" not in sys.argv
    world = json.load(open(src, encoding="utf-8"))
    compile_world(world, out, build_terrain)


if __name__ == "__main__":
    main()
