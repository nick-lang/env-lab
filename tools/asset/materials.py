"""Tileable PBR-ish material sets from the local Flux through ComfyUI.

  py -3 tools/asset/materials.py make --name ground_grass --prompt "..." [--seed 1] [--size 1024] [--normal 2.0]
  py -3 tools/asset/materials.py sheet                       # 2x2 tiled previews of every set -> build/materials/_sheet.png

make:
  1. Flux tile (top-down, even light)                      -> raw.png
  2. roll by half, repaint the seam cross with an inpaint  -> the borders are now interior pixels: seamless
  3. derive Normal (Sobel on blurred luminance) and Roughness (inverted luminance contrast)
  -> build/materials/<name>/{BaseColor,Normal,Roughness,preview2x2}.png

Everything is ours: no downloaded textures, no substance.
"""
import argparse
import glob
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "build", "materials")

TILE_PRE = ("seamless tileable texture of {subject}, flat top-down orthographic view, even diffuse lighting, no shadows, "
            "no border, no vignette, fills the entire frame edge to edge. Pure surface texture only: no text, no letters, "
            "no writing, no logo, no watermark, no objects. ")
STYLE = "Stylized painterly game texture, chunky readable detail, hand-painted feel, harmonious muted palette."


def flux(prompt, seed, size, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                                                   "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }


def inpaint(image_name, prompt, seed, prefix, denoise=0.55):
    """Repaint the transparent (masked) band of an RGBA image at partial denoise so it inherits the
    surrounding tone. LoadImage's MASK is 1 where alpha is 0."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "8": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["9", 0], "mask": ["8", 1]}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["10", 0],
                                                   "seed": seed, "steps": 6, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }


def run(graph):
    pid = comfy.queue(graph)
    entry = comfy.wait(pid, log=lambda *_: None)
    files = [f for f in comfy.output_files(entry) if f.lower().endswith(".png")]
    if not files:
        raise RuntimeError("no image produced")
    return files[-1]


def flatten(img, radius=96):
    """Remove vignette / low-frequency lighting so both sides of a seam share the same mean."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    low = np.asarray(img.convert("RGB").filter(ImageFilter.GaussianBlur(radius))).astype(np.float32)
    out = a - low + low.mean(axis=(0, 1), keepdims=True)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def band_weight(h, w, band=0.12, feather=0.05):
    """1 inside the central cross band, feathered to 0 outside."""
    yy = np.abs(np.arange(h) - h / 2) / h
    xx = np.abs(np.arange(w) - w / 2) / w
    fy = np.clip((band / 2 + feather - yy) / feather, 0, 1)
    fx = np.clip((band / 2 + feather - xx) / feather, 0, 1)
    return np.maximum(fy[:, None], fx[None, :])


def seam_score(img):
    """Mean abs difference across the wrap edges vs. the mean neighbour difference inside. ~1.0 = invisible."""
    a = np.asarray(img.convert("L")).astype(np.float32)
    inner = (np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean()) / 2
    wrap = (np.abs(a[0] - a[-1]).mean() + np.abs(a[:, 0] - a[:, -1]).mean()) / 2
    return round(float(wrap / max(inner, 1e-6)), 2)


def make_tileable(img, blend=0.18):
    """Structured tiles (grids, planks): roll by half and cross-fade the seam band. Blurry in the band,
    but no hallucinated content. Real fix for grids is procedural structure (E08)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    b = np.roll(np.roll(a, h // 2, axis=0), w // 2, axis=1)
    yy = np.abs(np.arange(h) - h / 2) / (h / 2)
    xx = np.abs(np.arange(w) - w / 2) / (w / 2)
    wy = np.clip(1 - yy / blend, 0, 1)[:, None]
    wx = np.clip(1 - xx / blend, 0, 1)[None, :]
    wgt = np.maximum(wy, wx)[..., None]
    return Image.fromarray(np.clip(a * (1 - wgt) + b * wgt, 0, 255).astype(np.uint8), "RGB")


def masked_rgba(rgb, mask):
    """RGBA where alpha=0 marks the region to repaint (LoadImage's MASK is 1 there)."""
    alpha = np.where(mask, 0, 255).astype(np.uint8)
    return Image.fromarray(np.concatenate([np.asarray(rgb.convert("RGB")), alpha[..., None]], axis=-1), "RGBA")


def band_mask(h, w, axis, band):
    m = np.zeros((h, w), dtype=bool)
    if axis == "x":  # vertical band through the centre column, full height
        bw = int(w * band / 2)
        m[:, w // 2 - bw:w // 2 + bw] = True
    elif axis == "y":  # horizontal band through the centre row, full width
        bh = int(h * band / 2)
        m[h // 2 - bh:h // 2 + bh, :] = True
    else:  # centre square
        bh, bw = int(h * band / 2), int(w * band / 2)
        m[h // 2 - bh:h // 2 + bh, w // 2 - bw:w // 2 + bw] = True
    return m


def feathered(mask, feather_px):
    """Float weight: 1 inside the mask, feathered to 0 within feather_px outside (box dilation)."""
    w = mask.astype(np.float32)
    for _ in range(feather_px):
        w = np.maximum(w, 0.0)
        w = np.maximum(w, np.roll(w, 1, 0) * 0.92)
        w = np.maximum(w, np.roll(w, -1, 0) * 0.92)
        w = np.maximum(w, np.roll(w, 1, 1) * 0.92)
        w = np.maximum(w, np.roll(w, -1, 1) * 0.92)
    return w[..., None]


def repaint(img, mask, prompt, seed, tag, d):
    """Inpaint the masked region through ComfyUI and blend it back with a feathered edge."""
    rp = os.path.join(d, f"_pass_{tag}.png")
    masked_rgba(img, mask).save(rp)
    up = comfy.upload_image(rp, subfolder="envlab_mat")
    fixed = Image.open(run(inpaint(up, prompt, seed, f"envlab/mat_{tag}"))).convert("RGB").resize(img.size)
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    f = np.asarray(fixed).astype(np.float32)
    # colour-match the repainted region to the untouched region (per-channel mean/std)
    keep = ~mask
    for c in range(3):
        src = f[..., c][mask]
        ref = a[..., c][keep]
        if src.size and ref.size and src.std() > 1e-3:
            f[..., c][mask] = (src - src.mean()) / src.std() * ref.std() + ref.mean()
    f = np.clip(f, 0, 255)
    wgt = feathered(mask, 12)
    return Image.fromarray(np.clip(f * wgt + a * (1 - wgt), 0, 255).astype(np.uint8), "RGB")


def make_seamless(img, prompt, seed, d, band=0.12, log=print):
    """Three passes: roll X + repaint the vertical band; roll Y + repaint the horizontal band; roll X +
    repaint the centre square where the previous band's ends meet. No pass touches an edge it hasn't
    already made continuous, so every wrap is interior content at the end."""
    a = np.asarray(img.convert("RGB"))
    h, w, _ = a.shape
    cur = Image.fromarray(np.roll(a, w // 2, axis=1), "RGB")
    cur = repaint(cur, band_mask(h, w, "x", band), prompt, seed + 1, "p1", d)
    cur = Image.fromarray(np.roll(np.asarray(cur), h // 2, axis=0), "RGB")
    cur = repaint(cur, band_mask(h, w, "y", band), prompt, seed + 2, "p2", d)
    cur = Image.fromarray(np.roll(np.asarray(cur), w // 2, axis=1), "RGB")
    cur = repaint(cur, band_mask(h, w, "xy", band * 1.6), prompt, seed + 3, "p3", d)
    return cur


def derive_maps(base, normal_strength=2.0, blur=1.2):
    g = np.asarray(base.convert("L").filter(ImageFilter.GaussianBlur(blur))).astype(np.float32) / 255.0
    # tile-aware gradients (wrap around edges so the normal map is seamless too)
    gx = (np.roll(g, -1, axis=1) - np.roll(g, 1, axis=1)) * 0.5
    gy = (np.roll(g, -1, axis=0) - np.roll(g, 1, axis=0)) * 0.5
    nx = -gx * normal_strength * 8.0
    ny = gy * normal_strength * 8.0  # +Y up in tangent space (OpenGL); Unreal flips green on import by default
    nz = np.ones_like(g)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], axis=-1)
    normal = Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")
    lum = np.asarray(base.convert("L")).astype(np.float32) / 255.0
    lum = (lum - lum.min()) / max(lum.max() - lum.min(), 1e-6)
    rough = np.clip(0.95 - 0.35 * lum, 0.35, 1.0)
    roughness = Image.fromarray((rough * 255).astype(np.uint8), "L")
    return normal, roughness


def preview(base, n=2):
    w, h = base.size
    s = Image.new("RGB", (w * n, h * n))
    for i in range(n):
        for j in range(n):
            s.paste(base, (i * w, j * h))
    return s.resize((1024, 1024))


def make(name, subject, seed=1, size=1024, normal_strength=2.0, extra="", log=print, seam="inpaint", contrast=1.0):
    if not comfy.alive():
        raise SystemExit("ComfyUI is not running on " + comfy.BASE)
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    prompt = TILE_PRE.format(subject=subject) + STYLE + (" " + extra if extra else "")
    raw = run(flux(prompt, seed, size, f"envlab/mat_{name}_{seed}_raw"))
    shutil.copyfile(raw, os.path.join(d, "raw.png"))
    flat = flatten(Image.open(raw))
    base = make_seamless(flat, prompt, seed + 1000, d) if seam == "inpaint" else make_tileable(flat, blend=0.18)
    if contrast != 1.0:
        from PIL import ImageEnhance
        base = ImageEnhance.Contrast(base).enhance(contrast)
    base.save(os.path.join(d, "BaseColor.png"))
    log(f"  seam score raw={seam_score(Image.open(raw))} flat={seam_score(flat)} final={seam_score(base)} (1.0 = invisible)")
    normal, rough = derive_maps(base, normal_strength)
    normal.save(os.path.join(d, "Normal.png"))
    rough.save(os.path.join(d, "Roughness.png"))
    preview(base).save(os.path.join(d, "preview2x2.png"))
    log(f"MATERIAL {name} -> {d}")
    return d


def sheet():
    dirs = sorted(p for p in glob.glob(os.path.join(OUT, "*")) if os.path.isdir(p) and os.path.isfile(os.path.join(p, "preview2x2.png")))
    S = 384
    cols = 3
    rows = (len(dirs) + cols - 1) // cols
    img = Image.new("RGB", (S * cols, S * rows), (30, 30, 30))
    for i, d in enumerate(dirs):
        img.paste(Image.open(os.path.join(d, "preview2x2.png")).resize((S, S)), ((i % cols) * S, (i // cols) * S))
    out = os.path.join(OUT, "_sheet.png")
    img.save(out)
    print("SHEET", out, [os.path.basename(d) for d in dirs])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["make", "sheet"])
    ap.add_argument("--name")
    ap.add_argument("--prompt")
    ap.add_argument("--extra", default="")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--normal", type=float, default=2.0)
    ap.add_argument("--seam", default="inpaint", choices=["inpaint", "fade"])
    ap.add_argument("--contrast", type=float, default=1.0)
    a = ap.parse_args()
    if a.mode == "make":
        make(a.name, a.prompt, a.seed, a.size, a.normal, a.extra, seam=a.seam, contrast=a.contrast)
    else:
        sheet()


if __name__ == "__main__":
    main()
