# Runs inside Unreal. Dumps a broad property set for look actors in two maps and prints the differences.
import json

import unreal

MAPS = {"E1": "/Game/Maps/Barrow_E1", "W": "/Game/Maps/Barrow_W"}
LABELS = {"E1": {"sun": "DirectionalLight", "sky": "SkyLight", "fog": "ExponentialHeightFog", "atmo": "SkyAtmosphere", "grade": "LookGrade", "clouds": "SkyClouds", "ward": "WardLight", "lantern": "WandererLight"},
          "W": {"sun": "look.sun", "sky": "look.sky", "fog": "look.fog", "atmo": "look.atmosphere", "grade": "look.grade", "clouds": "look.clouds", "ward": "site.gate.ward_light", "lantern": "prop.wanderer.light"}}
COMPS = {"sun": unreal.DirectionalLightComponent, "sky": unreal.SkyLightComponent, "fog": unreal.ExponentialHeightFogComponent, "atmo": unreal.SkyAtmosphereComponent, "clouds": unreal.VolumetricCloudComponent, "ward": unreal.PointLightComponent, "lantern": unreal.PointLightComponent}
PROPS = {
    "sun": ["intensity", "light_color", "temperature", "use_temperature", "atmosphere_sun_light", "light_source_angle", "light_source_soft_angle", "volumetric_scattering_intensity", "indirect_lighting_intensity", "specular_scale", "shadow_amount", "cascade_distribution_exponent", "dynamic_shadow_distance_movable_light", "cast_cloud_shadows", "cloud_shadow_strength", "forward_shading_priority", "light_function_material", "lighting_channels", "mobility"],
    "sky": ["intensity", "light_color", "real_time_capture", "source_type", "lower_hemisphere_color", "volumetric_scattering_intensity", "occlusion_max_distance", "min_occlusion", "cubemap_resolution", "sky_distance_threshold", "indirect_lighting_intensity", "mobility", "cast_shadows"],
    "fog": ["fog_density", "fog_height_falloff", "fog_inscattering_luminance", "fog_max_opacity", "start_distance", "end_distance", "fog_cutoff_distance", "directional_inscattering_luminance", "directional_inscattering_exponent", "directional_inscattering_start_distance", "volumetric_fog", "volumetric_fog_scattering_distribution", "volumetric_fog_albedo", "volumetric_fog_emissive", "volumetric_fog_extinction_scale", "volumetric_fog_distance", "second_fog_data", "sky_atmosphere_ambient_contribution_color_scale", "inscattering_color_cubemap", "fog_inscattering_color"],
    "atmo": ["rayleigh_scattering_scale", "rayleigh_scattering", "rayleigh_exponential_distribution", "mie_scattering_scale", "mie_scattering", "mie_absorption_scale", "mie_absorption", "mie_anisotropy", "mie_exponential_distribution", "other_absorption_scale", "other_absorption", "sky_luminance_factor", "aerial_pespective_view_distance_scale", "height_fog_contribution", "multi_scattering_factor", "transmittance_min_light_elevation_angle", "ground_albedo", "bottom_radius", "atmosphere_height", "transform_mode"],
    "clouds": ["layer_bottom_altitude", "layer_height", "tracing_start_max_distance", "tracing_max_distance", "material", "ground_albedo", "use_per_sample_atmospheric_light_transmittance", "sky_light_cloud_bottom_occlusion", "view_sample_count_scale", "reflection_view_sample_count_scale_value", "shadow_view_sample_count_scale", "shadow_tracing_distance"],
    "ward": ["intensity", "light_color", "attenuation_radius", "source_radius", "soft_source_radius", "source_length", "cast_shadows", "temperature", "use_temperature", "intensity_units", "volumetric_scattering_intensity", "indirect_lighting_intensity", "specular_scale", "mobility", "use_inverse_squared_falloff", "light_falloff_exponent"],
    "lantern": ["intensity", "light_color", "attenuation_radius", "source_radius", "soft_source_radius", "cast_shadows", "temperature", "use_temperature", "intensity_units", "volumetric_scattering_intensity", "indirect_lighting_intensity", "specular_scale", "mobility", "use_inverse_squared_falloff", "light_falloff_exponent"],
}
PPV = ["auto_exposure_method", "auto_exposure_bias", "auto_exposure_min_brightness", "auto_exposure_max_brightness", "auto_exposure_apply_physical_camera_exposure",
       "color_saturation", "color_contrast", "color_gamma", "color_gain", "color_offset", "color_saturation_shadows", "color_saturation_midtones", "color_saturation_highlights",
       "color_contrast_shadows", "color_gamma_shadows", "color_gain_shadows", "color_offset_shadows", "color_gain_highlights", "color_offset_highlights", "color_correction_shadows_max", "color_correction_highlights_min",
       "film_slope", "film_toe", "film_shoulder", "film_black_clip", "film_white_clip", "temperature_type", "white_temp", "white_tint",
       "bloom_method", "bloom_intensity", "bloom_threshold", "bloom_size_scale", "vignette_intensity", "grain_intensity", "film_grain_intensity", "sharpen",
       "ambient_occlusion_intensity", "ambient_occlusion_radius", "scene_color_tint", "indirect_lighting_intensity", "indirect_lighting_color", "lens_flare_intensity", "chromatic_aberration_start_offset", "scene_fringe_intensity",
       "dynamic_global_illumination_method", "reflection_method", "lumen_scene_lighting_quality", "lumen_final_gather_quality", "lumen_max_trace_distance", "lumen_scene_detail",
       "tone_curve_amount", "expand_gamut", "blue_correction", "local_exposure_highlight_contrast_scale", "local_exposure_shadow_contrast_scale", "local_exposure_detail_strength", "motion_blur_amount", "depth_of_field_fstop"]

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def js(v):
    if isinstance(v, (unreal.LinearColor, unreal.Color, unreal.Vector4, unreal.Vector, unreal.Rotator)):
        return str(v)
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    return str(v)


dump = {}
for key, mp in MAPS.items():
    les.load_level(mp)
    by = {a.get_actor_label(): a for a in eas.get_all_level_actors()}
    d = {}
    for role, lbl in LABELS[key].items():
        a = by.get(lbl)
        if a is None:
            d[role] = {"MISSING": lbl}
            continue
        rec = {}
        r = a.get_actor_rotation()
        rec["_rot"] = f"{r.pitch:.2f},{r.yaw:.2f},{r.roll:.2f}"
        l = a.get_actor_location()
        rec["_loc"] = f"{l.x:.0f},{l.y:.0f},{l.z:.0f}"
        if role == "grade":
            pps = a.get_editor_property("settings")
            rec["_unbound"] = str(a.get_editor_property("unbound"))
            rec["_priority"] = str(a.get_editor_property("priority"))
            rec["_blend_weight"] = str(a.get_editor_property("blend_weight"))
            for p in PPV:
                try:
                    if pps.get_editor_property("override_" + p):
                        rec[p] = js(pps.get_editor_property(p))
                except Exception:
                    pass
        else:
            c = a.get_component_by_class(COMPS[role])
            for p in PROPS[role]:
                try:
                    rec[p] = js(c.get_editor_property(p))
                except Exception:
                    pass
        d[role] = rec
    # anything else lit in the level: count of lights / ppvs
    d["_counts"] = {"ppv": sum(1 for a in by.values() if a.get_class().get_name() == "PostProcessVolume"),
                    "lights": sum(1 for a in by.values() if "Light" in a.get_class().get_name())}
    dump[key] = d

print("COUNTS E1", dump["E1"]["_counts"], "W", dump["W"]["_counts"])
for role in LABELS["E1"]:
    a, b = dump["E1"].get(role, {}), dump["W"].get(role, {})
    for p in sorted(set(a) | set(b)):
        if a.get(p) != b.get(p):
            print(f"DIFF {role}.{p}: E1={a.get(p)} | W={b.get(p)}")
print("DIFF_DONE")
