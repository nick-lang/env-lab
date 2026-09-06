"""Blender (headless): card-based vegetation kit — trees (trunk + branches + leaf-card clusters),
shrubs (card balls), grass (crossed cards). Textures come from tools/asset/textures.py.

  blender --background --python tools/blender/gen_veg.py -- <out_dir> <spec.json>

Every mesh: origin at bottom-center, meters, two material slots (Bark, Leaf) on trees, one (Leaf)
on shrubs/grass. Cards are unlit-facing quads with UV 0..1; Unreal gets a masked two-sided leaf
material built by ue_import_veg.py. Deterministic per species seed.
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]
SPEC = json.load(open(argv[1], encoding="utf-8"))
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

M_BARK = bpy.data.materials.new("Bark")
M_LEAF = bpy.data.materials.new("Leaf")


# ----------------------------------------------------------------------------- mesh helpers
def tube(bm, points, radii, sides=7, uv_layer=None, u_scale=1.0):
    """Skin a polyline (list of Vector) with rings; radii per point. Returns nothing (adds to bm)."""
    rings = []
    v_acc = 0.0
    for i, p in enumerate(points):
        if i < len(points) - 1:
            t = (points[i + 1] - p).normalized()
        else:
            t = (p - points[i - 1]).normalized()
        # frame
        up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
        n1 = t.cross(up).normalized()
        n2 = t.cross(n1).normalized()
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(bm.verts.new(p + (n1 * math.cos(a) + n2 * math.sin(a)) * radii[i]))
        rings.append(ring)
        if i > 0:
            v_acc += (points[i] - points[i - 1]).length
    for i in range(len(rings) - 1):
        for k in range(sides):
            a, b = rings[i][k], rings[i][(k + 1) % sides]
            c, d = rings[i + 1][(k + 1) % sides], rings[i + 1][k]
            try:
                f = bm.faces.new((a, b, c, d))
                f.material_index = 0
                if uv_layer is not None:
                    for loop, (uu, vv) in zip(f.loops, ((k / sides, i * u_scale), ((k + 1) / sides, i * u_scale), ((k + 1) / sides, (i + 1) * u_scale), (k / sides, (i + 1) * u_scale))):
                        loop[uv_layer].uv = (uu, vv)
            except ValueError:
                pass


def card(bm, center, size, normal_yaw, tilt, roll, uv_layer, aspect=1.0):
    """One quad of width size, height size*aspect, bottom-centered at `center` then rotated."""
    w, h = size / 2, size * aspect
    local = [Vector((-w, 0, 0)), Vector((w, 0, 0)), Vector((w, 0, h)), Vector((-w, 0, h))]
    rot = Matrix.Rotation(normal_yaw, 4, "Z") @ Matrix.Rotation(tilt, 4, "X") @ Matrix.Rotation(roll, 4, "Y")
    verts = [bm.verts.new(center + (rot @ v)) for v in local]
    try:
        f = bm.faces.new(verts)
        f.material_index = 1
        for loop, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv_layer].uv = uv
    except ValueError:
        pass


def cluster(bm, center, size, rng, uv_layer, cards=3, spread=0.35, aspect=1.0):
    """A leaf cluster: several cards through a common centre, random orientation, slight offsets."""
    for _ in range(cards):
        off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.6, 0.6))) * size * spread
        card(bm, center + off - Vector((0, 0, size * aspect * 0.5)), size, rng.uniform(0, math.pi), rng.uniform(-0.6, 0.6), rng.uniform(-0.4, 0.4), uv_layer, aspect)


# ----------------------------------------------------------------------------- generators
def grow(rng, start, direction, length, radius, level, sp, out_segments, tips):
    """Recursive branch growth. Appends (points, radii) polylines and tip positions."""
    n = max(3, int(length / sp["segment_m"]))
    pts = [Vector(start)]
    d = Vector(direction).normalized()
    for i in range(1, n + 1):
        # gravity/phototropism + jitter
        d = (d + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * sp["jitter"] + Vector((0, 0, sp["up_bias"] * (1 if level == 0 else 0.4))) ).normalized()
        pts.append(pts[-1] + d * (length / n))
    r_end = radius * sp["taper"] if level < sp["levels"] else radius * 0.25
    radii = [radius + (r_end - radius) * (i / n) for i in range(n + 1)]
    out_segments.append((pts, radii))
    if level >= sp["levels"]:
        tips.append((pts[-1], d))
        return
    # children along the upper part of this branch
    k = rng.randint(*sp["children"])
    for j in range(k):
        t = rng.uniform(sp["child_start"], 0.98)
        idx = min(int(t * n), n - 1)
        base = pts[idx]
        parent_dir = (pts[min(idx + 1, n)] - pts[max(idx - 1, 0)]).normalized()
        ang = math.radians(rng.uniform(*sp["branch_angle"]))
        around = rng.uniform(0, 2 * math.pi)
        # rotate parent dir away by ang around a random perpendicular axis
        perp = parent_dir.cross(Vector((0, 0, 1))).normalized() if abs(parent_dir.z) < 0.95 else Vector((1, 0, 0))
        axis = Matrix.Rotation(around, 4, parent_dir) @ perp
        cd = Matrix.Rotation(ang, 4, axis) @ parent_dir
        cl = length * rng.uniform(*sp["child_length"])
        cr = radii[idx] * sp["child_radius"]
        grow(rng, base, cd, cl, cr, level + 1, sp, out_segments, tips)
    if level >= 1 and sp.get("leaves_along", 0) > 0:
        for j in range(sp["leaves_along"]):
            t = rng.uniform(0.4, 1.0)
            tips.append((pts[min(int(t * n), n)], d))


def build_tree(name, sp, seed):
    rng = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    segs, tips = [], []
    lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * sp.get("lean", 0.08)
    grow(rng, Vector((0, 0, 0)), (Vector((0, 0, 1)) + lean).normalized(), sp["height"] * sp["trunk_frac"], sp["radius"], 0, sp, segs, tips)
    for pts, radii in segs:
        tube(bm, pts, radii, sides=sp.get("sides", 7), uv_layer=uv, u_scale=sp.get("bark_v_per_seg", 0.5))
    # crown shaping: drop tips outside the crown envelope, then add clusters
    kept = 0
    for pos, d in tips:
        h = pos.z / sp["height"]
        if sp["crown"] == "cone":
            rmax = sp["crown_radius"] * max(0.05, 1.0 - h)
        elif sp["crown"] == "spread":
            rmax = sp["crown_radius"] * (0.4 + 0.6 * min(1.0, h / 0.6))
        else:
            rmax = sp["crown_radius"] * math.sqrt(max(0.0, 1 - ((h - 0.65) / 0.45) ** 2)) if h > 0.2 else 0
        if Vector((pos.x, pos.y, 0)).length > rmax or pos.z < sp["height"] * sp.get("crown_min", 0.3):
            continue
        cluster(bm, pos, sp["cluster_size"] * rng.uniform(0.8, 1.2), rng, uv, cards=sp.get("cards", 3), aspect=sp.get("card_aspect", 1.0))
        kept += 1
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_BARK)
    me.materials.append(M_LEAF)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    # normalize height (origin already at base)
    zmax = max(v.co.z for v in me.vertices)
    s = sp["height"] / max(zmax, 1e-6)
    for v in me.vertices:
        v.co *= s
    print(f"TREE {name} tris={sum(len(p.vertices) - 2 for p in me.polygons)} clusters={kept} tips={len(tips)} height={sp['height']}")
    return ob


def build_shrub(name, sp, seed):
    rng = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    r = sp["radius"]
    for i in range(sp["cards"]):
        # points on a squashed sphere shell
        u, v = rng.uniform(0, 2 * math.pi), rng.uniform(0.15, 1.0)
        pos = Vector((math.cos(u) * r * v, math.sin(u) * r * v, sp["height"] * (0.15 + 0.5 * (1 - v) + rng.uniform(0, 0.3))))
        card(bm, pos - Vector((0, 0, sp["card_size"] * 0.5)), sp["card_size"] * rng.uniform(0.8, 1.2), u + rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.3, 0.3), uv)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_LEAF)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    print(f"SHRUB {name} tris={len(me.polygons) * 2} cards={sp['cards']}")
    return ob


def build_grass(name, sp, seed):
    rng = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    n = sp.get("cards", 3)
    for i in range(n):
        yaw = math.pi * i / n + rng.uniform(-0.15, 0.15)
        card(bm, Vector((0, 0, 0)), sp["width"], yaw, rng.uniform(-0.12, 0.12), 0, uv, aspect=sp["height"] / sp["width"])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_LEAF)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    print(f"GRASS {name} tris={len(me.polygons) * 2}")
    return ob


made = []
for item in SPEC["items"]:
    kind, name, sp, seed = item["kind"], item["name"], item["params"], item.get("seed", 1)
    ob = {"tree": build_tree, "shrub": build_shrub, "grass": build_grass}[kind](name, sp, seed)
    made.append(ob)

for ob in made:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, ob.name + ".fbx"), use_selection=True, apply_scale_options="FBX_SCALE_ALL",
                             mesh_smooth_type="FACE", add_leaf_bones=False)
    print(f"EXPORTED {ob.name}")
for i, ob in enumerate(made):
    ob.location.x = i * 8.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "veg_kit.blend"))
print("VEG_DONE")
