"""Blender (headless): generated GLB → game-ready FBX for Unreal.

  blender --background --python tools/blender/clean_glb.py -- <in.glb> <out.fbx> [--dims X Y Z | --height H]
                                                                 [--tris N] [--flat] [--no-textures]

Joins everything, optionally decimates to N triangles, scales to the requested size (meters),
puts the origin at bottom-center, keeps the GLB's PBR textures (embedded in the FBX) unless
--no-textures. Vertex order/UVs survive decimation badly, so decimate is off by default; the
ComfyUI pipeline already remeshes+decimates to a sane count.
"""
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, dst = argv[0], argv[1]
dims = None
height = None
tris = None
flat = "--flat" in argv
center = "--center" in argv
uniform = "--uniform" in argv
align = "--align" in argv
textures = "--no-textures" not in argv
if "--dims" in argv:
    i = argv.index("--dims")
    dims = tuple(float(v) for v in argv[i + 1:i + 4])
if "--height" in argv:
    height = float(argv[argv.index("--height") + 1])
if "--tris" in argv:
    tris = int(argv[argv.index("--tris") + 1])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("NO_MESH_IN_GLB")
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
ob = bpy.context.active_object
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
name = os.path.splitext(os.path.basename(dst))[0]
ob.name = name
ob.data.name = name

if tris:
    dec = ob.modifiers.new("Decimate", type="DECIMATE")
    dec.ratio = min(1.0, tris / max(len(ob.data.polygons), 1))
    bpy.ops.object.modifier_apply(modifier="Decimate")

if flat:
    bpy.ops.object.shade_flat()
else:
    bpy.ops.object.shade_smooth()

# glTF import is Y-up converted to Blender Z-up already. Scale + origin.
xs = [v.co.x for v in ob.data.vertices]
ys = [v.co.y for v in ob.data.vertices]
zs = [v.co.z for v in ob.data.vertices]
cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
z0 = min(zs)
ex, ey, ez = max(xs) - min(xs), max(ys) - min(ys), max(zs) - z0
if dims and (uniform or align):
    # rotate 90deg about Z if the target's long horizontal axis disagrees with the mesh's
    if (dims[0] >= dims[1]) != (ex >= ey):
        for v in ob.data.vertices:
            v.co.x, v.co.y = -v.co.y, v.co.x
        xs = [v.co.x for v in ob.data.vertices]
        ys = [v.co.y for v in ob.data.vertices]
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        ex, ey = max(xs) - min(xs), max(ys) - min(ys)
    if uniform:
        dom = max(range(3), key=lambda i: dims[i])
        s = dims[dom] / (ex, ey, ez)[dom]
        sx = sy = sz = s
    else:
        sx, sy, sz = dims[0] / ex, dims[1] / ey, dims[2] / ez
elif dims:
    sx, sy, sz = dims[0] / ex, dims[1] / ey, dims[2] / ez
elif height:
    s = height / ez
    sx = sy = sz = s
else:
    sx = sy = sz = 1.0
zc = (max(zs) + z0) / 2
for v in ob.data.vertices:
    v.co.x = (v.co.x - cx) * sx
    v.co.y = (v.co.y - cy) * sy
    v.co.z = (v.co.z - (zc if center else z0)) * sz
ob.location = (0, 0, 0)

# textures: write the GLB's images next to the FBX (glTF packing: base color sRGB,
# metallic-roughness with G=roughness B=metallic, tangent-space normal) and name the
# material per mesh so Unreal doesn't collapse every import onto one "Material_0".
tex_written = {}
if textures and ob.data.materials:
    mat = ob.data.materials[0]
    mat.name = "M_" + name
    if mat.use_nodes:
        role_of = {}
        for n in mat.node_tree.nodes:
            if n.type != "TEX_IMAGE" or not n.image:
                continue
            for out in n.outputs:
                for l in out.links:
                    if l.to_node.type == "BSDF_PRINCIPLED" and l.to_socket.name == "Base Color":
                        role_of[n.image.name] = "BaseColor"
                    elif l.to_node.type == "NORMAL_MAP":
                        role_of[n.image.name] = "Normal"
                    elif l.to_node.type == "SEPARATE_COLOR":
                        role_of[n.image.name] = "MetalRough"
        for img in bpy.data.images:
            role = role_of.get(img.name)
            if not role:
                continue
            path = os.path.join(os.path.dirname(dst), f"{name}_{role}.png")
            img.filepath_raw = path
            img.file_format = "PNG"
            img.save()
            tex_written[role] = path
if not textures:
    ob.data.materials.clear()

os.makedirs(os.path.dirname(dst), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.ops.export_scene.fbx(
    filepath=dst,
    use_selection=True,
    apply_scale_options="FBX_SCALE_ALL",
    mesh_smooth_type="FACE",
    add_leaf_bones=False,
    path_mode="COPY" if textures else "AUTO",
    embed_textures=textures,
)
print(f"CLEAN_DONE {dst} tris={len(ob.data.polygons)} dims={ex*sx:.2f}x{ey*sy:.2f}x{ez*sz:.2f} mats={len(ob.data.materials)} textures={sorted(tex_written)}")
