# Runs inside Unreal. Builds a level from a compiler plan (build/world/<name>/plan.json):
# fresh map, terrain import, every actor and HISM layer with its id as label and tag, look
# settings applied by property name, game mode + player start. No placement logic lives here.
import json
import os

import unreal

PLAN = open("C:/Users/nickl/Documents/env-lab/build/active_plan.txt", encoding="utf-8").read().strip()
with open(PLAN, encoding="utf-8") as f:
    plan = json.load(f)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
eal = unreal.EditorAssetLibrary
SDS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
try:
    les.editor_request_end_play()
except Exception:
    pass

MAP = plan["meta"]["map"]
DEST = "/Game/Meshes/World"

# ---------------------------------------------------------------- fresh level
# new_level() refuses to switch away from a dirty level in unattended mode; loading the saved package works
if eal.does_asset_exist(MAP):
    les.load_level(MAP)
else:
    les.new_level(MAP)
world = ues.get_editor_world()
pkg = world.get_outer().get_path_name()
print(f"LEVEL_PACKAGE {pkg}")
if pkg != MAP:
    raise SystemExit("WRONG_PACKAGE")
# new_level on an existing package keeps its actors; the plan is the whole truth, so wipe first
stale = eas.get_all_level_actors()
if stale:
    eas.destroy_actors(stale)
    print(f"WIPED {len(stale)} stale actors")


# ---------------------------------------------------------------- helpers
def V(v):
    return unreal.Vector(float(v[0]), float(v[1]), float(v[2]))


def R(r):
    return unreal.Rotator(pitch=float(r[0]), yaw=float(r[1]), roll=float(r[2]))


def coerce(current, value):
    """Build a value of the same type as `current` from a JSON value."""
    if isinstance(value, dict):
        if isinstance(current, unreal.LinearColor):
            return unreal.LinearColor(value["r"], value["g"], value["b"], value.get("a", 1.0))
        if isinstance(current, unreal.Color):
            # unreal.Color is BGRA: positional args are (b, g, r, a). Use keywords.
            return unreal.Color(r=int(value["r"]), g=int(value["g"]), b=int(value["b"]), a=int(value.get("a", 255)))
        if isinstance(current, unreal.Vector4):
            return unreal.Vector4(value["x"], value["y"], value["z"], value.get("w", 1.0))
        if isinstance(current, unreal.Vector):
            return unreal.Vector(value["x"], value["y"], value["z"])
        if isinstance(current, unreal.Rotator):
            return unreal.Rotator(pitch=value["pitch"], yaw=value["yaw"], roll=value["roll"])
        return None
    if isinstance(value, str) and value.startswith("/"):
        return eal.load_asset(value.split(".")[0]) or value
    return value


def apply_props(obj, props):
    for k, v in (props or {}).items():
        try:
            cur = obj.get_editor_property(k)
            val = coerce(cur, v)
            if val is None:
                continue
            obj.set_editor_property(k, val)
        except Exception as e:
            print(f"  prop {k}: {e}")


def import_fbx(path, dest, complex_collision=False):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_as_skeletal", False)
    smd = ui.static_mesh_import_data
    smd.set_editor_property("combine_meshes", True)
    smd.set_editor_property("auto_generate_collision", not complex_collision)
    smd.set_editor_property("generate_lightmap_u_vs", False)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", dest)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    name = os.path.splitext(os.path.basename(path))[0]
    m = eal.load_asset(f"{dest}/{name}")
    if m and complex_collision:
        try:
            bs = m.get_editor_property("body_setup")
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            eal.save_asset(f"{dest}/{name}")
        except Exception as e:
            print(f"  collision flag: {e}")
    print(f"IMPORTED {name}" if m else f"IMPORT_FAILED {name}")
    return m


def load_mesh(path):
    if path == "$terrain":
        return terrain_mesh
    return eal.load_asset(path.split(".")[0])


def load_mat(path):
    return eal.load_asset(path.split(".")[0]) if path else None


CLASSES = {
    "StaticMeshActor": unreal.StaticMeshActor, "PointLight": unreal.PointLight, "SpotLight": unreal.SpotLight,
    "DirectionalLight": unreal.DirectionalLight, "SkyLight": unreal.SkyLight, "SkyAtmosphere": unreal.SkyAtmosphere,
    "ExponentialHeightFog": unreal.ExponentialHeightFog, "VolumetricCloud": unreal.VolumetricCloud,
    "PostProcessVolume": unreal.PostProcessVolume, "PlayerStart": unreal.PlayerStart,
}
COMP = {
    "PointLight": unreal.PointLightComponent, "SpotLight": unreal.SpotLightComponent, "DirectionalLight": unreal.DirectionalLightComponent,
    "SkyLight": unreal.SkyLightComponent, "SkyAtmosphere": unreal.SkyAtmosphereComponent,
    "ExponentialHeightFog": unreal.ExponentialHeightFogComponent, "VolumetricCloud": unreal.VolumetricCloudComponent,
}

# ---------------------------------------------------------------- terrain
fbx = plan["terrain"]["fbx"]
if not os.path.isabs(fbx):
    fbx = os.path.join(os.path.dirname(PLAN), fbx)
terrain_mesh = import_fbx(fbx.replace("\\", "/"), DEST, complex_collision=True)

# ---------------------------------------------------------------- actors
n_ok = 0
for rec in plan["actors"]:
    cls = CLASSES.get(rec["class"])
    if cls is None:
        print(f"UNKNOWN_CLASS {rec['class']} for {rec['id']}")
        continue
    a = eas.spawn_actor_from_class(cls, V(rec["loc"]), R(rec.get("rot", [0, 0, 0])))
    a.set_actor_label(rec["id"])
    try:
        a.tags = [unreal.Name(rec["id"])]
    except Exception:
        pass
    sc = rec.get("scale", [1, 1, 1])
    if sc != [1, 1, 1]:
        a.set_actor_scale3d(V(sc))
    if rec["class"] == "StaticMeshActor":
        m = load_mesh(rec["mesh"])
        if m is None:
            print(f"MESH_MISSING {rec['mesh']} for {rec['id']}")
        else:
            a.static_mesh_component.set_static_mesh(m)
        for i, mp in enumerate(rec.get("materials") or []):
            mat = load_mat(mp)
            if mat:
                a.static_mesh_component.set_material(i, mat)
    elif rec["class"] == "PostProcessVolume":
        if rec.get("unbound"):
            a.set_editor_property("unbound", True)
        settings = rec.get("settings") or {}
        pps = a.get_editor_property("settings")
        for k, v in settings.items():
            try:
                pps.set_editor_property("override_" + k, True)
                cur = pps.get_editor_property(k)
                val = coerce(cur, v)
                if val is not None:
                    pps.set_editor_property(k, val)
            except Exception as e:
                print(f"  ppv {k}: {e}")
        a.set_editor_property("settings", pps)
    elif rec["class"] in COMP:
        c = a.get_component_by_class(COMP[rec["class"]])
        if c:
            if rec["class"] in ("DirectionalLight", "PointLight", "SpotLight", "SkyLight"):
                try:
                    c.set_mobility(unreal.ComponentMobility.MOVABLE)
                except Exception:
                    pass
            apply_props(c, rec.get("props"))
    n_ok += 1
print(f"ACTORS_PLACED {n_ok}/{len(plan['actors'])}")

# ---------------------------------------------------------------- HISM layers
MATS_CACHE = {}


def slot_material(slot):
    # slot names from the E1/E3 rules: "rock" -> stone material, "leaf" -> grass clump material, "bark" -> bark
    paths = {"rock": "/Game/Materials/M_LR3_L_Stone", "leaf": "/Game/Materials/M_GrassClump", "bark": "/Game/Materials/M_EnvLab_Bark"}
    paths.update(plan.get("materials") or {})
    p = paths.get(slot)
    if not p:
        return None
    if p not in MATS_CACHE:
        MATS_CACHE[p] = eal.load_asset(p)
    return MATS_CACHE[p]


total = 0
for layer in plan["hism"]:
    if not layer["instances"]:
        continue
    mesh = load_mesh(layer["mesh"])
    if mesh is None:
        print(f"MESH_MISSING {layer['mesh']} for {layer['id']}")
        continue
    a = eas.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    a.set_actor_label(layer["id"])
    try:
        a.tags = [unreal.Name(layer["id"])]
    except Exception:
        pass
    handles = SDS.k2_gather_subobject_data_for_instance(a)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.HierarchicalInstancedStaticMeshComponent)
    new_handle, fail = SDS.add_new_subobject(params)
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(SDS.k2_find_subobject_data_from_handle(new_handle))
    comp.set_static_mesh(mesh)
    for i, slot in enumerate(layer.get("material_slots", [])):
        m = slot_material(slot)
        if m:
            comp.set_material(i, m)
    transforms = [unreal.Transform(V(loc), R(rot), V(scl)) for loc, rot, scl in layer["instances"]]
    comp.add_instances(transforms, True)
    total += len(transforms)
    print(f"LAYER {layer['id']} instances={len(transforms)}")
print(f"HISM_TOTAL {total}")

# ---------------------------------------------------------------- game mode + save
gm = plan.get("game_mode")
if gm:
    gmc = unreal.load_class(None, gm)
    if gmc:
        try:
            world.get_world_settings().set_editor_property("default_game_mode", gmc)
        except Exception as e:
            print(f"  game mode: {e}")
les.save_current_level()
print("BUILD_WORLD_DONE")
