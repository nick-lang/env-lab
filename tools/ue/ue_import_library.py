# Runs inside Unreal. Imports an asset library (FBX + BaseColor/MetalRough/Normal PNGs from clean_glb.py),
# builds one *weathered* material per mesh, enables Nanite, and saves.
# Weathering v1, all from data we already have: the glTF ORM texture's R channel is baked ambient occlusion,
# so crevices darken with (1-AO)^2; moss grows where the surface faces up, sits low in the world and is
# occluded; a per-instance random shifts brightness so no two placed blocks read identical.
# Config: build/library/<lib>/import.json {"fbx_dir", "dest", "moss": {"z_low_cm", "z_high_cm"}, "nanite": true}
import glob
import json
import os

import unreal

CFG = json.load(open(open("C:/Users/nickl/Documents/env-lab/build/active_library.txt", encoding="utf-8").read().strip(), encoding="utf-8"))
DEST = CFG["dest"]
eal = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
MOSS = CFG.get("moss", {"z_low_cm": 0.0, "z_high_cm": 250.0})


def import_texture(path, name, srgb, normal=False):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    at.import_asset_tasks([t])
    tex = eal.load_asset(f"{DEST}/{name}")
    if tex is None:
        return None
    try:
        tex.set_editor_property("srgb", srgb)
        if normal:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
        elif not srgb:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        eal.save_asset(f"{DEST}/{name}")
    except Exception as e:
        print(f"  tex {name}: {e}")
    return tex


def E(m, cls, x, y, props=None):
    n = mel.create_material_expression(m, cls, x, y)
    for k, v in (props or {}).items():
        n.set_editor_property(k, v)
    return n


def C(a, ao, b, bi):
    mel.connect_material_expressions(a, ao, b, bi)


def weathered_material(name, d):
    paths = {r: os.path.join(d, f"{name}_{r}.png") for r in ("BaseColor", "MetalRough", "Normal")}
    if not os.path.isfile(paths["BaseColor"]):
        print(f"  NO_TEXTURES {name}")
        return None
    mname = f"M_{name}"
    full = f"{DEST}/{mname}"
    if eal.does_asset_exist(full):
        eal.delete_asset(full)
    m = at.create_asset(mname, DEST, unreal.Material, unreal.MaterialFactoryNew())
    bc = import_texture(paths["BaseColor"], f"T_{name}_BaseColor", True)
    mr = import_texture(paths["MetalRough"], f"T_{name}_MetalRough", False) if os.path.isfile(paths["MetalRough"]) else None
    nm = import_texture(paths["Normal"], f"T_{name}_Normal", False, normal=True) if os.path.isfile(paths["Normal"]) else None
    s_bc = E(m, unreal.MaterialExpressionTextureSample, -1500, -300, {"texture": bc})
    # ---- crevice dirt from baked AO (ORM.R): base * lerp(1, 0.45, (1-ao)^2)
    if mr:
        s_mr = E(m, unreal.MaterialExpressionTextureSample, -1500, 100, {"texture": mr, "sampler_type": unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR})
        inv = E(m, unreal.MaterialExpressionOneMinus, -1250, 100)
        C(s_mr, "R", inv, "")
        sq = E(m, unreal.MaterialExpressionMultiply, -1100, 100)
        C(inv, "", sq, "A")
        C(inv, "", sq, "B")
        dirt = E(m, unreal.MaterialExpressionLinearInterpolate, -900, 100, {"const_a": 1.0, "const_b": 0.62})
        C(sq, "", dirt, "Alpha")
        dirty = E(m, unreal.MaterialExpressionMultiply, -700, -200)
        C(s_bc, "RGB", dirty, "A")
        C(dirt, "", dirty, "B")
        C(s_mr, "G", None, "") if False else None
    else:
        dirty = s_bc
    # ---- moss: up-facing * low-in-world * occluded * noise
    vn = E(m, unreal.MaterialExpressionVertexNormalWS, -1500, 500)
    nz = E(m, unreal.MaterialExpressionComponentMask, -1300, 500, {"r": False, "g": False, "b": True, "a": False})
    C(vn, "", nz, "")
    up = E(m, unreal.MaterialExpressionSubtract, -1150, 500, {"const_b": 0.55})
    C(nz, "", up, "A")
    up2 = E(m, unreal.MaterialExpressionMultiply, -1000, 500, {"const_b": 2.5})
    C(up, "", up2, "A")
    up3 = E(m, unreal.MaterialExpressionSaturate, -850, 500)
    C(up2, "", up3, "")
    wp = E(m, unreal.MaterialExpressionWorldPosition, -1500, 700)
    wz = E(m, unreal.MaterialExpressionComponentMask, -1300, 700, {"r": False, "g": False, "b": True, "a": False})
    C(wp, "", wz, "")
    lowa = E(m, unreal.MaterialExpressionSubtract, -1150, 700, {"const_b": float(MOSS["z_high_cm"])})
    C(wz, "", lowa, "A")
    lowb = E(m, unreal.MaterialExpressionDivide, -1000, 700, {"const_b": float(MOSS["z_low_cm"] - MOSS["z_high_cm"])})
    C(lowa, "", lowb, "A")
    low = E(m, unreal.MaterialExpressionSaturate, -850, 700)
    C(lowb, "", low, "")
    noise = E(m, unreal.MaterialExpressionNoise, -1300, 900, {"scale": 1.0 / 60.0, "levels": 3, "output_min": -0.4, "output_max": 1.4})
    C(wp, "", noise, "Position")
    nsat = E(m, unreal.MaterialExpressionSaturate, -1100, 900)
    C(noise, "", nsat, "")
    m1 = E(m, unreal.MaterialExpressionMultiply, -700, 600)
    C(up3, "", m1, "A")
    C(low, "", m1, "B")
    m2 = E(m, unreal.MaterialExpressionMultiply, -550, 600)
    C(m1, "", m2, "A")
    C(nsat, "", m2, "B")
    moss_col = E(m, unreal.MaterialExpressionConstant3Vector, -550, 800, {"constant": unreal.LinearColor(0.10, 0.16, 0.04, 1.0)})
    mossed = E(m, unreal.MaterialExpressionLinearInterpolate, -350, -100)
    C(dirty, "", mossed, "A")
    C(moss_col, "", mossed, "B")
    C(m2, "", mossed, "Alpha")
    # ---- per-instance brightness jitter 0.88..1.12
    pir = E(m, unreal.MaterialExpressionPerInstanceRandom, -550, 1000)
    jit = E(m, unreal.MaterialExpressionMultiply, -400, 1000, {"const_b": 0.24 * float(CFG.get("albedo_gain", 1.0))})
    C(pir, "", jit, "A")
    jit2 = E(m, unreal.MaterialExpressionAdd, -250, 1000, {"const_b": 0.88 * float(CFG.get("albedo_gain", 1.0))})
    C(jit, "", jit2, "A")
    final = E(m, unreal.MaterialExpressionMultiply, -150, -100)
    C(mossed, "", final, "A")
    C(jit2, "", final, "B")
    mel.connect_material_property(final, "", unreal.MaterialProperty.MP_BASE_COLOR)
    if mr:
        rough = E(m, unreal.MaterialExpressionTextureSample, -1500, 300, {"texture": mr, "sampler_type": unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR})
        mel.connect_material_property(rough, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    if nm:
        s_n = E(m, unreal.MaterialExpressionTextureSample, -1500, 1200, {"texture": nm, "sampler_type": unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL})
        mel.connect_material_property(s_n, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.recompile_material(m)
    eal.save_asset(full)
    return m


n_ok = 0
for path in sorted(glob.glob(os.path.join(CFG["fbx_dir"], "*.fbx"))):
    name = os.path.splitext(os.path.basename(path))[0]
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_as_skeletal", False)
    smd = ui.static_mesh_import_data
    smd.set_editor_property("combine_meshes", True)
    smd.set_editor_property("auto_generate_collision", True)
    smd.set_editor_property("generate_lightmap_u_vs", False)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path.replace("\\", "/"))
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", ui)
    at.import_asset_tasks([t])
    mesh = eal.load_asset(f"{DEST}/{name}")
    if mesh is None:
        print(f"IMPORT_FAILED {name}")
        continue
    mat = weathered_material(name, CFG["fbx_dir"])
    if mat:
        for i in range(len(mesh.static_materials)):
            mesh.set_material(i, mat)
    if CFG.get("nanite", True):
        try:
            ns = mesh.get_editor_property("nanite_settings")
            ns.set_editor_property("enabled", True)
            mesh.set_editor_property("nanite_settings", ns)
        except Exception as e:
            print(f"  nanite {name}: {e}")
    eal.save_asset(f"{DEST}/{name}")
    n_ok += 1
    print(f"IMPORTED {name} tris={mesh.get_num_triangles(0)}")
print(f"LIBRARY_IMPORT_DONE {n_ok}")
