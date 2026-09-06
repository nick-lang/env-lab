# Runs inside Unreal. Imports generated material sets (BaseColor/Normal/Roughness tiles) and builds:
#   - M_Gen_<name>: UV-tiled PBR material (tiling param baked as a constant)          for props / slabs
#   - M_Ground_<name>: world-aligned terrain material blending three sets by height + slope
# Config: build/materials/import.json
#   {"dest": "/Game/Materials/Gen", "sets": {"name": {"dir": "...", "tiling": 2.0}},
#    "ground": {"name": "Barrow", "grass": "ground_grass", "dry": "ground_dry", "rock": "rock_face",
#               "tile_cm": 400, "z_low": 200, "z_high": 900, "slope_start": 0.55, "slope_end": 0.8}}
import json
import os

import unreal

CFG = json.load(open("C:/Users/nickl/Documents/env-lab/build/materials/import.json", encoding="utf-8"))
DEST = CFG.get("dest", "/Game/Materials/Gen")
eal = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
TEX = {}


def import_texture(path, name, srgb, normal=False):
    full = f"{DEST}/{name}"
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    at.import_asset_tasks([t])
    tex = eal.load_asset(full)
    if tex is None:
        print(f"  TEX_IMPORT_FAILED {name}")
        return None
    try:
        tex.set_editor_property("srgb", srgb)
        if normal:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
            tex.set_editor_property("flip_green_channel", False)
        elif not srgb:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        eal.save_asset(full)
    except Exception as e:
        print(f"  tex settings {name}: {e}")
    return tex


def textures_for(set_name):
    if set_name in TEX:
        return TEX[set_name]
    d = CFG["sets"][set_name]["dir"]
    TEX[set_name] = {
        "base": import_texture(os.path.join(d, "BaseColor.png"), f"T_{set_name}_BaseColor", True),
        "normal": import_texture(os.path.join(d, "Normal.png"), f"T_{set_name}_Normal", False, normal=True),
        "rough": import_texture(os.path.join(d, "Roughness.png"), f"T_{set_name}_Roughness", False),
    }
    return TEX[set_name]


def new_material(name):
    full = f"{DEST}/{name}"
    if eal.does_asset_exist(full):
        eal.delete_asset(full)
    return at.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew()), full


def sample(m, tex, uv_expr, x, y, kind):
    n = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, x, y)
    n.set_editor_property("texture", tex)
    if kind == "normal":
        n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif kind == "linear":
        n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    if uv_expr is not None:
        mel.connect_material_expressions(uv_expr, "", n, "UVs")
    return n


def uv_tiled(m, tiling, x, y):
    uv = mel.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, x, y)
    uv.set_editor_property("u_tiling", float(tiling))
    uv.set_editor_property("v_tiling", float(tiling))
    return uv


def build_simple(set_name, tiling):
    m, full = new_material(f"M_Gen_{set_name}")
    t = textures_for(set_name)
    uv = uv_tiled(m, tiling, -900, 0)
    if t["base"]:
        mel.connect_material_property(sample(m, t["base"], uv, -600, -200, "color"), "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    if t["normal"]:
        mel.connect_material_property(sample(m, t["normal"], uv, -600, 100, "normal"), "RGB", unreal.MaterialProperty.MP_NORMAL)
    if t["rough"]:
        mel.connect_material_property(sample(m, t["rough"], uv, -600, 400, "linear"), "R", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    eal.save_asset(full)
    print(f"  MATERIAL M_Gen_{set_name}")
    return full


def world_uv(m, tile_cm, x, y):
    wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, x, y)
    mask = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x + 200, y)
    mask.set_editor_property("r", True)
    mask.set_editor_property("g", True)
    mask.set_editor_property("b", False)
    mask.set_editor_property("a", False)
    mel.connect_material_expressions(wp, "", mask, "")
    div = mel.create_material_expression(m, unreal.MaterialExpressionDivide, x + 400, y)
    div.set_editor_property("const_b", float(tile_cm))
    mel.connect_material_expressions(mask, "", div, "A")
    return div


def height_alpha(m, z_low, z_high, x, y):
    wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, x, y)
    mz = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x + 200, y)
    mz.set_editor_property("r", False)
    mz.set_editor_property("g", False)
    mz.set_editor_property("b", True)
    mz.set_editor_property("a", False)
    mel.connect_material_expressions(wp, "", mz, "")
    sub = mel.create_material_expression(m, unreal.MaterialExpressionSubtract, x + 400, y)
    sub.set_editor_property("const_b", float(z_low))
    mel.connect_material_expressions(mz, "", sub, "A")
    div = mel.create_material_expression(m, unreal.MaterialExpressionDivide, x + 600, y)
    div.set_editor_property("const_b", float(z_high - z_low))
    mel.connect_material_expressions(sub, "", div, "A")
    sat = mel.create_material_expression(m, unreal.MaterialExpressionSaturate, x + 800, y)
    mel.connect_material_expressions(div, "", sat, "")
    return sat


def slope_alpha(m, s0, s1, x, y):
    """0 on flat ground, 1 on steep: (1 - normal.z - s0) / (s1 - s0), saturated."""
    vn = mel.create_material_expression(m, unreal.MaterialExpressionVertexNormalWS, x, y)
    nz = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x + 200, y)
    nz.set_editor_property("r", False)
    nz.set_editor_property("g", False)
    nz.set_editor_property("b", True)
    nz.set_editor_property("a", False)
    mel.connect_material_expressions(vn, "", nz, "")
    inv = mel.create_material_expression(m, unreal.MaterialExpressionOneMinus, x + 400, y)
    mel.connect_material_expressions(nz, "", inv, "")
    sub = mel.create_material_expression(m, unreal.MaterialExpressionSubtract, x + 600, y)
    sub.set_editor_property("const_b", float(s0))
    mel.connect_material_expressions(inv, "", sub, "A")
    div = mel.create_material_expression(m, unreal.MaterialExpressionDivide, x + 800, y)
    div.set_editor_property("const_b", float(s1 - s0))
    mel.connect_material_expressions(sub, "", div, "A")
    sat = mel.create_material_expression(m, unreal.MaterialExpressionSaturate, x + 1000, y)
    mel.connect_material_expressions(div, "", sat, "")
    return sat


def lerp(m, a, a_out, b, b_out, alpha, x, y):
    l = mel.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, x, y)
    mel.connect_material_expressions(a, a_out, l, "A")
    mel.connect_material_expressions(b, b_out, l, "B")
    mel.connect_material_expressions(alpha, "", l, "Alpha")
    return l


def noise(m, scale, x, y, lo=0.0, hi=1.0, levels=3):
    n = mel.create_material_expression(m, unreal.MaterialExpressionNoise, x, y)
    n.set_editor_property("scale", float(scale))
    n.set_editor_property("levels", int(levels))
    n.set_editor_property("output_min", float(lo))
    n.set_editor_property("output_max", float(hi))
    try:
        n.set_editor_property("noise_function", unreal.NoiseFunction.NOISEFUNCTION_GRADIENT_TEX)
    except Exception:
        pass
    wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, x - 200, y)
    mel.connect_material_expressions(wp, "", n, "Position")
    return n


def rotated_uv(m, uv, x, y, ox=0.37, oy=0.71):
    """(-v, u) + offset: the same tile rotated 90 degrees and shifted, for the second sample."""
    r = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x, y)
    r.set_editor_property("r", True)
    r.set_editor_property("g", False)
    r.set_editor_property("b", False)
    r.set_editor_property("a", False)
    gch = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x, y + 100)
    gch.set_editor_property("r", False)
    gch.set_editor_property("g", True)
    gch.set_editor_property("b", False)
    gch.set_editor_property("a", False)
    mel.connect_material_expressions(uv, "", r, "")
    mel.connect_material_expressions(uv, "", gch, "")
    neg = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, x + 150, y + 100)
    neg.set_editor_property("const_b", -1.0)
    mel.connect_material_expressions(gch, "", neg, "A")
    app = mel.create_material_expression(m, unreal.MaterialExpressionAppendVector, x + 300, y)
    mel.connect_material_expressions(neg, "", app, "A")
    mel.connect_material_expressions(r, "", app, "B")
    off = mel.create_material_expression(m, unreal.MaterialExpressionConstant2Vector, x + 300, y + 150)
    off.set_editor_property("r", ox)
    off.set_editor_property("g", oy)
    add = mel.create_material_expression(m, unreal.MaterialExpressionAdd, x + 450, y)
    mel.connect_material_expressions(app, "", add, "A")
    mel.connect_material_expressions(off, "", add, "B")
    return add


def stochastic(m, tex, uv, uv2, mask, x, y, kind):
    """Two samples of the same tile (one rotated + offset) blended by a world noise mask: hides the repeat."""
    a = sample(m, tex, uv, x, y, kind)
    b = sample(m, tex, uv2, x, y + 150, kind)
    out = "RGB" if kind != "linear" else "R"
    return lerp(m, a, out, b, out, mask, x + 300, y)


def build_ground(g):
    m, full = new_material(f"M_Ground_{g['name']}")
    tile = g.get("tile_cm", 400)
    uv = world_uv(m, tile, -3400, 0)
    uv2 = rotated_uv(m, uv, -2900, 0)
    # blend mask between the two samples: noise about 2 tiles wide, pushed toward 0/1 so mixing zones stay narrow
    nmask = noise(m, 1.0 / (tile * 2.0), -3400, 500, lo=-0.6, hi=1.6)
    smask = mel.create_material_expression(m, unreal.MaterialExpressionSaturate, -3000, 500)
    mel.connect_material_expressions(nmask, "", smask, "")
    ha = height_alpha(m, g.get("z_low", 200), g.get("z_high", 900), -3400, 900)
    sa = slope_alpha(m, g.get("slope_start", 0.55), g.get("slope_end", 0.8), -3400, 1200)
    # macro variation from large world noise (about 25 m), never from the tile itself
    macro = noise(m, 1.0 / 2500.0, -3400, 1500, lo=0.78, hi=1.18, levels=2)
    sets = {k: textures_for(g[k]) for k in ("grass", "dry", "rock")}
    for row, (kind, tex_key, prop) in enumerate((("color", "base", unreal.MaterialProperty.MP_BASE_COLOR),
                                                   ("normal", "normal", unreal.MaterialProperty.MP_NORMAL),
                                                   ("linear", "rough", unreal.MaterialProperty.MP_ROUGHNESS))):
        y = -900 + row * 700
        s_grass = stochastic(m, sets["grass"][tex_key], uv, uv2, smask, -2400, y, kind)
        s_dry = stochastic(m, sets["dry"][tex_key], uv, uv2, smask, -2400, y + 300, kind)
        s_rock = stochastic(m, sets["rock"][tex_key], uv, uv2, smask, -2400, y + 500, kind)
        l1 = lerp(m, s_grass, "", s_dry, "", ha, -1200, y)
        l2 = lerp(m, l1, "", s_rock, "", sa, -800, y)
        if kind == "color":
            final = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -400, y)
            mel.connect_material_expressions(l2, "", final, "A")
            mel.connect_material_expressions(macro, "", final, "B")
            mel.connect_material_property(final, "", prop)
        else:
            mel.connect_material_property(l2, "", prop)
    mel.recompile_material(m)
    eal.save_asset(full)
    print(f"  MATERIAL M_Ground_{g['name']}")
    return full


for name, spec in CFG["sets"].items():
    build_simple(name, spec.get("tiling", 1.0))
if CFG.get("ground"):
    build_ground(CFG["ground"])
print("MATERIALS_DONE")
