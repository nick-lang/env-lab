"""Measurement pack: objective image statistics for stills. Guard numbers, not verdicts.

  py -3 tools/measure.py build/snaps/e8 [more dirs...]   -> table per still + CSV next to each dir

Metrics (all from the rendered PNG, no learning):
  spectral_slope   slope of log radial power vs log frequency. Natural scenes sit near -2. Flatter (toward -1)
                   = high-frequency noise/pattern everywhere; steeper (< -2.6) = flat, detail-less surfaces.
  detail_octaves   fraction of the image's edge energy in each of 4 octaves (coarse→fine). A good scene has
                   energy in every octave; "pattern on a box" piles it into one.
  repeat_score     strongest autocorrelation peak at lags between 3% and 40% of the image, on the luminance
                   high-pass. Above ~0.35 a visible tiling repeat is likely.
  value_groups     share of pixels in shadow (<0.2), mid, light (>0.7) after a 3-bin split of luminance,
                   and the local-contrast mean (Weber). "Soup" reads as one dominant bin + low local contrast.
  saturation_mean  mean HSV saturation; the ember tint pushes this past 0.6 on everything.
"""
import csv
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageFilter


def luminance(img, size=512):
    im = img.convert("RGB")
    im.thumbnail((size, size))
    a = np.asarray(im).astype(np.float32) / 255.0
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2], a


def spectral_slope(lum):
    h, w = lum.shape
    n = min(h, w)
    x = lum[:n, :n] - lum[:n, :n].mean()
    win = np.outer(np.hanning(n), np.hanning(n))
    F = np.fft.fftshift(np.fft.fft2(x * win))
    P = np.abs(F) ** 2
    cy, cx = n // 2, n // 2
    yy, xx = np.indices(P.shape)
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2).astype(int)
    rad = np.bincount(r.ravel(), P.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    f = np.arange(len(rad))
    sel = (f >= 4) & (f <= n // 4) & (rad > 0)
    slope = np.polyfit(np.log(f[sel]), np.log(rad[sel]), 1)[0]
    return float(slope)


def detail_octaves(lum):
    """Edge energy per octave via differences of Gaussians."""
    im = Image.fromarray((lum * 255).astype(np.uint8))
    sig = [1, 2, 4, 8, 16]
    blurred = [np.asarray(im.filter(ImageFilter.GaussianBlur(s))).astype(np.float32) for s in sig]
    bands = [np.abs(blurred[i] - blurred[i + 1]).mean() for i in range(4)]
    tot = sum(bands) + 1e-6
    return [round(float(b) / tot, 3) for b in reversed(bands)]  # coarse -> fine


def repeat_score(lum):
    im = Image.fromarray((lum * 255).astype(np.uint8))
    hp = lum - np.asarray(im.filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255.0
    hp = hp - hp.mean()
    F = np.fft.fft2(hp)
    ac = np.real(np.fft.ifft2(F * np.conj(F)))
    ac /= max(ac[0, 0], 1e-9)
    h, w = ac.shape
    lo, hi = int(min(h, w) * 0.03), int(min(h, w) * 0.4)
    yy, xx = np.indices(ac.shape)
    dy = np.minimum(yy, h - yy)
    dx = np.minimum(xx, w - xx)
    d = np.sqrt(dy ** 2 + dx ** 2)
    mask = (d >= lo) & (d <= hi)
    return float(ac[mask].max()) if mask.any() else 0.0


def value_groups(lum):
    shadow = float((lum < 0.2).mean())
    light = float((lum > 0.7).mean())
    mid = 1.0 - shadow - light
    im = Image.fromarray((lum * 255).astype(np.uint8))
    local_mean = np.asarray(im.filter(ImageFilter.GaussianBlur(8))).astype(np.float32) / 255.0
    weber = float((np.abs(lum - local_mean) / (local_mean + 0.05)).mean())
    return round(shadow, 3), round(mid, 3), round(light, 3), round(weber, 3)


def saturation_mean(rgb):
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return float(s.mean())


def measure(path):
    img = Image.open(path)
    lum, rgb = luminance(img)
    sh, mid, li, weber = value_groups(lum)
    return {"still": os.path.basename(path), "spectral_slope": round(spectral_slope(lum), 2), "octaves_c2f": detail_octaves(lum),
            "repeat": round(repeat_score(lum), 3), "shadow": sh, "mid": mid, "light": li, "local_contrast": weber,
            "saturation": round(saturation_mean(rgb), 3)}


def main():
    dirs = sys.argv[1:] or ["build/snaps/e8"]
    for d in dirs:
        rows = [measure(p) for p in sorted(glob.glob(os.path.join(d, "*.png"))) if not os.path.basename(p).startswith("_")]
        if not rows:
            continue
        print(f"== {d}")
        print(f"{'still':28s} {'slope':>6s} {'octaves c-f':>26s} {'repeat':>7s} {'shd/mid/lit':>18s} {'lcon':>6s} {'sat':>5s}")
        for r in rows:
            print(f"{r['still'][:28]:28s} {r['spectral_slope']:6.2f} {str(r['octaves_c2f']):>26s} {r['repeat']:7.3f} "
                  f"{r['shadow']:5.2f}/{r['mid']:4.2f}/{r['light']:4.2f} {r['local_contrast']:6.3f} {r['saturation']:5.2f}")
        with open(os.path.join(d, "_measure.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
