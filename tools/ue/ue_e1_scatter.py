# Runs inside Unreal. Rules-based density: each layer is a set of rules (region, path distance,
# gate distance, slope band, clumping noise), not a list of instances. Instances land in one
# HierarchicalInstancedStaticMesh component per layer+mesh on an actor labelled Scatter_<layer>.
# Re-running replaces the layer. Units: rules in meters, world in cm.
import json
import os
import math
import random

import unreal

RULES = "C:/Users/nickl/Documents/env-lab/experiments/01-barrow-density/scatter_rules.json"
_ovr = "C:/Users/nickl/Documents/env-lab/build/active_rules.txt"
if os.path.isfile(_ovr):
    RULES = open(_ovr, encoding="utf-8").read().strip()
    print(f"USING RULES override: {RULES}")
with open(RULES, encoding="utf-8") as f:
    rules = json.load(f)

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eal = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary

try:
    les.editor_request_end_play()
except Exception:
    pass

by_label = {a.get_actor_label(): a for a in eas.get_all_level_actors()}
ground_labels = set(rules["ground_labels"])
KIT = "/Game/Meshes/EnvLab"


# ---------------------------------------------------------------- materials
def make_mat(name, rgb, roughness=0.9):
    full = f"/Game/Materials/{name}"
    if eal.does_asset_exist(full):
        return eal.load_asset(full)
    m = at.create_asset(name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    c = mel.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -400, 0)
    c.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 220)
    r.set_editor_property("r", roughness)
    mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    eal.save_asset(full)
    return m


def resolve_material(spec):
    if isinstance(spec, dict):
        return make_mat(spec["name"], spec["rgb"], spec.get("roughness", 0.9))
    if spec == "@grass":
        for lbl, a in by_label.items():
            if lbl.startswith("Grass_"):
                try:
                    return a.static_mesh_component.get_material(0)
                except Exception:
                    pass
        return eal.load_asset("/Game/Materials/M_GrassClump")
    return eal.load_asset(spec)


MATS = {k: resolve_material(v) for k, v in rules["materials"].items()}
for k, v in MATS.items():
    print(f"MAT {k} -> {v.get_name() if v else 'MISSING'}")


# ---------------------------------------------------------------- geometry helpers
def hit_actor(d):
    return d.get("hit_actor") or d.get("actor")


def ground_hit(x, y):
    """(z, normal) of the ground under x,y (cm), walking down through non-ground actors."""
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
        n = d.get("impact_normal") or d.get("normal")
        if n is not None and not hasattr(n, "z"):
            n = unreal.Vector(n["x"], n["y"], n["z"])
        a = hit_actor(d)
        if a is None:
            return z, n
        try:
            if a.get_actor_label() in ground_labels:
                return z, n
        except Exception:
            return z, n
        z_start = z - 2.0
    return None


P = rules["path"]
PATH_PTS = []
for i in range(400):
    y = P["y0"] + (P["y1"] - P["y0"]) * i / 399.0
    x = P["amp"] * math.sin(2.0 * math.pi * (y - P["y0"]) / P["period"])
    PATH_PTS.append((x, y))


def path_dist_m(x, y):
    best = 1e18
    for px, py in PATH_PTS[::4]:
        d = (x - px) ** 2 + (y - py) ** 2
        if d < best:
            best = d
    return math.sqrt(best) / 100.0


GATE = (rules["gate"]["x"], rules["gate"]["y"])


def gate_dist_m(x, y):
    return math.hypot(x - GATE[0], y - GATE[1]) / 100.0


def _h(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 4294967295.0


def vnoise(x, y, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _h(ix, iy, seed), _h(ix + 1, iy, seed)
    c, d = _h(ix, iy + 1, seed), _h(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def clump_noise(x_m, y_m, scale, seed):
    return 0.6 * vnoise(x_m / scale, y_m / scale, seed) + 0.4 * vnoise(x_m / scale * 2.3 + 7, y_m / scale * 2.3 + 3, seed + 1)


# ---------------------------------------------------------------- scatter
def load_mesh(name):
    path = name if name.startswith("/Game/") else f"{KIT}/{name}"
    m = eal.load_asset(path)
    if m is None:
        print(f"MESH_MISSING {path}")
    return m


def get_or_make_layer_actor(layer_name):
    lbl = f"Scatter_{layer_name}"
    for l2, old in list(by_label.items()):
        if l2 == lbl or l2.startswith(f"{layer_name}_SM_"):
            eas.destroy_actor(old)
    a = eas.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    a.set_actor_label(lbl)
    return a


SDS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


class ActorPlacer:
    """Fallback when a HISM component can't be attached: one StaticMeshActor per instance."""

    def __init__(self, mesh, mats, label):
        self.mesh, self.mats, self.label, self.n = mesh, mats, label, 0

    def add_instance(self, t, _world_space=True):
        a = eas.spawn_actor_from_class(unreal.StaticMeshActor, t.translation)
        a.set_actor_transform(t, False, False)
        a.static_mesh_component.set_static_mesh(self.mesh)
        for i, m in enumerate(self.mats):
            if m:
                a.static_mesh_component.set_material(i, m)
        a.set_actor_label(f"{self.label}_{self.n:04d}")
        self.n += 1


def add_hism(actor, mesh, mats, label):
    """Add a HISM component to a level actor via the SubobjectDataSubsystem (the 5.x way)."""
    try:
        handles = SDS.k2_gather_subobject_data_for_instance(actor)
        params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.HierarchicalInstancedStaticMeshComponent)
        new_handle, fail = SDS.add_new_subobject(params)
        data = SDS.k2_find_subobject_data_from_handle(new_handle)
        comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
        if comp is None:
            raise RuntimeError(f"no component object ({fail})")
        comp.set_static_mesh(mesh)
        for i, m in enumerate(mats):
            if m:
                comp.set_material(i, m)
        try:
            comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
        except Exception:
            pass
        return comp
    except Exception as e:
        print(f"  HISM_FALLBACK ({e}) -> per-instance actors for {label}")
        return ActorPlacer(mesh, mats, label)


def rot_from_normal(n, yaw_deg):
    """Rotator whose up axis is n (blend toward slope), with the given yaw."""
    if n is None:
        return unreal.Rotator(pitch=0.0, yaw=yaw_deg, roll=0.0)
    up = unreal.Vector(n.x, n.y, n.z)
    r = unreal.MathLibrary.make_rot_from_zx(up, unreal.Vector(math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg)), 0.0))
    return r


total = 0
rng_master = random.Random(int(rules.get("seed", 1)))
for L in rules["layers"]:
    seed = rng_master.randint(0, 1 << 30)
    rng = random.Random(seed)
    meshes = [load_mesh(n) for n in L["meshes"]]
    meshes = [m for m in meshes if m]
    if not meshes:
        print(f"LAYER {L['name']} SKIPPED (no meshes)")
        continue
    weights = L.get("weights") or [1.0] * len(meshes)
    mats = [MATS.get(s) for s in L.get("slots", [])]
    actor = get_or_make_layer_actor(L["name"])
    comps = [add_hism(actor, m, mats, f"{L['name']}_{m.get_name()}") for m in meshes]

    x0, y0, x1, y1 = L["region"]
    area = (x1 - x0) * (y1 - y0)
    attempts = int(area * L["attempts_per_m2"])
    nz = L.get("noise")
    placed = [0] * len(meshes)
    rejected = {"path": 0, "gate": 0, "slope": 0, "noise": 0, "ground": 0, "region": 0}
    max_count = L.get("max_count", 1 << 30)
    for _ in range(attempts):
        if sum(placed) >= max_count:
            break
        xm = rng.uniform(x0, x1)
        ym = rng.uniform(y0, y1)
        xc, yc = xm * 100.0, ym * 100.0
        pdm = path_dist_m(xc, yc)
        if pdm < L.get("path_min", 0.0) or pdm > L.get("path_max", 1e9):
            rejected["path"] += 1
            continue
        if gate_dist_m(xc, yc) < L.get("gate_min", 0.0):
            rejected["gate"] += 1
            continue
        if nz:
            v = clump_noise(xm, ym, nz["scale"], seed & 0xFFFF)
            if v < nz["threshold"]:
                rejected["noise"] += 1
                continue
        g = ground_hit(xc, yc)
        if g is None:
            rejected["ground"] += 1
            continue
        gz, n = g
        slope = 0.0
        if n is not None:
            slope = math.degrees(math.acos(max(-1.0, min(1.0, n.z))))
        smin, smax = L.get("slope_min", 0.0), L.get("slope_max", 90.0)
        if slope < smin or slope > smax:
            rejected["slope"] += 1
            continue
        boost = L.get("slope_boost")
        if boost and slope < boost and rng.random() < 0.5:
            rejected["slope"] += 1
            continue
        idx = rng.choices(range(len(meshes)), weights=weights)[0]
        s = rng.uniform(*L["scale"])
        yaw = rng.uniform(0, 360)
        rot = rot_from_normal(n, yaw) if L.get("align_to_slope") else unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
        bounds = meshes[idx].get_bounding_box()
        h = (bounds.max.z - bounds.min.z) * s
        z = gz - h * L.get("sink", 0.0)
        t = unreal.Transform(unreal.Vector(xc, yc, z), rot, unreal.Vector(s, s, s))
        comps[idx].add_instance(t, True)
        placed[idx] += 1
    n_placed = sum(placed)
    total += n_placed
    print(f"LAYER {L['name']} attempts={attempts} placed={n_placed} per_mesh={placed} rejected={rejected}")

les.save_current_level()
print(f"SCATTER_DONE total={total}")
