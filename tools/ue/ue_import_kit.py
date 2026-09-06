# Runs inside Unreal. Imports the modular kit FBXs and assigns the E07 generated materials by slot name.
# Config: build/kit/import.json {"dir": ..., "dest": "/Game/Meshes/Kit", "materials": {"Floor": path, ...}}
import glob
import json
import os

import unreal

CFG = json.load(open("C:/Users/nickl/Documents/env-lab/build/kit/import.json", encoding="utf-8"))
DEST = CFG.get("dest", "/Game/Meshes/Kit")
eal = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
MATS = {k: eal.load_asset(v) for k, v in CFG["materials"].items()}
mel = unreal.MaterialEditingLibrary
mortar_path = f"{DEST}/M_Mortar"
if not eal.does_asset_exist(mortar_path):
    mm = at.create_asset("M_Mortar", DEST, unreal.Material, unreal.MaterialFactoryNew())
    c = mel.create_material_expression(mm, unreal.MaterialExpressionConstant3Vector, -400, 0)
    c.set_editor_property("constant", unreal.LinearColor(0.045, 0.04, 0.035, 1.0))
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = mel.create_material_expression(mm, unreal.MaterialExpressionConstant, -400, 200)
    r.set_editor_property("r", 1.0)
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mm)
    eal.save_asset(mortar_path)
if not MATS.get("Mortar"):
    MATS["Mortar"] = eal.load_asset(mortar_path)
for k, v in MATS.items():
    print(f"MAT {k} -> {v.get_name() if v else 'MISSING'}")

for path in sorted(glob.glob(os.path.join(CFG["dir"], "SM_Kit_*.fbx"))):
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
    name = os.path.splitext(os.path.basename(path))[0]
    m = eal.load_asset(f"{DEST}/{name}")
    if m is None:
        print(f"IMPORT_FAILED {name}")
        continue
    slots = [str(s.material_slot_name) for s in m.static_materials]
    for i, slot in enumerate(slots):
        mat = MATS.get(slot)
        if mat:
            m.set_material(i, mat)
    try:
        bs = m.get_editor_property("body_setup")
        bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    except Exception as e:
        print(f"  collision {name}: {e}")
    try:
        ns = m.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", True)
        m.set_editor_property("nanite_settings", ns)
    except Exception as e:
        print(f"  nanite {name}: {e}")
    eal.save_asset(f"{DEST}/{name}")
    print(f"IMPORTED {name} tris={m.get_num_triangles(0)} slots={slots}")
print("KIT_IMPORT_DONE")
