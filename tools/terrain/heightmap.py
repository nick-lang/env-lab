"""Heightmap generator: designed macro shape + domain-warped fBm + droplet hydraulic erosion.

Units are meters. Output: float32 .npy (for Blender), 16-bit PNG, a preview PNG, and meta.json
(extent, z range, sample points for a round-trip check in Unreal).

Usage:
  py -3 tools/terrain/heightmap.py <params.json> <out_dir>
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

# ----------------------------------------------------------------------------- noise


def _hash(ix, iy, seed):
    n = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + int(seed) * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n.astype(np.float64) / 4294967295.0


def value_noise(x, y, seed):
    ix = np.floor(x).astype(np.int64)
    iy = np.floor(y).astype(np.int64)
    fx = x - ix
    fy = y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a = _hash(ix, iy, seed)
    b = _hash(ix + 1, iy, seed)
    c = _hash(ix, iy + 1, seed)
    d = _hash(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(x, y, seed, octaves=6, lacunarity=2.0, gain=0.5, freq=1.0):
    total = np.zeros_like(x)
    amp = 1.0
    norm = 0.0
    f = freq
    for o in range(octaves):
        total += amp * (value_noise(x * f, y * f, seed + o * 101) * 2 - 1)
        norm += amp
        amp *= gain
        f *= lacunarity
    return total / norm


def warped_fbm(x, y, seed, warp=0.3, **kw):
    wx = fbm(x + 13.1, y + 7.7, seed + 900, octaves=3, freq=kw.get("freq", 1.0))
    wy = fbm(x - 5.3, y + 21.9, seed + 901, octaves=3, freq=kw.get("freq", 1.0))
    return fbm(x + warp * wx, y + warp * wy, seed, **kw)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------- features


def feature_height(X, Y, feat, seed):
    kind = feat["type"]
    if kind == "dome":
        d2 = (X - feat["x"]) ** 2 + (Y - feat["y"]) ** 2
        return feat["height"] * np.exp(-d2 / (2 * feat["sigma"] ** 2))
    if kind == "bowl":
        d2 = (X - feat["x"]) ** 2 + (Y - feat["y"]) ** 2
        return -feat["depth"] * np.exp(-d2 / (2 * feat["sigma"] ** 2))
    if kind == "ridge":
        ang = math.radians(feat.get("angle", 0.0))
        ca, sa = math.cos(ang), math.sin(ang)
        u = (X - feat["x"]) * ca + (Y - feat["y"]) * sa  # along
        v = -(X - feat["x"]) * sa + (Y - feat["y"]) * ca  # across
        half = feat["length"] / 2
        along = np.exp(-np.clip(np.abs(u) - half, 0, None) ** 2 / (2 * (feat["width"] * 0.9) ** 2))
        across = np.exp(-v ** 2 / (2 * feat["width"] ** 2))
        mod = 0.65 + 0.35 * (fbm(u / feat["length"] * 3.0, v / feat["width"], seed + 55, octaves=3) * 0.5 + 0.5)
        return feat["height"] * along * across * mod
    raise ValueError(f"unknown feature {kind}")


def path_points(path, n=600):
    ys = np.linspace(path["y0"], path["y1"], n)
    xs = path["amp"] * np.sin(2 * np.pi * (ys - path["y0"]) / path["period"]) + path.get("x_offset", 0.0)
    return np.stack([xs, ys], axis=1)


def dist_to_polyline(X, Y, pts):
    d = np.full(X.shape, np.inf)
    for px, py in pts:
        d = np.minimum(d, (X - px) ** 2 + (Y - py) ** 2)
    return np.sqrt(d)


# ----------------------------------------------------------------------------- erosion


def erode(h, spacing, iters, seed, params):
    """Droplet hydraulic erosion (Lague-style). Operates in place on a copy."""
    rng = np.random.default_rng(seed)
    n = h.shape[0]
    inertia = params.get("inertia", 0.05)
    capacity = params.get("capacity", 4.0)
    min_slope = params.get("min_slope", 0.01)
    erode_speed = params.get("erode_speed", 0.3)
    deposit_speed = params.get("deposit_speed", 0.3)
    evaporate = params.get("evaporate", 0.01)
    gravity = params.get("gravity", 4.0)
    max_life = params.get("max_life", 30)
    radius = params.get("radius", 2)

    # brush weights
    offs = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            r = math.hypot(dx, dy)
            if r <= radius:
                offs.append((dx, dy, max(0.0, 1 - r / radius)))
    wsum = sum(w for _, _, w in offs)
    offs = [(dx, dy, w / wsum) for dx, dy, w in offs]

    def height_grad(px, py):
        x0 = int(px)
        y0 = int(py)
        u = px - x0
        v = py - y0
        h00 = h[y0, x0]
        h10 = h[y0, x0 + 1]
        h01 = h[y0 + 1, x0]
        h11 = h[y0 + 1, x0 + 1]
        gx = (h10 - h00) * (1 - v) + (h11 - h01) * v
        gy = (h01 - h00) * (1 - u) + (h11 - h10) * u
        hh = h00 * (1 - u) * (1 - v) + h10 * u * (1 - v) + h01 * (1 - u) * v + h11 * u * v
        return hh, gx, gy

    for _ in range(iters):
        px = rng.uniform(1, n - 2)
        py = rng.uniform(1, n - 2)
        dx = dy = 0.0
        speed = 1.0
        water = 1.0
        sediment = 0.0
        for _life in range(max_life):
            x0 = int(px)
            y0 = int(py)
            u = px - x0
            v = py - y0
            hh, gx, gy = height_grad(px, py)
            dx = dx * inertia - gx * (1 - inertia)
            dy = dy * inertia - gy * (1 - inertia)
            ln = math.hypot(dx, dy)
            if ln == 0:
                ang = rng.uniform(0, 2 * math.pi)
                dx, dy = math.cos(ang), math.sin(ang)
            else:
                dx /= ln
                dy /= ln
            npx = px + dx
            npy = py + dy
            if npx < 1 or npx >= n - 2 or npy < 1 or npy >= n - 2:
                break
            nh, _, _ = height_grad(npx, npy)
            dh = nh - hh
            cap = max(-dh, min_slope) * speed * water * capacity
            if sediment > cap or dh > 0:
                dep = min(dh, sediment) if dh > 0 else (sediment - cap) * deposit_speed
                sediment -= dep
                h[y0, x0] += dep * (1 - u) * (1 - v)
                h[y0, x0 + 1] += dep * u * (1 - v)
                h[y0 + 1, x0] += dep * (1 - u) * v
                h[y0 + 1, x0 + 1] += dep * u * v
            else:
                amt = min((cap - sediment) * erode_speed, -dh)
                for ox, oy, w in offs:
                    cx = x0 + ox
                    cy = y0 + oy
                    if 0 <= cx < n and 0 <= cy < n:
                        d = amt * w
                        take = min(h[cy, cx], d) if h[cy, cx] < d else d
                        h[cy, cx] -= take
                        sediment += take
            speed = math.sqrt(max(speed * speed + dh * gravity, 0.0))
            water *= 1 - evaporate
            px, py = npx, npy
    return h


# ----------------------------------------------------------------------------- main


def build(params):
    seed = int(params.get("seed", 1))
    size = float(params["size_m"])
    res = int(params["res"])
    x0, y0 = params["origin"]
    spacing = size / (res - 1)
    xs = x0 + np.arange(res) * spacing
    ys = y0 + np.arange(res) * spacing
    X, Y = np.meshgrid(xs, ys)  # [row=y, col=x]

    # macro: tilt + features
    macro = params.get("base_slope", 0.0) * (Y - y0) + params.get("base_z", 0.0)
    for feat in params.get("features", []):
        macro = macro + feature_height(X, Y, feat, seed)

    # broad rolling undulation
    roll = params.get("roll", {"amp": 2.0, "freq": 0.004})
    macro = macro + roll["amp"] * warped_fbm(X, Y, seed + 7, warp=40.0, octaves=3, freq=roll["freq"])

    # detail
    det = params.get("detail", {"amp": 1.2, "freq": 0.02})
    detail = det["amp"] * warped_fbm(X, Y, seed + 3, warp=8.0, octaves=5, freq=det["freq"])

    # corridor along the path: damp detail so the walk stays smooth
    path = params.get("path")
    if path:
        pts = path_points(path)
        dist = dist_to_polyline(X, Y, pts)
        w = 1.0 - smoothstep(path["inner"], path["outer"], dist)
        detail = detail * (1.0 - 0.85 * w)
        # damp the macro's own steepness near the path a little
    else:
        dist = np.full(X.shape, 1e9)

    h = macro + detail

    # edge fade: drop the rim below the fog so the mesh boundary never silhouettes
    fade = params.get("edge_fade", 0.0)
    if fade > 0:
        dx = np.minimum(X - x0, x0 + size - X)
        dy = np.minimum(Y - y0, y0 + size - Y)
        e = smoothstep(0.0, fade, np.minimum(dx, dy))
        h = h * e + (-6.0) * (1 - e)

    ero = params.get("erosion")
    if ero and ero.get("iters", 0) > 0:
        h = erode(h.astype(np.float64), spacing, int(ero["iters"]), seed + 11, ero)
        # settle: a light blur removes droplet scratch marks while keeping the gullies
        for _ in range(int(ero.get("smooth_passes", 1))):
            hp = np.pad(h, 1, mode="edge")
            h = (4 * hp[1:-1, 1:-1] + hp[:-2, 1:-1] + hp[2:, 1:-1] + hp[1:-1, :-2] + hp[1:-1, 2:]) / 8.0

    # optional gate exclusion: keep the crest clean for the dolmen
    return X, Y, h.astype(np.float32), dist.astype(np.float32)


def slope_deg(h, spacing):
    gy, gx = np.gradient(h, spacing)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        params = json.load(f)
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)

    X, Y, h, dist = build(params)
    size = float(params["size_m"])
    res = int(params["res"])
    x0, y0 = params["origin"]
    spacing = size / (res - 1)

    np.save(os.path.join(out, "height.npy"), h)
    np.save(os.path.join(out, "pathdist.npy"), dist)
    zmin = float(h.min())
    zmax = float(h.max())
    png = ((h - zmin) / max(zmax - zmin, 1e-6) * 65535).astype(np.uint16)
    Image.fromarray(png, mode="I;16").save(os.path.join(out, "heightmap16.png"))

    # preview: hillshade + height tint
    sl = slope_deg(h, spacing)
    gy, gx = np.gradient(h, spacing)
    nx, ny, nz = -gx, -gy, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    lx, ly, lz = -0.5, 0.5, 0.7
    shade = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
    tint = (h - zmin) / max(zmax - zmin, 1e-6)
    rgb = np.stack([shade * (0.55 + 0.45 * tint), shade * (0.6 + 0.2 * tint), shade * (0.35 + 0.15 * (1 - tint))], axis=-1)
    prev = (np.flipud(rgb) * 255).astype(np.uint8)  # flip so +Y is up in the image
    Image.fromarray(prev).resize((1024, 1024), Image.NEAREST).save(os.path.join(out, "preview.png"))

    # sample points for the Unreal round-trip check (meters)
    samples = []
    for sx, sy in params.get("samples", [[0, 120], [0, 7], [-95, 50], [95, 75], [-60, 200]]):
        i = int(round((sx - x0) / spacing))
        j = int(round((sy - y0) / spacing))
        if 0 <= i < res and 0 <= j < res:
            samples.append({"x": sx, "y": sy, "z": float(h[j, i])})

    meta = {
        "size_m": size,
        "res": res,
        "origin": [x0, y0],
        "spacing": spacing,
        "zmin": zmin,
        "zmax": zmax,
        "seed": params.get("seed", 1),
        "samples": samples,
        "stats": {
            "mean_slope_deg": float(sl.mean()),
            "p90_slope_deg": float(np.percentile(sl, 90)),
        },
    }
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"HEIGHTMAP_DONE res={res} z=[{zmin:.2f},{zmax:.2f}] mean_slope={sl.mean():.1f}deg samples={len(samples)}")


if __name__ == "__main__":
    main()
