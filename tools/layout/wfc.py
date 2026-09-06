"""Socket-based 3D wave-function collapse for the modular kit.

Cells are W x D x H boxes. A *tile* is a cell type with a socket on each of its six faces and a list of
kit pieces to place. Rotations (0/90/180/270 about Z) are generated from the base definition. Sockets
match through `compatible()`, which is not plain equality: "in" faces may carry a subtype (":w" window,
":a" alcove, ":p" pillar) and two equal subtypes never touch, which is how "no two windows side by side"
is expressed without a second rule system.

    solve(shape, tiles, allowed, seed) -> 3D list of tile names or None

`allowed(x, y, z)` returns the set of base tile names permitted at a cell (None = all). Pins are just
allowed() returning a single rotated tile name. Contradictions restart with the next seed.
"""
import math
import random

FACES = ["+x", "-x", "+y", "-y", "+z", "-z"]
OPP = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y", "+z": "-z", "-z": "+z"}
DELTA = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
ROT = {"+x": "+y", "+y": "-x", "-x": "-y", "-y": "+x", "+z": "+z", "-z": "-z"}  # 90 deg CCW about Z


def compatible(a, b):
    if a == "bnd" or b == "bnd":
        return True
    if a.startswith("in") and b.startswith("in"):
        sa, sb = a.partition(":")[2], b.partition(":")[2]
        return not (sa and sa == sb)
    if {a, b} == {"out", "ext"}:  # a wall's outward face may only touch the exterior, never another wall's back
        return True
    if a == "out" or b == "out":
        return False
    return a == b


class Tile:
    def __init__(self, name, sockets, pieces, weight=1.0, base=None, rot=0):
        self.name = name
        self.sockets = sockets
        self.pieces = pieces  # [(mesh, (ox, oy, oz), yaw_deg)]
        self.weight = weight
        self.base = base or name
        self.rot = rot

    def rotated(self, k):
        s = dict(self.sockets)
        pcs = list(self.pieces)
        for _ in range(k):
            s = {ROT[f]: v for f, v in s.items()}
            pcs = [(m, (-o[1], o[0], o[2]), (yaw + 90.0) % 360.0) for m, o, yaw in pcs]
        return Tile(f"{self.base}@{k * 90}", s, pcs, self.weight, self.base, k * 90)


def expand(base_tiles):
    """All distinct rotations of every base tile (rotationally symmetric tiles collapse to one)."""
    out = {}
    for t in base_tiles:
        seen = set()
        for k in range(4):
            r = t.rotated(k)
            key = tuple(sorted(r.sockets.items()))
            if key in seen:
                continue
            seen.add(key)
            out[r.name] = r
    return out


def solve(shape, tiles, allowed=None, seed=0, tries=20, log=print):
    X, Y, Z = shape
    names = list(tiles)
    idx = {n: i for i, n in enumerate(names)}
    n = len(names)
    # precompute compatibility per face: comp[f][i] = set of j allowed on the neighbour across face f
    comp = {f: [set() for _ in range(n)] for f in FACES}
    for f in FACES:
        for i, a in enumerate(names):
            sa = tiles[a].sockets[f]
            for j, b in enumerate(names):
                if compatible(sa, tiles[b].sockets[OPP[f]]):
                    comp[f][i].add(j)
    weights = [tiles[a].weight for a in names]

    def initial_domain(x, y, z):
        if allowed is None:
            return set(range(n))
        al = allowed(x, y, z)
        if al is None:
            return set(range(n))
        return {i for i, a in enumerate(names) if a in al or tiles[a].base in al}

    for attempt in range(tries):
        rng = random.Random(seed + attempt)
        dom = [[[initial_domain(x, y, z) for z in range(Z)] for y in range(Y)] for x in range(X)]
        queue = [(x, y, z) for x in range(X) for y in range(Y) for z in range(Z)]
        ok = True

        def propagate():
            nonlocal ok
            while queue:
                x, y, z = queue.pop()
                d = dom[x][y][z]
                if not d:
                    ok = False
                    return
                for f in FACES:
                    dx, dy, dz = DELTA[f]
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if not (0 <= nx < X and 0 <= ny < Y and 0 <= nz < Z):
                        continue
                    support = set()
                    for i in d:
                        support |= comp[f][i]
                    nd = dom[nx][ny][nz]
                    new = nd & support
                    if len(new) < len(nd):
                        dom[nx][ny][nz] = new
                        if not new:
                            ok = False
                            return
                        queue.append((nx, ny, nz))

        propagate()
        while ok:
            best = None
            best_e = 1e18
            for x in range(X):
                for y in range(Y):
                    for z in range(Z):
                        d = dom[x][y][z]
                        if len(d) <= 1:
                            continue
                        wsum = sum(weights[i] for i in d)
                        e = math.log(wsum) - sum(weights[i] * math.log(weights[i]) for i in d if weights[i] > 0) / max(wsum, 1e-9) + rng.random() * 1e-3
                        if e < best_e:
                            best_e, best = e, (x, y, z)
            if best is None:
                break
            x, y, z = best
            d = list(dom[x][y][z])
            w = [weights[i] for i in d]
            if sum(w) <= 0:
                w = [1.0] * len(d)
            pick = rng.choices(d, weights=w)[0]
            dom[x][y][z] = {pick}
            queue.append((x, y, z))
            propagate()
        if ok:
            result = [[[names[next(iter(dom[x][y][z]))] for z in range(Z)] for y in range(Y)] for x in range(X)]
            log(f"WFC solved {X}x{Y}x{Z} in attempt {attempt + 1} (seed {seed + attempt})")
            return result
        log(f"WFC contradiction on attempt {attempt + 1}, retrying")
    return None


# ----------------------------------------------------------------------------- the kit's tiles
def kit_tiles(cell):
    """Base tiles for the stone kit. Wall pieces face +Y in the base orientation."""
    W, D, H = cell
    F = "SM_Kit_Floor"
    lat_in = {"+x": "in", "-x": "in", "+y": "in", "-y": "in"}
    lvl = {"+z": "lvl", "-z": "lvl"}
    tiles = [
        Tile("EXT", {**{f: "ext" for f in FACES}}, [], weight=1.0),
        Tile("ROOM", {**lat_in, **lvl}, [(F, (0, 0, 0), 0)], weight=12.0),
        Tile("ROOM_P", {"+x": "in:p", "-x": "in:p", "+y": "in:p", "-y": "in:p", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_Pillar", (0, 0, 0), 0)], weight=0.8),
        Tile("WALL", {"+y": "out", "-y": "in", "+x": "in", "-x": "in", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_Wall", (0, 0, 0), 0)], weight=6.0),
        Tile("WALL_W", {"+y": "out", "-y": "in", "+x": "in:w", "-x": "in:w", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_WallWindow", (0, 0, 0), 0)], weight=3.0),
        Tile("WALL_A", {"+y": "out", "-y": "in", "+x": "in:a", "-x": "in:a", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_WallAlcove", (0, 0, 0), 0)], weight=1.5),
        Tile("WALL_D", {"+y": "out", "-y": "in", "+x": "in", "-x": "in", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_WallDoor", (0, 0, 0), 0)], weight=0.0),
        Tile("CORNER", {"+y": "out", "+x": "out", "-y": "in", "-x": "in", **lvl}, [(F, (0, 0, 0), 0), ("SM_Kit_Wall", (0, 0, 0), 0), ("SM_Kit_Wall", (0, 0, 0), -90)], weight=4.0),
        Tile("STAIR", {**lat_in, "-z": "lvl", "+z": "hole"}, [(F, (0, 0, 0), 0), ("SM_Kit_Stair", (0, 0, 0), 0)], weight=0.0),
        Tile("HOLE", {**lat_in, "-z": "hole", "+z": "lvl"}, [], weight=0.0),
    ]
    return expand(tiles)
