"""Drum stick models for Beat Drummer - several themed designs.

Every stick is built standing on its butt end: axis +Y, butt at y=0, tip at
y=L (metres).  Its 'front' (logo, bow, star face) faces +Z.  Each design is a
handful of MeshParts named ``<Design>_<Key>``; the setup script turns each
design into one welded Model with Grip / Tip attachments.

Run:  python sticks.py --out ../export/sticks
"""
import argparse
import json
import math
import os

import numpy as np

from mesh_lib import (TAU, Mesh, T, Sc, az, chain, cyl_wrap, finalize, frame,
                      hull, lathe, sphere, unit, write_obj)

STUD = 0.28          # metres per stud (same as the kits)
SEGS = 20            # lathe segments around a stick
GRIP_Y = 0.14        # fulcrum, measured from the butt (a 16" stick)
SPACING = 0.075      # distance between sticks in the exported row

# ---------------------------------------------------------------------------
# catalogue: names, look in Roblox and in the renders
#   material  : Roblox Enum.Material name
#   pbr       : (metallic, roughness, coat) for Blender / the web preview
#   glass / neon / grain : special shading
# ---------------------------------------------------------------------------
DESIGNS = [
    {
        "id": "Sovereign", "name": "ソブリン シグネチャー", "nameEn": "SOVEREIGN Signature",
        "theme": "スタンダードの高級品",
        "desc": "厳選ヒッコリーの 5A。ゴールドディップのグリップエンドと金箔ロゴ、どんぐり型のウッドチップ。",
        "size": {"L": 0.406, "D": 0.0144, "tip": "acorn"},
        "primary": "Wood", "logo": "Wood",
        "palette": {
            "Wood": {"color": [190, 136, 74], "material": "Wood", "reflectance": 0.05,
                     "pbr": [0.0, 0.38, 0.35], "grain": True},
            "Gold": {"color": [214, 170, 72], "material": "Metal", "reflectance": 0.25,
                     "pbr": [1.0, 0.16, 0.0]},
        },
    },
    {
        "id": "IronStorm", "name": "アイアンストーム", "nameEn": "IRON STORM",
        "theme": "メタル",
        "desc": "ガンメタルの合金シャフトに溝付きのラバーグリップ、真紅のライン、スパイク付きのクロームエンド。",
        "size": {"L": 0.406, "D": 0.0151, "tip": "barrel"},
        "primary": "Gunmetal", "logo": "Gunmetal",
        "palette": {
            "Gunmetal": {"color": [92, 96, 106], "material": "Metal", "reflectance": 0.2,
                         "pbr": [1.0, 0.3, 0.0]},
            "Rubber": {"color": [24, 24, 27], "material": "Rubber", "reflectance": 0.0,
                       "pbr": [0.0, 0.62, 0.0]},
            "Accent": {"color": [205, 18, 32], "material": "SmoothPlastic", "reflectance": 0.05,
                       "pbr": [0.0, 0.25, 0.6], "glow": True},
            "Nylon": {"color": [18, 18, 20], "material": "SmoothPlastic", "reflectance": 0.1,
                      "pbr": [0.0, 0.22, 0.4]},
            "Chrome": {"color": [214, 216, 222], "material": "Metal", "reflectance": 0.35,
                       "pbr": [1.0, 0.07, 0.0]},
        },
    },
    {
        "id": "SweetRibbon", "name": "スウィートリボン", "nameEn": "SWEET RIBBON",
        "theme": "かわいい",
        "desc": "パステルピンクにキャンディのようなストライプ。エンドにはハート付きのリボン、チップはパール。",
        "size": {"L": 0.394, "D": 0.0137, "tip": "ball"},
        "primary": "Lacquer", "logo": "Lacquer",
        "palette": {
            "Lacquer": {"color": [255, 184, 208], "material": "SmoothPlastic", "reflectance": 0.08,
                        "pbr": [0.0, 0.2, 0.8]},
            "Stripe": {"color": [255, 250, 252], "material": "SmoothPlastic", "reflectance": 0.05,
                       "pbr": [0.0, 0.25, 0.8]},
            "Ribbon": {"color": [232, 72, 142], "material": "SmoothPlastic", "reflectance": 0.05,
                       "pbr": [0.0, 0.32, 0.3], "sheen": True},
            "Heart": {"color": [236, 160, 150], "material": "Metal", "reflectance": 0.3,
                      "pbr": [1.0, 0.18, 0.0], "glow": True},
            "Pearl": {"color": [252, 246, 244], "material": "SmoothPlastic", "reflectance": 0.25,
                      "pbr": [0.0, 0.2, 1.0]},
        },
    },
    {
        "id": "Starlight", "name": "スターライト", "nameEn": "STARLIGHT",
        "theme": "ゆめかわ",
        "desc": "ラベンダーに金の星をちりばめた、魔法のステッキのような一本。エンドにはカットした大きな星。",
        "size": {"L": 0.394, "D": 0.0137, "tip": "teardrop"},
        "primary": "Lacquer", "logo": "Lacquer",
        "palette": {
            "Lacquer": {"color": [196, 170, 255], "material": "SmoothPlastic", "reflectance": 0.08,
                        "pbr": [0.0, 0.2, 0.8]},
            "Gold": {"color": [236, 196, 98], "material": "Metal", "reflectance": 0.25,
                     "pbr": [1.0, 0.16, 0.0]},
            "Star": {"color": [255, 228, 128], "material": "SmoothPlastic", "reflectance": 0.2,
                     "pbr": [0.0, 0.12, 1.0], "glow": True},
            "Pearl": {"color": [252, 248, 255], "material": "SmoothPlastic", "reflectance": 0.25,
                      "pbr": [0.0, 0.2, 1.0]},
        },
    },
    {
        "id": "Yozakura", "name": "夜桜", "nameEn": "YOZAKURA",
        "theme": "和モダン",
        "desc": "黒漆に朱のグリップエンドと金の輪。夜に舞う桜の花びらをあしらった和の一本。",
        "size": {"L": 0.406, "D": 0.0144, "tip": "oval"},
        "primary": "Lacquer", "logo": "Lacquer",
        "palette": {
            "Lacquer": {"color": [20, 17, 20], "material": "SmoothPlastic", "reflectance": 0.2,
                        "pbr": [0.0, 0.12, 1.0]},
            "Vermilion": {"color": [182, 32, 26], "material": "SmoothPlastic", "reflectance": 0.15,
                          "pbr": [0.0, 0.14, 1.0]},
            "Gold": {"color": [214, 170, 72], "material": "Metal", "reflectance": 0.25,
                     "pbr": [1.0, 0.16, 0.0]},
            "Petal": {"color": [255, 184, 204], "material": "SmoothPlastic", "reflectance": 0.05,
                      "pbr": [0.0, 0.3, 0.6], "glow": True},
        },
    },
    {
        "id": "NeonPulse", "name": "ネオンパルス", "nameEn": "NEON PULSE",
        "theme": "光る",
        "desc": "透明なシャフトの芯が光るライトアップスティック。叩くたびにフラッシュ。光の色は変えられます。",
        "size": {"L": 0.406, "D": 0.016, "tip": "barrel"},
        "primary": "Glass", "logo": "Rubber",
        "palette": {
            "Glass": {"color": [214, 240, 255], "material": "Glass", "reflectance": 0.1,
                      "transparency": 0.55, "pbr": [0.0, 0.04, 0.0], "glass": True},
            "Neon": {"color": [0, 228, 255], "material": "Neon", "reflectance": 0.0,
                     "pbr": [0.0, 0.3, 0.0], "neon": True, "glow": True},
            "Rubber": {"color": [22, 22, 26], "material": "Rubber", "reflectance": 0.0,
                       "pbr": [0.0, 0.6, 0.0]},
            "Chrome": {"color": [206, 210, 220], "material": "Metal", "reflectance": 0.35,
                       "pbr": [1.0, 0.08, 0.0]},
        },
        "neonColors": {"cyan": [0, 228, 255], "magenta": [255, 40, 200], "lime": [120, 255, 40],
                       "orange": [255, 130, 20], "white": [235, 245, 255]},
    },
]

BY_ID = {d["id"]: d for d in DESIGNS}


# ---------------------------------------------------------------------------
# stick profile
# ---------------------------------------------------------------------------
def tip_points(kind, y_n, L, rn, rt):
    """Profile points (r, y) above the neck (y_n, rn) up to the tip (0, L)."""
    tl = L - y_n
    pts = []
    if kind == "ball":
        # sphere of radius rt sitting on the neck
        yc = L - rt
        th0 = -math.acos(min(rn / rt, 0.999))
        for th in np.linspace(th0, math.pi / 2, 12)[1:]:
            pts.append((rt * math.cos(th), yc + rt * math.sin(th)))
        return pts
    for s in np.linspace(0, 1, 15)[1:]:
        y = y_n + s * tl
        if kind == "acorn":
            k = 0.36
            if s < k:
                r = rn + (rt - rn) * math.sin(math.pi / 2 * s / k)
            else:
                u = (s - k) / (1 - k)
                r = rt * math.sqrt(max(1 - u * u, 0)) * (1 - 0.32 * u)
        elif kind == "teardrop":
            k = 0.6
            if s < k:
                r = rn + (rt - rn) * math.sin(math.pi / 2 * s / k) ** 1.4
            else:
                u = (s - k) / (1 - k)
                r = rt * math.sqrt(max(1 - u * u, 0))
        elif kind == "oval":
            k = 0.5
            if s < k:
                r = rn + (rt - rn) * math.sin(math.pi / 2 * s / k)
            else:
                u = (s - k) / (1 - k)
                r = rt * math.sqrt(max(1 - u * u, 0))
        else:  # barrel
            if s < 0.18:
                r = rn + (rt - rn) * math.sin(math.pi / 2 * s / 0.18)
            elif s < 0.72:
                r = rt * (1 + 0.04 * math.sin(math.pi * (s - 0.18) / 0.54))
            else:
                u = (s - 0.72) / 0.28
                r = rt * math.sqrt(max(1 - u ** 2.2, 0))
        pts.append((r, y))
    pts[-1] = (0.0, L)
    return pts


def stick_profile(L, D, tip, taper_len=0.12, neck_d=None, tip_len=None, tip_d=None):
    R = D / 2
    rn = (neck_d or D * 0.42) / 2
    tip_d = tip_d or {"acorn": D * 0.66, "teardrop": D * 0.64, "oval": D * 0.6,
                      "barrel": D * 0.62, "ball": D * 0.62}[tip]
    tip_len = tip_len or {"acorn": 0.0135, "teardrop": 0.014, "oval": 0.0125,
                          "barrel": 0.0125, "ball": tip_d * 0.98}[tip]
    rt = tip_d / 2
    y_n = L - tip_len
    y_t = y_n - taper_len
    rb = R * 0.32
    pts = [(0.0, -0.0010), (R * 0.45, -0.0008)]
    for a in np.linspace(-math.pi / 2, 0, 6):
        pts.append((R - rb + rb * math.cos(a), rb + rb * math.sin(a)))
    pts.append((R, y_t))
    for t in np.linspace(0, 1, 17)[1:]:
        r = rn + (R - rn) * ((1 + math.cos(math.pi * t)) / 2) ** 0.75
        pts.append((r, y_t + t * taper_len))
    pts += tip_points(tip, y_n, L, rn, rt)
    prof = np.array(pts)
    assert np.all(np.diff(prof[:, 1]) > 0), "profile must rise monotonically"
    return prof, {"R": R, "y_t": y_t, "y_n": y_n, "rt": rt, "L": L}


def r_at(prof, y):
    return float(np.interp(y, prof[:, 1], prof[:, 0]))


def clip_profile(prof, y0, y1):
    ys = prof[:, 1]
    out = []
    if y0 <= ys[0]:
        out.append(tuple(prof[0]))
        y0 = ys[0]
    else:
        out.append((r_at(prof, y0), y0))
    out += [tuple(p) for p in prof if y0 < p[1] < min(y1, ys[-1])]
    if y1 >= ys[-1]:
        out.append(tuple(prof[-1]))
    else:
        out.append((r_at(prof, y1), y1))
    return out


def banded(prof, bands, L, segs=SEGS, smooth=40.0):
    """Split a stick profile into lathed bands of different materials.

    bands: [(y0, y1, key, dr, extra_ys)], sorted, touching.  ``dr`` is a
    radial offset (float or f(y)).  The radial step between two bands belongs
    to the band that stands proud, so the surface stays closed."""
    ymin, ymax = prof[0, 1], prof[-1, 1]
    built = []
    for y0, y1, key, dr, extra in bands:
        f = dr if callable(dr) else (lambda y, d=dr: d)
        lo, hi = max(y0, ymin), min(y1, ymax)
        ys = sorted(set([p[1] for p in clip_profile(prof, lo, hi)] +
                        [y for y in (extra or []) if lo < y < hi]))
        pts = []
        for y in ys:
            r = r_at(prof, y)
            if (y <= ymin and r < 1e-9) or (y >= ymax):
                pts.append((0.0 if y >= ymax or y <= ymin else r, y))
            else:
                pts.append((r + f(y), y))
        built.append([key, pts, y0 <= ymin, y1 >= ymax])
    for i, (key, pts, first, last) in enumerate(built):
        if i > 0 and not first:
            prev_r = built[i - 1][1][-1][0]
            if pts[0][0] > prev_r + 1e-7:
                pts.insert(0, (prev_r, pts[0][1]))
        if i + 1 < len(built) and not last:
            nxt = built[i + 1][1]
            if pts[-1][0] > nxt[0][0] + 1e-7:
                pts.append((nxt[0][0], pts[-1][1]))
    out = []
    for key, pts, first, last in built:
        m = lathe(pts, segs, smooth=smooth, phase=-math.pi / 2)
        absolute_v(m, L)
        out.append((key, m))
    return out


def absolute_v(m, L):
    """Texture v = height along the stick, so one image maps onto the
    whole stick whatever part it is."""
    m.cuv[..., 1] = np.clip(m.v[m.f][..., 1] / L, 0, 1)
    # u: start the seam at the back (phase -90deg), front = u 0.5
    return m


def grooves(y0, y1, pitch, depth, width, base=0.0):
    """Radial offset with round-bottomed rings (grip grooves)."""
    def f(y):
        if y < y0 or y > y1:
            return base
        k = ((y - y0) % pitch) / pitch
        w = width / pitch
        if k < w:
            return base - depth * math.sin(math.pi * k / w)
        return base
    ys = []
    y = y0
    while y < y1:
        w = width
        ys += [y + w * s for s in (0.0, 0.5, 1.0)]
        y += pitch
    return f, ys


# ---------------------------------------------------------------------------
# small shapes
# ---------------------------------------------------------------------------
def star_poly(r1, r2, n=5, rot=math.pi / 2):
    from shapely.geometry import Polygon
    pts = []
    for k in range(2 * n):
        r = r1 if k % 2 == 0 else r2
        a = rot + math.pi * k / n
        pts.append((r * math.cos(a), r * math.sin(a)))
    return Polygon(pts)


def petal_poly(length, width):
    """One sakura petal pointing +Y with the notch at its tip."""
    from shapely.geometry import Point, Polygon
    from shapely import affinity
    body = affinity.scale(Point(0, 0).buffer(1.0, 5), width / 2, length * 0.42)
    body = affinity.translate(body, 0, length * 0.52)
    stem = Polygon([(-width * 0.12, 0), (width * 0.12, 0),
                    (width * 0.42, length * 0.5), (-width * 0.42, length * 0.5)])
    notch = Polygon([(0, length * 0.8), (-width * 0.16, length * 1.05),
                     (width * 0.16, length * 1.05)])
    return body.union(stem).difference(notch).simplify(length * 0.015)


def flower_poly(d):
    from shapely import affinity
    from shapely.ops import unary_union
    p = petal_poly(d / 2, d * 0.36)
    f = unary_union([affinity.rotate(p, 72 * k, origin=(0, 0)) for k in range(5)])
    return f.simplify(d * 0.01)


def flat_on_stick(poly, thick, R, y, phi, sink=0.00012, spin=0.0):
    """Extrude a flat shape and lay it on the stick surface at height y,
    angle phi (lathe convention, front = +Z = 90deg)."""
    import trimesh
    from shapely import affinity
    if spin:
        poly = affinity.rotate(poly, spin, origin=(0, 0), use_radians=False)
    tm = trimesh.creation.extrude_polygon(poly, thick)
    v = np.asarray(tm.vertices, float)
    # polygon x -> arc length (Z), polygon y -> axial (Y), extrusion -> radial (X)
    flat = np.stack([v[:, 2] - sink, v[:, 1], -v[:, 0]], -1)
    m, _ = finalize(flat, np.asarray(tm.faces), 30.0)
    m = cyl_wrap(m, R)
    return m.transformed(chain(T(0, y, 0), az(phi)))


def faceted_star(r1, r2, edge, apex):
    """Gem-cut five point star in the XY plane, facing +Z."""
    ring = []
    for k in range(10):
        r = r1 if k % 2 == 0 else r2
        a = -math.pi / 2 + math.pi * k / 5
        ring.append((r * math.cos(a), r * math.sin(a)))
    ring = np.array(ring)
    V = [(0, 0, apex), (0, 0, -apex)]
    V += [(x, y, edge) for x, y in ring]
    V += [(x, y, -edge) for x, y in ring]
    V = np.array(V, float)
    F = []
    for k in range(10):
        a, b = 2 + k, 2 + (k + 1) % 10
        ab, bb = a + 10, b + 10
        F += [(0, a, b), (1, bb, ab), (a, ab, bb), (a, bb, b)]
    m, _ = finalize(V, np.array(F), 8.0)
    return m


def puffy_heart(w, depth):
    """Heart about ``w`` wide in the XY plane (point down), ``depth`` thick."""
    s = w / 7.6
    lobes = []
    for x in (-1.6, 1.6):
        lobes.append(sphere(2.2 * s, 16, 8).transformed(T(x * s, 1.2 * s, 0)))
    pts = []
    for x in (-1.6, 1.6):
        for a in np.linspace(math.pi, TAU, 9):
            for b in np.linspace(-1, 1, 5):
                r = 2.2 * s * math.sqrt(1 - b * b)
                pts.append((x * s + r * math.cos(a), 1.2 * s + r * math.sin(a), 2.2 * s * b))
    pts.append((0, -3.6 * s, 0))
    body = hull(pts, smooth=60.0)
    sq = Sc(1, 1, depth / (4.4 * s))
    return [m.transformed(sq) for m in lobes + [body]]


def ribbon_sweep(P, B, widths, thick, smooth=50.0):
    """Flat ribbon along path P; B gives the width direction per point."""
    P = np.asarray(P, float)
    n = len(P)
    Tg = np.gradient(P, axis=0)
    Tg = unit(Tg)
    B = unit(np.asarray(B, float))
    N = unit(np.cross(Tg, B))
    B = unit(np.cross(N, Tg))
    w = np.asarray(widths, float)[:, None] / 2
    t = thick / 2
    corners = [P + B * w + N * t, P - B * w + N * t, P - B * w - N * t, P + B * w - N * t]
    V = np.stack(corners, 1).reshape(-1, 3)
    F = []
    for i in range(n - 1):
        for c in range(4):
            a, b = i * 4 + c, i * 4 + (c + 1) % 4
            a2, b2 = a + 4, b + 4
            F += [(a, b, b2), (a, b2, a2)]
    F += [(0, 2, 1), (0, 3, 2)]
    e = (n - 1) * 4
    F += [(e, e + 1, e + 2), (e, e + 2, e + 3)]
    F = np.array(F)
    # make the first side face point along +N
    a, b, c = V[F[0, 0]], V[F[0, 1]], V[F[0, 2]]
    if np.dot(np.cross(b - a, c - a), N[0]) < 0:
        F = F[:, ::-1]
    m, _ = finalize(V, F, smooth)
    return m


def cone(rb, h, segs=8):
    return lathe([(0, 0), (rb, 0), (0, h)], segs, smooth=25.0)


# ---------------------------------------------------------------------------
# designs
# ---------------------------------------------------------------------------
class Stick:
    def __init__(self, d):
        self.d = d
        self.parts = {}
        sz = d["size"]
        self.L = sz["L"]
        self.prof, self.info = stick_profile(sz["L"], sz["D"], sz["tip"])
        self.R = self.info["R"]
        self.grip_y = GRIP_Y * self.L / 0.406
        self.tip_y = self.L - 0.006

    def add(self, key, mesh):
        if isinstance(mesh, (list, tuple)):
            for m in mesh:
                self.add(key, m)
            return
        self.parts.setdefault(key, []).append(mesh)

    def bands(self, bands, **kw):
        for key, m in banded(self.prof, bands, self.L, **kw):
            self.add(key, m)

    def merged(self):
        return [(k, Mesh.merge(v)) for k, v in self.parts.items()]


def build_sovereign(s):
    dip = 0.032
    lip = lambda y: 0.00028 * max(0.0, 1 - abs(y - (dip - 0.0009)) / 0.0009)  # noqa: E731
    s.bands([(-1, dip, "Gold", lambda y: 0.00012 + lip(y),
              [dip - 0.0024, dip - 0.0016, dip - 0.0009, dip - 0.0004]),
             (dip, 9, "Wood", 0.0, None)])


def build_ironstorm(s):
    R, L = s.R, s.L
    g, gy = grooves(0.016, 0.112, 0.0085, 0.00045, 0.0022, base=0.0007)
    sh0, sh1 = 0.268, L - 0.0145
    s.bands([
        (-1, 0.012, "Chrome", 0.0011, [0.004, 0.008]),
        (0.012, 0.014, "Accent", 0.0009, None),
        (0.014, 0.118, "Rubber", g, gy + [0.016, 0.115, 0.118]),
        (0.118, 0.121, "Accent", 0.0009, None),
        (0.121, sh0, "Gunmetal", 0.0, None),
        (sh0, sh0 + 0.003, "Accent", 0.0008, None),
        (sh0 + 0.003, sh1, "Rubber",
         lambda y: 0.0005 * min(1.0, (sh1 - y) / 0.01), [sh1 - 0.01, sh1 - 0.005]),
        (sh1, 9, "Nylon", 0.0, None),
    ])
    # spikes around the chrome end cap and one on the end
    rc = R + 0.0011
    for k in range(6):
        phi = math.pi / 2 + TAU * k / 6
        dvec = np.array([math.cos(phi), 0, math.sin(phi)])
        s.add("Chrome", cone(0.0019, 0.0052).transformed(
            frame(dvec * (rc - 0.0004) + np.array([0, 0.0062, 0]), dvec)))
    s.add("Chrome", cone(0.0022, 0.0058, 10).transformed(
        frame((0, -0.0006, 0), (0, -1, 0))))


def build_sweetribbon(s):
    R, L = s.R, s.L
    s.bands([(-1, s.info["y_n"] + 0.0004, "Lacquer", 0.0, None),
             (s.info["y_n"] + 0.0004, 9, "Pearl", 0.0, None)])
    # candy stripe spiral over the grip
    y0, y1, pitch = 0.05, 0.196, 0.03
    n = 130
    t = np.linspace(0, 1, n)
    th = (y1 - y0) / pitch * TAU * t
    y = y0 + (y1 - y0) * t
    P = np.stack([R * np.cos(th), y, R * np.sin(th)], -1)
    nrm = np.stack([np.cos(th), 0 * th, np.sin(th)], -1)
    tg = np.gradient(P, axis=0)
    Bw = np.cross(nrm, unit(tg))
    w = 0.0042 * np.minimum(1, np.minimum(t, 1 - t) / 0.04 + 0.25)
    s.add("Stripe", ribbon_sweep(P + nrm * 0.00012, Bw, w, 0.0005))
    # the bow: band around the stick, knot, two loops and two tails
    yk = 0.027
    s.add("Ribbon", lathe([(R + 0.0001, yk - 0.0034), (R + 0.0008, yk - 0.003),
                           (R + 0.0008, yk + 0.003), (R + 0.0001, yk + 0.0034)],
                          SEGS, smooth=50))
    zk = R + 0.0016
    for sx in (1, -1):
        tt = np.linspace(0, TAU, 48)
        q = (1 - np.cos(tt)) / 2                 # 0 at the knot, 1 at the fold
        x = sx * 0.0175 * q
        z = zk + 0.0009 + 0.0042 * np.sin(tt) * (0.5 + 0.5 * q)
        yy = yk + 0.0042 * q ** 1.5
        P = np.stack([x, yy, z], -1)
        w = 0.0118 * (0.28 + 0.72 * np.sin(np.pi * np.minimum(q * 0.78, 1)) ** 0.6)
        s.add("Ribbon", ribbon_sweep(P, np.tile([0, 1.0, 0], (len(P), 1)), w, 0.0006))
        # tail: hangs toward the butt and flares out
        tt = np.linspace(0, 1, 12)
        P = np.stack([sx * (0.0018 + 0.0046 * tt ** 1.2), yk - 0.0025 - 0.0155 * tt,
                      zk - 0.0002 + 0.0014 * np.sin(math.pi * tt)], -1)
        tg = np.gradient(P, axis=0)
        Bw = np.cross(unit(tg), np.array([0, 0, 1.0]))
        s.add("Ribbon", ribbon_sweep(P, Bw, 0.0056 + 0.0014 * tt, 0.0006))
    s.add("Ribbon", hull([(x * 0.0032, yk + y * 0.0036, zk + z * 0.0024)
                          for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)] +
                         [(0, yk, zk + 0.0034)], smooth=60))
    s.add("Heart", [m.transformed(T(0, yk + 0.0004, zk + 0.0042))
                    for m in puffy_heart(0.0072, 0.0034)])


def build_starlight(s):
    R, L = s.R, s.L
    s.bands([(-1, 0.009, "Gold", 0.0005, [0.003, 0.006]),
             (0.009, s.info["y_t"] - 0.002, "Lacquer", 0.0, None),
             (s.info["y_t"] - 0.002, s.info["y_t"] + 0.001, "Gold", 0.00035, None),
             (s.info["y_t"] + 0.001, s.info["y_n"] + 0.0004, "Lacquer", 0.0, None),
             (s.info["y_n"] + 0.0004, 9, "Pearl", 0.0, None)])
    s.add("Gold", lathe([(R + 0.0001, 0.0105), (R + 0.0004, 0.0108),
                         (R + 0.0004, 0.0118), (R + 0.0001, 0.0121)], SEGS, smooth=50))
    star = faceted_star(0.0188, 0.0082, 0.0017, 0.0046)
    s.add("Star", star.transformed(T(0, -0.0118, 0)))
    # little stars scattered round the shaft (kept off the logo at the front)
    rng = np.random.default_rng(11)
    spots = [(0.026, 120), (0.038, 250), (0.052, 20), (0.066, 160), (0.08, 290),
             (0.094, 70), (0.108, 200), (0.122, 330), (0.136, 110), (0.15, 240),
             (0.17, 10), (0.188, 150), (0.205, 280), (0.222, 20), (0.238, 170),
             (0.252, 300)]
    for y, deg in spots:
        size = rng.uniform(0.0052, 0.0068)
        s.add("Gold", flat_on_stick(star_poly(size / 2, size * 0.2), 0.00045, R, y,
                                    math.radians(deg), spin=rng.uniform(0, 72)))


def build_yozakura(s):
    R, L = s.R, s.L
    dip = 0.045
    s.bands([(-1, dip, "Vermilion", 0.0001, None),
             (dip, dip + 0.0012, "Gold", 0.00035, None),
             (dip + 0.0012, dip + 0.0032, "Lacquer", 0.0, None),
             (dip + 0.0032, dip + 0.0040, "Gold", 0.0003, None),
             (dip + 0.0040, 9, "Lacquer", 0.0, None)])
    rng = np.random.default_rng(5)
    flowers = [(0.022, 110, 0.0085), (0.03, 250, 0.0075), (0.062, 60, 0.008),
               (0.078, 175, 0.009), (0.096, 300, 0.0075), (0.118, 20, 0.0085),
               (0.142, 140, 0.0072), (0.152, 235, 0.0068)]
    for y, deg, dd in flowers:
        phi = math.radians(deg)
        s.add("Petal", flat_on_stick(flower_poly(dd), 0.0004, R + (0.0001 if y < dip else 0),
                                     y, phi, spin=rng.uniform(0, 72)))
        s.add("Gold", flat_on_stick(star_poly(dd * 0.11, dd * 0.05, 5), 0.0006,
                                    R + (0.0001 if y < dip else 0), y, phi,
                                    spin=rng.uniform(0, 72)))
    for y, deg in [(0.172, 300), (0.19, 230), (0.21, 320), (0.235, 250), (0.258, 290),
                   (0.105, 245), (0.05, 330)]:
        s.add("Petal", flat_on_stick(petal_poly(0.0042, 0.0034), 0.0004, R, y,
                                     math.radians(deg), spin=rng.uniform(0, 360)))


def build_neonpulse(s):
    R, L = s.R, s.L
    g, gy = grooves(0.016, 0.07, 0.008, 0.0005, 0.002, base=0.0008)
    s.bands([
        (-1, 0.0045, "Chrome", 0.0009, [0.002]),
        (0.0045, 0.0065, "Neon", 0.0006, None),
        (0.0065, 0.136, "Rubber", g, gy + [0.0065, 0.016, 0.132, 0.136]),
        (0.136, 9, "Glass", 0.0, None),
    ])
    rc = 0.0027
    core = [(0, 0.126), (rc * 0.7, 0.1265), (rc, 0.128), (rc, L - 0.04),
            (rc * 0.8, L - 0.022), (0.0022, L - 0.0135)]
    for a in np.linspace(-math.pi / 2, math.pi / 2, 9)[1:]:
        core.append((0.0045 * math.cos(a) if a < math.pi / 2 else 0.0,
                     L - 0.0085 + 0.0045 * math.sin(a)))
    core = [c for i, c in enumerate(core) if i == 0 or c[1] > core[i - 1][1]]
    s.add("Neon", lathe(core, 12, smooth=60))


BUILDERS = {
    "Sovereign": build_sovereign, "IronStorm": build_ironstorm,
    "SweetRibbon": build_sweetribbon, "Starlight": build_starlight,
    "Yozakura": build_yozakura, "NeonPulse": build_neonpulse,
}


def build_all():
    """[(design, Stick)] with each stick placed in the exported row."""
    out = []
    n = len(DESIGNS)
    for i, d in enumerate(DESIGNS):
        s = Stick(d)
        BUILDERS[d["id"]](s)
        s.x = (i - (n - 1) / 2) * SPACING
        out.append((d, s))
    return out


def parts_of(sticks, place=True):
    """(name, material, Mesh) in metres; material is design-specific."""
    parts = []
    for d, s in sticks:
        M = T(s.x, 0, 0) if place else np.eye(4)
        for key, m in s.merged():
            parts.append(("%s_%s" % (d["id"], key), "%s_%s" % (d["id"], key),
                          m.transformed(M)))
    return parts


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def stick_meta(d, s, parts):
    """Grip / tip positions relative to the primary MeshPart's bounding-box
    centre (what Roblox reports as its Position), in studs."""
    prim = "%s_%s" % (d["id"], d["primary"])
    m = next(mm for name, _, mm in parts if name == prim)
    lo, hi = m.bounds()
    c = (lo + hi) / 2
    grip = (np.array([s.x, s.grip_y, 0]) - c) / STUD
    tip = (np.array([s.x, s.tip_y, 0]) - c) / STUD
    return {"primary": prim, "grip": [round(float(v), 5) for v in grip],
            "tip": [round(float(v), 5) for v in tip],
            "length_studs": round(s.L / STUD, 4)}


def lua_color(c):
    return "Color3.fromRGB(%d, %d, %d)" % tuple(c)


def write_setup(path, sticks, meta):
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "..", "roblox", "DrumSticksSetup.lua"),
               encoding="utf-8").read()
    lines = ["local STICKS = {"]
    for d, s in sticks:
        mt = meta[d["id"]]
        lines.append("\t%s = {" % d["id"])
        lines.append("\t\tname = %s, nameEn = %s," % (json.dumps(d["name"], ensure_ascii=False),
                                                     json.dumps(d["nameEn"])))
        lines.append("\t\tprimary = %s," % json.dumps(mt["primary"]))
        lines.append("\t\tgrip = Vector3.new(%.5f, %.5f, %.5f)," % tuple(mt["grip"]))
        lines.append("\t\ttip = Vector3.new(%.5f, %.5f, %.5f)," % tuple(mt["tip"]))
        lines.append("\t\tpalette = {")
        for key, p in d["palette"].items():
            extra = ""
            if p.get("transparency"):
                extra += ", Transparency = %.2f" % p["transparency"]
            if p.get("glow"):
                extra += ", Glow = true"
            lines.append("\t\t\t%s = { Color = %s, Material = %s, Reflectance = %.2f%s }," % (
                key, lua_color(p["color"]), json.dumps(p["material"]), p["reflectance"], extra))
        lines.append("\t\t},")
        lines.append("\t},")
    lines.append("}")
    marker = "local STICKS = {} -- (filled in by sticks.py)"
    assert marker in tpl
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(tpl.replace(marker, "\n".join(lines)))


MODULE_HEADER = """--[[
	DrumSticks - Beat Drummer のスティック (%(count)d 種) を手に持たせる・叩いたときに光らせる
	※ このファイルは generator/sticks.py が作っています。

	前提: export/sticks/DrumSticks_Setup.lua を実行してできたテンプレート
	      (Folder "DrumSticks" の中の Model "Stick_<ID>") を ReplicatedStorage などに入れておく。

	使い方:
		local DrumSticks = require(ReplicatedStorage.BeatDrummer.DrumSticks)
		local template = DrumSticks.template(ReplicatedStorage.DrumSticks, "SweetRibbon")

		-- サーバー: 演奏するキャラクターに持たせる (全員に見える)
		DrumSticks.attach(character, template)
		DrumSticks.attach(character, template, { tilt = -10, inward = 15, scale = 1.2 })
		DrumSticks.detach(character)

		-- クライアント: ノーツを叩いたとき (見た目だけ)
		DrumSticks.hitLane(character, "SR", 1.0)        -- レーンから叩く手を決めて光らせる
		DrumSticks.hit(DrumSticks.get(character, "Left"), 0.8)

		-- NEON PULSE の光の色を変える
		DrumSticks.setColor(character, DrumSticks.NeonColors.magenta)

	向き:
		スティックは手の GripAttachment の位置で握り、手の正面 (-Z。腕を下ろしたときの前方) に伸びます。
		ゲームの腕のアニメーションに合わせて tilt (上下の角度) と inward (内側への角度) を度で調整してください。
		ずっと同じ値を使うなら DrumSticks.Defaults を書き換えます。

	光る仕組み:
		セットアップで StickGlow 属性が付いたパーツ (飾り・ライン・光る芯) が、叩くと一瞬 Neon になって明るくなります。
]]

local TweenService = game:GetService("TweenService")

local DrumSticks = {}
"""

MODULE_LOGIC = """
-- 手の中での向き (度) と大きさ。ゲームの腕のアニメーションに合わせて調整
DrumSticks.Defaults = { tilt = 0, inward = 0, scale = 1 }

-- レーン -> 叩く手 (BD は足なので無し)。ゲームの持ち手に合わせて変えてください
DrumSticks.HandForLane = {
	HH = "Right", CY = "Left", CR = "Left", SL = "Left", SR = "Right", SN = "Right",
	HT = "Left", LT = "Right", FT = "Right", RD = "Right",
}

local SIDES = { "Right", "Left" }
local HAND_PARTS = {
	Right = { "RightHand", "Right Arm" },
	Left = { "LeftHand", "Left Arm" },
}

function DrumSticks.info(id: string)
	for _, item in ipairs(DrumSticks.List) do
		if item.id == id then
			return item
		end
	end
	return nil
end

function DrumSticks.template(folder: Instance, id: string): Model?
	local m = folder:FindFirstChild("Stick_" .. id)
	return if m and m:IsA("Model") then m else nil
end

local function handOf(character: Model, side: string): BasePart?
	for _, name in ipairs(HAND_PARTS[side]) do
		local h = character:FindFirstChild(name)
		if h and h:IsA("BasePart") then
			return h
		end
	end
	return nil
end

function DrumSticks.get(character: Model, side: string): Model?
	local s = character:FindFirstChild("DrumStick_" .. side)
	return if s and s:IsA("Model") then s else nil
end

function DrumSticks.detach(character: Model)
	for _, side in ipairs(SIDES) do
		local s = DrumSticks.get(character, side)
		if s then
			s:Destroy()
		end
	end
end

-- 両手にスティックを持たせる。戻り値 { Right = Model, Left = Model }
function DrumSticks.attach(character: Model, template: Model, options: { [string]: number }?)
	assert(template and template.PrimaryPart, "DrumSticks.attach: テンプレートに PrimaryPart がありません")
	local o = options or {}
	local tilt = o.tilt or DrumSticks.Defaults.tilt
	local inward = o.inward or DrumSticks.Defaults.inward
	local scale = o.scale or DrumSticks.Defaults.scale
	DrumSticks.detach(character)
	local out = {}
	for _, side in ipairs(SIDES) do
		local hand = handOf(character, side)
		if not hand then
			continue
		end
		local stick = template:Clone()
		stick.Name = "DrumStick_" .. side
		if scale ~= 1 then
			stick:ScaleTo(stick:GetScale() * scale)
		end
		for _, p in ipairs(stick:GetDescendants()) do
			if p:IsA("BasePart") then
				p.Anchored = false
				p.CanCollide = false
				p.CanTouch = false
				p.CanQuery = false
				p.Massless = true
			end
		end
		local prim = stick.PrimaryPart :: BasePart
		local grip = prim:FindFirstChild("Grip") :: Attachment
		local handGrip = hand:FindFirstChild(side .. "GripAttachment")
		local pos = if handGrip and handGrip:IsA("Attachment")
			then handGrip.Position
			else Vector3.new(0, -hand.Size.Y * 0.4, 0)
		local yaw = math.rad(if side == "Right" then inward else -inward)
		local weld = Instance.new("Weld")
		weld.Name = "StickGrip"
		weld.Part0 = hand
		weld.Part1 = prim
		weld.C0 = CFrame.new(pos) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(math.rad(tilt), 0, 0)
		weld.C1 = grip.CFrame
		weld.Parent = prim
		stick:SetAttribute("Side", side)
		stick.Parent = character
		out[side] = stick
	end
	return out
end

local tokens = setmetatable({}, { __mode = "k" })

-- 叩いたときの光 (クライアントで呼ぶ)。strength 0〜1
function DrumSticks.hit(stick: Model?, strength: number?)
	if not stick then
		return
	end
	local k = math.clamp(strength or 1, 0, 1)
	for _, p in ipairs(stick:GetDescendants()) do
		if not (p:IsA("BasePart") and p:GetAttribute("StickGlow")) then
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
		p.Color = (base :: Color3):Lerp(Color3.new(1, 1, 1), 0.5 * k)
		task.delay(0.06, function()
			if tokens[p] ~= token then
				return
			end
			TweenService:Create(p, TweenInfo.new(0.25, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
				Color = base,
			}):Play()
			task.delay(0.25, function()
				if tokens[p] == token then
					p.Material = (Enum.Material :: any)[baseMat]
					tokens[p] = nil
				end
			end)
		end)
	end
end

function DrumSticks.hitLane(character: Model, lane: string, strength: number?)
	local side = DrumSticks.HandForLane[lane]
	if side then
		DrumSticks.hit(DrumSticks.get(character, side), strength)
	end
end

-- 光る芯 (*_Neon パーツ) の色を変える。character でもスティック 1 本でも可
function DrumSticks.setColor(target: Instance, color: Color3)
	for _, p in ipairs(target:GetDescendants()) do
		if p:IsA("BasePart") and p.Name:match("_Neon$") then
			p.Color = color
			p:SetAttribute("BaseColor", color)
		end
	end
end

return DrumSticks
"""


def lua_str(x):
    return json.dumps(x, ensure_ascii=False)


def write_module(path):
    out = [MODULE_HEADER % {"count": len(DESIGNS)}]
    out.append("-- 選べるスティック (ショップや装備画面にそのまま並べられます)")
    out.append("DrumSticks.List = {")
    for d in DESIGNS:
        out.append("\t{ id = %s, name = %s, nameEn = %s, theme = %s,\n\t  desc = %s }," % (
            lua_str(d["id"]), lua_str(d["name"]), lua_str(d["nameEn"]), lua_str(d["theme"]),
            lua_str(d["desc"])))
    out.append("}")
    out.append("")
    out.append("-- NEON PULSE の光の色")
    out.append("DrumSticks.NeonColors = {")
    for k, c in BY_ID["NeonPulse"]["neonColors"].items():
        out.append("\t%s = %s," % (k, lua_color(c)))
    out.append("}")
    out.append(MODULE_LOGIC)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))

def export(out_dir, base="DrumSticks"):
    os.makedirs(out_dir, exist_ok=True)
    sticks = build_all()
    parts = parts_of(sticks)
    write_obj(os.path.join(out_dir, base + ".obj"), base + ".mtl", parts, scale=1 / STUD)
    with open(os.path.join(out_dir, base + ".mtl"), "w") as fh:
        for d, _ in sticks:
            for key, p in d["palette"].items():
                r, g, b = (c / 255 for c in p["color"])
                fh.write("newmtl %s_%s\nKd %.3f %.3f %.3f\nKa 0 0 0\nKs 0.5 0.5 0.5\n"
                         "Ns 200\nd 1\nillum 2\n" % (d["id"], key, r, g, b))
                if key == d["logo"]:
                    fh.write("map_Kd logos/stick_%s.png\n" % d["id"])
    meta = {d["id"]: stick_meta(d, s, parts) for d, s in sticks}
    stats = {"parts": [], "sticks": {}}
    for name, _, m in parts:
        stats["parts"].append({"name": name, "triangles": int(m.ntris)})
    for d, s in sticks:
        tris = sum(p["triangles"] for p in stats["parts"] if p["name"].startswith(d["id"] + "_"))
        nparts = sum(1 for p in stats["parts"] if p["name"].startswith(d["id"] + "_"))
        stats["sticks"][d["id"]] = dict(meta[d["id"]], triangles=tris, parts=nparts)
    with open(os.path.join(out_dir, base + "_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=1, ensure_ascii=False)
    write_setup(os.path.join(out_dir, base + "_Setup.lua"), sticks, meta)
    write_module(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roblox",
                              "DrumSticks.lua"))
    for k, v in stats["sticks"].items():
        print("%-12s %5d tris  %d parts" % (k, v["triangles"], v["parts"]))
    return sticks, parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..",
                                                  "export", "sticks"))
    a = ap.parse_args()
    export(a.out)


if __name__ == "__main__":
    main()
