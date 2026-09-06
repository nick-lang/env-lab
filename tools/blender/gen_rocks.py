"""Blender (headless): stylized scatter kit -- boulders, rocks, pebbles, shrubs, trees.

  blender --background --python tools/blender/gen_rocks.py -- <out_dir>

Every mesh: faceted (flat shaded, decimated), origin at bottom-center so a scatter tool can
seat it with z = ground. Rocks use layered global-space displacement on an icosphere (not a
tapered cube), which is the difference between "primitive with noise" and a rock silhouette.
Trees carry two material slots (Bark, Leaf) so Unreal can assign per-slot materials.
"""
import math
import os
import random
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

tex_big = bpy.data.textures.new("BigNoise", type="CLOUDS")
tex_big.noise_scale = 1.6
tex_mid = bpy.data.textures.new("MidNoise", type="CLOUDS")
tex_mid.noise_scale = 0.55
tex_vor = bpy.data.textures.new("Facets", type="VORONOI")
tex_vor.noise_scale = 0.9
tex_vor.noise_intensity = 1.0

M_BARK = bpy.data.materials.new("Bark")
M_LEAF = bpy.data.materials.new("Leaf")
M_ROCK = bpy.data.materials.new("Rock")


def bbox(ob):
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize(ob, dims, bottom_origin=True):
    """Scale to exact dims about the bbox center; origin at bottom-center (or center)."""
    (x0, x1), (y0, y1), (z0, z1) = bbox(ob)
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    sx = dims[0] / max(x1 - x0, 1e-6)
    sy = dims[1] / max(y1 - y0, 1e-6)
    sz = dims[2] / max(z1 - z0, 1e-6)
    for v in ob.data.vertices:
        v.co.x = (v.co.x - cx) * sx
        v.co.y = (v.co.y - cy) * sy
        v.co.z = (v.co.z - cz) * sz + (dims[2] / 2 if bottom_origin else 0.0)
    ob.location = (0, 0, 0)


def apply_all(ob):
    bpy.context.view_layer.objects.active = ob
    for m in [m.name for m in ob.modifiers]:
        bpy.ops.object.modifier_apply(modifier=m)


def uv_unwrap(ob):
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def rock(name, dims, offset, dec_ratio, facet=0.35, subdiv=5):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=0.5, location=offset)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    m = min(dims)
    for tex, strength in ((tex_big, 0.32), (tex_mid, 0.10), (tex_vor, facet)):
        d = ob.modifiers.new("D_" + tex.name, type="DISPLACE")
        d.texture = tex
        d.strength = strength * m
        d.texture_coords = "GLOBAL"
        d.mid_level = 0.5
    apply_all(ob)
    # flatten the underside a little so it sits instead of balancing on a point
    (_, _), (_, _), (z0, z1) = bbox(ob)
    cut = z0 + (z1 - z0) * 0.12
    for v in ob.data.vertices:
        if v.co.z < cut:
            v.co.z = cut + (v.co.z - cut) * 0.25
    dec = ob.modifiers.new("Decimate", type="DECIMATE")
    dec.ratio = dec_ratio
    apply_all(ob)
    bpy.ops.object.shade_flat()
    normalize(ob, dims)
    ob.data.materials.append(M_ROCK)
    uv_unwrap(ob)
    print(f"ROCK {name} tris={len(ob.data.polygons)}")
    return ob


def shrub(name, seed, height):
    rng = random.Random(seed)
    parts = []
    n = rng.randint(4, 7)
    for i in range(n):
        r = height * rng.uniform(0.22, 0.4)
        px = rng.uniform(-1, 1) * height * 0.32
        py = rng.uniform(-1, 1) * height * 0.32
        pz = r * 0.75 + rng.uniform(0, height * 0.25)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(px + seed * 50, py, pz))
        b = bpy.context.active_object
        d = b.modifiers.new("D", type="DISPLACE")
        d.texture = tex_mid
        d.strength = r * 0.5
        d.texture_coords = "GLOBAL"
        apply_all(b)
        parts.append(b)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    dec = ob.modifiers.new("Decimate", type="DECIMATE")
    dec.ratio = 0.45
    apply_all(ob)
    bpy.ops.object.shade_flat()
    (x0, x1), (y0, y1), (z0, z1) = bbox(ob)
    normalize(ob, ((x1 - x0), (y1 - y0), height))
    ob.data.materials.append(M_LEAF)
    uv_unwrap(ob)
    print(f"SHRUB {name} tris={len(ob.data.polygons)}")
    return ob


def tree(name, seed, height, canopy=True):
    rng = random.Random(seed)
    trunk_h = height * (0.72 if canopy else 1.0)
    r0 = height * 0.038
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=r0, depth=trunk_h, location=(seed * 40, 0, trunk_h / 2))
    trunk = bpy.context.active_object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # taper + bend
    lean = rng.uniform(-0.06, 0.06)
    bend_dir = rng.uniform(0, 2 * math.pi)
    for v in trunk.data.vertices:
        t = v.co.z / trunk_h
        s = 1.0 - 0.5 * t
        v.co.x = seed * 40 + (v.co.x - seed * 40) * s + math.cos(bend_dir) * lean * height * t * t
        v.co.y = v.co.y * s + math.sin(bend_dir) * lean * height * t * t
    trunk.data.materials.append(M_BARK)
    parts = [trunk]
    # a couple of stub branches
    for k in range(rng.randint(2, 4)):
        bz = trunk_h * rng.uniform(0.45, 0.9)
        ang = rng.uniform(0, 2 * math.pi)
        ln = height * rng.uniform(0.12, 0.22)
        bpy.ops.mesh.primitive_cylinder_add(vertices=5, radius=r0 * 0.35, depth=ln,
                                            location=(seed * 40 + math.cos(ang) * ln * 0.45, math.sin(ang) * ln * 0.45, bz + ln * 0.25),
                                            rotation=(math.radians(rng.uniform(50, 75)) * math.sin(ang), math.radians(rng.uniform(50, 75)) * math.cos(ang), 0))
        br = bpy.context.active_object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        br.data.materials.append(M_BARK)
        parts.append(br)
    if canopy:
        n = rng.randint(3, 5)
        for i in range(n):
            r = height * rng.uniform(0.11, 0.18)
            px = rng.uniform(-1, 1) * height * 0.12
            py = rng.uniform(-1, 1) * height * 0.12
            pz = trunk_h - height * 0.04 + height * rng.uniform(0.0, 0.2)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(seed * 40 + px, py, pz))
            c = bpy.context.active_object
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            d = c.modifiers.new("D", type="DISPLACE")
            d.texture = tex_mid
            d.strength = r * 0.55
            d.texture_coords = "GLOBAL"
            apply_all(c)
            c.data.materials.append(M_LEAF)
            parts.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = trunk
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    # NB: never decimate trees -- the thin branch cylinders collapse into huge spikes
    bpy.ops.object.shade_flat()
    (x0, x1), (y0, y1), (z0, z1) = bbox(ob)
    # keep proportions; only move origin to bottom-center and clamp height
    sc = height / max(z1 - z0, 1e-6)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for v in ob.data.vertices:
        v.co.x = (v.co.x - cx) * sc
        v.co.y = (v.co.y - cy) * sc
        v.co.z = (v.co.z - z0) * sc
    ob.location = (0, 0, 0)
    uv_unwrap(ob)
    (x0, x1), (y0, y1), (z0, z1) = bbox(ob)
    print(f"TREE {name} tris={len(ob.data.polygons)} slots={len(ob.data.materials)} dims={x1 - x0:.1f}x{y1 - y0:.1f}x{z1 - z0:.1f}")
    return ob


made = []
# name, dims (m), world offset (unique noise), decimate ratio, facet strength
made += [
    rock("SM_BoulderA", (3.6, 2.8, 2.4), (10, 0, 0), 0.12, 0.40),
    rock("SM_BoulderB", (4.4, 3.1, 3.2), (20, 5, 0), 0.10, 0.45),
    rock("SM_BoulderC", (2.9, 2.6, 2.0), (30, 10, 0), 0.14, 0.35),
    rock("SM_RockA", (1.4, 1.1, 0.8), (40, 15, 0), 0.22, 0.35),
    rock("SM_RockB", (1.0, 0.9, 0.7), (50, 20, 0), 0.25, 0.40),
    rock("SM_RockC", (1.6, 0.8, 0.6), (60, 25, 0), 0.22, 0.30),
    rock("SM_PebbleA", (0.4, 0.32, 0.22), (70, 30, 0), 0.15, 0.30, subdiv=3),
    rock("SM_PebbleB", (0.3, 0.28, 0.18), (80, 35, 0), 0.15, 0.30, subdiv=3),
    rock("SM_PebbleC", (0.5, 0.3, 0.2), (90, 40, 0), 0.15, 0.25, subdiv=3),
]
made += [shrub("SM_ShrubA", 1, 0.9), shrub("SM_ShrubB", 2, 1.2), shrub("SM_ShrubC", 3, 0.7)]
made += [tree("SM_TreeA", 1, 11.0), tree("SM_TreeB", 2, 13.5), tree("SM_TreeDead", 3, 8.0, canopy=False)]

for ob in made:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, ob.name + ".fbx"),
        use_selection=True,
        apply_scale_options="FBX_SCALE_ALL",
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
    )
    print(f"EXPORTED {ob.name}")

for i, ob in enumerate(made):
    ob.location.x = i * 6.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "scatter_kit.blend"))
print("KIT_DONE")
