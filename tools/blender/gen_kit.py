"""Blender (headless): modular stone kit with exact grid dimensions and world-aligned UVs.

  blender --background --python tools/blender/gen_kit.py -- <out_dir> <kit_spec.json>

Cell: W x D x H metres (default 4 x 4 x 3.5). Every piece's origin is the cell's floor centre; the
wall pieces sit on the +Y face (rotated by the solver for other faces). Material slots by name:
Floor, Wall, Trim, Ceil — Unreal maps them to the E07 generated materials. UVs are planar per face
at 1 tile per `uv_m` metres so tiles line up across pieces.

Pieces: Floor, Ceiling, Wall, WallWindow, WallDoor, WallAlcove, Pillar, Stair, Parapet.
"""
import json
import os
import sys

import bpy
import bmesh
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]
SPEC = json.load(open(argv[1], encoding="utf-8"))
os.makedirs(OUT, exist_ok=True)
W, D, H = SPEC["cell"]
T = SPEC.get("wall_thickness", 0.4)
UVM = SPEC.get("uv_m", 2.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
MATS = {n: bpy.data.materials.new(n) for n in ("Floor", "Wall", "Trim", "Ceil", "Mortar", "Plaster")}
SLOT = {n: i for i, n in enumerate(MATS)}


def box(bm, lo, hi, slot, uv, side_slot=None):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = [bm.verts.new((x, y, z)) for x, y, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for f in faces:
        try:
            face = bm.faces.new([v[i] for i in f])
        except ValueError:
            continue
        face.normal_update()
        n = face.normal
        face.material_index = SLOT[side_slot] if (side_slot and abs(n.z) < 0.5) else SLOT[slot]
        for loop in face.loops:
            p = loop.vert.co
            if abs(n.z) > 0.5:
                loop[uv].uv = (p.x / UVM, p.y / UVM)
            elif abs(n.x) > 0.5:
                loop[uv].uv = (p.y / UVM, p.z / UVM)
            else:
                loop[uv].uv = (p.x / UVM, p.z / UVM)


def piece(name, builder):
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    builder(bm, uv)
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in MATS.values():
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    # bounds for the validator
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    bounds = [[round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)], [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)]]
    print(f"PIECE {name} tris={sum(len(p.vertices) - 2 for p in me.polygons)} bounds={bounds}")
    return ob, bounds


hw, hd = W / 2, D / 2
ft = SPEC.get("floor_thickness", 0.3)
yw0, yw1 = hd - T, hd  # wall slab y range on the +Y face


def floor(bm, uv):
    box(bm, (-hw, -hd, -ft), (hw, hd, 0.0), "Floor", uv, side_slot="Wall")


def ceiling(bm, uv):
    box(bm, (-hw, -hd, H), (hw, hd, H + ft), "Ceil", uv, side_slot="Wall")


def trims(bm, uv, x_ranges=((-hw, hw),)):
    for x0, x1 in x_ranges:
        box(bm, (x0, yw0 - 0.1, 0.0), (x1, yw0, 0.25), "Trim", uv)       # baseboard
    box(bm, (-hw, yw0 - 0.2, H - 0.2), (hw, yw0, H), "Trim", uv)         # cornice


def wall(bm, uv):
    box(bm, (-hw, yw0, 0.0), (hw, yw1, H), "Wall", uv)
    trims(bm, uv)


def wall_window(bm, uv):
    ox, z0, z1 = 0.7, 1.1, 2.6
    box(bm, (-hw, yw0, 0.0), (-ox, yw1, H), "Wall", uv)
    box(bm, (ox, yw0, 0.0), (hw, yw1, H), "Wall", uv)
    box(bm, (-ox, yw0, 0.0), (ox, yw1, z0), "Wall", uv)
    box(bm, (-ox, yw0, z1), (ox, yw1, H), "Wall", uv)
    box(bm, (-ox - 0.15, yw0 - 0.15, z0 - 0.05), (ox + 0.15, yw1, z0 + 0.05), "Trim", uv)  # sill
    trims(bm, uv)


def wall_door(bm, uv):
    ox, z1 = 0.8, 2.6
    box(bm, (-hw, yw0, 0.0), (-ox, yw1, H), "Wall", uv)
    box(bm, (ox, yw0, 0.0), (hw, yw1, H), "Wall", uv)
    box(bm, (-ox, yw0, z1), (ox, yw1, H), "Wall", uv)
    box(bm, (-ox - 0.2, yw0 - 0.15, z1), (ox + 0.2, yw1, z1 + 0.25), "Trim", uv)  # lintel
    trims(bm, uv, x_ranges=((-hw, -ox), (ox, hw)))


def wall_alcove(bm, uv):
    ox, z0, z1, depth = 1.2, 0.5, 2.8, 0.25
    box(bm, (-hw, yw0, 0.0), (-ox, yw1, H), "Wall", uv)
    box(bm, (ox, yw0, 0.0), (hw, yw1, H), "Wall", uv)
    box(bm, (-ox, yw0, 0.0), (ox, yw1, z0), "Wall", uv)
    box(bm, (-ox, yw0, z1), (ox, yw1, H), "Wall", uv)
    box(bm, (-ox, yw0 + depth, z0), (ox, yw1, z1), "Wall", uv)  # recessed back panel
    trims(bm, uv)


def pillar(bm, uv):
    box(bm, (-0.45, -0.45, 0.0), (0.45, 0.45, 0.3), "Trim", uv)
    box(bm, (-0.3, -0.3, 0.3), (0.3, 0.3, H - 0.3), "Wall", uv)
    box(bm, (-0.45, -0.45, H - 0.3), (0.45, 0.45, H), "Trim", uv)


def stair(bm, uv):
    n = SPEC.get("steps", 10)
    run = D / n
    rise = (H + ft) / n
    for i in range(n):
        y0 = -hd + i * run
        box(bm, (-hw + 0.2, y0, 0.0), (hw - 0.2, y0 + run, (i + 1) * rise), "Floor", uv)
    box(bm, (-hw, -hd, 0.0), (-hw + 0.2, hd, H + ft), "Wall", uv)  # stringer walls
    box(bm, (hw - 0.2, -hd, 0.0), (hw, hd, H + ft), "Wall", uv)


CI = 0.1  # cores stop short of the cell edge so their end faces never share a plane with the next wall's blocks


def core_slab(bm, uv, x0, x1, z0, z1):
    box(bm, (x0, yw0 - 0.02, z0), (x1, yw0 + 0.03, z1), "Plaster", uv)   # interior finish
    box(bm, (x0, yw0 + 0.03, z0), (x1, yw0 + 0.12, z1), "Mortar", uv)    # dark bed behind the joints


def wall_core(bm, uv):
    core_slab(bm, uv, -hw + CI, hw - CI, 0.0, H)


def wall_core_window(bm, uv):
    ox, z0, z1 = 0.7 + 0.06, 1.1 - 0.06, 2.6 + 0.06
    core_slab(bm, uv, -hw + CI, -ox, 0.0, H)
    core_slab(bm, uv, ox, hw - CI, 0.0, H)
    core_slab(bm, uv, -ox, ox, 0.0, z0)
    core_slab(bm, uv, -ox, ox, z1, H)


def wall_core_door(bm, uv):
    ox, z1 = 0.8 + 0.06, 2.6 + 0.06
    core_slab(bm, uv, -hw + CI, -ox, 0.0, H)
    core_slab(bm, uv, ox, hw - CI, 0.0, H)
    core_slab(bm, uv, -ox, ox, z1, H)


def floor_core(bm, uv):
    box(bm, (-hw, -hd, -ft), (hw, hd, -0.05), "Mortar", uv, side_slot="Wall")


def parapet_core(bm, uv):
    box(bm, (-hw + CI, yw0 - 0.02, H + ft), (hw - CI, yw0 + 0.12, H + ft + 1.0), "Mortar", uv)


def parapet(bm, uv):
    box(bm, (-hw, yw0, H + ft), (hw, yw1, H + ft + 1.0), "Wall", uv)
    box(bm, (-hw, yw0 - 0.1, H + ft + 1.0), (hw, yw1 + 0.1, H + ft + 1.2), "Trim", uv)


builders = {"SM_Kit_Floor": floor, "SM_Kit_Ceiling": ceiling, "SM_Kit_Wall": wall, "SM_Kit_WallWindow": wall_window,
            "SM_Kit_WallDoor": wall_door, "SM_Kit_WallAlcove": wall_alcove, "SM_Kit_Pillar": pillar, "SM_Kit_Stair": stair,
            "SM_Kit_Parapet": parapet, "SM_Kit_WallCore": wall_core, "SM_Kit_WallCoreWindow": wall_core_window,
            "SM_Kit_WallCoreDoor": wall_core_door, "SM_Kit_FloorCore": floor_core, "SM_Kit_ParapetCore": parapet_core}
made = {}
for name, b in builders.items():
    ob, bounds = piece(name, b)
    made[name] = (ob, bounds)

for name, (ob, _) in made.items():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), use_selection=True, apply_scale_options="FBX_SCALE_ALL",
                             mesh_smooth_type="FACE", add_leaf_bones=False)
with open(os.path.join(OUT, "kit_bounds.json"), "w", encoding="utf-8") as f:
    json.dump({n: b for n, (_, b) in made.items()}, f, indent=1)
for i, (ob, _) in enumerate(made.values()):
    ob.location.x = i * 6.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "kit.blend"))
print("KIT_DONE")
