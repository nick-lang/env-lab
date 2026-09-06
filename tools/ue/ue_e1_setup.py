# Runs inside Unreal (via tools/ue/remote.py). Experiment 01 setup:
#   1. duplicate the Barrow map to Barrow_E1 (baseline stays untouched)
#   2. import the heightmap terrain mesh + the scatter kit
#   3. record each dressing actor's height above the OLD ground, swap the ground for
#      the terrain mesh, and reseat every actor at the same height above the NEW ground
#   4. verify the terrain landed where the heightmap says (Y-flip round-trip check)
import json
import os

import unreal

CFG = "C:/Users/nickl/Documents/env-lab/experiments/01-barrow-density/e1.json"
with open(CFG, encoding="utf-8") as f:
    cfg = json.load(f)

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
eal = unreal.EditorAssetLibrary

# ---------------------------------------------------------------- 0. PIE off, map dup
try:
    les.editor_request_end_play()
except Exception:
    pass

src, dst = cfg["source_map"], cfg["target_map"]
# NB: duplicate_asset + load_level of the copy crashes the editor (the returned World keeps
# the package alive across the load). "Save As" from the source map is the safe route.
# save_map(world, dst) writes a copy to dst but the editor STAYS on the source package, so the
# target must be loaded explicitly afterwards, and the package is checked before any edit.
if not eal.does_asset_exist(dst):
    les.load_level(src)
    world = ues.get_editor_world()
    ok = unreal.EditorLoadingAndSavingUtils.save_map(world, dst)
    print(f"MAP_SAVED_AS {dst} ok={bool(ok)}")
les.load_level(dst)
world = ues.get_editor_world()
pkg = world.get_outer().get_path_name()
print(f"LEVEL_PACKAGE {pkg}")
if pkg != dst:
    raise SystemExit(f"WRONG_PACKAGE {pkg} != {dst} -- refusing to edit")


# ---------------------------------------------------------------- helpers
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
    if m is None:
        print(f"IMPORT_FAILED {name}")
        return None
    if complex_collision:
        try:
            bs = m.get_editor_property("body_setup")
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            try:
                bs.invalidate_physics_data()
                bs.create_physics_meshes()
            except Exception as e:
                print(f"  physics rebuild: {e}")
            eal.save_asset(f"{dest}/{name}")
            print(f"  complex-as-simple set on {name}")
        except Exception as e:
            print(f"  COLLISION_FLAG_FAIL {name}: {e}")
    print(f"IMPORTED {name} tris={m.get_num_triangles(0)}")
    return m


def hit_actor(d):
    a = d.get("hit_actor") or d.get("actor")
    return a


def ground_z(x, y, ground_labels, ignore=None):
    """Z of the first hit whose actor label is in ground_labels, walking down through others."""
    z_start = 30000.0
    for _ in range(12):
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, z_start), unreal.Vector(x, y, -30000.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignore or [],
            unreal.DrawDebugTrace.NONE, True, unreal.LinearColor.RED, unreal.LinearColor.GREEN, 0.0,
        )
        if not hit:
            return None
        d = hit.to_dict()
        if not d.get("blocking_hit"):
            return None
        loc = d["location"]
        z = float(loc.z) if hasattr(loc, "z") else float(loc["z"])
        a = hit_actor(d)
        if a is None:
            return z  # no actor info exposed: trust the hit
        try:
            lbl = a.get_actor_label()
        except Exception:
            return z
        if lbl in ground_labels:
            return z
        z_start = z - 2.0
    return None


# ---------------------------------------------------------------- 1. record deltas vs old ground
by_label = {a.get_actor_label(): a for a in eas.get_all_level_actors()}
old_ground = set(l for l in cfg["old_ground_labels"] + ["Terrain_E1"] if l in by_label)
print(f"OLD_GROUND {sorted(old_ground)}")
missing = [l for l in cfg["old_ground_labels"] if l not in by_label]
if missing:
    print(f"OLD_GROUND_MISSING {missing}")

ground_mat = None
gp = by_label.get("GroundPlane")
if gp:
    try:
        ground_mat = gp.static_mesh_component.get_material(0)
        print(f"GROUND_MAT {ground_mat.get_name() if ground_mat else None}")
    except Exception as e:
        print(f"ground mat read: {e}")

prefixes = tuple(cfg["reseat_prefixes"])
classes = tuple(cfg.get("reseat_classes", []))
targets = []
for lbl, a in by_label.items():
    cls = a.get_class().get_name()
    if lbl.startswith(prefixes) or cls in classes:
        if lbl in old_ground:
            continue
        targets.append((lbl, a))
print(f"RESEAT_TARGETS {len(targets)}")

deltas = {}
unseated = []
for lbl, a in targets:
    loc = a.get_actor_location()
    gz = ground_z(loc.x, loc.y, old_ground)
    if gz is None:
        unseated.append(lbl)
        continue
    deltas[lbl] = loc.z - gz
print(f"DELTAS_RECORDED {len(deltas)} no_old_ground={len(unseated)}")
if unseated:
    print(f"  no old ground under: {unseated[:12]}{' ...' if len(unseated) > 12 else ''}")

# ---------------------------------------------------------------- 2. import terrain + kit
terrain = import_fbx(cfg["terrain_fbx"], cfg["terrain_dest"], complex_collision=True)
kit = {}
for name in cfg["kit_meshes"]:
    p = os.path.join(cfg["kit_dir"], name + ".fbx")
    if os.path.isfile(p):
        m = import_fbx(p, cfg["kit_dest"])
        if m:
            kit[name] = m
    else:
        print(f"KIT_MISSING {p}")
print(f"KIT_IMPORTED {len(kit)}")

# ---------------------------------------------------------------- 3. swap ground
if terrain:
    for lbl in list(old_ground):
        a = by_label.get(lbl)
        if a:
            eas.destroy_actor(a)
    old_t = by_label.get("Terrain_E1")
    if old_t:
        eas.destroy_actor(old_t)
    ta = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
    ta.set_actor_label("Terrain_E1")
    ta.static_mesh_component.set_static_mesh(terrain)
    if ground_mat:
        ta.static_mesh_component.set_material(0, ground_mat)
    try:
        ta.static_mesh_component.set_editor_property("collision_profile_name", "BlockAll")
    except Exception as e:
        print(f"  collision profile: {e}")
    print("TERRAIN_PLACED")

    new_ground = {"Terrain_E1"}
    moved = 0
    lost = []
    for lbl, a in targets:
        if lbl not in deltas:
            continue
        loc = a.get_actor_location()
        gz = ground_z(loc.x, loc.y, new_ground)
        if gz is None:
            lost.append(lbl)
            continue
        a.set_actor_location(unreal.Vector(loc.x, loc.y, gz + deltas[lbl]), False, False)
        moved += 1
    print(f"RESEATED {moved} lost={len(lost)}")
    if lost:
        print(f"  no new ground under: {lost[:12]}")

    # ---------------------------------------------------------- 4. round-trip check
    with open(cfg["terrain_meta"], encoding="utf-8") as f:
        meta = json.load(f)
    worst = 0.0
    for s in meta.get("samples", []):
        gz = ground_z(s["x"] * 100.0, s["y"] * 100.0, new_ground)
        exp = s["z"] * 100.0
        if gz is None:
            print(f"  SAMPLE ({s['x']},{s['y']}) expected z={exp:.0f}cm got NO_HIT")
            worst = max(worst, 9e9)
            continue
        err = abs(gz - exp)
        worst = max(worst, err)
        print(f"  SAMPLE ({s['x']},{s['y']}) expected z={exp:.0f}cm got {gz:.0f}cm err={err:.0f}")
    print(f"TERRAIN_CHECK worst_err_cm={worst:.0f} {'OK' if worst < 60 else 'MISMATCH (Y flip?)'}")

les.save_current_level()
print("E1_SETUP_DONE")
