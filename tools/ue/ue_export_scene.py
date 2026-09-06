# Runs inside Unreal. Dumps the current level's actors to JSON so a world file can be authored
# from the real scene: transforms, meshes, materials, and a curated property set for lights,
# fog, sky, clouds and post-process volumes. Scatter_* and Terrain_E1 are summarised, not dumped.
import json
import os

import unreal

OUT = "C:/Users/nickl/Documents/env-lab/build/world/export_scene.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ues.get_editor_world()

PROPS = {
    "DirectionalLightComponent": ["intensity", "light_color", "temperature", "use_temperature", "atmosphere_sun_light", "cast_shadows", "light_source_angle", "volumetric_scattering_intensity", "indirect_lighting_intensity"],
    "SkyLightComponent": ["intensity", "light_color", "real_time_capture", "source_type", "lower_hemisphere_color", "volumetric_scattering_intensity"],
    "ExponentialHeightFogComponent": ["fog_density", "fog_height_falloff", "fog_inscattering_luminance", "fog_max_opacity", "start_distance", "directional_inscattering_luminance", "directional_inscattering_exponent", "directional_inscattering_start_distance", "volumetric_fog", "volumetric_fog_scattering_distribution", "volumetric_fog_albedo", "volumetric_fog_extinction_scale", "second_fog_data"],
    "SkyAtmosphereComponent": ["rayleigh_scattering_scale", "rayleigh_scattering", "mie_scattering_scale", "mie_absorption_scale", "mie_anisotropy", "aerial_pespective_view_distance_scale", "multi_scattering_factor"],
    "VolumetricCloudComponent": ["layer_bottom_altitude", "layer_height", "tracing_start_max_distance", "tracing_max_distance", "material"],
    "PointLightComponent": ["intensity", "light_color", "attenuation_radius", "source_radius", "cast_shadows", "temperature", "use_temperature"],
    "SpotLightComponent": ["intensity", "light_color", "attenuation_radius", "inner_cone_angle", "outer_cone_angle"],
}
PPV_SETTINGS = [
    "auto_exposure_method", "auto_exposure_bias", "auto_exposure_min_brightness", "auto_exposure_max_brightness",
    "color_saturation", "color_contrast", "color_gamma", "color_gain", "color_offset", "color_saturation_shadows", "color_saturation_highlights",
    "film_slope", "film_toe", "film_shoulder", "film_black_clip", "film_white_clip",
    "white_temp", "white_tint", "bloom_intensity", "bloom_threshold", "vignette_intensity", "grain_intensity",
    "ambient_occlusion_intensity", "ambient_occlusion_radius", "scene_color_tint", "indirect_lighting_intensity", "indirect_lighting_color",
]


def jsonable(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, unreal.LinearColor):
        return {"r": v.r, "g": v.g, "b": v.b, "a": v.a}
    if isinstance(v, unreal.Color):
        return {"r": v.r, "g": v.g, "b": v.b, "a": v.a}
    if isinstance(v, unreal.Vector4):
        return {"x": v.x, "y": v.y, "z": v.z, "w": v.w}
    if isinstance(v, unreal.Vector):
        return {"x": v.x, "y": v.y, "z": v.z}
    if isinstance(v, unreal.Rotator):
        return {"pitch": v.pitch, "yaw": v.yaw, "roll": v.roll}
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    if isinstance(v, unreal.Name):
        return str(v)
    try:
        return str(v)
    except Exception:
        return None


def dump_props(obj, names):
    out = {}
    for n in names:
        try:
            out[n] = jsonable(obj.get_editor_property(n))
        except Exception:
            pass
    return out


def dump_ppv(pps):
    out = {}
    for n in PPV_SETTINGS:
        try:
            if pps.get_editor_property("override_" + n):
                out[n] = jsonable(pps.get_editor_property(n))
        except Exception:
            pass
    return out


actors = []
summary = {"scatter": {}, "terrain": None, "skipped": 0}
for a in eas.get_all_level_actors():
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    if lbl.startswith("Scatter_"):
        n = 0
        for c in a.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
            n += c.get_instance_count()
        summary["scatter"][lbl] = n
        continue
    loc = a.get_actor_location()
    rot = a.get_actor_rotation()
    scl = a.get_actor_scale3d()
    rec = {"label": lbl, "class": cls, "loc": [loc.x, loc.y, loc.z], "rot": [rot.pitch, rot.yaw, rot.roll], "scale": [scl.x, scl.y, scl.z]}
    if lbl == "Terrain_E1":
        summary["terrain"] = rec
        continue
    smc = a.get_component_by_class(unreal.StaticMeshComponent)
    if smc:
        m = smc.static_mesh
        rec["mesh"] = m.get_path_name() if m else None
        rec["materials"] = [(smc.get_material(i).get_path_name() if smc.get_material(i) else None) for i in range(smc.get_num_materials())]
        try:
            rec["hidden"] = bool(smc.get_editor_property("hidden_in_game"))
        except Exception:
            pass
    for comp_cls, names in PROPS.items():
        klass = getattr(unreal, comp_cls, None)
        if klass is None:
            continue
        c = a.get_component_by_class(klass)
        if c:
            rec[comp_cls] = dump_props(c, names)
    if cls == "PostProcessVolume":
        try:
            rec["ppv"] = dump_ppv(a.get_editor_property("settings"))
            rec["unbound"] = bool(a.get_editor_property("unbound"))
            rec["priority"] = float(a.get_editor_property("priority"))
        except Exception as e:
            rec["ppv_error"] = str(e)
    tags = []
    try:
        tags = [str(t) for t in a.tags]
    except Exception:
        pass
    if tags:
        rec["tags"] = tags
    actors.append(rec)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"level": world.get_outer().get_path_name(), "summary": summary, "actors": actors}, f, indent=1)
print(f"EXPORT_DONE actors={len(actors)} scatter={summary['scatter']} -> {OUT}")
