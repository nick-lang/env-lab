# Runs inside Unreal. Asset lineup shots: spawn each mesh in a row on the terrain at a spot away
# from the ward light, capture one frame with locked exposure, destroy the temp actors.
# Config: build/lineup.json {"out": dir, "sets": [{"name", "meshes": [paths], "material": optional}], "y": cm, "ev": float}
import json
import os

import unreal

CFG = "C:/Users/nickl/Documents/env-lab/build/lineup.json"
with open(CFG, encoding="utf-8") as f:
    cfg = json.load(f)
OUT = cfg["out"]
os.makedirs(OUT, exist_ok=True)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
eal = unreal.EditorAssetLibrary
ground_labels = {"Terrain_E1", "terrain"}


def ground_z(x, y):
    z_start = 30000.0
    for _ in range(10):
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x, y, z_start), unreal.Vector(x, y, -30000.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            unreal.DrawDebugTrace.NONE, True, unreal.LinearColor.RED, unreal.LinearColor.GREEN, 0.0,
        )
        if not hit:
            return None
        d = hit.to_dict()
        if not d.get("blocking_hit"):
            return None
        z = float(d["location"].z)
        a = d.get("hit_actor") or d.get("actor")
        try:
            if a is None or a.get_actor_label() in ground_labels:
                return z
        except Exception:
            return z
        z_start = z - 2.0
    return None


def capture(name, loc, rot, fov, ev=None, w=1600, h=900):
    rt = unreal.RenderingLibrary.create_render_target2d(world, w, h, unreal.TextureRenderTargetFormat.RTF_RGBA8, unreal.LinearColor(0, 0, 0, 1), False)
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(*loc))
    cap.set_actor_rotation(unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=0.0), False)
    comp = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", float(fov))
    comp.set_editor_property("post_process_blend_weight", 1.0)
    if ev is not None:
        pps = comp.get_editor_property("post_process_settings")
        pps.set_editor_property("override_auto_exposure_min_brightness", True)
        pps.set_editor_property("override_auto_exposure_max_brightness", True)
        pps.set_editor_property("auto_exposure_min_brightness", float(ev))
        pps.set_editor_property("auto_exposure_max_brightness", float(ev))
        comp.set_editor_property("post_process_settings", pps)
    comp.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
    cap.destroy_actor()
    print(f"LINEUP_WRITTEN {name}")


y = float(cfg.get("y", -2500))
spacing = float(cfg.get("spacing", 700))
row_x = cfg.get("row_x")  # if set: objects run along Y at x=row_x and cameras look east (+X)
for s in cfg["sets"]:
    temps = []
    meshes = [eal.load_asset(p) for p in s["meshes"]]
    n = len(meshes)
    mat = eal.load_asset(s["material"]) if s.get("material") else None
    for i, m in enumerate(meshes):
        if m is None:
            print(f"  MISSING {s['meshes'][i]}")
            continue
        off = (i - (n - 1) / 2.0) * spacing
        x, yy = (float(row_x), y + off) if row_x is not None else (off, y)
        gz = ground_z(x, yy) or 0.0
        b = m.get_bounding_box()
        z = gz - b.min.z
        a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x, yy, z))
        a.static_mesh_component.set_static_mesh(m)
        if mat:
            for k in range(a.static_mesh_component.get_num_materials()):
                a.static_mesh_component.set_material(k, mat)
        a.set_actor_label(f"Lineup_{s['name']}_{i}")
        temps.append(a)
    cams = cfg.get("cameras") or [{"name": "", "dist": float(cfg.get("cam_dist", 3000)), "height": 1250.0, "pitch": -17.0, "fov": cfg.get("fov", 55)}]
    for cam in cams:
        suffix = f"_{cam['name']}" if cam.get("name") else ""
        if row_x is not None:
            cx, cy = float(row_x) - cam["dist"], y + float(cam.get("side", 0.0))
            yaw = 0.0
        else:
            cx, cy = float(cam.get("x", -400.0)), y - cam["dist"]
            yaw = 84.0 if cam["dist"] < 8000 else 90.0
        gzc = ground_z(cx, cy) or 0.0
        capture(f"lineup_{s['name']}{suffix}", (cx, cy, gzc + cam["height"]), (cam["pitch"], yaw), cam.get("fov", 55), cfg.get("ev"))
    for a in temps:
        eas.destroy_actor(a)
print("LINEUP_DONE")
