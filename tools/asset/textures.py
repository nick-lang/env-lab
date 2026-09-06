"""Vegetation textures on the local Flux through ComfyUI.

  py -3 tools/asset/textures.py cutout  --name leaf_oak  --prompt "..." [--seed 1] [--n 2]
  py -3 tools/asset/textures.py tile    --name bark_oak  --prompt "..." [--seed 1]

cutout: single subject on a flat white background → BiRefNet background removal in ComfyUI → RGBA PNG
        (build/textures/<name>_<seed>.png), alpha premultiplied against nothing: straight alpha.
tile:   a flat texture → made seamless with an offset cross-fade → build/textures/<name>_<seed>.png
"""
import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "build", "textures")

CUTOUT_PRE = ("game texture of {subject}, isolated and centered on a plain flat pure white background, whole subject fully "
              "in frame with margin, front view, soft even lighting, no cast shadow, no ground, no text. ")
STYLE = "Stylized painterly game art, chunky readable shapes, hand-painted feel, saturated but harmonious palette."
TILE_PRE = ("seamless tileable texture of {subject}, flat top-down orthographic view, even lighting, no shadows, no border, "
            "no text, fills the entire frame edge to edge. ")


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


def cutout_graph(image_name, prefix):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
        "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["1", 0], "alpha": ["3", 0]}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": prefix}},
    }


def run(graph):
    pid = comfy.queue(graph)
    entry = comfy.wait(pid, log=lambda *_: None)
    files = [f for f in comfy.output_files(entry) if f.lower().endswith(".png")]
    if not files:
        raise RuntimeError("no image produced")
    return files[-1]


def make_tileable(img, blend=0.25):
    """Offset by half and cross-fade the seams: cheap, good enough for stylized bark/ground."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    b = np.roll(np.roll(a, h // 2, axis=0), w // 2, axis=1)
    # weight: 1 near the (now central) seams of b, 0 far from them
    yy = np.abs(np.arange(h) - h / 2) / (h / 2)
    xx = np.abs(np.arange(w) - w / 2) / (w / 2)
    wy = np.clip(1 - yy / blend, 0, 1)[:, None]
    wx = np.clip(1 - xx / blend, 0, 1)[None, :]
    wgt = np.maximum(wy, wx)[..., None]
    out = a * (1 - wgt) + b * wgt
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def pad_edges(im, iters=24, cut=96):
    """Alpha bleed: push foreground colour outward under the transparent area so masked/mip-filtered
    edges never sample the white background. Pixels with alpha < cut get the mean colour of their
    nearest opaque neighbours (iterative 3x3 dilation)."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    filled = alpha >= cut
    for _ in range(iters):
        if filled.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(alpha.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                sh = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                sf = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
                acc += sh * sf[..., None]
                cnt += sf
        grow = (~filled) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        filled = filled | grow
    out = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def alpha_stats(path):
    im = Image.open(path)
    if im.mode != "RGBA":
        return im.mode, None
    a = np.asarray(im.split()[3])
    return "RGBA", round(float((a > 128).mean()), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cutout", "tile"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--extra", default="")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--size", type=int, default=1024)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not comfy.alive():
        raise SystemExit("ComfyUI is not running on " + comfy.BASE)
    for i in range(a.n):
        seed = a.seed + i
        if a.mode == "cutout":
            prompt = CUTOUT_PRE.format(subject=a.prompt) + STYLE + (" " + a.extra if a.extra else "")
            raw = run(flux(prompt, seed, a.size, f"envlab/tex_{a.name}_{seed}_raw"))
            up = comfy.upload_image(raw, subfolder="envlab_tex")
            rgba = run(cutout_graph(up, f"envlab/tex_{a.name}_{seed}"))
            dst = os.path.join(OUT, f"{a.name}_{seed}.png")
            im = Image.open(rgba).convert("RGBA")
            r, g, b, al = im.split()
            from PIL import ImageOps
            pad_edges(Image.merge("RGBA", (r, g, b, ImageOps.invert(al)))).save(dst)  # JoinImageWithAlpha treats the mask as transparency
            print("CUTOUT", dst, alpha_stats(dst))
        else:
            prompt = TILE_PRE.format(subject=a.prompt) + STYLE + (" " + a.extra if a.extra else "")
            raw = run(flux(prompt, seed, a.size, f"envlab/tex_{a.name}_{seed}_raw"))
            dst = os.path.join(OUT, f"{a.name}_{seed}.png")
            make_tileable(Image.open(raw)).save(dst)
            print("TILE", dst)


if __name__ == "__main__":
    main()
