"""Rebuild build/critic/barrow_pairs.html from build/snaps/* (downscaled, embedded as data URIs)."""
import base64, glob, json, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS = {"baseline": ("build/snaps/baseline", ""), "e1": ("build/snaps/e1", "E1_"), "e3": ("build/snaps/e3", "E3_")}
os.makedirs(os.path.join(ROOT, "build", "critic", "img"), exist_ok=True)
stills = []
for exp, (d, prefix) in SETS.items():
    for p in sorted(glob.glob(os.path.join(ROOT, d, "*.png"))):
        n = os.path.basename(p)[:-4]
        if n.startswith("_"):
            continue
        shot = n.replace(prefix, "") if prefix else n.split("_", 1)[1]
        im = Image.open(p).convert("RGB"); im.thumbnail((960, 540))
        out = os.path.join(ROOT, "build", "critic", "img", f"{exp}__{n}.jpg"); im.save(out, "JPEG", quality=82, optimize=True)
        stills.append({"id": f"{exp}__{n}", "exp": exp, "shot": shot, "src": "data:image/jpeg;base64," + base64.b64encode(open(out, "rb").read()).decode()})
tpl = open(os.path.join(ROOT, "critic", "page", "barrow_pairs.template.html"), encoding="utf-8").read().replace("--line: #33.2e28; ", "")
html = tpl.replace("__STILLS_JSON__", json.dumps(stills))
open(os.path.join(ROOT, "build", "critic", "barrow_pairs.html"), "w", encoding="utf-8").write(html)
print("built", len(html) // 1024, "KB", len(stills), "stills")
