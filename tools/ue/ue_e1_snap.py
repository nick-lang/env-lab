# Runs inside Unreal. Captures the fixed shot list for an experiment via SceneCapture2D
# (works with the editor window backgrounded). Shot z may be ground-relative ("rel": true).
import json
import os

import unreal

SHOTS = "C:/Users/nickl/Documents/env-lab/experiments/01-barrow-density/shots.json"
_ovr = "C:/Users/nickl/Documents/env-lab/build/active_shots.txt"
if os.path.isfile(_ovr):
    SHOTS = open(_ovr, encoding="utf-8").read().strip()
    print(f"USING SHOTS override: {SHOTS}")
with open(SHOTS, encoding="utf-8") as f:
    spec = json.load(f)
OUT = spec["out"]
PREFIX = spec.get("prefix", "")
os.makedirs(OUT, exist_ok=True)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ground_labels = set(spec.get("ground_labels", ["Terrain_E1"]))


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
        loc = d["location"]
        z = float(loc.z) if hasattr(loc, "z") else float(loc["z"])
        a = d.get("hit_actor") or d.get("actor")
        if a is None:
            return z
        try:
            if a.get_actor_label() in ground_labels:
                return z
        except Exception:
            return z
        z_start = z - 2.0
    return None


for shot in spec["shots"]:
    w = int(shot.get("width", 1600))
    h = int(shot.get("height", 900))
    loc = list(shot["loc"])
    if shot.get("rel"):
        gz = ground_z(loc[0], loc[1])
        if gz is not None:
            loc[2] = gz + loc[2]
    rot = shot["rot"]
    rt = unreal.RenderingLibrary.create_render_target2d(
        world, w, h, unreal.TextureRenderTargetFormat.RTF_RGBA8, unreal.LinearColor(0, 0, 0, 1), False
    )
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(loc[0], loc[1], loc[2]))
    cap.set_actor_rotation(unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2] if len(rot) > 2 else 0.0), False)
    comp = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", float(shot.get("fov", 70.0)))
    comp.set_editor_property("post_process_blend_weight", 1.0)
    if "ev" in shot:
        pps = comp.get_editor_property("post_process_settings")
        pps.set_editor_property("override_auto_exposure_min_brightness", True)
        pps.set_editor_property("override_auto_exposure_max_brightness", True)
        pps.set_editor_property("auto_exposure_min_brightness", float(shot["ev"]))
        pps.set_editor_property("auto_exposure_max_brightness", float(shot["ev"]))
        comp.set_editor_property("post_process_settings", pps)
    comp.capture_scene()
    name = f"{PREFIX}{shot['name']}.png"
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
    cap.destroy_actor()
    print(f"SNAP_WRITTEN {name} z={loc[2]:.0f}")

print("SNAP_DONE")
