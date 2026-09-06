"""Blender (headless): quick turntable render of a GLB/FBX for inspection.

  blender --background --python tools/blender/render_glb.py -- <in.glb|in.fbx> <out_prefix> [--views 3] [--size 640]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, prefix = argv[0], argv[1]
views = int(argv[argv.index("--views") + 1]) if "--views" in argv else 3
size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 640

bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith(".glb") or src.lower().endswith(".gltf"):
    bpy.ops.import_scene.gltf(filepath=src)
else:
    bpy.ops.import_scene.fbx(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
tris = sum(len(o.data.polygons) for o in meshes)

# bounds
mn = Vector((1e9, 1e9, 1e9))
mx = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w))
        mx = Vector(map(max, mx, w))
center = (mn + mx) / 2
radius = max((mx - mn).length / 2, 1e-3)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = size
scene.render.film_transparent = False
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.35, 0.36, 0.38, 1)
bg.inputs[1].default_value = 1.0

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
scene.collection.objects.link(sun)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
dist = radius * 2.6
for i in range(views):
    ang = math.radians(35 + i * (360 / views))
    pos = center + Vector((math.cos(ang) * dist, math.sin(ang) * dist, radius * 0.9))
    cam.location = pos
    direction = center - pos
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{prefix}_{i}.png"
    bpy.ops.render.render(write_still=True)
print(f"RENDER_DONE tris={tris} dims={(mx - mn).x:.2f}x{(mx - mn).y:.2f}x{(mx - mn).z:.2f} views={views}")
