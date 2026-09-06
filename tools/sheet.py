"""Side-by-side contact sheet of two snap sets.

  py -3 tools/sheet.py <left_dir> <left_prefix> <right_dir> <right_prefix> <out.png> [shot ...]
  e.g. py -3 tools/sheet.py build/snaps/e1 E1_ build/snaps/e3 E3_ build/snaps/E03_contact_sheet.png gate stone gate_low hero player
"""
import os
import sys

from PIL import Image, ImageDraw

ld, lp, rd, rp, out = sys.argv[1:6]
shots = sys.argv[6:] or ["player", "hero", "path_low", "gate", "stone", "gate_low", "wide"]
W, H = 800, 450
pairs = [(os.path.join(ld, f"{lp}{s}.png"), os.path.join(rd, f"{rp}{s}.png"), s) for s in shots]
pairs = [p for p in pairs if os.path.isfile(p[0]) and os.path.isfile(p[1])]
sheet = Image.new("RGB", (W * 2 + 30, (H + 40) * len(pairs) + 50), (18, 18, 18))
d = ImageDraw.Draw(sheet)
d.text((10, 10), f"LEFT: {ld} ({lp})", fill=(230, 230, 230))
d.text((W + 40, 10), f"RIGHT: {rd} ({rp})", fill=(230, 230, 230))
y = 50
for l, r, s in pairs:
    sheet.paste(Image.open(l).resize((W, H)), (10, y))
    sheet.paste(Image.open(r).resize((W, H)), (W + 40, y))
    d.text((10, y + H + 8), f"{lp}{s}", fill=(200, 200, 200))
    d.text((W + 40, y + H + 8), f"{rp}{s}", fill=(200, 200, 200))
    y += H + 40
sheet.save(out)
print("SHEET", out, sheet.size, len(pairs), "pairs")
