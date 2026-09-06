# Runs inside Unreal. Addressability test: for each shot in build/active_pick.json, cast N random
# screen-space rays from the camera, and report what they hit as (actor label, instance index) so the
# lab can resolve them against the manifest. Writes build/world/<name>/picks.json.
import json
import math
import os
import random

import unreal

CFG = json.load(open("C:/Users/nickl/Documents/env-lab/build/active_pick.json", encoding="utf-8"))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rng = random.Random(int(CFG.get("seed", 1)))
ground = {a.get_actor_label(): a for a in eas.get_all_level_actors()}.get("terrain")


def ground_z(x, y):
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(x, y, 30000.0), unreal.Vector(x, y, -30000.0),
                                                 unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True,
                                                 unreal.LinearColor.RED, unreal.LinearColor.GREEN, 0.0)
    if hit:
        d = hit.to_dict()
        if d.get("blocking_hit"):
            return float(d["location"].z)
    return 0.0


results = []
for shot in CFG["shots"]:
    loc = list(shot["loc"])
    if shot.get("rel"):
        loc[2] = ground_z(loc[0], loc[1]) + loc[2]
    rot = unreal.Rotator(pitch=shot["rot"][0], yaw=shot["rot"][1], roll=0.0)
    fov = float(shot.get("fov", 70.0))
    aspect = 16.0 / 9.0
    fwd = rot.get_forward_vector()
    right = rot.get_right_vector()
    up = rot.get_up_vector()
    half_w = math.tan(math.radians(fov / 2.0))
    half_h = half_w / aspect
    for k in range(int(CFG.get("per_shot", 10))):
        sx = rng.uniform(-1, 1)
        sy = rng.uniform(-1, 1)
        d = fwd + right * (sx * half_w) + up * (-sy * half_h)
        d = d / d.length()
        start = unreal.Vector(*loc)
        end = start + d * 200000.0
        hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                                                     unreal.DrawDebugTrace.NONE, True, unreal.LinearColor.RED, unreal.LinearColor.GREEN, 0.0)
        rec = {"shot": shot["name"], "px": round((sx + 1) / 2, 3), "py": round((sy + 1) / 2, 3), "hit": None}
        if hit:
            dd = hit.to_dict()
            if dd.get("blocking_hit"):
                a = dd.get("hit_actor") or dd.get("actor")
                comp = dd.get("hit_component") or dd.get("component")
                item = dd.get("item")
                lbl = a.get_actor_label() if a else None
                rec["hit"] = {"label": lbl, "component": comp.get_class().get_name() if comp else None, "item": int(item) if item is not None else None,
                              "location": [round(dd["location"].x, 1), round(dd["location"].y, 1), round(dd["location"].z, 1)]}
        results.append(rec)

out = CFG["out"]
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)
print(f"PICK_DONE {len(results)} rays -> {out}")
