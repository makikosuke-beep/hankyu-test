"""Guitars and basses for the Beat Drummer band - ten classic body styles.

Each instrument stands on the bottom of its body: neck along +Y, the top
(strings side) facing +Z, treble side to +X.  Lengths in the tables are
millimetres; meshes are built in metres.  No brand names or logos, and the
headstocks are generic outlines in the spirit of each style.

Run:  python instruments.py --out ../export/instruments
"""
import argparse
import json
import math
import os

import numpy as np

from mesh_lib import (Mesh, Rx, T, chain, cylinder, finalize, frame, lathe, sphere,
                      tube_between, unit, write_obj)

MM = 0.001
STUD = 0.28
SPACING = 0.5        # metres between instruments in the exported row


# ---------------------------------------------------------------------------
# 2D helpers (millimetres)
# ---------------------------------------------------------------------------
def spline(points, corners=(), step=5.0):
    """Closed centripetal Catmull-Rom through ``points``; indices listed in
    ``corners`` stay sharp."""
    P = np.asarray(points, float)
    n = len(P)
    cs = set(i % n for i in corners)
    out = []
    for i in range(n):
        p1, p2 = P[i], P[(i + 1) % n]
        p0 = P[i - 1] if i not in cs else 2 * p1 - p2
        p3 = P[(i + 2) % n] if (i + 1) % n not in cs else 2 * p2 - p1
        L = np.linalg.norm(p2 - p1)
        k = max(2, int(math.ceil(L / step)))
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-6) ** 0.5
        t2 = t1 + max(L, 1e-6) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-6) ** 0.5
        for t in np.linspace(t1, t2, k, endpoint=False):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.array(out)


def polygon(points, corners=(), step=5.0):
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    p = Polygon(spline(points, corners, step)).buffer(0)
    if p.geom_type != "Polygon":
        p = max(p.geoms, key=lambda g: g.area)
    return orient(p, 1.0)


def largest(g):
    if g.is_empty:
        return None
    if g.geom_type == "Polygon":
        return g
    polys = [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]
    return max(polys, key=lambda x: x.area) if polys else None


def soften(p, r):
    return largest(p.buffer(-r, quad_segs=4).buffer(2 * r, quad_segs=4).buffer(-r, quad_segs=4))


def rrect(cx, cy, w, h, r, ang=0.0):
    from shapely import affinity
    from shapely.geometry import box
    b = box(cx - w / 2 + r, cy - h / 2 + r, cx + w / 2 - r, cy + h / 2 - r).buffer(r, quad_segs=6)
    return affinity.rotate(b, ang, origin=(cx, cy)) if ang else b


def stadium(cx, cy, w, h, ang=0.0):
    return rrect(cx, cy, w, h, h / 2 - 0.01, ang)


def resample(ring, n, ref):
    """n points evenly spaced along a closed ring, CCW, starting near ref."""
    from shapely.geometry import LinearRing, Point
    lr = LinearRing(ring)
    if not lr.is_ccw:
        lr = LinearRing(list(lr.coords)[::-1])
    L = lr.length
    s0 = lr.project(Point(ref))
    return np.array([lr.interpolate((s0 + L * i / n) % L).coords[0] for i in range(n)])


def triangulate(pts2d, holes=()):
    import mapbox_earcut as earcut
    verts = [np.asarray(pts2d, float)] + [np.asarray(h, float) for h in holes]
    allv = np.vstack(verts)
    rings = np.cumsum([len(v) for v in verts]).astype(np.uint32)
    tri = earcut.triangulate_float64(allv, rings).reshape(-1, 3)
    return allv, tri


# ---------------------------------------------------------------------------
# 3D builders (inputs in mm, meshes in metres)
# ---------------------------------------------------------------------------
class UV:
    """Planar texture mapping over a square around the body."""

    def __init__(self, poly, pad=4.0):
        x0, y0, x1, y1 = poly.bounds
        self.size = max(x1 - x0, y1 - y0) + 2 * pad
        self.x0 = (x0 + x1) / 2 - self.size / 2
        self.y0 = (y0 + y1) / 2 - self.size / 2

    def __call__(self, v_m):
        p = v_m[..., :2] / MM
        return np.stack([(p[..., 0] - self.x0) / self.size, (p[..., 1] - self.y0) / self.size], -1)

    def info(self):
        return {"x0": self.x0, "y0": self.y0, "size": self.size}


def planar_uv(mesh, uv):
    mesh.cuv = uv(mesh.v[mesh.f])
    return mesh


def grid_cap(ring, fz, dense=None, fine=10.0, coarse=40.0, up=True):
    """Triangulate a cap with interior points so it can bend: fz(x, y) -> z.
    Interior points are fine where dense(x, y) is true, coarse elsewhere."""
    from scipy.spatial import Delaunay
    from shapely import contains_xy
    from shapely.geometry import Polygon
    pg = Polygon(ring)
    x0, y0, x1, y1 = pg.bounds
    gx, gy = np.meshgrid(np.arange(x0, x1, fine), np.arange(y0, y1, fine))
    cand = np.column_stack([gx.ravel(), gy.ravel()])
    keep = contains_xy(pg.buffer(-fine * 0.35), cand[:, 0], cand[:, 1])
    if dense is not None:
        k = int(round(coarse / fine))
        ix = np.round((cand[:, 0] - x0) / fine).astype(int)
        iy = np.round((cand[:, 1] - y0) / fine).astype(int)
        lattice = (ix % k == 0) & (iy % k == 0)
        keep &= dense(cand[:, 0], cand[:, 1]) | lattice
    pts = np.vstack([ring, cand[keep]])
    tri = Delaunay(pts).simplices
    cen = pts[tri].mean(1)
    tri = tri[contains_xy(pg, cen[:, 0], cen[:, 1])]
    P = np.column_stack([pts, fz(pts[:, 0], pts[:, 1])])
    e = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    flip = (e[:, 2] < 0) if up else (e[:, 2] > 0)
    tri[flip] = tri[flip][:, ::-1]
    return P, tri


def slab(poly, z0, z1, profile_bottom=(), profile_top=(), n=140, keys=None, carve=None,
         ref=(0.0, -1e4), smooth=40.0, uv=None, cap_keys=("cap_bottom", "cap_top"),
         contour_top=None, contour_bottom=None):
    """Extrude a shapely polygon (mm) between z0 and z1 (mm) with edge
    profiles.  profile_*: [(inset, dz)] from the side wall toward the cap;
    for the bottom dz is measured up from z0, for the top down from z1.
    keys(i, z_lo, z_hi) -> part key of side band i.  carve(x, y) -> extra
    height (mm) of the top cap only; contour_top / contour_bottom(x, y) ->
    height change of the whole top / bottom (cap and edge), for sculpted
    arm and belly contours.  Returns {key: Mesh}."""
    prof = [(ins, z0 + dz) for ins, dz in reversed(list(profile_bottom))]
    if not prof or prof[-1][0] > 1e-9:
        prof.append((0.0, z0 if not prof else prof[-1][1]))
    prof.append((0.0, z1 - (profile_top[0][1] if profile_top else 0.0)))
    prof += [(ins, z1 - dz) for ins, dz in profile_top[1:]] if profile_top else []
    if profile_top and profile_top[-1][0] > 1e-9 and prof[-1] != (profile_top[-1][0], z1 - profile_top[-1][1]):
        prof.append((profile_top[-1][0], z1 - profile_top[-1][1]))
    zmid = (z0 + z1) / 2
    none = (lambda x, y: np.zeros_like(x))  # noqa: E731
    ct = contour_top or none
    cb = contour_bottom or none
    rings = []
    for ins, z in prof:
        g = poly if ins <= 1e-9 else largest(poly.buffer(-ins, quad_segs=6))
        rings.append((resample(g.exterior.coords, n, ref), z))
    V, F, K = [], [], []
    for r, z in rings:
        dz = ct(r[:, 0], r[:, 1]) if z > zmid else cb(r[:, 0], r[:, 1])
        V.append(np.column_stack([r, z + dz]))
    V = np.vstack(V)
    for i in range(len(rings) - 1):
        a = i * n + np.arange(n)
        b = i * n + (np.arange(n) + 1) % n
        c = (i + 1) * n + (np.arange(n) + 1) % n
        d = (i + 1) * n + np.arange(n)
        f = np.concatenate([np.stack([a, b, c], -1), np.stack([a, c, d], -1)])
        F.append(f)
        k = keys(i, rings[i][1], rings[i + 1][1]) if keys else "side"
        K += [k] * len(f)
    out_v = [V]

    def attach_cap(ring_index, P, tri):
        """Reuse the ring's own vertices for the cap boundary."""
        nv = sum(len(v) for v in out_v)
        m = len(P) - n
        out_v.append(P[n:])
        idx = np.concatenate([ring_index * n + np.arange(n), nv + np.arange(m)])
        return idx[tri]

    # bottom cap
    r0, z_b = rings[0]
    if contour_bottom is None:
        verts, tri = triangulate(r0)
        F.append(tri[:, ::-1])
    else:
        P, tri = grid_cap(r0, lambda x, y: z_b + cb(x, y),
                          dense=lambda x, y: np.abs(cb(x, y)) > 1e-3, up=False)
        F.append(attach_cap(0, P, tri))
    K += [cap_keys[0]] * len(F[-1])
    # top cap
    rt, z_t = rings[-1]
    if carve is None and contour_top is None:
        verts, tri = triangulate(rt)
        F.append(tri + (len(rings) - 1) * n)
    else:
        cv = carve or none
        P, tri = grid_cap(rt, lambda x, y: z_t + cv(x, y) + ct(x, y),
                          dense=None if carve else (lambda x, y: np.abs(ct(x, y)) > 1e-3),
                          fine=11.0 if carve else 10.0)
        F.append(attach_cap(len(rings) - 1, P, tri))
    K += [cap_keys[1]] * len(F[-1])
    P = np.vstack(out_v) * MM
    F = np.concatenate(F)
    K = np.array(K)
    out = {}
    for k in dict.fromkeys(K.tolist()):
        sel = F[K == k]
        used = np.unique(sel)
        remap = -np.ones(len(P), np.int64)
        remap[used] = np.arange(len(used))
        m, _ = finalize(P[used], remap[sel], smooth)
        if uv is not None:
            planar_uv(m, uv)
        out[k] = m
    return out


def bevel(origin, direction, depth, slope=0.34, soft=14.0, sign=-1.0):
    """Planar contour cut: zero behind a line, then sloping down (or up for
    the back) toward ``direction``, never deeper than ``depth`` (mm)."""
    u = unit(np.asarray(direction, float))
    o = np.asarray(origin, float)

    def f(x, y):
        s = (x - o[0]) * u[0] + (y - o[1]) * u[1]
        ramp = np.where(s < soft, np.clip(s, 0, None) ** 2 / (2 * soft), s - soft / 2)
        return sign * np.minimum(ramp * slope, depth)
    return f


def flat(poly, z0, z1, r_top=0.0, n=None, uv=None, smooth=35.0):
    """Thin plate (pickguard, plate) with an optional rounded top edge."""
    n = n or int(np.clip(poly.exterior.length / 7, 24, 110))
    top = [(0.0, r_top), (r_top, 0.0)] if r_top > 0 else []
    parts = slab(poly, z0, z1, (), top, n=n, uv=uv, smooth=smooth,
                 ref=(poly.centroid.x, poly.bounds[1] - 100))
    return Mesh.merge(list(parts.values()))


def box(c, s):
    """Axis box, centre c / size s in mm."""
    cx, cy, cz = c
    sx, sy, sz = (v / 2 for v in s)
    v = np.array([[cx + a * sx, cy + b * sy, cz + d * sz] for a in (-1, 1) for b in (-1, 1)
                  for d in (-1, 1)]) * MM
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                  [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    m, _ = finalize(v, f, 20.0)
    return m


def rbox(c, s, bevel=None):
    from mesh_lib import rbox as _rbox
    m = _rbox(s[0] * MM, s[1] * MM, s[2] * MM, None if bevel is None else bevel * MM)
    return m.transformed(T(*(np.asarray(c) * MM)))


def cyl(c, r, h, axis=(0, 0, 1), segs=14, bevel=0.0):
    c = np.asarray(c, float) * MM
    a = unit(axis)
    m = cylinder(r * MM, h * MM, segs, bevel=bevel * MM)
    return m.transformed(chain(frame(c, a), T(0, -h * MM / 2, 0)))


def lathe_at(c, prof_mm, axis=(0, 0, 1), segs=18, smooth=45.0):
    m = lathe([(r * MM, y * MM) for r, y in prof_mm], segs, smooth=smooth)
    return m.transformed(frame(np.asarray(c, float) * MM, axis))


def ellipsoid(c, r):
    m = sphere(1.0, 10, 6)
    v = m.v * np.asarray(r, float) * MM + np.asarray(c, float) * MM
    m2, _ = finalize(v, m.f, 70.0)
    return m2


def loft(sections, smooth=45.0, caps=True):
    """sections: list of (m, 3) point rings in mm -> closed tube mesh."""
    S = np.asarray(sections, float)
    k, m = S.shape[:2]
    V = S.reshape(-1, 3)
    F = []
    for i in range(k - 1):
        a = i * m + np.arange(m)
        b = i * m + (np.arange(m) + 1) % m
        c = (i + 1) * m + (np.arange(m) + 1) % m
        d = (i + 1) * m + np.arange(m)
        F += [np.stack([a, b, c], -1), np.stack([a, c, d], -1)]
    F = np.concatenate(F)
    if caps:
        c0 = len(V)
        c1 = c0 + 1
        V = np.vstack([V, S[0].mean(0), S[-1].mean(0)])
        j = np.arange(m)
        F = np.concatenate([F, np.stack([np.full(m, c0), (j + 1) % m, j], -1),
                            np.stack([np.full(m, c1), (k - 1) * m + j, (k - 1) * m + (j + 1) % m], -1)])
    V = V * MM
    # make the tube face outward
    cen = V.mean(0)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    nrm = np.cross(b - a, c - a)
    if (((a + b + c) / 3 - cen) * nrm).sum() < 0:
        F = F[:, ::-1]
    mesh, _ = finalize(V, F, smooth)
    return mesh


# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------
GLOSS = {"material": "SmoothPlastic", "reflectance": 0.12, "pbr": [0.0, 0.18, 1.0]}


def finish(color, texture=None, **kw):
    d = dict(GLOSS, color=color)
    if texture:
        d["texture"] = texture
    d.update(kw)
    return d


def common_palette(fretboard, inlay=(240, 236, 226), hardware=(214, 216, 222),
                   pickup=(24, 24, 26), knob=(24, 24, 26), neck=(232, 196, 140)):
    return {
        "Neck": {"color": list(neck), "material": "Wood", "reflectance": 0.05,
                 "pbr": [0.0, 0.35, 0.6], "grain": "maple"},
        "Board": {"color": list(fretboard), "material": "Wood", "reflectance": 0.0,
                  "pbr": [0.0, 0.55, 0.0],
                  "grain": "rosewood" if sum(fretboard) < 400 else "maple"},
        "Frets": {"color": [208, 206, 198], "material": "Metal", "reflectance": 0.3,
                  "pbr": [1.0, 0.18, 0.0]},
        "Inlay": {"color": list(inlay), "material": "SmoothPlastic", "reflectance": 0.2,
                  "pbr": [0.0, 0.25, 0.8]},
        "Nut": {"color": [238, 230, 210], "material": "SmoothPlastic", "reflectance": 0.05,
                "pbr": [0.0, 0.35, 0.3]},
        "Hardware": {"color": list(hardware), "material": "Metal", "reflectance": 0.35,
                     "pbr": [1.0, 0.1, 0.0]},
        "Strings": {"color": [206, 206, 202], "material": "Metal", "reflectance": 0.3,
                    "pbr": [1.0, 0.22, 0.0], "glow": True},
        "Pickup": {"color": list(pickup), "material": "SmoothPlastic", "reflectance": 0.08,
                   "pbr": [0.0, 0.35, 0.4]},
        "Knob": {"color": list(knob), "material": "SmoothPlastic", "reflectance": 0.12,
                 "pbr": [0.0, 0.25, 0.8]},
    }


ROSEWOOD = (62, 36, 26)
MAPLE_BOARD = (228, 190, 132)
CHROME = (214, 216, 222)

INSTRUMENTS = [
    # ------------------------------------------------------------------ guitars
    {
        "id": "Skyline", "kind": "Guitar", "type": "ST", "name": "スカイライン",
        "nameEn": "SKYLINE", "style": "ST タイプ",
        "desc": "3 トーンサンバーストに白いピックガード。シングルコイル 3 基とトレモロの、いちばん定番のシェイプ。",
        "scale": 648, "frets": 21, "nut": 42.0, "saddle_y": 130, "notch_y": 381,
        "thick": 45, "edge": 7.5, "fb_h": 11, "head": "six", "head_angle": 0,
        "outline": [(0, 0), (70, 3), (118, 16), (150, 42), (164, 82), (163, 125), (150, 165),
                    (128, 200), (118, 232), (122, 262), (134, 296), (136, 330), (124, 362),
                    (110, 392), (98, 412), (84, 416), (70, 402), (56, 388), (40, 381), (28.5, 380),
                    (-28.5, 380), (-40, 385), (-56, 402), (-72, 428), (-88, 450), (-102, 458),
                    (-116, 450), (-126, 422), (-133, 388), (-142, 352), (-146, 318), (-140, 286),
                    (-128, 258), (-120, 232), (-126, 205), (-146, 170), (-160, 128), (-162, 84),
                    (-150, 44), (-120, 16), (-72, 3)],
        "corners": [19, 20],
        "guard_poly": [(-51, 343), (-56, 314), (-60, 283), (-63, 251), (-69, 220), (-71, 194), (-70, 173), (-65, 158), (-55, 148), (-33, 145), (48, 137), (53, 132), (75, 126), (97, 111), (118, 103), (134, 98), (150, 96), (300, 96), (300, 440), (-28, 440), (-28, 346)],
        "pickups": [("single", 158, 0, 0), ("single", 100, 0, 0), ("single", 45, 0, -9)],
        "pickup_color": "cover", "bridge": "trem",
        "knobs": [("skirt", 59, 169), ("skirt", 93, 144), ("skirt", 126, 119)],
        "switch": ("blade", 89, 188),
        "palette": dict(common_palette(ROSEWOOD, knob=(240, 238, 228)),
                        Body=finish([214, 120, 38], "burst_3ts"),
                        Guard={"color": [242, 240, 232], "material": "SmoothPlastic",
                               "reflectance": 0.06, "pbr": [0.0, 0.3, 0.3]},
                        Cover={"color": [240, 238, 228], "material": "SmoothPlastic",
                               "reflectance": 0.08, "pbr": [0.0, 0.3, 0.4]}),
    },
    {
        "id": "Prairie", "kind": "Guitar", "type": "TL", "name": "プレーリー",
        "nameEn": "PRAIRIE", "style": "TL タイプ",
        "desc": "バタースコッチのアッシュに黒いピックガード、メイプル指板。アッシュトレイのブリッジが目印のシングルカット。",
        "scale": 648, "frets": 21, "nut": 42.0, "saddle_y": 136, "notch_y": 387,
        "thick": 45, "edge": 3.5, "fb_h": 11, "head": "tele", "head_angle": 0,
        "outline": [(0, 0), (72, 3), (120, 15), (150, 40), (162, 80), (163, 130), (158, 180),
                    (151, 222), (150, 262), (153, 292), (149, 320), (136, 340), (116, 352),
                    (96, 352), (78, 342), (60, 324), (44, 309), (28.5, 304), (-28.5, 304),
                    (-28.5, 375), (-45, 383), (-80, 388), (-112, 382), (-138, 364), (-155, 336),
                    (-162, 300), (-160, 262), (-154, 225), (-158, 185), (-163, 130), (-162, 80),
                    (-150, 40), (-120, 15), (-72, 3)],
        "corners": [17, 18, 19],
        "guard_poly": [(-83, 202), (-83, 253), (-82, 268), (-74, 306), (-66, 327), (-54, 348), (-42, 362), (-28, 369), (-28, 400), (28, 400), (28, 333), (36, 325), (46, 321), (55, 321), (64, 323), (75, 329), (82, 336), (92, 352), (101, 378), (109, 385), (119, 384), (126, 375), (129, 360), (129, 336), (122, 310), (107, 272), (104, 255), (105, 236), (116, 204)],
        "pickups": [("tele_neck", 164, 0, 0), ("single", 53, 0, -6)],
        "pickup_color": "black", "bridge": "ashtray",
        "control_plate": {"c": (88, 137), "w": 30, "h": 157, "ang": 0,
                          "knobs": [(-61,), (3,)], "switch": (43,)},
        "palette": dict(common_palette(MAPLE_BOARD, inlay=(30, 26, 24), knob=CHROME),
                        Body=finish([226, 168, 80], "ash_blonde"),
                        Guard={"color": [20, 20, 22], "material": "SmoothPlastic",
                               "reflectance": 0.1, "pbr": [0.0, 0.25, 0.6]}),
    },
    {
        "id": "Heritage", "kind": "Guitar", "type": "LP", "name": "ヘリテージ",
        "nameEn": "HERITAGE", "style": "LP タイプ",
        "desc": "チェリーサンバーストのトラ杢トップにクリームのバインディング。ハムバッカー 2 基のずっしりしたシングルカット。",
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 181, "notch_y": 432,
        "thick": 46, "edge": 3.0, "fb_h": 21, "carve": 14, "head": "gibson",
        "head_angle": 14, "binding": True, "board_binding": True, "inlays": "trapezoid",
        "outline": [(0, 0), (75, 4), (122, 18), (153, 46), (165, 88), (164, 132), (152, 172),
                    (130, 202), (116, 226), (114, 250), (120, 276), (124, 302), (118, 330),
                    (104, 354), (88, 372), (74, 381), (62, 376), (52, 358), (40, 338), (28, 330),
                    (-28, 330), (-28, 395), (-45, 400), (-75, 404), (-102, 398), (-122, 382),
                    (-134, 358), (-138, 330), (-133, 300), (-122, 272), (-118, 246), (-124, 218),
                    (-142, 186), (-158, 150), (-165, 108), (-162, 66), (-148, 34), (-122, 13),
                    (-76, 3)],
        "corners": [19, 20, 21],
        "raised_guard": [(43, 358), (58, 343), (73, 311), (88, 279), (103, 247), (115, 219), (122, 202), (117, 192), (101, 191), (72, 201), (52, 214), (45, 258), (41, 317), (40, 351)],
        "pickups": [("humbucker", 144, 0, 0), ("humbucker", 53, 0, 0)],
        "rings": True, "pickup_color": "chrome", "bridge": "tom_stop",
        "knobs": [("tophat", 115, 158), ("tophat", 68, 134), ("tophat", 113, 100), ("tophat", 68, 75)],
        "switch": ("toggle", -96, 334),
        "palette": dict(common_palette(ROSEWOOD, hardware=(222, 218, 206), knob=(214, 160, 60),
                                       neck=(120, 52, 30)),
                        Head=finish([16, 14, 14], pbr=[0.0, 0.3, 0.35]),
                        Body=finish([96, 16, 12]),
                        Top=finish([196, 70, 30], "burst_cherry_flame"),
                        Binding={"color": [238, 226, 196], "material": "SmoothPlastic",
                                 "reflectance": 0.1, "pbr": [0.0, 0.25, 0.8]},
                        Guard={"color": [238, 226, 196], "material": "SmoothPlastic",
                               "reflectance": 0.06, "pbr": [0.0, 0.3, 0.4]}),
    },
    {
        "id": "CrimsonHorn", "kind": "Guitar", "type": "SG", "name": "クリムゾンホーン",
        "nameEn": "CRIMSON HORN", "style": "SG タイプ",
        "desc": "チェリーレッドの薄いボディに尖った 2 本のホーンと深いベベル。大きな黒いピックガードの攻撃的な一本。",
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 197, "notch_y": 370,
        "thick": 34, "edge": 2.5, "bevel": (12, 6), "fb_h": 12, "head": "gibson",
        "head_angle": 14, "inlays": "trapezoid",
        "outline": [(0, 0), (70, 3), (118, 16), (150, 42), (163, 80), (162, 122), (150, 160),
                    (132, 190), (122, 214), (120, 238), (128, 264), (128, 292), (118, 318),
                    (106, 342), (100, 364), (102, 388), (98, 408), (88, 418), (78, 412), (68, 394),
                    (56, 372), (40, 352), (28, 346), (-28, 346), (-40, 354), (-56, 374), (-70, 398),
                    (-84, 422), (-96, 438), (-106, 434), (-110, 414), (-112, 388), (-118, 360),
                    (-128, 330), (-132, 298), (-126, 266), (-122, 240), (-126, 214), (-140, 186),
                    (-156, 156), (-164, 118), (-162, 78), (-150, 42), (-120, 16), (-72, 3)],
        "corners": [22, 23],
        "guard_poly": [(-90, 330), (-64, 341), (-44, 350), (17, 349), (54, 331), (78, 339), (91, 343), (96, 322), (101, 273), (98, 224), (99, 194), (101, 165), (72, 170), (47, 176), (27, 180), (-14, 180), (-39, 179), (-72, 178), (-74, 215), (-72, 249), (-77, 283), (-85, 307)],
        "pickups": [("open_humbucker", 125, 0, 0), ("open_humbucker", 36, 0, 0)],
        "pickup_color": "black", "bridge": "tom_stop",
        "knobs": [("tophat", 88, 102), ("tophat", 127, 101), ("tophat", 77, 62), ("tophat", 115, 55)],
        "switch": ("toggle", 98, 148),
        "palette": dict(common_palette(ROSEWOOD, knob=(20, 20, 22), neck=(118, 26, 20)),
                        Head=finish([16, 14, 14], pbr=[0.0, 0.3, 0.35]),
                        Body=finish([104, 14, 12]),
                        Guard={"color": [16, 16, 18], "material": "SmoothPlastic",
                               "reflectance": 0.1, "pbr": [0.0, 0.25, 0.6]}),
    },
    {
        "id": "Valkyrie", "kind": "Guitar", "type": "V", "name": "ヴァルキリー",
        "nameEn": "VALKYRIE", "style": "V タイプ",
        "desc": "漆黒の V シェイプに白いピックガードと V 字のテールピース。メタルのステージ映えする変形ギター。",
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 287, "notch_y": 476,
        "thick": 35, "edge": 3.0, "fb_h": 12, "head": "arrow", "head_angle": 14,
        "inlays": "dots",
        "outline": [(28, 470), (44, 474), (60, 466), (70, 448), (200, 40), (210, 26), (208, 12),
                    (196, 4), (182, 6), (40, 168), (20, 184), (0, 190), (-20, 184), (-40, 168),
                    (-182, 6), (-196, 4), (-208, 12), (-210, 26), (-200, 40), (-70, 448),
                    (-60, 466), (-44, 474), (-28, 470)],
        "corners": [0, 22],
        "guard": {"region": [(-300, 700), (300, 700), (300, 380), (82, 262), (48, 250),
                             (-48, 250), (-82, 262), (-300, 380)], "inset": 9,
                  "cut": [(0, 272, 96, 26)]},
        "pickups": [("humbucker", 145, 0, 0), ("humbucker", 40, 0, 0)],
        "pickup_color": "chrome", "bridge": "tom_v",
        "knobs": [("tophat", 92, 208), ("tophat", 124, 156), ("tophat", 82, 150)],
        "switch": ("toggle", -110, 300),
        "palette": dict(common_palette(ROSEWOOD, knob=(20, 20, 22), neck=(30, 28, 28)),
                        Head=finish([16, 14, 14], pbr=[0.0, 0.3, 0.35]),
                        Body=finish([14, 14, 16]),
                        Guard={"color": [242, 240, 232], "material": "SmoothPlastic",
                               "reflectance": 0.06, "pbr": [0.0, 0.3, 0.3]}),
    },
    # ------------------------------------------------------------------- basses
    {
        "id": "Velvet", "kind": "Bass", "type": "JB", "name": "ヴェルヴェット",
        "nameEn": "VELVET", "style": "JB タイプ",
        "desc": "オフセットしたウエストにシングルコイル 2 基。3 トーンサンバーストとべっ甲柄ピックガードの細いネックのベース。",
        "scale": 864, "frets": 20, "nut": 38.0, "neck_end_w": 62.0, "saddle_y": 73,
        "notch_y": 419, "thick": 45, "edge": 8.0, "fb_h": 13, "head": "bass4",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (84, 4), (134, 18), (166, 48), (180, 94), (176, 142), (158, 184),
                    (134, 218), (122, 248), (124, 280), (134, 314), (140, 350), (136, 384),
                    (124, 410), (110, 430), (96, 444), (82, 446), (70, 438), (56, 431), (40, 428),
                    (31, 428), (-31, 428), (-42, 434), (-56, 450), (-72, 474), (-90, 500),
                    (-106, 518), (-122, 524), (-134, 512), (-140, 486), (-142, 452), (-148, 416),
                    (-158, 380), (-162, 342), (-154, 306), (-140, 276), (-132, 252), (-138, 222),
                    (-158, 190), (-172, 148), (-174, 100), (-158, 52), (-124, 18), (-70, 3)],
        "corners": [20, 21],
        # the guard wraps the treble horn but leaves the bass horn in the body finish
        "guard": {"region": [(-25, 700), (-25, 432), (-61, 414), (-56, 400), (-49, 377),
                             (-43, 352), (-45, 327), (-53, 302), (-64, 273), (-74, 244),
                             (-79, 223), (-76, 210), (-66, 198), (-37, 188), (5, 181), (42, 177),
                             (63, 185), (109, 202), (300, 202), (300, 700)], "inset": 8},
        "pickups": [("jbass", 156, 0, 0), ("jbass", 62, 0, 0)],
        "pickup_color": "black", "bridge": "fender_bass",
        "control_plate": {"c": (124, 124), "w": 34, "h": 140, "ang": 34,
                          "knobs": [(48,), (2,), (-44,)]},
        "palette": dict(common_palette(ROSEWOOD, knob=CHROME),
                        Body=finish([210, 112, 36], "burst_3ts"),
                        Guard={"color": [120, 50, 22], "material": "SmoothPlastic",
                               "reflectance": 0.08, "pbr": [0.0, 0.5, 0.0],
                               "texture": "tortoise"}),
    },
    {
        "id": "Foundation", "kind": "Bass", "type": "PB", "name": "ファウンデーション",
        "nameEn": "FOUNDATION", "style": "PB タイプ",
        "desc": "オリンピックホワイトにべっ甲柄ピックガード。スプリットコイル 1 基と太めのネックの、ロックの土台になる一本。",
        "scale": 864, "frets": 20, "nut": 42.0, "neck_end_w": 64.0, "saddle_y": 61,
        "notch_y": 417, "thick": 45, "edge": 8.0, "fb_h": 13, "head": "bass4",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (82, 4), (132, 18), (164, 48), (178, 94), (176, 142), (160, 184),
                    (140, 216), (132, 246), (136, 280), (146, 316), (148, 352), (140, 386),
                    (126, 414), (110, 432), (94, 444), (80, 444), (68, 434), (54, 427), (40, 424),
                    (31, 424), (-31, 424), (-42, 430), (-58, 448), (-76, 472), (-94, 494),
                    (-110, 508), (-124, 510), (-136, 498), (-142, 472), (-144, 442), (-152, 406),
                    (-162, 370), (-164, 334), (-154, 300), (-140, 272), (-134, 250), (-142, 220),
                    (-162, 186), (-176, 144), (-178, 96), (-162, 50), (-128, 17), (-72, 3)],
        "corners": [20, 21],
        # big guard that wraps round the split coil and carries the two knobs
        "guard": {"region": [(-84, 700), (-84, 164), (53, 164), (71, 43), (90, 10), (300, 10),
                             (300, 700)], "inset": 8},
        "pickups": [("psplit", 155, 0, 0)],
        "pickup_color": "black", "bridge": "fender_bass",
        "knobs": [("dome", 115, 150), ("dome", 117, 94)],
        "palette": dict(common_palette(ROSEWOOD, knob=CHROME),
                        Body=finish([236, 234, 220]),
                        Guard={"color": [120, 50, 22], "material": "SmoothPlastic",
                               "reflectance": 0.08, "pbr": [0.0, 0.5, 0.0],
                               "texture": "tortoise"}),
    },
    {
        "id": "Manta", "kind": "Bass", "type": "SR", "name": "マンタ",
        "nameEn": "MANTA", "style": "SR タイプ",
        "desc": "丸いボディに大きなハムバッカー 1 基、3+1 のヘッドと丸いコントロールプレート。ナチュラルアッシュに黒いピックガード。",
        "scale": 864, "frets": 21, "nut": 42.0, "neck_end_w": 64.0, "saddle_y": 47,
        "notch_y": 398, "thick": 45, "edge": 10.0, "fb_h": 13, "head": "three_one",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (88, 5), (140, 22), (172, 56), (182, 102), (178, 150), (162, 192),
                    (146, 222), (138, 252), (142, 286), (150, 320), (148, 356), (136, 384),
                    (118, 406), (100, 418), (84, 418), (70, 408), (54, 402), (36, 400), (31, 400),
                    (-31, 400), (-44, 408), (-60, 424), (-78, 446), (-96, 464), (-112, 472),
                    (-126, 466), (-136, 446), (-142, 418), (-150, 384), (-158, 350), (-156, 314),
                    (-144, 284), (-138, 258), (-146, 226), (-164, 192), (-178, 150), (-182, 104),
                    (-170, 58), (-140, 22), (-88, 5)],
        "corners": [19, 20],
        "guard_poly": [(-88, 156), (-76, 133), (-45, 105), (-22, 101), (23, 101), (49, 111), (72, 134), (82, 154), (87, 216), (67, 275), (27, 317), (31, 333), (21, 370), (-9, 372), (-27, 367), (-28, 315), (-66, 284), (-80, 259), (-91, 216)],
        "pickups": [("mm", 118, 0, 0)], "pickup_color": "black", "bridge": "mm_bridge",
        "round_plate": {"c": (110, 120), "r": 42, "knobs": [(92, 148), (112, 126), (126, 98)]},
        "palette": dict(common_palette(MAPLE_BOARD, inlay=(30, 26, 24), knob=CHROME),
                        Body=finish([214, 176, 120], "ash_natural"),
                        Guard={"color": [20, 20, 22], "material": "SmoothPlastic",
                               "reflectance": 0.1, "pbr": [0.0, 0.25, 0.6]}),
    },
    {
        "id": "Tempest", "kind": "Bass", "type": "TB", "name": "テンペスト",
        "nameEn": "TEMPEST", "style": "TB タイプ",
        "desc": "高音側のホーンが長く伸びたリバースボディ。タバコサンバーストにクロームのハムバッカー 2 基のスルーネック。",
        "scale": 864, "frets": 20, "nut": 40.0, "neck_end_w": 62.0, "saddle_y": 96,
        "notch_y": 442, "thick": 40, "edge": 6.0, "fb_h": 12, "head": "reverse4",
        "head_angle": 10, "strings": 4, "inlays": "dots",
        "outline": [(-10, 0), (64, 6), (122, 24), (160, 54), (178, 96), (174, 144), (158, 186),
                    (144, 218), (140, 250), (146, 284), (154, 320), (160, 358), (160, 398),
                    (154, 436), (142, 470), (128, 498), (112, 516), (96, 522), (84, 512),
                    (74, 488), (64, 458), (52, 430), (40, 410), (31, 402), (-31, 402), (-44, 396),
                    (-62, 378), (-86, 358), (-112, 348), (-134, 342), (-150, 326), (-158, 302),
                    (-160, 270), (-164, 236), (-172, 200), (-182, 160), (-186, 116), (-180, 72),
                    (-162, 38), (-132, 14), (-80, 2)],
        "corners": [23, 24],
        "pickups": [("tb_humbucker", 183, 0, 0), ("tb_humbucker", 78, 0, 0)],
        "pickup_color": "chrome", "bridge": "tb_bridge",
        "guard_poly": [(62, 401), (68, 354), (68, 263), (72, 235), (65, 227), (72, 221), (78, 225), (100, 270), (153, 411), (155, 455), (141, 465), (120, 460), (80, 418), (67, 411)],
        "knobs": [("tophat", 68, 85), ("tophat", 68, 127), ("tophat", 68, 169)],
        "palette": dict(common_palette(ROSEWOOD, knob=(20, 20, 22), neck=(120, 66, 34)),
                        Head=finish([16, 14, 14], pbr=[0.0, 0.3, 0.35]),
                        Body=finish([176, 104, 40], "burst_tobacco"),
                        Guard={"color": [236, 228, 208], "material": "SmoothPlastic",
                               "reflectance": 0.06, "pbr": [0.0, 0.35, 0.4]}),
    },
    {
        "id": "Crestwave", "kind": "Bass", "type": "RK", "name": "クレストウェーブ",
        "nameEn": "CRESTWAVE", "style": "RK タイプ",
        "desc": "波頭のように巻いたホーンとバインディング。ファイアーグローの赤いボディに白い大きなピックガード、三角のインレイ。",
        "scale": 845, "frets": 20, "nut": 42.0, "neck_end_w": 62.0, "saddle_y": 81,
        "notch_y": 355, "thick": 36, "edge": 1.2, "fb_h": 11, "head": "two_two",
        "head_angle": 10, "strings": 4, "binding": True, "board_binding": True,
        "inlays": "triangle",
        "outline": [(0, 0), (86, 4), (138, 20), (166, 50), (176, 94), (172, 142), (160, 184),
                    (152, 220), (152, 258), (156, 296), (156, 330), (146, 358), (130, 380),
                    (110, 392), (92, 390), (78, 380), (62, 372), (44, 370), (31, 370), (-31, 370),
                    (-36, 382), (-42, 404), (-52, 432), (-66, 460), (-84, 484), (-102, 498),
                    (-120, 500), (-132, 488), (-132, 462), (-124, 436), (-122, 410), (-130, 382),
                    (-144, 354), (-156, 322), (-162, 288), (-160, 252), (-164, 218), (-176, 180),
                    (-182, 136), (-180, 90), (-164, 48), (-134, 18), (-82, 3)],
        "corners": [18, 19],
        "guard": {"region": [(-74, 700), (-74, 232), (48, 236), (48, 41), (60, 0), (300, 0),
                             (300, 700)], "inset": 8},
        "pickups": [("rk_neck", 209, 0, 0)], "pickup_color": "black", "bridge": "rk_bridge",
        "knobs": [("tophat", 90, 78), ("tophat", 84, 120), ("tophat", 127, 96),
                  ("tophat", 133, 139)],
        "switch": ("toggle", 128, 178),
        "palette": dict(common_palette(ROSEWOOD, inlay=(236, 232, 222), knob=(20, 20, 22),
                                       neck=(232, 196, 140)),
                        Body=finish([196, 32, 24], "burst_fireglo"),
                        Binding={"color": [238, 232, 214], "material": "SmoothPlastic",
                                 "reflectance": 0.1, "pbr": [0.0, 0.25, 0.8]},
                        Guard={"color": [244, 242, 236], "material": "SmoothPlastic",
                               "reflectance": 0.06, "pbr": [0.0, 0.3, 0.3]}),
    },
]
# ---------------------------------------------------------------------------
# refined outlines (inches, traced to the classic proportions).  A third
# element "c" keeps that point sharp (the neck pocket corners).
# ---------------------------------------------------------------------------
OUTLINES_IN = {
    "Skyline": [
        (1.13, 12.76, "c"), (-1.13, 12.76, "c"), (-1.13, 15.01, "c"), (-1.46, 14.59), (-1.65, 14.47), (-1.95, 14.38), (-2.26, 14.35),
        (-2.58, 14.39), (-2.87, 14.49), (-3.14, 14.66), (-3.5, 14.97), (-3.71, 15.3), (-3.82, 15.68), (-4, 16.94),
        (-4.15, 17.18), (-4.34, 17.28), (-4.49, 17.29), (-4.71, 17.24), (-4.91, 17.13), (-5.09, 16.97), (-5.23, 16.79),
        (-5.39, 16.51), (-5.56, 15.98), (-5.67, 15.35), (-5.7, 14.96), (-5.51, 13.48), (-5.41, 13.1), (-4.78, 11.12),
        (-4.6, 10.35), (-4.58, 9.96), (-4.68, 9.41), (-4.89, 8.72), (-5.9, 6.37), (-6.23, 5.47), (-6.49, 4.22),
        (-6.52, 3.58), (-6.5, 3.02), (-6.44, 2.63), (-6.35, 2.33), (-5.74, 1.43), (-5.51, 1.21), (-5.13, 0.92),
        (-4.35, 0.52), (-3.9, 0.35), (-3.2, 0.21), (-1.53, 0.04), (-0.41, 0.01), (0.63, 0.04), (1.19, 0.09),
        (2.22, 0.22), (2.69, 0.33), (3.68, 0.62), (4.61, 1.08), (4.88, 1.25), (5.48, 1.77), (5.87, 2.05),
        (5.98, 2.16), (6.09, 2.35), (6.19, 2.65), (6.26, 3.04), (6.29, 3.76), (6.24, 4.4), (6.07, 5.15),
        (5.73, 6.12), (4.72, 8.3), (4.54, 8.83), (4.48, 9.22), (4.49, 9.62), (4.55, 10.01), (5.16, 11.66),
        (5.44, 12.74), (5.46, 13.14), (5.44, 13.45), (5.34, 13.92), (5.23, 14.22), (5.03, 14.55), (4.79, 14.74),
        (4.49, 14.82), (4.11, 14.78), (3.98, 14.71), (3.84, 14.54), (3.56, 13.8), (3.39, 13.44), (3.21, 13.18),
        (2.98, 12.98), (2.62, 12.81), (2.16, 12.71), (1.6, 12.69)],
    "Prairie": [
        (-0.37, 0), (1.11, 0.02), (2.55, 0.11), (3.49, 0.29), (4.11, 0.5), (4.64, 0.78), (5.34, 1.39),
        (5.76, 2.03), (6.12, 2.85), (6.27, 3.68), (6.27, 4.29), (6.12, 5.25), (5.88, 6.07), (5.54, 6.92),
        (4.68, 8.77), (4.44, 9.64), (4.44, 10.27), (4.5, 10.64), (5.23, 12.57), (5.41, 13.5), (5.38, 14.16),
        (5.29, 14.62), (5.1, 15.05), (4.87, 15.36), (4.62, 15.5), (4.42, 15.55), (4.13, 15.51), (3.89, 15.39),
        (3.62, 15.01), (3.43, 14.36), (3.13, 13.74), (2.69, 13.24), (2.43, 13.09), (2.12, 13), (1.78, 13),
        (1.51, 13.12), (1.36, 13.24), (1.12, 13.65, "c"), (-1.12, 13.65, "c"), (-1.12, 15.23, "c"), (-2.04, 15.39), (-2.74, 15.69),
        (-3, 15.77), (-3.7, 15.78), (-4.02, 15.75), (-4.41, 15.62), (-4.87, 15.3), (-5.13, 14.9), (-5.26, 14.55),
        (-5.35, 14.01), (-5.35, 13.42), (-5.14, 12.42), (-4.53, 10.78), (-4.44, 10.39), (-4.41, 9.87), (-4.62, 8.98),
        (-5.51, 7.04), (-6.02, 5.68), (-6.27, 4.55), (-6.3, 4.14), (-6.21, 3.06), (-5.94, 2.27), (-5.62, 1.73),
        (-5.13, 1.18), (-4.63, 0.81), (-4, 0.48), (-3.62, 0.35), (-2.78, 0.17), (-1.54, 0.05), (-0.72, 0.05)],
    "Heritage": [
        (1.1, 15, "c"), (-1.1, 15, "c"), (-1.1, 16.99, "c"), (-1.88, 17.18), (-2.51, 17.29), (-2.83, 17.29), (-3.38, 17.2),
        (-3.98, 16.99), (-4.45, 16.7), (-4.84, 16.29), (-5.04, 15.95), (-5.18, 15.58), (-5.23, 15.19), (-5.15, 14.8),
        (-5.14, 14.42), (-5.08, 13.96), (-4.87, 13.29), (-4.58, 12.72), (-4.29, 12.24), (-4.17, 11.95), (-4.07, 11.57),
        (-4.07, 10.94), (-4.16, 10.64), (-4.35, 10.29), (-4.65, 9.92), (-5.44, 9.05), (-6.06, 8.02), (-6.32, 7.29),
        (-6.47, 6.61), (-6.52, 5.34), (-6.4, 4.66), (-6.28, 4.21), (-6.06, 3.62), (-5.84, 3.2), (-5.34, 2.47),
        (-5.09, 2.17), (-4.45, 1.57), (-3.45, 0.94), (-3.02, 0.74), (-2.36, 0.49), (-1.38, 0.24), (0.08, 0.03),
        (0.79, 0.02), (1.5, 0.06), (2.26, 0.18), (2.79, 0.32), (3.16, 0.46), (3.6, 0.66), (4.07, 0.95),
        (5.52, 2.09), (5.79, 2.37), (6.05, 2.92), (6.31, 3.65), (6.49, 4.48), (6.51, 5.75), (6.35, 6.59),
        (6.06, 7.4), (5.62, 8.2), (5.32, 8.67), (4.73, 9.41), (3.91, 10.28), (3.61, 10.74), (3.47, 11.1),
        (3.44, 11.58), (3.51, 11.96), (3.7, 12.47), (4.07, 13.18), (4.22, 13.54), (4.29, 13.84), (4.32, 14.55),
        (4.21, 15), (4.13, 15.13), (4.02, 15.23), (3.89, 15.27), (3.75, 15.26), (3.41, 15.08), (2.98, 14.62),
        (2.85, 14.55), (2.62, 14.52), (2.06, 14.54), (1.69, 14.63), (1.48, 14.72)],
    "CrimsonHorn": [
        (1.1, 14.08, "c"), (-1.1, 14.08, "c"), (-1.1, 14.55, "c"), (-1.66, 14.53), (-2.1, 14.24), (-2.32, 14.2), (-2.55, 14.21),
        (-2.85, 14.28), (-3.07, 14.37), (-3.26, 14.5), (-3.51, 14.8), (-3.67, 15.23), (-3.7, 15.7), (-3.61, 16.29),
        (-3.66, 16.38), (-3.72, 16.4), (-3.84, 16.36), (-4.03, 16.24), (-4.49, 15.79), (-4.69, 15.55), (-5.01, 14.99),
        (-5.21, 14.48), (-5.33, 13.96), (-5.43, 13.11), (-5.42, 12.79), (-5.34, 12.1), (-5.17, 11.37), (-4.97, 10.78),
        (-4.54, 9.85), (-4.45, 9.56), (-4.4, 9.26), (-4.41, 8.7), (-4.47, 8.47), (-4.72, 7.97), (-5.51, 6.99),
        (-5.9, 6.3), (-6.07, 5.78), (-6.17, 5.25), (-6.18, 4.38), (-6.06, 3.76), (-5.79, 3.03), (-5.44, 2.51),
        (-4.99, 1.98), (-4.51, 1.59), (-4.18, 1.37), (-3.63, 1.07), (-2.9, 0.79), (-2.15, 0.57), (-0.94, 0.29),
        (-0.34, 0.19), (0.07, 0.06), (0.43, 0.13), (1.95, 0.12), (2.65, 0.2), (3.18, 0.28), (3.7, 0.42),
        (4.15, 0.55), (4.44, 0.68), (4.97, 1.03), (5.37, 1.41), (5.58, 1.65), (6, 2.2), (6.26, 2.84),
        (6.39, 3.59), (6.39, 3.99), (6.3, 4.68), (6.18, 5.2), (5.99, 5.7), (5.53, 6.43), (4.49, 7.82),
        (4.23, 8.55), (4.21, 9.11), (4.23, 9.42), (4.8, 10.94), (4.95, 11.94), (4.95, 12.33), (4.84, 13.01),
        (4.58, 13.83), (4.49, 14.04), (4.12, 14.65), (3.93, 14.9), (3.48, 15.34), (3.3, 15.42), (3.26, 15.4),
        (3.2, 15.3), (3.07, 14.55), (2.95, 14.35), (2.71, 14.14), (2.49, 14.08), (2.09, 14.07), (1.86, 14.08),
        (1.48, 14.16)],
    "Valkyrie": [
        (1.1, 18.75, "c"), (-1.1, 18.75, "c"), (-1.42, 18.76), (-1.7, 18.69), (-1.99, 18.66), (-2.11, 18.58), (-2.27, 18.34),
        (-2.6, 18.15), (-2.8, 17.92), (-2.96, 17.42), (-3.1, 17.06), (-7.92, 2.23), (-7.98, 1.93), (-8.1, 1.66),
        (-8.27, 1.02), (-8.28, 0.79), (-8.23, 0.65), (-8.02, 0.31), (-7.85, 0.16), (-7.57, 0.05), (-7.27, 0.07),
        (-7.12, 0.1), (-6.83, 0.22), (-6.71, 0.31), (-6.45, 0.61), (-6.21, 0.81), (-5.79, 0.98), (-5.65, 1.51),
        (-0.9, 7.07), (-0.73, 7.23), (-0.53, 7.32), (-0.3, 7.35), (0, 7.31), (0.3, 7.35), (0.53, 7.32),
        (0.73, 7.23), (0.9, 7.07), (5.65, 1.51), (5.79, 0.98), (6.21, 0.81), (6.45, 0.61), (6.71, 0.31),
        (6.83, 0.22), (7.12, 0.1), (7.27, 0.07), (7.57, 0.05), (7.85, 0.16), (8.02, 0.31), (8.23, 0.65),
        (8.28, 0.79), (8.27, 1.02), (8.1, 1.66), (7.98, 1.93), (7.92, 2.23), (3.1, 17.06), (2.96, 17.42),
        (2.8, 17.92), (2.6, 18.15), (2.27, 18.34), (2.11, 18.58), (1.99, 18.66), (1.7, 18.69), (1.42, 18.76)],
    "Velvet": [
        (0, 0), (2.4, 0.04), (4.0, 0.22), (5.25, 0.58), (6.1, 1.05), (6.62, 1.6), (6.92, 2.3),
        (7.05, 3.05), (6.95, 3.8), (6.68, 4.6), (6.25, 5.45), (5.7, 6.3), (5.2, 7.15),
        (4.88, 7.95), (4.78, 8.7), (4.92, 9.55), (5.25, 10.5), (5.58, 11.5), (5.77, 12.5),
        (5.85, 13.45), (5.8, 14.4), (5.6, 15.3), (5.27, 16.0), (4.9, 16.48), (4.45, 16.68),
        (4.08, 16.58), (3.88, 16.2), (3.78, 15.6), (3.6, 14.95), (3.2, 14.38), (2.7, 14.1),
        (2.25, 14.05), (1.75, 14.12), (1.22, 14.22, "c"), (-1.22, 14.22, "c"), (-1.22, 16.5, "c"),
        (-1.6, 16.42), (-2.05, 16.5), (-2.45, 16.75), (-2.78, 17.15), (-2.98, 17.65),
        (-3.08, 18.4), (-3.2, 19.3), (-3.42, 19.92), (-3.8, 20.2), (-4.25, 20.22), (-4.65, 20.0),
        (-5.02, 19.6), (-5.3, 19.0), (-5.48, 18.2), (-5.53, 17.2), (-5.45, 16.2), (-5.28, 15.4),
        (-5.05, 14.6), (-4.75, 13.7), (-4.55, 12.8), (-4.53, 11.9), (-4.75, 11.1), (-5.15, 10.25),
        (-5.6, 9.4), (-6.05, 8.5), (-6.42, 7.6), (-6.68, 6.6), (-6.84, 5.6), (-6.8, 4.8),
        (-6.55, 4.1), (-6.1, 3.2), (-5.6, 2.45), (-5.0, 1.85), (-4.2, 1.25), (-3.3, 0.68),
        (-2.3, 0.28), (-1.2, 0.07)],
    "Foundation": [
        (1.22, 14.45, "c"), (-1.22, 14.45, "c"), (-1.22, 16.4, "c"), (-1.93, 16.46), (-2.15, 16.51), (-2.39, 16.69), (-2.58, 16.93),
        (-2.74, 17.19), (-2.82, 17.39), (-3.02, 18.2), (-3.07, 18.89), (-3.2, 19.32), (-3.37, 19.66), (-3.75, 20.05),
        (-3.94, 20.13), (-4.07, 20.12), (-4.2, 20.06), (-4.71, 19.74), (-5.09, 19.35), (-5.32, 18.88), (-5.49, 18.37),
        (-5.59, 17.85), (-5.68, 16.77), (-5.59, 15.92), (-5.48, 15.32), (-5.3, 14.58), (-4.79, 12.85), (-4.7, 12.4),
        (-4.67, 12.01), (-4.69, 10.66), (-4.8, 10.06), (-4.88, 9.77), (-5.77, 7.79), (-6.28, 6.48), (-6.46, 5.83),
        (-6.55, 5.09), (-6.48, 4.17), (-6.31, 3.43), (-6.14, 2.93), (-5.84, 2.33), (-5.49, 1.83), (-4.99, 1.32),
        (-4.3, 0.84), (-3.9, 0.64), (-2.97, 0.35), (-2.29, 0.23), (-0.86, 0.19), (-0.29, 0.07), (0.36, 0.18),
        (1.8, 0.2), (2.47, 0.33), (3.77, 0.69), (4.58, 1.11), (4.93, 1.42), (5.37, 1.88), (5.69, 2.4),
        (5.91, 2.87), (6.1, 3.52), (6.23, 4.36), (6.21, 4.91), (6.05, 5.89), (5.92, 6.4), (5.38, 7.88),
        (5.02, 8.7), (4.56, 9.64), (4.46, 10.01), (4.37, 10.53), (4.38, 10.84), (4.51, 11.34), (5.07, 12.73),
        (5.18, 13.09), (5.28, 13.61), (5.31, 14), (5.31, 14.8), (5.22, 15.32), (5.13, 15.61), (4.9, 16.01),
        (4.5, 16.38), (4.31, 16.49), (4.1, 16.56), (3.82, 16.54), (3.56, 16.39), (3.37, 16.16), (3.28, 15.95),
        (3.17, 15.43), (3.05, 15.08), (2.9, 14.82), (2.62, 14.47), (2.23, 14.27), (1.87, 14.18), (1.65, 14.22)],
    "Manta": [
        (1.25, 13.37, "c"), (-1.25, 13.37, "c"), (-1.25, 15.67, "c"), (-1.86, 15.65), (-2.15, 15.7), (-2.48, 15.89), (-2.74, 16.17),
        (-2.88, 16.44), (-3.16, 17.29), (-3.21, 17.99), (-3.35, 18.9), (-3.52, 19.23), (-3.8, 19.58), (-3.96, 19.68),
        (-4.09, 19.68), (-4.27, 19.57), (-4.69, 19.24), (-4.84, 19.07), (-5.09, 18.68), (-5.37, 18.07), (-5.45, 17.62),
        (-5.46, 16.82), (-5.32, 15.75), (-5.15, 15.09), (-4.86, 14.16), (-4.73, 13.57), (-4.52, 12.84), (-4.47, 12.47),
        (-4.45, 11.75), (-4.53, 10.99), (-4.61, 10.7), (-4.86, 10.16), (-6.02, 7.97), (-6.48, 6.79), (-6.55, 6.5),
        (-6.58, 6.27), (-6.56, 5.08), (-6.45, 4.4), (-6.25, 3.68), (-5.9, 2.85), (-5.73, 2.6), (-5.3, 2.14),
        (-4.9, 1.66), (-4.54, 1.36), (-4.02, 1.03), (-3.43, 0.73), (-2.58, 0.43), (-1.84, 0.27), (-0.97, 0.23),
        (-0.39, 0.09), (-0.18, 0.07), (0.71, 0.23), (1.33, 0.28), (2, 0.42), (2.46, 0.47), (3.25, 0.7),
        (3.51, 0.84), (4.46, 1.46), (4.89, 1.8), (5.34, 2.25), (5.8, 2.86), (6.23, 3.74), (6.36, 4.09),
        (6.49, 4.68), (6.61, 5.52), (6.62, 5.83), (6.56, 6.13), (6.3, 6.92), (5.98, 7.59), (5.32, 8.6),
        (4.94, 9.09), (4.79, 9.34), (4.59, 9.83), (4.5, 10.27), (4.51, 10.49), (4.59, 11.01), (4.73, 11.43),
        (4.93, 11.91), (5.14, 12.56), (5.28, 13.23), (5.31, 13.76), (5.28, 14.3), (5.24, 14.52), (5.12, 14.8),
        (4.89, 15.11), (4.54, 15.42), (4.26, 15.51), (3.97, 15.47), (3.78, 15.35), (3.65, 15.18), (3.18, 13.75),
        (2.97, 13.44), (2.69, 13.16), (2.5, 13.05), (2.28, 13), (1.97, 13.02), (1.77, 13.1), (1.54, 13.29),
        (1.41, 13.48), (1.36, 13.62), (1.32, 13.95)],
    "Tempest": [
        (1.22, 16.9, "c"), (-1.22, 16.9, "c"), (-1.22, 17.4, "c"), (-1.5, 17.34), (-2.06, 16.96), (-2.66, 16.66), (-4.24, 16.02),
        (-4.5, 15.88), (-4.85, 15.57), (-5.28, 15.1), (-5.43, 14.84), (-5.62, 14.34), (-5.66, 14.04), (-5.65, 13.72),
        (-5.45, 12.93), (-5.33, 12.57), (-4.66, 11), (-4.48, 10.35), (-4.35, 9.68), (-4.34, 8.88), (-4.36, 8.57),
        (-4.47, 8.05), (-4.7, 7.33), (-5.02, 6.58), (-6.52, 3.67), (-6.9, 2.7), (-7.12, 1.9), (-7.13, 1.62),
        (-7.06, 1.25), (-6.97, 0.96), (-6.83, 0.69), (-6.68, 0.52), (-6.44, 0.32), (-6.18, 0.18), (-5.82, 0.05),
        (-5.44, 0), (-4.73, 0.01), (-3.67, 0.2), (-2.51, 0.51), (-1.84, 0.64), (-0.14, 1.22), (1.29, 1.83),
        (1.89, 2.15), (4.72, 3.51), (5.24, 3.82), (5.49, 4), (5.81, 4.35), (6, 4.67), (6.09, 5.04),
        (6.09, 5.27), (6.04, 5.49), (5.8, 6.28), (5.57, 6.74), (5.07, 7.9), (4.82, 8.6), (4.69, 9.36),
        (4.68, 10.47), (4.81, 11.31), (5.1, 12.48), (5.64, 14.03), (6.11, 15.29), (6.39, 16.15), (6.52, 16.66),
        (6.58, 17.04), (6.58, 17.43), (6.53, 17.74), (6.43, 18.1), (6.22, 18.41), (5.86, 18.69), (5.44, 18.86),
        (5.08, 18.86), (4.73, 18.73), (4.35, 18.48), (3.95, 18.09), (3.45, 17.49), (3.16, 17.22), (2.97, 17.11),
        (2.63, 16.97), (2.34, 16.94), (1.75, 17.06), (1.31, 17.29), (1.25, 17.19)],
    "Crestwave": [
        (1.2, 13.62, "c"), (-1.2, 13.62, "c"), (-1.2, 13.97, "c"), (-1.83, 13.99), (-2.35, 14.12), (-3.15, 14.54), (-3.58, 14.84),
        (-4.3, 15.58), (-4.55, 15.97), (-4.81, 16.5), (-4.87, 16.7), (-4.87, 17.11), (-4.76, 17.9), (-4.78, 18.04),
        (-4.88, 18.23), (-5.48, 18.86), (-5.72, 19.01), (-5.85, 19.01), (-5.98, 18.96), (-6.38, 18.59), (-6.63, 18.21),
        (-6.73, 17.84), (-6.74, 17.45), (-6.64, 16.76), (-6.23, 15.39), (-5.09, 12.23), (-4.85, 11.35), (-4.78, 10.98),
        (-4.67, 10.13), (-4.66, 8.77), (-4.68, 8.38), (-4.79, 7.62), (-5.04, 6.76), (-5.41, 6.1), (-6.1, 5.35),
        (-6.25, 5.09), (-6.38, 4.74), (-6.56, 4.08), (-6.58, 3.61), (-6.53, 3.23), (-6.32, 2.66), (-5.96, 2.08),
        (-5.48, 1.56), (-4.99, 1.18), (-4.4, 0.85), (-3.85, 0.63), (-2.76, 0.33), (-2, 0.21), (-0.31, 0.04),
        (0.52, 0.11), (1.45, 0.21), (2.36, 0.35), (3.09, 0.54), (4, 0.88), (4.52, 1.18), (5.02, 1.54),
        (5.76, 2.26), (5.94, 2.51), (6.25, 3.03), (6.44, 3.51), (6.55, 3.86), (6.62, 4.32), (6.61, 5.36),
        (6.45, 5.94), (6.25, 6.91), (5.77, 7.83), (5.57, 8.31), (4.98, 9.03), (4.87, 9.23), (4.71, 9.64),
        (4.32, 10.21), (4.2, 10.48), (4.15, 10.71), (4.08, 11.31), (4.11, 11.61), (4.31, 12.25), (4.83, 13.33),
        (5.02, 13.98), (5.04, 14.21), (5.03, 14.42), (4.86, 14.83), (4.73, 15), (4.47, 15.15), (4.25, 15.19),
        (3.96, 15.14), (3.76, 15.05), (3.64, 14.96), (3.53, 14.78), (3.43, 14.42), (3.32, 14.23), (3.05, 13.95),
        (2.8, 13.77), (2.3, 13.58), (1.93, 13.5), (1.47, 13.51)],
}

# sculpted contours: (side, origin mm, direction toward the edge, depth mm)
CONTOURS = {
    "Skyline": [("top", (-95, 110), (-1, -0.25), 12), ("back", (-88, 250), (-0.92, 0.39), 10)],
    "Velvet": [("top", (-108, 120), (-1, -0.25), 11), ("back", (-100, 290), (-0.92, 0.39), 9)],
    "Foundation": [("top", (-108, 120), (-1, -0.25), 11), ("back", (-100, 290), (-0.92, 0.39), 9)],
    "Manta": [("top", (-112, 112), (-1, -0.25), 10), ("back", (-104, 280), (-0.92, 0.39), 9)],
}
EDGES = {"Skyline": 6.0, "Velvet": 7.0, "Foundation": 7.0, "Manta": 8.0}


def _apply_refinements():
    for d in INSTRUMENTS:
        pts = OUTLINES_IN.get(d["id"])
        if pts:
            d["outline"] = [(p[0] * 25.4, p[1] * 25.4) for p in pts]
            d["corners"] = [i for i, p in enumerate(pts) if len(p) > 2]
        if d["id"] in CONTOURS:
            d["contours"] = CONTOURS[d["id"]]
        if d["id"] in EDGES:
            d["edge"] = EDGES[d["id"]]


_apply_refinements()

BY_ID = {d["id"]: d for d in INSTRUMENTS}


# ---------------------------------------------------------------------------
# headstocks (mm, origin at the nut centre, +Y away from the body)
# ---------------------------------------------------------------------------
def headstock(kind, nut_w):
    h = nut_w / 2
    if kind == "six":
        # traced from a photo: straight tuner edge, small lobe and hook on the treble side
        pts = [(h, 0), (h, 6.7), (h + 1, 16.4), (28.3, 28.7), (36.9, 38.5), (43.1, 45.9), (43.1, 53.3),
               (40.7, 65.5), (37.1, 77.8), (33.5, 90.1), (31, 102.4), (29.8, 114.7), (32.4, 129.1),
               (39.8, 133.4), (48.5, 142.2), (52.3, 154.6), (51.1, 167), (43.7, 178.2), (32.6, 183.8),
               (20.2, 184.2), (10.3, 180.4), (4, 174.1), (0.8, 164.1), (-1, 151.7), (-5.9, 126.8),
               (-10.9, 102.1), (-17.1, 77.4), (-22, 65.1), (-26.9, 52.8), (-33, 40.5), (-37.9, 30.7),
               (-39.2, 24.6), (-36.7, 16), (-h - 1, 6.4), (-h, 0)]
        posts = [(-23.2, 40.6, "L"), (-16.6, 63.1, "L"), (-9.7, 86.8, "L"), (-2.8, 110, "L"),
                 (4, 133.1, "L"), (11.4, 157.2, "L")]
    elif kind == "tele":
        # traced from a photo: plain paddle with a rounded tip, tuners along the bass edge
        pts = [(h, 0), (h, 9), (h + 0.5, 21.6), (h + 1.2, 36.6), (h + 2.2, 48.8), (h + 4.2, 64.1),
               (h + 8, 78.9), (h + 13, 93.9), (h + 18, 109), (h + 21, 124), (h + 20.6, 139),
               (h + 16.8, 154.3), (h + 10.5, 164.4), (h + 0.5, 171.9), (10.3, 172.8), (0.2, 166.8),
               (-6, 154.1), (-11.3, 139), (-23.5, 91.7), (-26.3, 78.9), (-30.3, 54.1), (-h - 11.3, 39.1),
               (-h - 10.8, 21.6), (-h - 6.3, 11.5), (-h, 0)]
        posts = [(-18.6 + 6.5 * i, 37.8 + 22.5 * i, "L") for i in range(6)]
    elif kind == "gibson":
        pts = [(h, 0), (h + 5, 14), (h + 14, 36), (h + 21, 70), (h + 25, 110), (h + 27, 150),
               (h + 29, 176), (18, 186), (0, 194), (-18, 186), (-h - 29, 176), (-h - 27, 150),
               (-h - 25, 110), (-h - 21, 70), (-h - 14, 36), (-h - 5, 14), (-h, 0)]
        posts = [(-29, 58, "L"), (-31, 100, "L"), (-32, 142, "L"),
                 (32, 142, "R"), (31, 100, "R"), (29, 58, "R")]
        return polygon(pts, corners=(0, 6, 8, 10, len(pts) - 1), step=4.0), posts
    elif kind == "arrow":
        pts = [(h, 0), (h + 7, 20), (h + 18, 56), (h + 22, 100), (h + 18, 140), (h + 6, 172),
               (0, 196), (-h - 6, 172), (-h - 18, 140), (-h - 22, 100), (-h - 18, 56),
               (-h - 7, 20), (-h, 0)]
        posts = [(-28, 52, "L"), (-30, 92, "L"), (-26, 132, "L"),
                 (26, 132, "R"), (30, 92, "R"), (28, 52, "R")]
    elif kind == "bass4":
        # classic bass head: tuner edge slanting in toward the tip, scroll on the treble side
        pts = [(h, 0), (h + 3, 13), (31, 25), (41, 42), (45, 58), (44, 80), (38, 103), (31, 126),
               (29, 148), (31, 162), (37, 173), (43, 183), (44.5, 195), (40, 207), (30, 216),
               (17, 221), (4, 221), (-6, 218), (-14, 209), (-19.5, 188), (-26.5, 152),
               (-33.5, 111), (-40.5, 69), (-46, 36), (-42, 21), (-31, 9), (-h, 0)]
        posts = [(-23.5 + 9.3 * i, 35 + 45 * i, "L") for i in range(4)]
    elif kind == "three_one":
        pts = [(h, 0), (h + 8, 28), (h + 22, 76), (h + 26, 120), (h + 24, 154), (h + 14, 178),
               (6, 190), (-14, 190), (-34, 180), (-46, 152), (-50, 110), (-46, 62), (-32, 22),
               (-h, 0)]
        posts = [(-24, 54, "L"), (-26, 104, "L"), (-24, 152, "L"), (26, 120, "R")]
    elif kind == "reverse4":
        pts = [(h, 0), (h + 6, 30), (h + 14, 80), (h + 20, 140), (h + 24, 200), (h + 22, 236),
               (h + 10, 252), (-6, 250), (-16, 232), (-20, 190), (-22, 130), (-22, 60),
               (-h, 0)]
        posts = [(14 - 1.5 * i, 56 + 54 * i, "R") for i in range(4)]
    else:  # two_two
        pts = [(h, 0), (h + 8, 30), (h + 20, 72), (h + 32, 124), (h + 40, 168), (h + 42, 196),
               (h + 30, 208), (10, 216), (-20, 214), (-42, 204), (-52, 182), (-52, 140),
               (-44, 86), (-32, 36), (-h, 0)]
        posts = [(-28, 74, "L"), (-31, 150, "L"), (32, 156, "R"), (30, 84, "R")]
        return polygon(pts, corners=(0, 5, len(pts) - 1), step=4.0), posts
    return polygon(pts, corners=(0, len(pts) - 1), step=4.0), posts


# ---------------------------------------------------------------------------
# instrument
# ---------------------------------------------------------------------------
class Build:
    def __init__(self, d):
        self.d = d
        self.parts = {}

    def add(self, key, mesh):
        if mesh is None:
            return
        if isinstance(mesh, (list, tuple)):
            for m in mesh:
                self.add(key, m)
            return
        self.parts.setdefault(key, []).append(mesh)

    def merged(self):
        return [(k, Mesh.merge(v)) for k, v in self.parts.items()]


def fret_y(d, n):
    """Distance from the nut to fret n (mm)."""
    return d["scale"] * (1 - 2 ** (-n / 12))


def build(d):
    """-> (Build, info) for one instrument, coordinates in metres."""
    from shapely.geometry import Polygon, box as sbox
    b = Build(d)
    bass = d["kind"] == "Bass"
    ns = d.get("strings", 6)
    T_ = d["thick"]
    body = polygon(d["outline"], d.get("corners", ()))
    uv = UV(body)
    saddle = d["saddle_y"]
    nut_y = saddle + d["scale"]
    nfr = d["frets"]
    last = nut_y - fret_y(d, nfr)
    fb_end = last - (9 if bass else 7)
    nut_w = d["nut"]
    end_w = d.get("neck_end_w", 56.0)

    def neck_w(y):
        return nut_w + (end_w - nut_w) * (nut_y - y) / (nut_y - last)

    carve_h = d.get("carve", 0)
    z_fb = T_ + d["fb_h"]
    fb_t = 6.0 if bass else 5.5
    z_neck_top = z_fb - fb_t

    # ---- body
    edge = d["edge"]
    arc = [(edge * (1 - math.cos(a)), edge * (1 - math.sin(a)))
           for a in np.linspace(0, math.pi / 2, 3)]          # inset, dz from wall to cap
    bottom = arc
    if d.get("bevel"):
        bw, bh = d["bevel"]
        top = [(0.0, bh + 1.5), (0.6, bh + 0.2), (bw * 0.5, bh * 0.45), (bw, 0.0)]
    else:
        top = arc
    carve = None
    if carve_h:
        mask_poly = body.buffer(-edge)

        def carve(x, y, P=mask_poly):
            from shapely.geometry import Point
            dist = np.array([P.exterior.distance(Point(a, c)) for a, c in zip(x, y)])
            t = np.clip((dist - 8) / 70.0, 0, 1)
            return carve_h * (t * t * (3 - 2 * t))
    binding = d.get("binding")

    def keys(i, z_lo, z_hi):
        if binding and z_lo >= T_ - 3.2:
            return "Binding"
        return "Body"
    ctop = cbot = None
    for side, o, u, depth in d.get("contours", []):
        f = bevel(o, u, depth, sign=-1.0 if side == "top" else 1.0)
        if side == "top":
            ctop = f if ctop is None else (lambda a, c, f1=ctop, f2=f: f1(a, c) + f2(a, c))
        else:
            cbot = f if cbot is None else (lambda a, c, f1=cbot, f2=f: f1(a, c) + f2(a, c))
    parts = slab(body, 0, T_, bottom, top, n=128, keys=keys, carve=carve, uv=uv,
                 cap_keys=("Body", "Top" if carve_h else "Body"),
                 contour_top=ctop, contour_bottom=cbot)
    for k, m in parts.items():
        b.add(k, m)

    def surface(x, y):
        z = T_
        if carve_h:
            z += float(carve(np.array([x]), np.array([y]))[0])
        if ctop is not None:
            z += float(ctop(np.array([float(x)]), np.array([float(y)]))[0])
        return z

    # ---- neck: shaft, heel, fretboard, frets, inlays, nut
    notch = d["notch_y"]
    heel0 = notch - 72
    secs = []
    ys = list(np.linspace(nut_y + 2, notch - 2, 16))
    for y in ys:
        w = neck_w(y) / 2
        depth = (16.5 if not bass else 18) + 2.5 * (nut_y - y) / (nut_y - last)
        ring = []
        for a in np.linspace(0, math.pi, 13):
            ring.append((w * math.cos(a) * 0.999, y, z_neck_top - depth * math.sin(a) ** 0.8))
        ring += [(-w, y, z_neck_top), (w, y, z_neck_top)]
        secs.append(ring)
    b.add("Neck", loft(secs))
    w_heel = neck_w(notch) - 0.5
    b.add("Neck", box((0, (heel0 + notch) / 2, (z_neck_top + T_ - 17) / 2),
                      (w_heel, notch - heel0, z_neck_top - (T_ - 17))))
    bind = d.get("board_binding")
    bw = 1.6 if bind else 0.0
    fb = Polygon([(nut_w / 2 - bw, nut_y), (-nut_w / 2 + bw, nut_y),
                  (-neck_w(fb_end) / 2 + bw, fb_end), (neck_w(fb_end) / 2 - bw, fb_end)])
    b.add("Board", flat(fb, z_neck_top, z_fb, r_top=0.6, n=40))
    if bind:
        for s in (1, -1):
            strip = Polygon([(s * nut_w / 2, nut_y), (s * (nut_w / 2 - bw), nut_y),
                             (s * (neck_w(fb_end) / 2 - bw), fb_end), (s * neck_w(fb_end) / 2, fb_end)])
            b.add("Binding", flat(strip.buffer(0), z_neck_top, z_fb, n=8))
    for n in range(1, nfr + 1):
        y = nut_y - fret_y(d, n)
        b.add("Frets", box((0, y, z_fb + 0.45), (neck_w(y) - 0.6, 2.3, 1.5)))
    marks = [3, 5, 7, 9, 12, 15, 17, 19, 21]
    style = d.get("inlays", "dots")
    for n in [m for m in marks if m <= nfr]:
        ya = nut_y - fret_y(d, n - 1)
        yb = nut_y - fret_y(d, n)
        yc = (ya + yb) / 2
        span = ya - yb
        w = neck_w(yc)
        if style == "trapezoid":
            t = 0.5 + 0.5 * min(1, n / 12)
            q = Polygon([(-w * 0.36, yc - span * 0.22), (w * 0.36, yc - span * 0.22),
                         (w * 0.40 * t + w * 0.12, yc + span * 0.22),
                         (-(w * 0.40 * t + w * 0.12), yc + span * 0.22)])
            b.add("Inlay", flat(q, z_fb - 0.2, z_fb + 0.15, n=8))
        elif style == "triangle":
            q = Polygon([(w * 0.42, yc - span * 0.3), (-w * 0.42, yc - span * 0.3),
                         (w * 0.42, yc + span * 0.3)])
            b.add("Inlay", flat(q, z_fb - 0.2, z_fb + 0.15, n=6))
        else:
            r = 3.4 if bass else 3.0
            offs = [-w * 0.22, w * 0.22] if n == 12 else [0.0]
            for ox in offs:
                b.add("Inlay", cyl((ox, yc, z_fb), r, 0.4, segs=12))
    b.add("Nut", box((0, nut_y + 1.6, z_fb - 1.2), (nut_w, 3.4, fb_t + 3.4)))

    # ---- headstock and tuners
    hpoly, posts = headstock(d["head"], nut_w)
    ang = math.radians(d.get("head_angle", 0))
    th = 15.0 if bass else 14.0
    z_face = z_neck_top - (1.0 if not ang else 0.0)
    Hm = chain(T(0, nut_y * MM, z_neck_top * MM), Rx(-ang), T(0, 3.4 * MM, 0))
    hs = flat(hpoly, -th - (z_neck_top - z_face), -(z_neck_top - z_face), r_top=1.5)
    b.add("Head" if "Head" in d["palette"] else "Neck", hs.transformed(Hm))
    face = -(z_neck_top - z_face)

    def H(p):
        p = np.asarray(p, float) * MM
        return (Hm[:3, :3] @ p + Hm[:3, 3]) / MM

    post_r = 4.6 if bass else 3.0
    post_h = 14.0 if bass else 9.0
    head_pts = []
    def edge_at(py, side):
        """x of the headstock edge level with a tuner post."""
        from shapely.geometry import LineString
        cut = hpoly.intersection(LineString([(-500, py), (500, py)]))
        x0, _, x1, _ = cut.bounds
        return x0 if side == "L" else x1

    for px, py, side in posts:
        c0 = H((px, py, face))
        n_ax = Hm[:3, 2]
        b.add("Hardware", cyl(c0 + n_ax * (post_h / 2), post_r, post_h, axis=n_ax, segs=10))
        b.add("Hardware", cyl(c0 + n_ax * 1.0, post_r + 2.4, 2.0, axis=n_ax, segs=10))
        sx = -1 if side == "L" else 1
        edge_x = edge_at(py, side)
        back = face - th
        hous = H((px, py, back - 5))
        hs_size = (11, 13, 10) if not bass else (16, 18, 10)
        b.add("Hardware", box((0, 0, 0), hs_size).transformed(chain(T(*(hous * MM)), Rx(-ang))))
        tip = H((edge_x + sx * (14 if not bass else 20), py, back - 5))
        b.add("Hardware", tube_between(hous * MM, tip * MM, (1.6 if not bass else 2.4) * MM,
                                       segs=6, caps=False))
        kr = (6.5, 9.0, 2.6) if not bass else (9.0, 14.0, 3.2)
        key = ellipsoid((0, 0, 0), kr).transformed(
            chain(T(*(tip * MM)), Rx(-ang), T(sx * kr[0] * 0.8 * MM, 0, 0)))
        b.add("Knob" if bass else "Hardware", key)
        head_pts.append(c0 + n_ax * (post_h * 0.55))

    # ---- strings
    z_nut_s = z_fb + 1.7
    z_br_s = z_fb + (4.6 if bass else 3.6)
    sp_nut = (nut_w - (8 if bass else 7))
    sp_br = 57.0 if bass else 52.0
    sr = [0.55, 0.48, 0.42, 0.36] if bass else [0.42, 0.37, 0.32, 0.28, 0.24, 0.21]
    string_pts = []
    for i in range(ns):
        f = i / (ns - 1) - 0.5
        a = np.array([f * sp_br, saddle, z_br_s])
        nn = np.array([f * sp_nut, nut_y, z_nut_s])
        string_pts.append((a, nn))
        b.add("Strings", tube_between(a * MM, nn * MM, sr[i] * MM, segs=5, caps=False))
        b.add("Strings", tube_between(nn * MM, head_pts[i] * MM, sr[i] * MM, segs=5, caps=False))

    # ---- pickguard
    neck_cut = sbox(-neck_w(notch) / 2 - 1.5, heel0 - 30, neck_w(notch) / 2 + 1.5, 900)
    g = None
    if d.get("guard"):
        gd = d["guard"]
        g = body.buffer(-gd["inset"]).intersection(Polygon(gd["region"]))
        g = largest(g.difference(neck_cut))
        for cx, cy, w, h in gd.get("cut", []):
            g = largest(g.difference(sbox(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)))
        g = soften(g, 3.0)
    elif d.get("guard_poly"):
        g = soften(largest(body.buffer(-8).intersection(polygon(d["guard_poly"]))
                           .difference(neck_cut)), 3.0)
    z_guard = T_
    if g is not None:
        gm = flat(g, T_, T_ + 2.3, r_top=0.8, uv=uv)
        b.add("Guard", gm)
        z_guard = T_ + 2.3
    if d.get("raised_guard"):
        rg = polygon(d["raised_guard"])
        cx, cy = rg.centroid.x, rg.centroid.y
        zr = surface(cx, cy) + 4.0
        b.add("Guard", flat(rg, zr, zr + 1.8, r_top=0.6, uv=uv))
        b.add("Hardware", rbox((cx - 8, cy - 40, (surface(cx, cy) + zr) / 2), (6, 6, zr - surface(cx, cy)), 1))

    # ---- pickups
    cover_key = "Cover" if d.get("pickup_color") == "cover" else (
        "Hardware" if d.get("pickup_color") == "chrome" else "Pickup")
    for kind, off, dx, angd in d["pickups"]:
        y = saddle + off
        zb = surface(dx, y) if g is None else max(z_guard, surface(dx, y))
        add_pickup(b, kind, dx, y, zb, angd, ns, cover_key, d.get("rings"), bass)

    # ---- bridge
    add_bridge(b, d, saddle, z_br_s, surface, string_pts, z_guard, bass)

    # ---- controls
    for kind, x, y in d.get("knobs", []):
        add_knob(b, kind, x, y, (z_guard if g is not None and g.contains(_pt(x, y)) else surface(x, y)))
    if d.get("switch"):
        kind, x, y = d["switch"]
        zs = z_guard if g is not None and g.contains(_pt(x, y)) else surface(x, y)
        add_switch(b, kind, x, y, zs)
    if d.get("control_plate"):
        cp = d["control_plate"]
        cx, cy = cp["c"]
        plate = rrect(cx, cy, cp["w"], cp["h"], cp["w"] / 2 - 1, cp["ang"])
        b.add("Hardware", flat(plate, T_, T_ + 1.6, r_top=0.6))
        a = math.radians(cp["ang"])
        along = np.array([-math.sin(a), math.cos(a)])
        for (t,) in cp["knobs"]:
            x, y = np.array([cx, cy]) + along * t
            add_knob(b, "dome", x, y, T_ + 1.6)
        if cp.get("switch"):
            x, y = np.array([cx, cy]) + along * cp["switch"][0]
            add_switch(b, "tele", x, y, T_ + 1.6)
    if d.get("round_plate"):
        rp = d["round_plate"]
        from shapely.geometry import Point
        b.add("Hardware", flat(Point(*rp["c"]).buffer(rp["r"], quad_segs=10), T_, T_ + 1.6,
                               r_top=0.6))
        for x, y in rp["knobs"]:
            add_knob(b, "dome", x, y, T_ + 1.6)

    # ---- strap buttons
    bot = min(body.exterior.coords, key=lambda p: p[1])
    b.add("Hardware", lathe_at((bot[0], bot[1] - 4, T_ / 2),
                               [(0, 0), (3.5, 0), (3.5, 3), (2.4, 4), (5, 6), (5, 7.5), (0, 8.5)],
                               axis=(0, -1, 0), segs=12))
    horn = max((p for p in body.exterior.coords if p[0] < -20), key=lambda p: p[1])
    b.add("Hardware", lathe_at((horn[0], horn[1] - 3, T_ / 2),
                               [(0, 0), (3.5, 0), (3.5, 3), (2.4, 4), (5, 6), (5, 7.5), (0, 8.5)],
                               axis=(0, 1, 0), segs=12))

    xb0, yb0, xb1, yb1 = body.bounds
    info = {
        "uv": uv.info(), "body_poly": [list(map(float, p)) for p in body.exterior.coords],
        "nut_y": nut_y, "saddle_y": saddle, "fb_end": fb_end, "thick": T_,
        "body_center": ((xb0 + xb1) / 2, (yb0 + yb1) / 2),
        "head_top": nut_y + max(y for _, y in hpoly.exterior.coords),
        "neck_mid_y": nut_y - fret_y(d, 7), "strum_y": saddle + 70,
        "z_fb": z_fb,
    }
    return b, info


def _pt(x, y):
    from shapely.geometry import Point
    return Point(x, y)


def add_pickup(b, kind, x, y, z, angd, ns, cover_key, ring, bass):
    poles = []
    if kind == "single":
        b.add(cover_key, flat(stadium(x, y, 70, 17.5, angd), z, z + 13, r_top=2.5))
        poles = [(-25 + 10 * i, 0) for i in range(6)]
        pz = z + 13
    elif kind == "tele_neck":
        b.add("Hardware", flat(rrect(x, y, 66, 18, 8, angd), z, z + 12, r_top=2.0))
        pz = None
    elif kind == "humbucker":
        if ring:
            b.add("Binding", flat(rrect(x, y, 92, 50, 6, angd), z, z + 4, r_top=1.0))
            z += 4
        b.add(cover_key, flat(rrect(x, y, 70, 38, 4, angd), z, z + 9, r_top=1.6))
        poles = [(-25 + 10 * i, -9) for i in range(6)]
        pz = z + 9
    elif kind == "open_humbucker":
        for s in (-1, 1):
            b.add("Pickup", flat(stadium(x, y + s * 9.2, 70, 17.5, angd), z, z + 10, r_top=2.0))
        poles = [(-25 + 10 * i, 9.2) for i in range(6)] + [(-25 + 10 * i, -9.2) for i in range(6)]
        pz = z + 10
    elif kind == "jbass":
        b.add("Pickup", flat(stadium(x, y, 94, 20, angd), z, z + 12, r_top=2.5))
        poles = [(-33 + 9.4 * i, 0) for i in range(8)]
        pz = z + 12
    elif kind == "psplit":
        for s, yo in ((-1, 8), (1, -8)):
            b.add("Pickup", flat(stadium(x + s * 25, y + yo, 54, 20, 0), z, z + 12, r_top=2.5))
        poles = [(-43 + 13 * i, 8) for i in range(4)] + [(7 + 13 * i, -8) for i in range(4)]
        pz = z + 12
    elif kind == "mm":
        b.add("Pickup", flat(rrect(x, y, 98, 44, 9, angd), z, z + 13, r_top=2.5))
        for s in (-1, 1):
            for i in range(4):
                b.add("Hardware", cyl((x - 28.5 + 19 * i, y + s * 10, z + 13), 4.6, 1.2, segs=12))
        pz = None
    elif kind == "tb_humbucker":
        b.add("Hardware", flat(rrect(x, y, 102, 42, 6, angd), z, z + 11, r_top=2.0))
        pz = None
    elif kind == "rk_neck":
        b.add("Pickup", flat(rrect(x, y, 88, 22, 6, 0), z, z + 11, r_top=2.0))
        poles = [(-30 + 20 * i, 0) for i in range(4)]
        pz = z + 11
    if pz is not None:
        a = math.radians(angd)
        for px, py in poles:
            rx = px * math.cos(a) - py * math.sin(a)
            ry = px * math.sin(a) + py * math.cos(a)
            b.add("Hardware", cyl((x + rx, y + ry, pz), 2.4 if not bass else 2.8, 0.9, segs=8))


def add_bridge(b, d, saddle, z_s, surface, strings, z_guard, bass):
    kind = d["bridge"]
    T_ = d["thick"]
    sr = 0.45
    if kind == "trem":
        b.add("Hardware", flat(rrect(0, saddle - 2, 88, 46, 4), T_, T_ + 2.0, r_top=0.6))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle - 4, (T_ + 2 + z_s - sr) / 2),
                                   (9.6, 20, z_s - sr - T_ - 2), 1.2))
        b.add("Hardware", tube_between(np.array([24, saddle - 26, T_ + 2]) * MM,
                                       np.array([24, saddle - 26, T_ + 14]) * MM, 2.2 * MM, 8))
        arm = [(24, saddle - 26, T_ + 14), (38, saddle - 46, T_ + 19), (62, saddle - 76, T_ + 23),
               (88, saddle - 104, T_ + 25)]
        for p, q in zip(arm[:-1], arm[1:]):
            b.add("Hardware", tube_between(np.array(p) * MM, np.array(q) * MM, 2.2 * MM, 8))
        b.add("Knob", ellipsoid(arm[-1], (4.5, 4.5, 4.5)))
    elif kind == "ashtray":
        b.add("Hardware", flat(rrect(0, saddle + 10, 86, 92, 3), T_, T_ + 1.4, r_top=0.4))
        for sx in (-1, 1):
            b.add("Hardware", box((sx * 42.3, saddle + 10, T_ + 6), (1.4, 92, 12)))
        b.add("Hardware", box((0, saddle - 35.3, T_ + 6), (86, 1.4, 12)))
        for i in range(3):
            xa = (strings[2 * i][0][0] + strings[2 * i + 1][0][0]) / 2
            b.add("Hardware", cyl((xa, saddle, z_s - sr - 4.5), 4.5, 17, axis=(1, 0, 0), segs=12))
    elif kind in ("tom_stop", "tom_v"):
        zs = surface(0, saddle)
        for sx in (-1, 1):
            b.add("Hardware", cyl((sx * 37, saddle, (zs + z_s - 6) / 2), 3.0, z_s - 6 - zs, segs=10))
        b.add("Hardware", rbox((0, saddle, z_s - sr - 3.5), (80, 9, 5), 1.2))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle, z_s - sr - 0.6), (3.2, 8, 1.6), 0.5))
        if kind == "tom_stop":
            yt = saddle - 38
            zt = surface(0, yt)
            for sx in (-1, 1):
                b.add("Hardware", cyl((sx * 41, yt, zt + 4), 4.2, 8, segs=10))
            b.add("Hardware", cyl((0, yt, zt + 9), 5.6, 86, axis=(1, 0, 0), segs=14, bevel=1.5))
        else:
            from shapely.geometry import Polygon
            vp = soften(Polygon([(-34, saddle - 28), (34, saddle - 28), (12, saddle - 88),
                                 (-12, saddle - 88)]), 3)
            b.add("Hardware", flat(vp, z_guard, z_guard + 1.6, r_top=0.6))
    elif kind == "fender_bass":
        b.add("Hardware", flat(rrect(0, saddle - 20, 72, 68, 3), T_, T_ + 2.0, r_top=0.5))
        b.add("Hardware", box((0, saddle - 53, T_ + 6.5), (72, 2.0, 13)))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle - 2, (T_ + 2 + z_s - 0.6) / 2),
                                   (11, 22, z_s - 0.6 - T_ - 2), 1.5))
    elif kind == "mm_bridge":
        b.add("Hardware", flat(rrect(0, saddle + 6, 82, 80, 14), T_, T_ + 2.5, r_top=0.8))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle - 2, (T_ + 2.5 + z_s - 0.6) / 2),
                                   (11, 18, z_s - 0.6 - T_ - 2.5), 1.5))
        for sx in (-1, 1):
            b.add("Knob", cyl((sx * 34, saddle + 16, T_ + 6), 4.5, 7, segs=12))
    elif kind == "tb_bridge":
        b.add("Hardware", rbox((0, saddle, (T_ + z_s) / 2), (92, 24, z_s - T_), 3))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle, z_s - 0.5), (8, 12, 2.4), 0.8))
    elif kind == "rk_bridge":
        b.add("Hardware", flat(rrect(0, saddle - 6, 120, 64, 12), T_, T_ + 11, r_top=2.5))
        b.add("Hardware", rbox((0, saddle + 4, (T_ + z_s) / 2), (84, 20, z_s - T_), 2))
        b.add("Hardware", flat(rrect(0, saddle - 64, 74, 46, 16), T_, T_ + 3, r_top=1))


def add_knob(b, kind, x, y, z):
    if kind == "skirt":
        prof = [(0, 0), (12.5, 0), (12.5, 2.5), (10.5, 4), (9.5, 17), (8.5, 18.5), (0, 19)]
        key = "Knob"
    elif kind == "tophat":
        prof = [(0, 0), (12.5, 0), (12.5, 3), (9.6, 4), (9.6, 15), (8.6, 17.5), (0, 18.5)]
        key = "Knob"
    else:  # dome chrome
        prof = [(0, 0), (9.5, 0), (9.5, 13), (8, 15.5), (0, 16.5)]
        key = "Hardware"
    b.add(key, lathe_at((x, y, z), prof, segs=14))


def add_switch(b, kind, x, y, z):
    if kind == "toggle":
        b.add("Hardware", cyl((x, y, z + 2), 6.5, 4, segs=12))
        b.add("Hardware", tube_between(np.array([x, y, z + 3]) * MM,
                                       np.array([x - 5, y + 8, z + 20]) * MM, 1.4 * MM, 8))
        b.add("Knob", ellipsoid((x - 5.6, y + 9, z + 22.5), (3.6, 3.6, 4.6)))
    elif kind == "blade":
        b.add("Knob", rbox((x, y, z + 6), (5, 9, 10), 1.5))
    else:
        b.add("Knob", cyl((x, y, z + 6), 4.2, 12, segs=12))


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def build_all():
    out = []
    guitars = [d for d in INSTRUMENTS if d["kind"] == "Guitar"]
    basses = [d for d in INSTRUMENTS if d["kind"] == "Bass"]
    for row, group in ((0, guitars), (1, basses)):
        for i, d in enumerate(group):
            b, info = build(d)
            b.x = (i - (len(group) - 1) / 2) * SPACING
            b.z = -row * 0.35
            out.append((d, b, info))
    return out


def parts_of(built, place=True):
    parts = []
    for d, b, _ in built:
        M = T(b.x, 0, b.z) if place else np.eye(4)
        for key, m in b.merged():
            name = "%s_%s" % (d["id"], key)
            parts.append((name, name, m.transformed(M)))
    return parts


def meta(d, b, info, parts):
    """Attachment points relative to the body part's bounding-box centre (studs)."""
    prim = "%s_Body" % d["id"]
    m = next(mm for name, _, mm in parts if name == prim)
    lo, hi = m.bounds()
    c = (lo + hi) / 2
    cx, cy = info["body_center"]
    org = np.array([b.x, 0, b.z])

    def rel(x_mm, y_mm, z_mm):
        return [round(float(v), 5) for v in ((org + np.array([x_mm, y_mm, z_mm]) * MM) - c) / STUD]
    return {
        "primary": prim,
        "wear": rel(cx * 0.4, cy, 0.0),
        "neck": rel(0, info["neck_mid_y"], info["z_fb"]),
        "strum": rel(0, info["strum_y"], info["z_fb"]),
        "length_studs": round((info["head_top"] - min(p[1] for p in info["body_poly"])) * MM / STUD, 3),
    }


def lua_color(c):
    return "Color3.fromRGB(%d, %d, %d)" % tuple(c)


def write_setup(path, built, metas):
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "..", "roblox", "BandInstrumentsSetup.lua"),
               encoding="utf-8").read()
    L = ["local INSTRUMENTS = {"]
    for d, _, _ in built:
        mt = metas[d["id"]]
        L.append("\t%s = {" % d["id"])
        L.append("\t\tkind = %s, name = %s, nameEn = %s, style = %s," % (
            json.dumps(d["kind"]), json.dumps(d["name"], ensure_ascii=False),
            json.dumps(d["nameEn"]), json.dumps(d["style"], ensure_ascii=False)))
        L.append("\t\tprimary = %s," % json.dumps(mt["primary"]))
        for k in ("wear", "neck", "strum"):
            L.append("\t\t%s = Vector3.new(%.5f, %.5f, %.5f)," % ((k,) + tuple(mt[k])))
        L.append("\t\tpalette = {")
        for key, p in d["palette"].items():
            extra = ", Glow = true" if p.get("glow") else ""
            extra += ", Textured = true" if p.get("texture") else ""
            L.append("\t\t\t%s = { Color = %s, Material = %s, Reflectance = %.2f%s }," % (
                key, lua_color(p["color"]), json.dumps(p["material"]), p["reflectance"], extra))
        L.append("\t\t},")
        L.append("\t},")
    L.append("}")
    marker = "local INSTRUMENTS = {} -- (filled in by instruments.py)"
    assert marker in tpl
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(tpl.replace(marker, "\n".join(L)))


MODULE_HEADER = """--[[
	BandInstruments - Beat Drummer のギター (%(g)d 本)・ベース (%(b)d 本) をキャラクターに構えさせる
	※ このファイルは generator/instruments.py が作っています。

	前提: export/instruments/BandInstruments_Setup.lua を実行してできたテンプレート
	      (Folder "BandInstruments" の中の Model "Guitar_<ID>" / "Bass_<ID>") を ReplicatedStorage などに入れておく。

	使い方:
		local BandInstruments = require(ReplicatedStorage.BeatDrummer.BandInstruments)
		local template = BandInstruments.template(ReplicatedStorage.BandInstruments, "Manta")

		-- サーバー: バンドのメンバー (またはプレイヤー) に構えさせる (全員に見える)
		BandInstruments.attach(character, template)
		BandInstruments.attach(character, template, { tilt = 22, offset = Vector3.new(0.3, -0.1, 0), scale = 0.9 })
		BandInstruments.detach(character)

		-- クライアント: ノーツに合わせて (見た目だけ)
		BandInstruments.strum(character, 1.0)    -- 楽器が少し揺れて弦が光る

	向き:
		体の正面のアタッチメント (R15 は LowerTorso の WaistFrontAttachment、R6 は Torso の BodyFrontAttachment)
		に楽器の Wear を合わせ、ネックがキャラクターの左へ伸びるように構えます。
		tilt (ネックを上げる角度、度)、offset (アタッチメントからのずれ、studs)、scale で調整してください。
		左手・右手の位置は楽器の Attachment "Neck" / "Strum" で取れます (腕の IK やアニメーションの目標に)。
]]

local TweenService = game:GetService("TweenService")

local BandInstruments = {}
"""

MODULE_LOGIC = """
-- 構えたときの角度・位置・大きさ。ゲームのキャラクターに合わせて調整
BandInstruments.Defaults = {
	tilt = 20, -- ネックを上げる角度 (度)
	offset = Vector3.new(0.3, 0, 0), -- R15: 腰の正面から右へ 0.3 studs
	offsetR6 = Vector3.new(0.3, -0.6, 0),
	scale = 1,
}

function BandInstruments.info(id: string)
	for _, item in ipairs(BandInstruments.List) do
		if item.id == id then
			return item
		end
	end
	return nil
end

function BandInstruments.template(folder: Instance, id: string): Model?
	local info = BandInstruments.info(id)
	local m = info and folder:FindFirstChild(info.kind .. "_" .. id)
	return if m and m:IsA("Model") then m else nil
end

function BandInstruments.get(character: Model): Model?
	local m = character:FindFirstChild("BandInstrument")
	return if m and m:IsA("Model") then m else nil
end

function BandInstruments.detach(character: Model)
	local m = BandInstruments.get(character)
	if m then
		m:Destroy()
	end
end

local function mount(character: Model): (BasePart?, CFrame, boolean)
	local lower = character:FindFirstChild("LowerTorso")
	if lower and lower:IsA("BasePart") then
		local a = lower:FindFirstChild("WaistFrontAttachment")
		return lower, if a and a:IsA("Attachment") then a.CFrame else CFrame.new(0, 0, -lower.Size.Z / 2), false
	end
	local torso = character:FindFirstChild("Torso") or character:FindFirstChild("UpperTorso")
	if torso and torso:IsA("BasePart") then
		local a = torso:FindFirstChild("BodyFrontAttachment")
		return torso, if a and a:IsA("Attachment") then a.CFrame else CFrame.new(0, 0, -torso.Size.Z / 2), true
	end
	return nil, CFrame.new(), false
end

-- 楽器を構えさせる。戻り値は楽器の Model
function BandInstruments.attach(character: Model, template: Model, options: { [string]: any }?)
	assert(template and template.PrimaryPart, "BandInstruments.attach: テンプレートに PrimaryPart がありません")
	local o = options or {}
	local part, base, r6 = mount(character)
	if not part then
		return nil
	end
	BandInstruments.detach(character)
	local inst = template:Clone()
	inst.Name = "BandInstrument"
	local scale = o.scale or BandInstruments.Defaults.scale
	if scale ~= 1 then
		inst:ScaleTo(inst:GetScale() * scale)
	end
	for _, p in ipairs(inst:GetDescendants()) do
		if p:IsA("BasePart") then
			p.Anchored = false
			p.CanCollide = false
			p.CanTouch = false
			p.CanQuery = false
			p.Massless = true
		end
	end
	local prim = inst.PrimaryPart :: BasePart
	local wear = prim:FindFirstChild("Wear") :: Attachment
	local offset = o.offset or (if r6 then BandInstruments.Defaults.offsetR6 else BandInstruments.Defaults.offset)
	local tilt = o.tilt or BandInstruments.Defaults.tilt
	local weld = Instance.new("Weld")
	weld.Name = "InstrumentWear"
	weld.Part0 = part
	weld.Part1 = prim
	weld.C0 = base * CFrame.new(offset) * CFrame.Angles(0, 0, -math.rad(tilt))
	weld.C1 = wear.CFrame
	weld.Parent = prim
	inst:SetAttribute("BaseC0", weld.C0)
	inst.Parent = character
	return inst
end

local tokens = setmetatable({}, { __mode = "k" })

-- ノーツに合わせて弾いた感じを出す (クライアントで呼ぶ)。strength 0〜1
function BandInstruments.strum(target: Instance?, strength: number?)
	local inst = if target and target:IsA("Model") and target:FindFirstChild("BandInstrument")
		then target:FindFirstChild("BandInstrument")
		else target
	if not inst then
		return
	end
	local k = math.clamp(strength or 1, 0, 1)
	local prim = (inst :: Model).PrimaryPart
	local weld = prim and prim:FindFirstChild("InstrumentWear")
	local baseC0 = inst:GetAttribute("BaseC0")
	if weld and weld:IsA("Weld") and typeof(baseC0) == "CFrame" then
		weld.C0 = baseC0 * CFrame.Angles(0, 0, math.rad(1.6 * k)) * CFrame.new(0, -0.025 * k, 0)
		TweenService:Create(weld, TweenInfo.new(0.22, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
			C0 = baseC0,
		}):Play()
	end
	for _, p in ipairs(inst:GetDescendants()) do
		if not (p:IsA("BasePart") and p:GetAttribute("InstrumentGlow")) then
			continue
		end
		local base = p:GetAttribute("BaseColor")
		if typeof(base) ~= "Color3" then
			base = p.Color
			p:SetAttribute("BaseColor", base)
		end
		local baseMat = p:GetAttribute("BaseMaterial")
		if type(baseMat) ~= "string" then
			baseMat = p.Material.Name
			p:SetAttribute("BaseMaterial", baseMat)
		end
		local token = (tokens[p] or 0) + 1
		tokens[p] = token
		p.Material = Enum.Material.Neon
		p.Color = (base :: Color3):Lerp(Color3.new(1, 1, 1), 0.6 * k)
		task.delay(0.08, function()
			if tokens[p] ~= token then
				return
			end
			TweenService:Create(p, TweenInfo.new(0.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
				Color = base,
			}):Play()
			task.delay(0.2, function()
				if tokens[p] == token then
					p.Material = (Enum.Material :: any)[baseMat]
					tokens[p] = nil
				end
			end)
		end)
	end
end

return BandInstruments
"""


def lua_str(x):
    return json.dumps(x, ensure_ascii=False)


def write_module(path):
    g = sum(1 for d in INSTRUMENTS if d["kind"] == "Guitar")
    out = [MODULE_HEADER % {"g": g, "b": len(INSTRUMENTS) - g}]
    out.append("-- 選べる楽器 (ショップや装備画面にそのまま並べられます)")
    out.append("BandInstruments.List = {")
    for d in INSTRUMENTS:
        out.append("\t{ id = %s, kind = %s, name = %s, nameEn = %s, style = %s,\n\t  desc = %s }," % (
            lua_str(d["id"]), lua_str(d["kind"]), lua_str(d["name"]), lua_str(d["nameEn"]),
            lua_str(d["style"]), lua_str(d["desc"])))
    out.append("}")
    out.append(MODULE_LOGIC)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def export(out_dir, base="BandInstruments"):
    os.makedirs(out_dir, exist_ok=True)
    built = build_all()
    parts = parts_of(built)
    write_obj(os.path.join(out_dir, base + ".obj"), base + ".mtl", parts, scale=1 / STUD)
    with open(os.path.join(out_dir, base + ".mtl"), "w") as fh:
        for d, _, _ in built:
            for key, p in d["palette"].items():
                r, g, bb = (c / 255 for c in p["color"])
                fh.write("newmtl %s_%s\nKd %.3f %.3f %.3f\nKa 0 0 0\nKs 0.5 0.5 0.5\n"
                         "Ns 200\nd 1\nillum 2\n" % (d["id"], key, r, g, bb))
                if p.get("texture"):
                    fh.write("map_Kd textures/%s_%s.png\n" % (d["id"], key))
    metas = {d["id"]: meta(d, b, info, parts) for d, b, info in built}
    stats = {"parts": [{"name": n, "triangles": int(m.ntris)} for n, _, m in parts],
             "instruments": {}}
    for d, b, info in built:
        mine = [p for p in stats["parts"] if p["name"].startswith(d["id"] + "_")]
        stats["instruments"][d["id"]] = dict(metas[d["id"]], kind=d["kind"],
                                             triangles=sum(p["triangles"] for p in mine),
                                             parts=len(mine))
    with open(os.path.join(out_dir, base + "_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, base + "_uv.json"), "w") as fh:
        json.dump({d["id"]: info for d, _, info in built}, fh)
    write_setup(os.path.join(out_dir, base + "_Setup.lua"), built, metas)
    write_module(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roblox",
                              "BandInstruments.lua"))
    for k, v in stats["instruments"].items():
        print("%-12s %-6s %6d tris  %2d parts  %.2f studs" % (k, v["kind"], v["triangles"],
                                                              v["parts"], v["length_studs"]))
    return built, parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "export",
                                                  "instruments"))
    a = ap.parse_args()
    export(a.out)


if __name__ == "__main__":
    main()
