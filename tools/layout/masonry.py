"""Masonry assembler: turns a kit piece's envelope into instanced sculpted blocks.

Given the block library manifest (classes with dims and mesh names), produce block placements for:
  wall(W, H, T, opening=None)   coursed running bond, jitter, recessed joints, occasional proud/missing block
  floor(W, D)                    flagstone slabs on a jittered grid
  pillar(H)                      stacked squared blocks
  parapet(W, H)                  short wall

All placements are in the piece's local frame (metres; origin at the cell floor centre; the wall face at
+Y like the kit) and are deterministic per seed. structure.py rotates and offsets them per cell.
Each placement: (mesh_name, (x, y, z), (pitch, yaw, roll), (sx, sy, sz)).
"""
import math
import random


class Masonry:
    def __init__(self, manifest, joint=0.025, seed=0):
        self.m = manifest["classes"]
        self.root = manifest.get("mesh_root", "/Game/Meshes/blocks")
        self.joint = joint
        self.seed = seed

    # ---------------------------------------------------------------- helpers
    def _pick(self, rng, cls):
        c = self.m[cls]
        return rng.choice(c["meshes"]), c["dims"]

    def _course_plan(self, rng, length, course_h):
        """Split a run of `length` into blocks of mixed classes that fit the course height."""
        out = []
        x = 0.0
        while x < length - 0.05:
            r = rng.random()
            cls = "large" if r < 0.5 else ("medium" if r < 0.85 else "small")
            mesh, dims = self._pick(rng, cls)
            bl = dims[0] * rng.uniform(0.85, 1.1)
            if x + bl > length:
                bl = length - x
                if bl < 0.12:
                    break
            out.append((mesh, dims, x, bl))
            x += bl + self.joint
        return out

    # ---------------------------------------------------------------- pieces
    def wall(self, W, H, T, opening=None, seed_salt=0, y_face=None, proud=0.05, missing=0.006):
        """opening: (x0, x1, z0, z1) in local x/z, or None. Blocks fill the slab y in [y_face - T, y_face]."""
        rng = random.Random(self.seed * 7919 + seed_salt)
        yf = y_face if y_face is not None else 0.0
        course_h = 0.40
        n_courses = max(1, int(round(H / course_h)))
        course_h = H / n_courses
        out = []
        for ci in range(n_courses):
            z0 = ci * course_h
            offset = (ci % 2) * 0.35 * rng.uniform(0.6, 1.4)  # running bond
            plan = self._course_plan(rng, W + offset, course_h)
            for mesh, dims, x, bl in plan:
                x0 = -W / 2 - offset + x
                x1 = x0 + bl
                if x1 <= -W / 2 or x0 >= W / 2:
                    continue
                # clip to the wall run
                cx0, cx1 = max(x0, -W / 2), min(x1, W / 2)
                blen = cx1 - cx0
                if blen < 0.1:
                    continue
                zc = z0 + course_h / 2
                # opening: skip blocks fully inside; shrink blocks that straddle
                if opening:
                    ox0, ox1, oz0, oz1 = opening
                    if z0 + course_h > oz0 + 0.01 and z0 < oz1 - 0.01:
                        if cx0 >= ox0 - 0.01 and cx1 <= ox1 + 0.01:
                            continue
                        if cx0 < ox0 < cx1:
                            cx1 = ox0 - self.joint
                        if cx0 < ox1 < cx1:
                            cx0 = ox1 + self.joint
                        blen = cx1 - cx0
                        if blen < 0.1:
                            continue
                if rng.random() < missing and 0 < ci < n_courses - 1:
                    continue
                depth = T - self.joint
                y_off = rng.uniform(0.0, 0.008)
                if rng.random() < proud:
                    y_off = rng.uniform(0.02, 0.05)
                sx = blen / dims[0]
                sy = depth / dims[1]
                sz = (course_h - self.joint) / dims[2]
                yaw = rng.uniform(-1.2, 1.2)
                out.append((mesh, ((cx0 + cx1) / 2, yf - depth / 2 + y_off, zc), (rng.uniform(-0.6, 0.6), yaw, rng.uniform(-0.6, 0.6)), (sx, sy, sz)))
        return out

    def lintel(self, x0, x1, z, T, y_face, seed_salt=0):
        rng = random.Random(self.seed * 104729 + seed_salt)
        mesh, dims = self._pick(rng, "large")
        L = x1 - x0
        return [(mesh, ((x0 + x1) / 2, y_face - T / 2, z), (0, rng.uniform(-0.5, 0.5), 0), (L / dims[0], (T - self.joint) / dims[1], 0.3 / dims[2]))]

    def floor(self, W, D, seed_salt=0, z_top=0.0):
        rng = random.Random(self.seed * 15485863 + seed_salt)
        out = []
        cls = self.m["slab"]
        sw, sd, sh = cls["dims"]
        nx = max(1, int(round(W / (sw * 0.95))))
        ny = max(1, int(round(D / (sd * 0.95))))
        cw, cd = W / nx, D / ny
        for i in range(nx):
            for j in range(ny):
                mesh = rng.choice(cls["meshes"])
                x = -W / 2 + (i + 0.5) * cw + rng.uniform(-0.02, 0.02)
                y = -D / 2 + (j + 0.5) * cd + rng.uniform(-0.02, 0.02)
                yaw = rng.choice([0, 90, 180, 270]) + rng.uniform(-2.5, 2.5)
                s = rng.uniform(0.96, 1.0)
                sx, sy = (cw - self.joint) / sw * s, (cd - self.joint) / sd * s
                if int(yaw / 90) % 2 == 1:
                    sx, sy = (cd - self.joint) / sw * s, (cw - self.joint) / sd * s
                out.append((mesh, (x, y, z_top - sh / 2 + rng.uniform(-0.006, 0.0)), (rng.uniform(-0.4, 0.4), yaw, rng.uniform(-0.4, 0.4)), (sx, sy, 1.0)))
        return out

    def pillar(self, H, side=0.6, seed_salt=0):
        rng = random.Random(self.seed * 32452843 + seed_salt)
        out = []
        course_h = 0.4
        n = max(1, int(round(H / course_h)))
        course_h = H / n
        for i in range(n):
            mesh, dims = self._pick(rng, "medium")
            s = side + (0.25 if i == 0 or i == n - 1 else 0.0)
            out.append((mesh, (0, 0, i * course_h + course_h / 2), (0, rng.choice([0, 90, 180, 270]) + rng.uniform(-3, 3), 0),
                        (s / dims[0], s / dims[1], (course_h - self.joint) / dims[2])))
        return out


def rotate_xy(x, y, yaw_deg):
    a = math.radians(yaw_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
