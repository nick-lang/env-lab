"""Concept images on the local Flux (schnell fp8) through ComfyUI.

  py -3 tools/asset/concept.py --name dolmen_upright --prompt "..." [--n 4] [--seed 1] [--size 1024]

Writes build/concepts/<name>_<seed>.png. Prompts are wrapped with the asset-shot preamble
(single object, centered, flat neutral background) so image-to-3D gets a clean silhouette.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "build", "concepts")

PREAMBLE = ("game asset concept render of a single {subject}, whole object fully in frame, centered, "
            "three-quarter view slightly from above, plain flat light gray studio background, soft even "
            "lighting, no ground shadow, no text, no watermark. ")
STYLE = ("Stylized painterly game art, chunky readable forms, simplified surface detail, "
         "hand-painted texture feel, saturated but harmonious palette, clean silhouette.")


def build(prompt, seed, size, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                                                   "latent_image": ["4", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                                                   "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }


def generate(name, subject, style=STYLE, extra="", n=1, seed=1, size=1024, log=print):
    os.makedirs(OUT, exist_ok=True)
    if not comfy.alive():
        raise SystemExit("ComfyUI is not running on " + comfy.BASE)
    prompt = PREAMBLE.format(subject=subject) + style + (" " + extra if extra else "")
    outs = []
    for i in range(n):
        s = seed + i
        pid = comfy.queue(build(prompt, s, size, f"envlab/{name}_{s}"))
        entry = comfy.wait(pid, log=log)
        files = [f for f in comfy.output_files(entry) if f.lower().endswith(".png")]
        if not files:
            raise RuntimeError("no image produced")
        dst = os.path.join(OUT, f"{name}_{s}.png")
        shutil.copyfile(files[-1], dst)
        log(f"CONCEPT {dst}")
        outs.append(dst)
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--prompt", required=True, help="the subject, e.g. 'weathered standing stone megalith'")
    ap.add_argument("--extra", default="")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--size", type=int, default=1024)
    a = ap.parse_args()
    generate(a.name, a.prompt, extra=a.extra, n=a.n, seed=a.seed, size=a.size)


if __name__ == "__main__":
    main()
