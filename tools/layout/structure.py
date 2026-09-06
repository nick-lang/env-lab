"""Structure node for the world compiler: a rectangular multi-floor building solved by WFC.

world.json:
  "structures": [{"id": "hall", "intent": "...", "at": [x_cm, y_cm], "grid": [20, 20, 3], "cell": [4, 4, 3.5],
                  "seed": 3, "doors": [[10, 0, "-y"]], "stairs": [[4, 4, 0, "+y"], [14, 14, 1, "+y"]],
                  "kit_root": "/Game/Meshes/Kit", "kit_bounds": "build/kit/kit_bounds.json"}]

place(node, base_z_cm) -> (layers, cells, report)
  layers: {mesh_path: [[loc_cm, rot, scale], ...]}
  cells:  {(x,y,z): tile_name}
  report: validator counts (socket mismatches, cross-cell overlaps, uncovered cells)
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wfc import FACES, DELTA, OPP, compatible, kit_tiles, solve  # noqa: E402
from masonry import Masonry, rotate_xy  # noqa: E402

ROT_K = {"+y": 0, "-x": 1, "-y": 2, "+x": 3}  # which rotation puts the base +y face on the given side
BLOCKED = {"SM_Kit_Floor", "SM_Kit_Wall", "SM_Kit_WallWindow", "SM_Kit_WallDoor", "SM_Kit_WallAlcove", "SM_Kit_Pillar", "SM_Kit_Parapet", "$quoin"}


def dress(mesh, mas, W, D, H, ft, salt):
    """Kit piece -> [(core_mesh or None, [block placements])] in the piece's local frame (+Y wall face)."""
    T = 0.4
    yf = D / 2
    if mesh == "SM_Kit_Floor":
        return [("SM_Kit_FloorCore", mas.floor(W, D, seed_salt=salt, z_top=0.0))]
    if mesh in ("SM_Kit_Wall", "SM_Kit_WallAlcove"):
        return [("SM_Kit_WallCore", mas.wall(W, H, T, None, seed_salt=salt, y_face=yf))]
    if mesh == "SM_Kit_WallWindow":
        blocks = mas.wall(W, H, T, (-0.7, 0.7, 1.1, 2.6), seed_salt=salt, y_face=yf)
        blocks += mas.lintel(-0.95, 0.95, 2.75, T, yf, seed_salt=salt)
        blocks += mas.lintel(-0.95, 0.95, 0.98, T, yf, seed_salt=salt + 1)
        return [("SM_Kit_WallCoreWindow", blocks)]
    if mesh == "SM_Kit_WallDoor":
        blocks = mas.wall(W, H, T, (-0.8, 0.8, 0.0, 2.6), seed_salt=salt, y_face=yf)
        blocks += mas.lintel(-1.05, 1.05, 2.75, T, yf, seed_salt=salt)
        return [("SM_Kit_WallCoreDoor", blocks)]
    if mesh == "SM_Kit_Pillar":
        return [(None, mas.pillar(H, side=0.6, seed_salt=salt))]
    if mesh == "$quoin":
        # corner stack covering the seam where the two wall cores meet (base orientation: +x/+y corner)
        cx, cy = W / 2 - 0.22, D / 2 - 0.22
        blocks = [(bm, (bx + cx, by + cy, bz), rot, scl) for bm, (bx, by, bz), rot, scl in mas.pillar(H, side=0.48, seed_salt=salt + 7)]
        return [(None, blocks)]
    if mesh == "SM_Kit_Parapet":
        blocks = [(bm, (bx, by, bz + H + ft), rot, scl) for bm, (bx, by, bz), rot, scl in mas.wall(W, 1.0, T, None, seed_salt=salt, y_face=yf, missing=0.0)]
        return [("SM_Kit_ParapetCore", blocks)]
    return [(mesh, [])]


def place(node, base_z_cm, log=print):
    gx, gy, gz = node["grid"]
    cell = node.get("cell", [4.0, 4.0, 3.5])
    W, D, H = cell
    ft = float(node.get("floor_thickness", 0.3))
    pitch = H + ft
    X, Y, Z = gx + 2, gy + 2, gz  # one-cell exterior ring
    tiles = kit_tiles(cell)
    pins = {}
    for cx, cy, side in node.get("doors", []):
        pins[(cx + 1, cy + 1, 0)] = {f"WALL_D@{ROT_K[side] * 90}"}
    for cx, cy, cz, side in node.get("stairs", []):
        pins[(cx + 1, cy + 1, cz)] = {f"STAIR@{ROT_K[side] * 90}"}
    top = Z - 1

    def allowed(x, y, z):
        if (x, y, z) in pins:
            return pins[(x, y, z)]
        if x == 0 or y == 0 or x == X - 1 or y == Y - 1:
            return {"EXT"}
        base = {"ROOM", "ROOM_P", "WALL", "WALL_W", "WALL_A", "CORNER", "HOLE"}
        if z < top:
            base.add("STAIR") if False else None  # stairs only where pinned
        return base

    grid = solve((X, Y, Z), tiles, allowed, seed=int(node.get("seed", 1)), log=log)
    if grid is None:
        raise SystemExit(f"WFC failed for structure {node['id']}")

    # ---- pieces
    masonry = None
    lib = node.get("library")
    if node.get("dressing") == "blocks" and lib and os.path.isfile(lib):
        masonry = Masonry(json.load(open(lib, encoding="utf-8")), seed=int(node.get("seed", 1)))
    ox, oy = node["at"]
    layers = {}
    cells = {}
    root = node.get("kit_root", "/Game/Meshes/Kit")
    for x in range(X):
        for y in range(Y):
            for z in range(Z):
                name = grid[x][y][z]
                t = tiles[name]
                cells[(x, y, z)] = name
                if t.base == "EXT":
                    continue
                cx = ox + (x - 1) * W * 100.0
                cy = oy + (y - 1) * D * 100.0
                cz = base_z_cm + z * pitch * 100.0
                pcs = list(t.pieces)
                if masonry is not None and t.base == "CORNER":
                    pcs.append(("$quoin", (0, 0, 0), t.rot))
                if z == top and t.base != "HOLE":
                    pcs.append(("SM_Kit_Ceiling", (0, 0, 0), 0))
                    for f in ("+x", "-x", "+y", "-y"):
                        if t.sockets[f] == "out":
                            pcs.append(("SM_Kit_Parapet", (0, 0, 0), ROT_K[f] * 90))
                for pi, (mesh, off, yaw) in enumerate(pcs):
                    loc = [round(cx + off[0] * 100.0, 2), round(cy + off[1] * 100.0, 2), round(cz + off[2] * 100.0, 2)]
                    cellinfo = [x - 1, y - 1, z, name]
                    if masonry is None or mesh not in BLOCKED:
                        layers.setdefault(f"{root}/{mesh}", []).append([loc, [0.0, float(yaw % 360), 0.0], [1.0, 1.0, 1.0], cellinfo])
                        continue
                    salt = ((x * 131 + y) * 131 + z) * 16 + pi
                    for core, blocks in dress(mesh, masonry, W, D, H, ft, salt):
                        if core:
                            layers.setdefault(f"{root}/{core}", []).append([loc, [0.0, float(yaw % 360), 0.0], [1.0, 1.0, 1.0], cellinfo])
                        for bmesh, (bx, by, bz), (bp, byaw, br), (sx, sy, sz) in blocks:
                            rx, ry = rotate_xy(bx, by, yaw)
                            bloc = [round(cx + rx * 100.0, 2), round(cy + ry * 100.0, 2), round(cz + bz * 100.0, 2)]
                            layers.setdefault(f"{masonry.root}/{bmesh}", []).append([bloc, [round(bp, 3), round((byaw + yaw) % 360, 3), round(br, 3)], [round(sx, 4), round(sy, 4), round(sz, 4)], cellinfo])

    # ---- validator
    mismatches = 0
    for x in range(X):
        for y in range(Y):
            for z in range(Z):
                a = tiles[grid[x][y][z]]
                for f in ("+x", "+y", "+z"):
                    dx, dy, dz = DELTA[f]
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if not (0 <= nx < X and 0 <= ny < Y and 0 <= nz < Z):
                        continue
                    b = tiles[grid[nx][ny][nz]]
                    if not compatible(a.sockets[f], b.sockets[OPP[f]]):
                        mismatches += 1
    uncovered = 0
    for (x, y, z), name in cells.items():
        t = tiles[name]
        if t.base in ("EXT", "HOLE"):
            continue
        if not any(m == "SM_Kit_Floor" for m, _, _ in t.pieces):
            uncovered += 1
    overlaps = 0
    bounds_path = node.get("kit_bounds")
    if bounds_path and os.path.isfile(bounds_path):
        kb = json.load(open(bounds_path, encoding="utf-8"))
        boxes = []
        for mesh, insts in layers.items():
            mname = mesh.rsplit("/", 1)[-1]
            if mname not in kb:
                continue
            (bx0, by0, bz0), (bx1, by1, bz1) = kb[mname]
            for loc, rot, _s, cellinfo in insts:
                yaw = math.radians(rot[1])
                c, s = math.cos(yaw), math.sin(yaw)
                xs, ys = [], []
                for px, py in ((bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)):
                    xs.append(px * c - py * s)
                    ys.append(px * s + py * c)
                boxes.append((loc[0] + min(xs) * 100, loc[1] + min(ys) * 100, loc[2] + bz0 * 100,
                              loc[0] + max(xs) * 100, loc[1] + max(ys) * 100, loc[2] + bz1 * 100, tuple(cellinfo[:3])))
        eps = 1.0  # cm tolerance for touching faces
        for i in range(len(boxes)):
            a = boxes[i]
            for j in range(i + 1, len(boxes)):
                b = boxes[j]
                if a[6] == b[6]:
                    continue  # same cell: pieces are designed to meet
                if a[0] + eps < b[3] and b[0] + eps < a[3] and a[1] + eps < b[4] and b[1] + eps < a[4] and a[2] + eps < b[5] and b[2] + eps < a[5]:
                    overlaps += 1
    n_cells = sum(1 for n in cells.values() if tiles[n].base != "EXT")
    report = {"cells": n_cells, "pieces": sum(len(v) for v in layers.values()), "socket_mismatches": mismatches,
              "cross_cell_overlaps": overlaps, "uncovered_cells": uncovered,
              "tiles": {b: sum(1 for n in cells.values() if tiles[n].base == b) for b in sorted({tiles[n].base for n in cells.values()})}}
    log(f"STRUCTURE {node['id']}: {report}")
    return layers, cells, report
