"""Author experiments/05-world-file/world.json for the Barrow from the E1/E3 scene export.

Reads build/world/export_scene.json (from ue_export_scene.py), the E1 terrain params and heightmap,
and the E3 scatter rules, and writes a world file where every placed thing has an id, an intent,
and a ground-relative height. This is a one-time bootstrap; after this the world file is the source.
"""
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORT = os.path.join(ROOT, "build", "world", "export_scene.json")
TERRAIN_PARAMS = os.path.join(ROOT, "experiments", "01-barrow-density", "terrain.json")
TERRAIN_BUILD = os.path.join(ROOT, "build", "terrain")
RULES = os.path.join(ROOT, "experiments", "03-asset-factory", "scatter_rules.json")
OUT = os.path.join(ROOT, "experiments", "05-world-file", "world.json")

exp = json.load(open(EXPORT, encoding="utf-8"))
meta = json.load(open(os.path.join(TERRAIN_BUILD, "meta.json"), encoding="utf-8"))
h = np.load(os.path.join(TERRAIN_BUILD, "height.npy"))
x0, y0 = meta["origin"]
sp = meta["spacing"]
res = meta["res"]


def ground_cm(x_cm, y_cm):
    """Bilinear sample of the heightmap (meters in, cm out). Matches the mesh exactly at vertices."""
    fx = (x_cm / 100.0 - x0) / sp
    fy = (y_cm / 100.0 - y0) / sp
    i = int(np.clip(np.floor(fx), 0, res - 2))
    j = int(np.clip(np.floor(fy), 0, res - 2))
    u = float(np.clip(fx - i, 0, 1))
    v = float(np.clip(fy - j, 0, 1))
    z = (h[j, i] * (1 - u) * (1 - v) + h[j, i + 1] * u * (1 - v) + h[j + 1, i] * (1 - u) * v + h[j + 1, i + 1] * u * v)
    return float(z) * 100.0


actors = {a["label"]: a for a in exp["actors"]}


def part(pid, label, intent, material=None, keep_material=False):
    a = actors[label]
    x, y, z = a["loc"]
    rec = {"id": pid, "intent": intent, "mesh": a["mesh"], "at": [round(x, 1), round(y, 1)],
           "above_ground": round(z - ground_cm(x, y), 1), "rot": [round(v, 2) for v in a["rot"]],
           "scale": [round(v, 3) for v in a["scale"]]}
    if keep_material:
        rec["materials"] = a.get("materials")
    elif material is not None:
        rec["materials"] = material
    else:
        rec["materials"] = None  # mesh default (generated PBR)
    return rec


def light(pid, label, intent):
    a = actors[label]
    x, y, z = a["loc"]
    p = a.get("PointLightComponent", {})
    return {"id": pid, "intent": intent, "class": "PointLight", "at": [round(x, 1), round(y, 1)],
            "above_ground": round(z - ground_cm(x, y), 1),
            "props": {k: p[k] for k in ("intensity", "light_color", "attenuation_radius", "source_radius", "cast_shadows") if k in p}}


def comp_props(label, comp, skip=()):
    p = actors[label].get(comp, {})
    return {k: v for k, v in p.items() if k not in skip and not (isinstance(v, str) and v.startswith("<"))}


terrain_params = json.load(open(TERRAIN_PARAMS, encoding="utf-8"))
rules = json.load(open(RULES, encoding="utf-8"))
KIT = "/Game/Meshes/EnvLab"
layers = []
for L in rules["layers"]:
    layers.append({
        "id": "biome.barrow." + L["name"].lower(),
        "intent": {
            "Pebbles": "small stones along the walk so the ground reads at 1-3 m",
            "Rocks": "mid-size rocks favouring slopes; the hill's bones showing through",
            "Boulders": "a few generated hero boulders on flanks, never on the path",
            "GrassDense": "grass band hugging the path corridor, thinning outward",
            "Shrubs": "low shrubs on the flats, clumped",
            "Trees": "sparse trees on the flanks, none near the path or the gate, so the gate crowns the hill against sky",
        }.get(L["name"], L["name"]),
        "meshes": [m if m.startswith("/Game/") else f"{KIT}/{m}" for m in L["meshes"]],
        "weights": L.get("weights"),
        "materials": {"slots": L.get("slots", [])},
        "rules": {k: L[k] for k in ("region", "attempts_per_m2", "path_min", "path_max", "gate_min", "slope_min", "slope_max", "slope_boost", "noise", "scale", "sink", "align_to_slope", "max_count") if k in L},
    })

world = {
    "meta": {"name": "barrow", "version": 0, "seed": 7, "map": "/Game/Maps/Barrow_W", "units": "cm",
             "intent": "A sixty-second walk up a hillside at ember dusk to an ancient stone gate with something magical burning in it, lantern in hand."},
    "terrain": {"id": "terrain", "intent": "a valley floor rising to a gate crest, far ridges lower than the gate so it silhouettes against sky; path corridor kept smooth",
                "params": terrain_params, "material": "/Game/Materials/M_LR6_Ground"},
    "look": {
        "id": "look", "intent": "Ember Dusk: warm low sun, blue fog, filmic grade, cumulus",
        "sun": {"class": "DirectionalLight", "rot": actors["DirectionalLight"]["rot"], "props": comp_props("DirectionalLight", "DirectionalLightComponent")},
        "sky": {"class": "SkyLight", "props": comp_props("SkyLight", "SkyLightComponent", skip=("source_type",))},
        "atmosphere": {"class": "SkyAtmosphere", "props": comp_props("SkyAtmosphere", "SkyAtmosphereComponent")},
        "fog": {"class": "ExponentialHeightFog", "props": comp_props("ExponentialHeightFog", "ExponentialHeightFogComponent", skip=("second_fog_data",))},
        "clouds": {"class": "VolumetricCloud", "props": comp_props("SkyClouds", "VolumetricCloudComponent")},
        "grade": {"class": "PostProcessVolume", "unbound": True, "settings": actors["LookGrade"].get("ppv", {})},
    },
    "sites": [
        {"id": "site.gate", "intent": "the destination: a dolmen gate on the crest with a ward veil burning between the uprights",
         "anchor": [0, 12000],
         "parts": [
             part("site.gate.upright_w", "Dolmen_UprightWest", "west upright, generated megalith with the carved spiral"),
             part("site.gate.upright_e", "Dolmen_UprightEast", "east upright"),
             part("site.gate.lintel", "Dolmen_Lintel", "capstone"),
             part("site.gate.fallen", "Dolmen_Fallen", "a fallen stone off the west side, hints the gate is older than the path"),
             part("site.gate.veil", "WardSeam", "the ward veil between the uprights", keep_material=True),
             part("site.gate.glow", "WardGroundGlow", "ground glow under the veil", keep_material=True),
         ] + [part(f"site.gate.ramp_{i:02d}", f"Ramp_{i:02d}", "stepped flagstone ramp climbing the crest to the gate", keep_material=True) for i in range(7)],
         "lights": [light("site.gate.ward_light", "WardLight", "the veil's light on the stones")]},
    ],
    "props": [
        {"id": "prop.wanderer", "intent": "the player's stand-in: a cloaked figure mid-path with a lantern, the scene's scale cue and warm accent",
         "parts": [part("prop.wanderer.figure", "Wanderer", "cloaked figure", keep_material=True),
                   part("prop.wanderer.lantern", "Wanderer_Lantern", "lantern", keep_material=True)],
         "lights": [light("prop.wanderer.light", "WandererLight", "lantern light")]},
    ],
    "paths": [
        {"id": "path.walk", "intent": "an S-curve of stepping stones from the start to the ramp; the walk itself",
         "kind": "flagstones", "curve": {"amp": 220, "period": 3800, "y0": 760, "y1": 8280}, "count": 26,
         "mesh": "/Engine/BasicShapes/Cube", "materials": ["/Game/Materials/M_LR5_P2_grayflag"],
         "scale": [2.6, 1.7, 0.22], "above_ground": -8.0, "yaw_jitter": 7.0},
    ],
    "biomes": [{"id": "biome.barrow", "intent": "worn hill grassland, sparse trees on the flanks, bare crest",
                "path": rules["path"], "gate": rules["gate"], "layers": layers}],
    "player": {"id": "player.start", "at": [0, 600], "above_ground": 125.0, "yaw": 90.0,
               "game_mode": "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"},
    "shots": json.load(open(os.path.join(ROOT, "experiments", "03-asset-factory", "shots.json"), encoding="utf-8"))["shots"],
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(world, open(OUT, "w", encoding="utf-8"), indent=1)
print("WORLD_WRITTEN", OUT, "parts", sum(len(s["parts"]) for s in world["sites"]) + sum(len(p["parts"]) for p in world["props"]), "layers", len(layers))
