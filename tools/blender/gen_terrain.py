"""Blender (headless): heightmap .npy -> terrain static mesh FBX for Unreal.

  blender --background --python tools/blender/gen_terrain.py -- <build_dir> [--no-flip-y]

Reads <build_dir>/height.npy + meta.json + pathdist.npy. Verts are in world meters, so the
Unreal actor sits at (0,0,0). By default Y is negated on export because Unreal mirrors Y on
FBX import (Blender +Y == Unreal -Y); the setup script verifies this with sample points.
Vertex colors: R = slope 0..1 (0..45deg), G = normalized height, B = path proximity mask.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
build_dir = argv[0]
flip_y = "--no-flip-y" not in argv
with_vcol = "--no-vcol" not in argv

with open(os.path.join(build_dir, "meta.json"), encoding="utf-8") as f:
    meta = json.load(f)
h = np.load(os.path.join(build_dir, "height.npy")).astype(np.float64)
pd = np.load(os.path.join(build_dir, "pathdist.npy")).astype(np.float64)
res = int(meta["res"])
sp = float(meta["spacing"])
x0, y0 = meta["origin"]

bpy.ops.wm.read_factory_settings(use_empty=True)

verts = []
for j in range(res):
    for i in range(res):
        x = x0 + i * sp
        y = y0 + j * sp
        verts.append((x, -y if flip_y else y, float(h[j, i])))

faces = []
for j in range(res - 1):
    for i in range(res - 1):
        a = j * res + i
        b = a + 1
        c = a + res
        d = c + 1
        # winding: keep normals up after the optional Y flip
        if flip_y:
            faces.append((a, c, d, b))
        else:
            faces.append((a, b, d, c))

me = bpy.data.meshes.new("SM_Terrain_E1")
me.from_pydata(verts, [], faces)
me.update()
ob = bpy.data.objects.new("SM_Terrain_E1", me)
bpy.context.collection.objects.link(ob)
bpy.context.view_layer.objects.active = ob
ob.select_set(True)

# slope / height / path masks as point colors
gy, gx = np.gradient(h, sp)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
zmin, zmax = float(h.min()), float(h.max())
if with_vcol:
    col = me.color_attributes.new(name="Masks", type="FLOAT_COLOR", domain="POINT")
    k = 0
    for j in range(res):
        for i in range(res):
            r = min(slope[j, i] / 45.0, 1.0)
            g = (h[j, i] - zmin) / max(zmax - zmin, 1e-6)
            b = max(0.0, 1.0 - pd[j, i] / 12.0)
            col.data[k].color = (r, g, b, 1.0)
            k += 1

for p in me.polygons:
    p.use_smooth = True

# a single UV set: planar, ONE tile over the whole mesh (the original ground plane had 0..1 UVs;
# the LR ground materials scale their UV-driven pattern accordingly and use world-space noise)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.reset()
bpy.ops.object.mode_set(mode="OBJECT")
uv = me.uv_layers.active
if uv is None:
    uv = me.uv_layers.new(name="UVMap")
for poly in me.polygons:
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = ((v.x - x0) / (res - 1) / sp, (-v.y - y0) / (res - 1) / sp if flip_y else (v.y - y0) / (res - 1) / sp)

mat = bpy.data.materials.new("M_Terrain")
me.materials.append(mat)

out = os.path.join(build_dir, "SM_Terrain_E1.fbx")
bpy.ops.export_scene.fbx(
    filepath=out,
    use_selection=True,
    apply_scale_options="FBX_SCALE_ALL",
    mesh_smooth_type="FACE",
    use_mesh_modifiers=True,
    add_leaf_bones=False,
)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(build_dir, "terrain.blend"))
print(f"TERRAIN_EXPORTED verts={len(verts)} faces={len(faces)} flip_y={flip_y} vcol={with_vcol} -> {out}")
