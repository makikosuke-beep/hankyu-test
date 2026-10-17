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
        "scale": 648, "frets": 21, "nut": 42.0, "saddle_y": 119, "notch_y": 376,
        "thick": 45, "edge": 7.5, "fb_h": 11, "head": "six", "head_angle": 0,
        "outline": [(0, 0), (70, 3), (118, 16), (150, 42), (164, 82), (163, 125), (150, 165),
                    (128, 200), (118, 232), (122, 262), (134, 296), (136, 330), (124, 362),
                    (110, 392), (98, 412), (84, 416), (70, 402), (56, 388), (40, 381), (28.5, 380),
                    (-28.5, 380), (-40, 385), (-56, 402), (-72, 428), (-88, 450), (-102, 458),
                    (-116, 450), (-126, 422), (-133, 388), (-142, 352), (-146, 318), (-140, 286),
                    (-128, 258), (-120, 232), (-126, 205), (-146, 170), (-160, 128), (-162, 84),
                    (-150, 44), (-120, 16), (-72, 3)],
        "corners": [19, 20],
        "guard": {"region": [(-300, 700), (-300, 236), (-112, 214), (-86, 184), (-66, 156),
                             (-50, 149), (48, 149), (52, 132), (55, 108), (60, 84), (72, 62),
                             (92, 44), (116, 34), (300, 20), (300, 150), (122, 176), (90, 206),
                             (74, 248), (66, 300), (60, 352), (52, 420), (40, 700)], "inset": 9},
        "pickups": [("single", 162, 0, 0), ("single", 100, 0, 0), ("single", 42, 0, -9)],
        "pickup_color": "cover", "bridge": "trem",
        "knobs": [("skirt", 60, 104), ("skirt", 80, 76), ("skirt", 92, 48)],
        "switch": ("blade", 74, 128),
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
        "scale": 648, "frets": 21, "nut": 42.0, "saddle_y": 118, "notch_y": 375,
        "thick": 45, "edge": 3.5, "fb_h": 11, "head": "six_small", "head_angle": 0,
        "outline": [(0, 0), (72, 3), (120, 15), (150, 40), (162, 80), (163, 130), (158, 180),
                    (151, 222), (150, 262), (153, 292), (149, 320), (136, 340), (116, 352),
                    (96, 352), (78, 342), (60, 324), (44, 309), (28.5, 304), (-28.5, 304),
                    (-28.5, 375), (-45, 383), (-80, 388), (-112, 382), (-138, 364), (-155, 336),
                    (-162, 300), (-160, 262), (-154, 225), (-158, 185), (-163, 130), (-162, 80),
                    (-150, 40), (-120, 15), (-72, 3)],
        "corners": [17, 18, 19],
        "guard": {"region": [(-300, 700), (-300, 212), (-112, 200), (-62, 178), (46, 178),
                             (64, 188), (300, 240), (300, 700)], "inset": 7},
        "pickups": [("tele_neck", 160, 0, 0), ("single", 32, 0, -6)],
        "pickup_color": "black", "bridge": "ashtray",
        "control_plate": {"c": (84, 92), "w": 30, "h": 140, "ang": -22,
                          "knobs": [(-38,), (12,)], "switch": (52,)},
        "palette": dict(common_palette(MAPLE_BOARD, inlay=(30, 26, 24), knob=CHROME),
                        Body=finish([226, 168, 80], "ash_blonde"),
                        Guard={"color": [20, 20, 22], "material": "SmoothPlastic",
                               "reflectance": 0.1, "pbr": [0.0, 0.25, 0.6]}),
    },
    {
        "id": "Heritage", "kind": "Guitar", "type": "LP", "name": "ヘリテージ",
        "nameEn": "HERITAGE", "style": "LP タイプ",
        "desc": "チェリーサンバーストのトラ杢トップにクリームのバインディング。ハムバッカー 2 基のずっしりしたシングルカット。",
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 146, "notch_y": 395,
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
        "raised_guard": [(40, 318), (60, 322), (82, 308), (96, 282), (98, 252), (90, 218),
                         (76, 190), (58, 176), (46, 182), (41, 210), (39, 250), (38, 290)],
        "pickups": [("humbucker", 145, 0, 0), ("humbucker", 40, 0, 0)],
        "rings": True, "pickup_color": "chrome", "bridge": "tom_stop",
        "knobs": [("tophat", 64, 116), ("tophat", 104, 102), ("tophat", 74, 70),
                  ("tophat", 114, 58)],
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
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 168, "notch_y": 346,
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
        "guard": {"region": [(-300, 330), (-300, 262), (-108, 232), (-80, 212), (-54, 202),
                             (56, 202), (84, 214), (112, 234), (300, 262), (300, 330)],
                  "inset": 13},
        "pickups": [("open_humbucker", 145, 0, 0), ("open_humbucker", 40, 0, 0)],
        "pickup_color": "black", "bridge": "tom_stop",
        "knobs": [("tophat", 56, 112), ("tophat", 94, 100), ("tophat", 66, 76),
                  ("tophat", 104, 62)],
        "switch": ("toggle", 88, 296),
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
        "scale": 628, "frets": 22, "nut": 43.0, "saddle_y": 272, "notch_y": 470,
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
        "scale": 864, "frets": 20, "nut": 38.0, "neck_end_w": 62.0, "saddle_y": 104,
        "notch_y": 428, "thick": 45, "edge": 8.0, "fb_h": 13, "head": "bass4",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (84, 4), (134, 18), (166, 48), (180, 94), (176, 142), (158, 184),
                    (134, 218), (122, 248), (124, 280), (134, 314), (140, 350), (136, 384),
                    (124, 410), (110, 430), (96, 444), (82, 446), (70, 438), (56, 431), (40, 428),
                    (31, 428), (-31, 428), (-42, 434), (-56, 450), (-72, 474), (-90, 500),
                    (-106, 518), (-122, 524), (-134, 512), (-140, 486), (-142, 452), (-148, 416),
                    (-158, 380), (-162, 342), (-154, 306), (-140, 276), (-132, 252), (-138, 222),
                    (-158, 190), (-172, 148), (-174, 100), (-158, 52), (-124, 18), (-70, 3)],
        "corners": [20, 21],
        "guard": {"region": [(-300, 700), (-300, 236), (-62, 226), (60, 222), (300, 246),
                             (300, 700)], "inset": 8},
        "pickups": [("jbass", 150, 0, 0), ("jbass", 52, 0, 0)],
        "pickup_color": "black", "bridge": "fender_bass",
        "control_plate": {"c": (108, 118), "w": 34, "h": 150, "ang": -24,
                          "knobs": [(-48,), (2,), (50,)]},
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
        "scale": 864, "frets": 20, "nut": 42.0, "neck_end_w": 64.0, "saddle_y": 100,
        "notch_y": 424, "thick": 45, "edge": 8.0, "fb_h": 13, "head": "bass4",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (82, 4), (132, 18), (164, 48), (178, 94), (176, 142), (160, 184),
                    (140, 216), (132, 246), (136, 280), (146, 316), (148, 352), (140, 386),
                    (126, 414), (110, 432), (94, 444), (80, 444), (68, 434), (54, 427), (40, 424),
                    (31, 424), (-31, 424), (-42, 430), (-58, 448), (-76, 472), (-94, 494),
                    (-110, 508), (-124, 510), (-136, 498), (-142, 472), (-144, 442), (-152, 406),
                    (-162, 370), (-164, 334), (-154, 300), (-140, 272), (-134, 250), (-142, 220),
                    (-162, 186), (-176, 144), (-178, 96), (-162, 50), (-128, 17), (-72, 3)],
        "corners": [20, 21],
        "guard": {"region": [(-300, 700), (-300, 172), (-104, 152), (-64, 190), (38, 204),
                             (300, 232), (300, 700)], "inset": 8},
        "pickups": [("psplit", 150, 0, 0)],
        "pickup_color": "black", "bridge": "fender_bass",
        "control_plate": {"c": (110, 112), "w": 34, "h": 104, "ang": -24,
                          "knobs": [(-26,), (26,)]},
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
        "scale": 864, "frets": 21, "nut": 42.0, "neck_end_w": 64.0, "saddle_y": 100,
        "notch_y": 400, "thick": 45, "edge": 10.0, "fb_h": 13, "head": "three_one",
        "head_angle": 0, "strings": 4, "inlays": "dots",
        "outline": [(0, 0), (88, 5), (140, 22), (172, 56), (182, 102), (178, 150), (162, 192),
                    (146, 222), (138, 252), (142, 286), (150, 320), (148, 356), (136, 384),
                    (118, 406), (100, 418), (84, 418), (70, 408), (54, 402), (36, 400), (31, 400),
                    (-31, 400), (-44, 408), (-60, 424), (-78, 446), (-96, 464), (-112, 472),
                    (-126, 466), (-136, 446), (-142, 418), (-150, 384), (-158, 350), (-156, 314),
                    (-144, 284), (-138, 258), (-146, 226), (-164, 192), (-178, 150), (-182, 104),
                    (-170, 58), (-140, 22), (-88, 5)],
        "corners": [19, 20],
        "guard_poly": [(-31, 398), (-80, 394), (-114, 368), (-128, 318), (-122, 262),
                       (-98, 214), (-58, 184), (0, 174), (54, 182), (88, 210), (106, 256),
                       (110, 310), (100, 356), (76, 388), (31, 398)],
        "pickups": [("mm", 105, 0, 0)], "pickup_color": "black", "bridge": "mm_bridge",
        "round_plate": {"c": (108, 92), "r": 50, "knobs": [(84, 128), (112, 104), (132, 72)]},
        "palette": dict(common_palette(MAPLE_BOARD, inlay=(30, 26, 24), knob=CHROME),
                        Body=finish([214, 176, 120], "ash_natural"),
                        Guard={"color": [20, 20, 22], "material": "SmoothPlastic",
                               "reflectance": 0.1, "pbr": [0.0, 0.25, 0.6]}),
    },
    {
        "id": "Tempest", "kind": "Bass", "type": "TB", "name": "テンペスト",
        "nameEn": "TEMPEST", "style": "TB タイプ",
        "desc": "高音側のホーンが長く伸びたリバースボディ。タバコサンバーストにクロームのハムバッカー 2 基のスルーネック。",
        "scale": 864, "frets": 20, "nut": 40.0, "neck_end_w": 62.0, "saddle_y": 112,
        "notch_y": 402, "thick": 40, "edge": 6.0, "fb_h": 12, "head": "reverse4",
        "head_angle": 10, "strings": 4, "inlays": "dots",
        "outline": [(-10, 0), (64, 6), (122, 24), (160, 54), (178, 96), (174, 144), (158, 186),
                    (144, 218), (140, 250), (146, 284), (154, 320), (160, 358), (160, 398),
                    (154, 436), (142, 470), (128, 498), (112, 516), (96, 522), (84, 512),
                    (74, 488), (64, 458), (52, 430), (40, 410), (31, 402), (-31, 402), (-44, 396),
                    (-62, 378), (-86, 358), (-112, 348), (-134, 342), (-150, 326), (-158, 302),
                    (-160, 270), (-164, 236), (-172, 200), (-182, 160), (-186, 116), (-180, 72),
                    (-162, 38), (-132, 14), (-80, 2)],
        "corners": [23, 24],
        "pickups": [("tb_humbucker", 168, 0, 0), ("tb_humbucker", 56, 0, 0)],
        "pickup_color": "chrome", "bridge": "tb_bridge",
        "knobs": [("tophat", 92, 100), ("tophat", 124, 76), ("tophat", 100, 52)],
        "palette": dict(common_palette(ROSEWOOD, knob=(20, 20, 22), neck=(120, 66, 34)),
                        Head=finish([16, 14, 14], pbr=[0.0, 0.3, 0.35]),
                        Body=finish([176, 104, 40], "burst_tobacco")),
    },
    {
        "id": "Crestwave", "kind": "Bass", "type": "RK", "name": "クレストウェーブ",
        "nameEn": "CRESTWAVE", "style": "RK タイプ",
        "desc": "波頭のように巻いたホーンとバインディング。ファイアーグローの赤いボディに白い大きなピックガード、三角のインレイ。",
        "scale": 845, "frets": 20, "nut": 42.0, "neck_end_w": 62.0, "saddle_y": 90,
        "notch_y": 370, "thick": 36, "edge": 1.2, "fb_h": 11, "head": "two_two",
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
        "guard": {"region": [(-300, 392), (-300, 252), (-84, 240), (-44, 196), (-40, 150),
                             (60, 132), (150, 100), (300, 100), (300, 700), (-40, 700),
                             (-40, 392)], "inset": 8,
                  "cut": [(0, 54, 120, 64)]},
        "pickups": [("rk_neck", 168, 0, 0)], "pickup_color": "black", "bridge": "rk_bridge",
        "knobs": [("tophat", 74, 150), ("tophat", 104, 142), ("tophat", 84, 112),
                  ("tophat", 114, 104)],
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
        (0, 0), (2.5, 0.15), (4.2, 0.7), (5.4, 1.7), (6.1, 3.0), (6.3, 4.4), (6.1, 5.9),
        (5.6, 7.1), (4.9, 8.1), (4.5, 9.0), (4.42, 9.8), (4.6, 10.6), (4.95, 11.4), (5.1, 12.1),
        (5.0, 12.9), (4.7, 13.7), (4.25, 14.5), (3.75, 15.2), (3.25, 15.75), (2.8, 16.05),
        (2.4, 16.1), (2.05, 15.9), (1.75, 15.45), (1.45, 15.0), (1.1, 14.8, "c"),
        (-1.1, 14.8, "c"), (-1.35, 14.95), (-1.6, 15.3), (-1.85, 15.85), (-2.1, 16.5),
        (-2.4, 17.15), (-2.75, 17.68), (-3.15, 18.0), (-3.55, 18.08), (-3.92, 17.9), (-4.2, 17.5),
        (-4.45, 16.9), (-4.75, 16.05), (-5.1, 15.05), (-5.45, 14.0), (-5.65, 13.0), (-5.6, 12.1),
        (-5.32, 11.2), (-4.98, 10.4), (-4.8, 9.7), (-4.95, 9.0), (-5.35, 8.1), (-5.9, 7.0),
        (-6.25, 5.7), (-6.35, 4.4), (-6.15, 3.0), (-5.5, 1.7), (-4.3, 0.7), (-2.6, 0.15)],
    "Prairie": [
        (0, 0), (2.6, 0.12), (4.3, 0.6), (5.5, 1.5), (6.2, 2.8), (6.4, 4.3), (6.35, 5.8),
        (6.15, 7.2), (5.95, 8.4), (5.9, 9.6), (5.98, 10.8), (6.0, 11.9), (5.85, 12.7),
        (5.45, 13.35), (4.85, 13.8), (4.15, 13.95), (3.55, 13.75), (3.0, 13.3), (2.4, 12.65),
        (1.85, 12.15), (1.45, 11.98), (1.1, 11.95, "c"), (-1.1, 11.95, "c"), (-1.1, 14.75, "c"),
        (-1.6, 14.95), (-2.6, 15.2), (-3.7, 15.25), (-4.7, 15.0), (-5.5, 14.4), (-6.05, 13.4),
        (-6.3, 12.2), (-6.3, 10.9), (-6.15, 9.7), (-6.1, 8.6), (-6.2, 7.3), (-6.35, 5.8),
        (-6.4, 4.3), (-6.2, 2.8), (-5.5, 1.5), (-4.3, 0.6), (-2.6, 0.12)],
    "Heritage": [
        (0, 0), (2.6, 0.12), (4.4, 0.65), (5.65, 1.7), (6.35, 3.1), (6.5, 4.6), (6.3, 6.1),
        (5.75, 7.35), (5.05, 8.3), (4.6, 9.1), (4.48, 9.9), (4.62, 10.8), (4.85, 11.7),
        (4.92, 12.6), (4.78, 13.5), (4.42, 14.35), (3.88, 15.08), (3.3, 15.5), (2.78, 15.62),
        (2.38, 15.42), (2.1, 14.95), (1.85, 14.2), (1.55, 13.48), (1.25, 13.08), (1.1, 13.0, "c"),
        (-1.1, 13.0, "c"), (-1.1, 15.55, "c"), (-1.6, 15.76), (-2.5, 16.0), (-3.4, 15.95),
        (-4.2, 15.55), (-4.85, 14.85), (-5.25, 13.9), (-5.4, 12.9), (-5.3, 11.8), (-4.95, 10.75),
        (-4.7, 9.85), (-4.85, 8.95), (-5.4, 7.95), (-6.05, 6.7), (-6.45, 5.2), (-6.45, 3.7),
        (-5.95, 2.25), (-4.95, 1.05), (-3.3, 0.3)],
    "CrimsonHorn": [
        (0, 0), (2.5, 0.12), (4.3, 0.65), (5.55, 1.65), (6.25, 3.05), (6.4, 4.5), (6.15, 5.9),
        (5.5, 7.0), (4.85, 7.8), (4.5, 8.5), (4.45, 9.3), (4.6, 10.1), (4.75, 10.9), (4.65, 11.7),
        (4.25, 12.5), (3.75, 13.35), (3.4, 14.2), (3.3, 15.05), (3.45, 15.75), (3.6, 16.25),
        (3.45, 16.48), (3.14, 16.32), (2.8, 15.76), (2.4, 14.86), (1.96, 14.1), (1.5, 13.7),
        (1.1, 13.6, "c"), (-1.1, 13.6, "c"), (-1.5, 13.76), (-1.96, 14.22), (-2.42, 15.02),
        (-2.86, 15.96), (-3.3, 16.8), (-3.66, 17.26), (-3.88, 17.22), (-3.92, 16.86),
        (-3.86, 16.1), (-3.92, 15.2), (-4.16, 14.2), (-4.55, 13.2), (-4.8, 12.2), (-4.75, 11.2),
        (-4.55, 10.2), (-4.5, 9.4), (-4.7, 8.6), (-5.3, 7.6), (-6.05, 6.3), (-6.4, 4.8),
        (-6.35, 3.3), (-5.75, 1.9), (-4.6, 0.8), (-2.7, 0.15)],
    "Valkyrie": [
        (1.1, 18.5, "c"), (1.75, 18.68), (2.4, 18.4), (2.82, 17.7), (7.95, 1.62), (8.28, 1.02),
        (8.2, 0.44), (7.76, 0.12), (7.18, 0.24), (1.62, 6.62), (0.82, 7.24), (0, 7.48),
        (-0.82, 7.24), (-1.62, 6.62), (-7.18, 0.24), (-7.76, 0.12), (-8.2, 0.44), (-8.28, 1.02),
        (-7.95, 1.62), (-2.82, 17.7), (-2.4, 18.4), (-1.75, 18.68), (-1.1, 18.5, "c")],
    "Velvet": [
        (0, 0), (2.8, 0.15), (4.7, 0.7), (6.05, 1.8), (6.75, 3.4), (6.85, 5.0), (6.55, 6.5),
        (5.9, 7.7), (5.15, 8.65), (4.72, 9.5), (4.65, 10.4), (4.85, 11.4), (5.12, 12.4),
        (5.2, 13.4), (5.0, 14.4), (4.68, 15.35), (4.22, 16.3), (3.7, 17.1), (3.2, 17.68),
        (2.75, 17.95), (2.35, 17.92), (2.02, 17.62), (1.72, 17.2), (1.42, 16.92), (1.2, 16.85, "c"),
        (-1.2, 16.85, "c"), (-1.45, 17.0), (-1.72, 17.4), (-2.0, 18.05), (-2.3, 18.85),
        (-2.62, 19.65), (-3.0, 20.3), (-3.42, 20.7), (-3.85, 20.82), (-4.25, 20.62), (-4.52, 20.15),
        (-4.72, 19.45), (-4.95, 18.6), (-5.25, 17.5), (-5.55, 16.3), (-5.78, 15.1), (-5.82, 14.0),
        (-5.62, 12.95), (-5.28, 11.95), (-4.92, 11.2), (-4.98, 10.3), (-5.5, 9.2), (-6.18, 8.0),
        (-6.7, 6.5), (-6.85, 5.0), (-6.65, 3.4), (-5.95, 1.8), (-4.6, 0.7), (-2.7, 0.15)],
    "Foundation": [
        (0, 0), (2.8, 0.15), (4.65, 0.7), (6.0, 1.8), (6.7, 3.4), (6.85, 5.0), (6.6, 6.5),
        (6.0, 7.75), (5.4, 8.8), (5.15, 9.7), (5.22, 10.6), (5.45, 11.6), (5.55, 12.7),
        (5.42, 13.8), (5.12, 14.85), (4.66, 15.85), (4.12, 16.72), (3.56, 17.38), (3.02, 17.72),
        (2.55, 17.74), (2.18, 17.48), (1.86, 17.06), (1.52, 16.78), (1.2, 16.7, "c"),
        (-1.2, 16.7, "c"), (-1.45, 16.85), (-1.72, 17.25), (-2.0, 17.9), (-2.32, 18.65),
        (-2.7, 19.35), (-3.15, 19.92), (-3.62, 20.25), (-4.08, 20.3), (-4.45, 20.08), (-4.7, 19.6),
        (-4.9, 18.9), (-5.15, 17.95), (-5.45, 16.85), (-5.78, 15.6), (-6.0, 14.2), (-6.0, 12.8),
        (-5.75, 11.6), (-5.4, 10.5), (-5.42, 9.4), (-5.88, 8.3), (-6.45, 7.0), (-6.8, 5.5),
        (-6.85, 4.0), (-6.5, 2.6), (-5.7, 1.4), (-4.4, 0.55), (-2.6, 0.12)],
    "Manta": [
        (0, 0), (2.9, 0.2), (4.9, 0.85), (6.25, 2.0), (6.95, 3.6), (7.15, 5.2), (6.9, 6.7),
        (6.3, 7.9), (5.65, 8.8), (5.35, 9.6), (5.42, 10.5), (5.65, 11.5), (5.72, 12.6),
        (5.5, 13.7), (5.08, 14.62), (4.52, 15.45), (3.9, 16.08), (3.3, 16.42), (2.75, 16.45),
        (2.3, 16.22), (1.9, 15.95), (1.52, 15.8), (1.22, 15.75, "c"), (-1.22, 15.75, "c"),
        (-1.48, 15.85), (-1.75, 16.2), (-2.05, 16.8), (-2.42, 17.5), (-2.85, 18.12),
        (-3.35, 18.55), (-3.88, 18.72), (-4.35, 18.6), (-4.72, 18.2), (-5.0, 17.55), (-5.3, 16.6),
        (-5.65, 15.45), (-5.95, 14.25), (-6.02, 13.3), (-5.9, 12.3), (-5.66, 11.3), (-5.42, 10.3),
        (-5.55, 9.3), (-6.12, 8.2), (-6.75, 6.9), (-7.1, 5.4), (-7.1, 3.8), (-6.6, 2.3),
        (-5.6, 1.1), (-4.0, 0.35), (-2.2, 0.07)],
    "Tempest": [
        (-0.4, 0), (1.8, 0.15), (3.8, 0.75), (5.3, 1.85), (6.3, 3.4), (6.75, 5.1), (6.6, 6.8),
        (6.05, 8.1), (5.6, 9.1), (5.45, 10.1), (5.6, 11.2), (5.95, 12.5), (6.2, 13.9),
        (6.25, 15.3), (6.05, 16.7), (5.6, 18.0), (4.95, 19.15), (4.25, 20.05), (3.62, 20.55),
        (3.16, 20.6), (2.86, 20.3), (2.6, 19.5), (2.3, 18.4), (1.9, 17.2), (1.5, 16.3),
        (1.22, 15.85, "c"), (-1.22, 15.85, "c"), (-1.55, 15.7), (-2.05, 15.2), (-2.7, 14.55),
        (-3.5, 14.05), (-4.35, 13.75), (-5.1, 13.45), (-5.65, 12.85), (-5.95, 12.0),
        (-6.05, 10.9), (-6.15, 9.7), (-6.45, 8.4), (-6.95, 7.0), (-7.25, 5.5), (-7.2, 4.0),
        (-6.75, 2.6), (-5.85, 1.35), (-4.4, 0.45), (-2.4, 0.05)],
    "Crestwave": [
        (0, 0), (2.9, 0.15), (4.8, 0.75), (6.0, 1.85), (6.65, 3.4), (6.8, 5.0), (6.55, 6.6),
        (6.1, 7.9), (5.85, 9.0), (5.9, 10.2), (6.1, 11.4), (6.1, 12.6), (5.8, 13.65), (5.2, 14.6),
        (4.45, 15.25), (3.7, 15.5), (3.15, 15.4), (2.75, 15.0), (2.35, 14.7), (1.85, 14.6),
        (1.5, 14.58), (1.22, 14.57, "c"), (-1.22, 14.57, "c"), (-1.4, 15.0), (-1.6, 15.8),
        (-1.95, 16.85), (-2.45, 17.95), (-3.1, 18.9), (-3.8, 19.55), (-4.45, 19.75),
        (-4.95, 19.55), (-5.15, 19.05), (-5.05, 18.45), (-4.75, 17.95), (-4.7, 17.3),
        (-4.95, 16.4), (-5.4, 15.3), (-5.95, 14.1), (-6.35, 12.8), (-6.4, 11.5), (-6.25, 10.2),
        (-6.4, 8.9), (-6.85, 7.5), (-7.1, 6.0), (-7.05, 4.4), (-6.55, 2.8), (-5.6, 1.45),
        (-4.2, 0.5), (-2.4, 0.1)],
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
        pts = [(h, 0), (h + 2, 8), (h + 6, 20), (h + 14, 34), (h + 20, 50), (h + 21, 64),
               (h + 17, 80), (h + 11, 96), (h + 8, 114), (h + 9, 132), (h + 14, 150), (h + 20, 166),
               (h + 22, 178), (h + 19, 190), (h + 10, 197), (h - 4, 200), (-10, 199), (-20, 193),
               (-25, 182), (-27, 160), (-28, 120), (-28, 80), (-27, 44), (-25, 20), (-22, 6),
               (-h, 0)]
        posts = [(-17 + 2.1 * i, 40 + 26.5 * i, "L") for i in range(6)]
    elif kind == "six_small":
        pts = [(h, 0), (h + 3, 16), (h + 10, 40), (h + 13, 80), (h + 12, 120), (h + 10, 150),
               (h + 6, 168), (-4, 176), (-18, 172), (-25, 156), (-28, 120), (-28, 70),
               (-25, 26), (-h, 0)]
        posts = [(-16 + 1.8 * i, 34 + 25 * i, "L") for i in range(6)]
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
        pts = [(h, 0), (h + 3, 12), (h + 10, 28), (h + 20, 48), (h + 26, 70), (h + 25, 92),
               (h + 19, 114), (h + 14, 138), (h + 13, 162), (h + 16, 186), (h + 20, 206),
               (h + 19, 220), (h + 11, 229), (h - 4, 232), (-12, 231), (-24, 224), (-31, 208),
               (-34, 170), (-34, 120), (-33, 70), (-30, 30), (-26, 10), (-h, 0)]
        posts = [(-18 + 3 * i, 46 + 52 * i, "L") for i in range(4)]
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
    xs_edge_l = min(x for x, _ in hpoly.exterior.coords)
    xs_edge_r = max(x for x, _ in hpoly.exterior.coords)
    for px, py, side in posts:
        c0 = H((px, py, face))
        n_ax = Hm[:3, 2]
        b.add("Hardware", cyl(c0 + n_ax * (post_h / 2), post_r, post_h, axis=n_ax, segs=10))
        b.add("Hardware", cyl(c0 + n_ax * 1.0, post_r + 2.4, 2.0, axis=n_ax, segs=10))
        sx = -1 if side == "L" else 1
        edge_x = xs_edge_l if side == "L" else xs_edge_r
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
            yt = saddle - 56
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
        b.add("Hardware", flat(rrect(0, saddle - 18, 72, 84, 3), T_, T_ + 2.0, r_top=0.5))
        b.add("Hardware", box((0, saddle - 59, T_ + 6.5), (72, 2.0, 13)))
        for a, _ in strings:
            b.add("Hardware", rbox((a[0], saddle - 2, (T_ + 2 + z_s - 0.6) / 2),
                                   (11, 22, z_s - 0.6 - T_ - 2), 1.5))
    elif kind == "mm_bridge":
        b.add("Hardware", flat(rrect(0, saddle - 24, 82, 96, 14), T_, T_ + 2.5, r_top=0.8))
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
