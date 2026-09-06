# Runs inside Unreal. Experiment 03: swap dressing actors' meshes for generated ones.
# Config: experiments/03-asset-factory/e3.json  { "swaps": [{"label", "fbx", "material": "textured"|"<asset path>"}],
#                                                 "restore": false }
# Generated FBXs are normalized to the blockout dims with centered origins, so actor transforms
# stay put. "restore": true puts the E01 meshes/materials back (recorded on first swap).
import json
import os

import unreal

CFG = "C:/Users/nickl/Documents/env-lab/experiments/03-asset-factory/e3.json"
STATE = "C:/Users/nickl/Documents/env-lab/build/e3_swap_state.json"
DEST = "/Game/Meshes/EnvLabGen"
with open(CFG, encoding="utf-8") as f:
    cfg = json.load(f)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
eal = unreal.EditorAssetLibrary
try:
    les.editor_request_end_play()
except Exception:
    pass
world = ues.get_editor_world()
pkg = world.get_outer().get_path_name()
if pkg != cfg.get("map", "/Game/Maps/Barrow_E1"):
    les.load_level(cfg.get("map", "/Game/Maps/Barrow_E1"))
    world = ues.get_editor_world()
    pkg = world.get_outer().get_path_name()
print(f"LEVEL_PACKAGE {pkg}")
if pkg != cfg.get("map", "/Game/Maps/Barrow_E1"):
    raise SystemExit("WRONG_PACKAGE")

by_label = {a.get_actor_label(): a for a in eas.get_all_level_actors()}
state = {}
if os.path.isfile(STATE):
    with open(STATE, encoding="utf-8") as f:
        state = json.load(f)


at = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


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
        print(f"  TEX_IMPORT_FAILED {name}")
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
        print(f"  tex settings {name}: {e}")
    return tex


def build_pbr_material(mesh_name, fbx_path):
    """M_<mesh> from <fbx dir>/<mesh>_{BaseColor,MetalRough,Normal}.png (glTF packing)."""
    d = os.path.dirname(fbx_path)
    paths = {r: os.path.join(d, f"{mesh_name}_{r}.png") for r in ("BaseColor", "MetalRough", "Normal")}
    if not os.path.isfile(paths["BaseColor"]):
        print(f"  NO_TEXTURES for {mesh_name}")
        return None
    mname = f"M_{mesh_name}"
    full = f"{DEST}/{mname}"
    if eal.does_asset_exist(full):
        eal.delete_asset(full)
    m = at.create_asset(mname, DEST, unreal.Material, unreal.MaterialFactoryNew())
    bc = import_texture(paths["BaseColor"], f"T_{mesh_name}_BaseColor", True)
    if bc:
        n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -600, -200)
        n.set_editor_property("texture", bc)
        mel.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    if os.path.isfile(paths["MetalRough"]):
        mr = import_texture(paths["MetalRough"], f"T_{mesh_name}_MetalRough", False)
        if mr:
            n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -600, 100)
            n.set_editor_property("texture", mr)
            n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
            mel.connect_material_property(n, "G", unreal.MaterialProperty.MP_ROUGHNESS)
            mel.connect_material_property(n, "B", unreal.MaterialProperty.MP_METALLIC)
    if os.path.isfile(paths["Normal"]):
        nm = import_texture(paths["Normal"], f"T_{mesh_name}_Normal", False, normal=True)
        if nm:
            n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -600, 400)
            n.set_editor_property("texture", nm)
            n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            mel.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.recompile_material(m)
    eal.save_asset(full)
    print(f"  MATERIAL {mname}")
    return m


def import_fbx(path, textured):
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
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    name = os.path.splitext(os.path.basename(path))[0]
    m = eal.load_asset(f"{DEST}/{name}")
    if m:
        print(f"IMPORTED {name} tris={m.get_num_triangles(0)} mats={len(m.static_materials)}")
        if textured:
            mat = build_pbr_material(name, path)
            if mat:
                for i in range(len(m.static_materials)):
                    m.set_material(i, mat)
                eal.save_asset(f"{DEST}/{name}")
    else:
        print(f"IMPORT_FAILED {name}")
    return m


if cfg.get("restore"):
    n = 0
    for lbl, rec in state.items():
        a = by_label.get(lbl)
        if not a:
            continue
        mesh = eal.load_asset(rec["mesh"]) if rec.get("mesh") else None
        if mesh:
            a.static_mesh_component.set_static_mesh(mesh)
        for i, mp in enumerate(rec.get("materials", [])):
            if mp:
                mat = eal.load_asset(mp)
                if mat:
                    a.static_mesh_component.set_material(i, mat)
        n += 1
    print(f"RESTORED {n}")
else:
    for path in cfg.get("imports", []):
        name = os.path.splitext(os.path.basename(path))[0]
        import_fbx(path, True)
    for sw in cfg["swaps"]:
        a = by_label.get(sw["label"])
        if not a:
            print(f"ACTOR_MISSING {sw['label']}")
            continue
        if sw["label"] not in state:
            comp = a.static_mesh_component
            old_mesh = comp.static_mesh
            state[sw["label"]] = {
                "mesh": old_mesh.get_path_name() if old_mesh else None,
                "materials": [(comp.get_material(i).get_path_name() if comp.get_material(i) else None) for i in range(comp.get_num_materials())],
            }
        textured = sw.get("material", "textured") == "textured"
        want = os.path.splitext(os.path.basename(sw["fbx"]))[0]
        cur = a.static_mesh_component.static_mesh
        if cur and cur.get_name() == want and not cfg.get("reimport"):
            print(f"ALREADY {sw['label']} = {want}")
            continue
        mesh = import_fbx(sw["fbx"], textured)
        if not mesh:
            continue
        comp = a.static_mesh_component
        comp.set_static_mesh(mesh)
        if not textured:
            mat = eal.load_asset(sw["material"])
            if mat:
                for i in range(comp.get_num_materials()):
                    comp.set_material(i, mat)
        print(f"SWAPPED {sw['label']} -> {mesh.get_name()} ({'textured' if textured else sw['material']})")
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)

les.save_current_level()
print("E3_SWAP_DONE")
