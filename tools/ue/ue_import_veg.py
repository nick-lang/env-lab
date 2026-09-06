# Runs inside Unreal. Imports the vegetation kit FBXs and builds their materials from generated textures:
# a masked, two-sided foliage material per leaf texture and an opaque bark material per bark tile.
# Config: build/veg/import.json {"meshes": [{"fbx", "bark": png|null, "leaf": png}], "dest": "/Game/Meshes/Veg"}
import json
import os

import unreal

CFG = json.load(open("C:/Users/nickl/Documents/env-lab/build/veg/import.json", encoding="utf-8"))
DEST = CFG.get("dest", "/Game/Meshes/Veg")
eal = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
CACHE = {}


def import_texture(path, name, srgb=True):
    full = f"{DEST}/{name}"
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    at.import_asset_tasks([t])
    tex = eal.load_asset(full)
    if tex:
        try:
            tex.set_editor_property("srgb", srgb)
            eal.save_asset(full)
        except Exception as e:
            print(f"  tex {name}: {e}")
    return tex


def leaf_material(png):
    key = os.path.splitext(os.path.basename(png))[0]
    if ("leaf", key) in CACHE:
        return CACHE[("leaf", key)]
    mname = f"M_Leaf_{key}"
    full = f"{DEST}/{mname}"
    if eal.does_asset_exist(full):
        eal.delete_asset(full)
    m = at.create_asset(mname, DEST, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("two_sided", True)
    try:
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    except Exception as e:
        print(f"  shading model: {e}")
    try:
        m.set_editor_property("opacity_mask_clip_value", 0.5)
    except Exception:
        pass
    tex = import_texture(png, f"T_{key}", True)
    if tex:
        n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, -100)
        n.set_editor_property("texture", tex)
        mel.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        mel.connect_material_property(n, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
        # subsurface colour = base colour * warm tint, roughness constant
        mul = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, 150)
        c = mel.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, 250)
        c.set_editor_property("constant", unreal.LinearColor(0.35, 0.35, 0.15, 1.0))
        mel.connect_material_expressions(n, "RGB", mul, "A")
        mel.connect_material_expressions(c, "", mul, "B")
        try:
            mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        except Exception as e:
            print(f"  subsurface: {e}")
    r = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 400)
    r.set_editor_property("r", 0.85)
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    eal.save_asset(full)
    CACHE[("leaf", key)] = m
    print(f"  MATERIAL {mname}")
    return m


def bark_material(png):
    key = os.path.splitext(os.path.basename(png))[0]
    if ("bark", key) in CACHE:
        return CACHE[("bark", key)]
    mname = f"M_Bark_{key}"
    full = f"{DEST}/{mname}"
    if eal.does_asset_exist(full):
        eal.delete_asset(full)
    m = at.create_asset(mname, DEST, unreal.Material, unreal.MaterialFactoryNew())
    tex = import_texture(png, f"T_{key}", True)
    if tex:
        n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, -100)
        n.set_editor_property("texture", tex)
        uv = mel.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -750, -100)
        uv.set_editor_property("u_tiling", 1.0)
        uv.set_editor_property("v_tiling", 1.0)
        mel.connect_material_expressions(uv, "", n, "UVs")
        mel.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    r = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 300)
    r.set_editor_property("r", 0.95)
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    eal.save_asset(full)
    CACHE[("bark", key)] = m
    print(f"  MATERIAL {mname}")
    return m


def import_fbx(path):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_as_skeletal", False)
    smd = ui.static_mesh_import_data
    smd.set_editor_property("combine_meshes", True)
    smd.set_editor_property("auto_generate_collision", False)
    smd.set_editor_property("generate_lightmap_u_vs", False)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", ui)
    at.import_asset_tasks([t])
    name = os.path.splitext(os.path.basename(path))[0]
    return eal.load_asset(f"{DEST}/{name}"), name


for item in CFG["meshes"]:
    m, name = import_fbx(item["fbx"])
    if m is None:
        print(f"IMPORT_FAILED {name}")
        continue
    slots = [str(s.material_slot_name) for s in m.static_materials]
    for i, slot in enumerate(slots):
        if slot.lower().startswith("bark") and item.get("bark"):
            m.set_material(i, bark_material(item["bark"]))
        elif slot.lower().startswith("leaf") and item.get("leaf"):
            m.set_material(i, leaf_material(item["leaf"]))
    eal.save_asset(f"{DEST}/{name}")
    print(f"IMPORTED {name} tris={m.get_num_triangles(0)} slots={slots}")
print("VEG_IMPORT_DONE")
