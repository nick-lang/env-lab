"""Rank stills from the Barrow Pairs picks and measure model/user agreement.

Input: a directory of JSON documents exported from the artifact's `picks` collection
(Artifact read_db with out_dir → <dir>/picks/<id>.json), or a single JSON array file.

  py -3 critic/rank.py build/critic/db            # prints ranking + agreement, writes critic/ranking.csv
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    if os.path.isfile(path):
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, list) else list(data.values())
    docs = []
    for f in glob.glob(os.path.join(path, "**", "*.json"), recursive=True):
        d = json.load(open(f, encoding="utf-8"))
        docs.append(d.get("data", d) if isinstance(d, dict) and "data" in d and "a" not in d else d)
    return docs


def key(a, b):
    return (a, b) if a < b else (b, a)


def bradley_terry(picks, iters=200):
    ids = sorted({p["a"] for p in picks} | {p["b"] for p in picks})
    wins = defaultdict(float)
    games = defaultdict(int)
    pairs = defaultdict(int)
    for p in picks:
        pairs[key(p["a"], p["b"])] += 1
        games[p["a"]] += 1
        games[p["b"]] += 1
        if p["winner"] == "a":
            wins[p["a"]] += 1
        elif p["winner"] == "b":
            wins[p["b"]] += 1
        else:
            wins[p["a"]] += .5
            wins[p["b"]] += .5
    s = {i: 1.0 for i in ids}
    for _ in range(iters):
        denom = defaultdict(float)
        for (a, b), c in pairs.items():
            d = c / (s[a] + s[b])
            denom[a] += d
            denom[b] += d
        ns = {i: (wins[i] + .01) / (denom[i] + .01) if games[i] else 1.0 for i in ids}
        mean = sum(ns.values()) / len(ns)
        s = {i: v / mean for i, v in ns.items()}
    return sorted(((i, s[i], wins[i], games[i]) for i in ids), key=lambda x: -x[1])


def agreement(picks):
    user = [p for p in picks if p["rater"] == "user" and p["winner"] != "tie"]
    model = {key(p["a"], p["b"]): p for p in picks if p["rater"] == "model" and p["winner"] != "tie"}
    both = agree = 0
    for u in user:
        m = model.get(key(u["a"], u["b"]))
        if not m:
            continue
        both += 1
        uw = u["a"] if u["winner"] == "a" else u["b"]
        mw = m["a"] if m["winner"] == "a" else m["b"]
        agree += uw == mw
    return both, agree


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "critic", "db")
    picks = [p for p in load(src) if isinstance(p, dict) and "a" in p and "winner" in p]
    user = [p for p in picks if p.get("rater") == "user"]
    print(f"picks: {len(picks)} (user {len(user)}, model {len(picks) - len(user)})")
    rank = bradley_terry(user) if user else []
    out = os.path.join(ROOT, "critic", "ranking.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "still", "strength", "wins", "games"])
        for i, (sid, s, wins, games) in enumerate(rank, 1):
            w.writerow([i, sid, f"{s:.3f}", wins, games])
            print(f"{i:3d} {sid:32s} {s:6.2f}  {wins:g}/{games}")
    both, agree = agreement(picks)
    print(f"agreement: {agree}/{both}" + (f" = {100 * agree / both:.0f}%" if both else " (no overlap yet)"))
    print("wrote", out)


if __name__ == "__main__":
    main()
