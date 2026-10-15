"""Procedural metal drum kit for Roblox.

Double bass drums, 3 rack toms, 2 floor toms, snare, hi-hat, a curved
3-sided drum rack with boom arms, crash / ride / china / splash / china stack,
double kick pedals, snare stand and throne.

Run:  python drumkit.py [--detail 1.0] [--out ../export]

Units: metres internally (Y-up, drummer faces +Z while building).  On export
the kit is turned 180 degrees so the drummer faces -Z (Roblox "forward") and
converted to studs (1 stud = 0.28 m).
"""
import argparse
import json
import math
import os

import numpy as np
from shapely import affinity
from shapely.geometry import Point, Polygon

from mesh_lib import (TAU, Mesh, M4, T, Rx, Ry, Rz, Sc, az, apply, apply_dir,
                      chain, circle_poly, cyl_wrap, cylinder, extrude,
                      fillet_path, frame, helix, lathe, rbox, rot_axis,
                      round_poly, sphere, sweep, torus, tube_between, unit,
                      write_obj)

IN = 0.0254
STUD = 0.28          # metres per stud (Roblox avatar scale)
DETAIL = 1.0
MICRO = True         # tiny details (gaskets, chain links, springs...)
FLOOR = 0.0
# maps a shapely polygon (x, y) extruded along z  ->  (x, up=z, forward=y)
P_XZ = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]])


def S(n, lo=6):
    """Segment count scaled by the global detail level (always even)."""
    return max(lo, int(round(n * DETAIL / 2.0)) * 2)


# ---------------------------------------------------------------------------
# kit container
# ---------------------------------------------------------------------------
class Kit:
    def __init__(self):
        self.parts = {}
        self.order = []
        self.meta = {}

    def add(self, comp, mat, mesh, M=None):
        if mesh is None:
            return
        if isinstance(mesh, (list, tuple)):
            for m in mesh:
                self.add(comp, mat, m, M)
            return
        if M is not None:
            mesh = mesh.transformed(M)
        key = (comp, mat)
        if key not in self.parts:
            self.parts[key] = []
            self.order.append(key)
        self.parts[key].append(mesh)

    def merged(self):
        out = []
        for comp, mat in self.order:
            m = Mesh.merge(self.parts[(comp, mat)])
            if m is not None:
                out.append((f"{comp}_{mat}", mat, m))
        return out


class G:
    """A component group with a local frame."""

    def __init__(self, kit, comp, M=None):
        self.kit = kit
        self.comp = comp
        self.M = np.eye(4) if M is None else M

    def add(self, mat, mesh, M=None):
        if isinstance(mesh, (list, tuple)):
            for m in mesh:
                self.add(mat, m, M)
            return
        if M is not None:
            mesh = mesh.transformed(M)
        self.kit.add(self.comp, mat, mesh, self.M)

    def sub(self, M, comp=None):
        return G(self.kit, comp or self.comp, self.M @ M)

    def world(self, p):
        return apply(self.M, p)


# ---------------------------------------------------------------------------
# small hardware pieces (built at the origin, +Y up)
# ---------------------------------------------------------------------------
def wing_nut(r_hub=0.0055, h=0.010, span=0.018):
    hub = lathe([(0, 0), (r_hub, 0), (r_hub, h * 0.55), (r_hub * 0.7, h * 0.7),
                 (0, h * 0.7)], S(16))
    wing = Polygon([(-span, h * 0.95), (-r_hub * 0.6, h * 0.15),
                    (r_hub * 0.6, h * 0.15), (span, h * 0.95),
                    (span * 0.75, h * 1.12), (-span * 0.75, h * 1.12)])
    wing = round_poly(wing, 0.0012)
    w = extrude(wing, 0.0024, z0=-0.0012)
    return [hub, w]


def key_bolt(r=0.0045, h=0.008):
    """Square drum-key head with washer, sitting on y=0, pointing +Y."""
    washer = cylinder(r * 1.35, 0.0012, S(10))
    head = lathe([(0, 0.0012), (r, 0.0012), (r, h - 0.0008), (r * 0.8, h),
                  (0, h)], 4, phase=math.pi / 4, smooth=20)
    return [washer, head]


def t_handle(length=0.03, r=0.003, stem=0.012):
    """T-bolt handle (stem along +Y, bar along Z)."""
    s = cylinder(r * 0.9, stem, S(10))
    bar = cylinder(r, length, S(10), bevel=r * 0.4).transformed(
        chain(T(0, stem, length / 2), Rx(math.pi / 2)))
    return [s, bar]


def hex_nut(r=0.006, h=0.006):
    return lathe([(r * 0.55, 0), (r, 0), (r, h), (r * 0.55, h)], 6,
                 closed=True, smooth=20, phase=math.pi / 6)


def rubber_foot(r=0.012, h=0.035):
    return lathe([(0, 0), (r * 0.85, 0), (r, r * 0.25), (r, h * 0.8),
                  (r * 0.8, h), (0, h)], S(16))


def knurl_knob(r=0.009, h=0.016, n=20):
    prof_r = [(0, 0), (r * 0.9, 0), (r, h * 0.12), (r, h * 0.88),
              (r * 0.9, h), (0, h)]
    m = lathe(prof_r, n * 2, smooth=60)
    # alternate radius around the circumference for a knurled look
    ang = np.arctan2(m.v[:, 2], m.v[:, 0])
    rr = np.hypot(m.v[:, 0], m.v[:, 2])
    k = 1 + 0.06 * np.cos(ang * n) * (rr > r * 0.95)
    m.v[:, 0] *= k
    m.v[:, 2] *= k
    return m


# ---------------------------------------------------------------------------
# drums
# ---------------------------------------------------------------------------
def head_profile(R, yb, th=0.0008):
    yt = yb + th
    return [(0, yb), (R - 0.004, yb), (R + 0.0006, yb - 0.004),
            (R + 0.0006, yb - 0.013), (R + 0.0036, yb - 0.013),
            (R + 0.0036, yt - 0.003), (R + 0.0018, yt - 0.0002),
            (R - 0.006, yt), (0, yt)]


def tf_hoop_profile(R, yt):
    """Triple-flange hoop cross-section (closed, CCW)."""
    rin = R + 0.0045
    tk = 0.0018
    yb = yt - 0.016
    ytop = yt + 0.011
    cx, cy, rb = rin + 0.0011, ytop - 0.0024, 0.0024
    pts = [(rin, yb), (rin + 0.0145, yb), (rin + 0.0145, yb + tk),
           (rin + tk, yb + tk), (rin + tk, ytop - 0.0050)]
    for a in np.radians(np.linspace(-40, 220, 6)):
        pts.append((cx + rb * math.cos(a), cy + rb * math.sin(a)))
    pts.append((rin, ytop - 0.0050))
    return pts, yb + tk


def wood_hoop_profile(R, yt):
    rin, rout = R + 0.0042, R + 0.0175
    yb, ytop = yt - 0.019, yt + 0.011
    c = 0.0022
    return [(rin + c, yb), (rout - c, yb), (rout, yb + c), (rout, ytop - c),
            (rout - c, ytop), (rin + c, ytop), (rin, ytop - c), (rin, yb + c)], \
        (rout, (yb + ytop) / 2)


def tube_lug(R, u, y0, y1, rt, posts):
    seg = S(12)
    chrome = [lathe([(0, y0), (rt - 0.0018, y0), (rt, y0 + 0.0024),
                     (rt, y1 - 0.0024), (rt - 0.0018, y1), (0, y1)], seg)
              .transformed(T(R + u, 0, 0))]
    rubber = []
    for yp in posts:
        chrome.append(tube_between((R - 0.002, yp, 0), (R + u, yp, 0), 0.0045,
                                   S(8)))
        if MICRO:
            rubber.append(tube_between((R - 0.001, yp, 0), (R + 0.0018, yp, 0),
                                       0.0078, S(10)))
    return chrome, rubber


def badge(R, w=0.05, h=0.032):
    ell = affinity.scale(Point(0, 0).buffer(1, quad_segs=8), w / 2, h / 2)
    P = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1.0]])
    plate = cyl_wrap(extrude(ell, 0.0016).transformed(P), R)
    inner = affinity.scale(ell, 0.72, 0.68)
    acc = cyl_wrap(extrude(inner, 0.0009, z0=0.0014).transformed(P), R)
    vent = cyl_wrap(extrude(circle_poly(0, 0, 0.0042, 16), 0.0007,
                            z0=0.0021).transformed(P), R)
    ring = cyl_wrap(extrude(circle_poly(0, 0, 0.0058, 16)
                            .difference(circle_poly(0, 0, 0.0042, 16)),
                            0.001, z0=0.002).transformed(P), R)
    return [plate, ring], [acc], [vent]


def build_drum(kit, comp, D, H, M, nlug, kind, batter="HeadCoated",
               reso="HeadBlack", lug_phase=0.0, badge_phi=None, port=None,
               stripes=True):
    """Generic drum. Local frame: +Y = batter side, origin at drum centre."""
    R = D / 2
    h = H / 2
    seg = S(72 if D > 0.45 else 64 if D > 0.38 else 56 if D > 0.3 else 48)
    g = G(kit, comp, M)
    MIR = Sc(1, -1, 1)

    # shell ------------------------------------------------------------
    t = 0.0075
    g.add("Finish", lathe([(R - t, -h + 0.0012), (R - 0.0016, -h + 0.0012),
                           (R, -h + 0.0028), (R, h - 0.0028),
                           (R - 0.0016, h - 0.0012), (R - t, h - 0.0012)],
                          seg, closed=True))
    if stripes:
        off = 0.06 if kind == "kick" else 0.035
        for yc in (-h + off, h - off):
            w = 0.0032
            g.add("Accent", lathe([(R - 0.0004, yc - w), (R + 0.0012, yc - w),
                                   (R + 0.0012, yc + w), (R - 0.0004, yc + w)],
                                  seg))

    # heads ------------------------------------------------------------
    yb = h - 0.0006
    yt = yb + 0.0008
    top_head = lathe(head_profile(R, yb), seg, closed=True, smooth=35)
    g.add(batter, top_head)
    if port is None:
        g.add(reso, top_head, MIR)
    else:
        # resonant head with offset port hole + logo-ready planar UVs
        px, pz, pr = port
        disk = circle_poly(0, 0, R - 0.003, seg).difference(
            circle_poly(px, pz, pr, S(40)))
        memb = extrude(disk, 0.0008)
        # planar UVs for the logo texture (seen from the front of the kit)
        mv = memb.v[memb.f]
        memb.cuv = np.stack([0.5 - mv[..., 0] / (2 * R),
                             0.5 + mv[..., 1] / (2 * R)], -1)
        Pm = np.array([[1, 0, 0, 0], [0, 0, 1, yb], [0, 1, 0, 0],
                       [0, 0, 0, 1.0]])
        memb = memb.transformed(Pm)
        collar = lathe(head_profile(R, yb)[1:-1], seg, smooth=35)
        g.add(reso, [memb, collar], MIR)
        ring = lathe([(pr - 0.0005, yt - 0.004), (pr + 0.006, yt - 0.004),
                      (pr + 0.008, yt), (pr + 0.006, yt + 0.0035),
                      (pr - 0.0005, yt + 0.0035)], S(40), closed=True)
        g.add("Chrome", ring, chain(MIR, T(px, 0, pz)))

    anchors = {}
    phis = [lug_phase + TAU * k / nlug for k in range(nlug)]

    if kind == "kick":
        prof, (rout, ym) = wood_hoop_profile(R, yt)
        hoop = lathe(prof, seg, closed=True, smooth=35)
        inlay = lathe([(rout - 0.0003, ym - 0.0045), (rout + 0.0012, ym - 0.0045),
                       (rout + 0.0012, ym + 0.0045), (rout - 0.0003, ym + 0.0045)],
                      seg)
        for side in (1, -1):
            Ms = Sc(1, side, 1)
            g.add("Finish", hoop, Ms)
            g.add("Accent", inlay, Ms)
        u = 0.0295
        claw = Polygon([(0.0095, 0.0118), (0.0103, 0.0148), (0.0215, 0.0148),
                        (0.0235, 0.0128), (0.0235, -0.024), (0.0255, -0.026),
                        (0.0345, -0.026), (0.036, -0.0275), (0.036, -0.032),
                        (0.0345, -0.0335), (0.019, -0.0335), (0.0175, -0.032),
                        (0.0175, 0.011)])
        claw_m = extrude(claw, 0.011, z0=-0.0055).transformed(T(R, yt, 0))
        shaft_top = yt - 0.0335
        tube_end = h - 0.052
        rod = tube_between((R + u, tube_end - 0.004, 0),
                           (R + u, shaft_top + 0.002, 0), 0.0028, S(10))
        th = t_handle(0.044, 0.0042, 0.016)
        tparts = [m.transformed(T(R + u, yt - 0.026, 0)) for m in th]
        tparts.append(cylinder(0.0062, 0.0012, S(10)).transformed(
            T(R + u, yt - 0.026, 0)))
        kparts = [m.transformed(T(R + u, yt - 0.026, 0)) for m in key_bolt()]
        lug_c, lug_r = tube_lug(R, u, -tube_end, tube_end, 0.0075,
                                (-h * 0.62, h * 0.62))
        for phi in phis:
            A = az(phi)
            g.add("Chrome", lug_c, A)
            g.add("Rubber", lug_r, A)
            for side in (1, -1):
                Ms = A @ Sc(1, side, 1)
                g.add("Chrome", [claw_m, rod], Ms)
                g.add("Chrome", tparts if side == 1 else kparts, Ms)
    else:
        prof, y_ft = tf_hoop_profile(R, yt)
        hoop = lathe(prof, seg, closed=True, smooth=35)
        g.add("Chrome", hoop)
        g.add("Chrome", hoop, MIR)
        u = 0.0115
        tube_end = h - 0.032
        if tube_end < 0.03:
            tube_end = 0.03
        rod = tube_between((u + R, tube_end - 0.004, 0),
                           (u + R, y_ft + 0.002, 0), 0.0024, S(8))
        kb = [m.transformed(T(R + u, y_ft, 0)) for m in key_bolt()]
        py = min(h * 0.55, tube_end - 0.016)
        lug_c, lug_r = tube_lug(R, u, -tube_end, tube_end, 0.0062, (-py, py))
        for phi in phis:
            A = az(phi)
            g.add("Chrome", lug_c, A)
            g.add("Rubber", lug_r, A)
            for side in (1, -1):
                g.add("Chrome", [rod] + kb, A @ Sc(1, side, 1))

    if badge_phi is not None:
        ch, ac, ru = badge(R + 0.0002)
        A = az(badge_phi)
        g.add("Chrome", ch, A)
        g.add("Accent", ac, A)
        g.add("Rubber", ru, A)

    anchors["R"] = R
    anchors["h"] = h
    anchors["yt"] = yt
    anchors["phis"] = phis
    return g, anchors


def shell_bracket(g, R, phi, y, size=(0.026, 0.05, 0.03), bolt=True):
    """Chrome bracket on the shell at azimuth phi / height y (local)."""
    sr, sy, st = size
    A = az(phi)
    g.add("Chrome", rbox(sr, sy, st, center=(R + sr / 2 - 0.001, y, 0)), A)
    g.add("Rubber", rbox(0.002, sy * 1.15, st * 1.15,
                         center=(R + 0.0005, y, 0)), A)
    if bolt:
        th = t_handle(0.026, 0.0032, 0.012)
        Mb = chain(A, T(R + sr * 0.55, y, st / 2 - 0.001), Rx(math.pi / 2))
        g.add("Chrome", th, Mb)


# ---------------------------------------------------------------------------
# cymbals
# ---------------------------------------------------------------------------
CYM = {
    #           bell_d/D  bell_h  drop   t_c     t_e    lathe
    "crash":  (0.32, 0.026, 0.034, 0.0017, 0.0008, 0.09),
    "ride":   (0.30, 0.033, 0.030, 0.0024, 0.0012, 0.08),
    "splash": (0.34, 0.017, 0.014, 0.0012, 0.0006, 0.09),
    "hihat":  (0.33, 0.022, 0.019, 0.0019, 0.0011, 0.08),
    "china":  (0.30, 0.022, 0.018, 0.0015, 0.0009, 0.035),
}


def cymbal_mesh(D, kind="crash"):
    """Cymbal with bell up.  Origin = underside of the centre hole, +Y = axis.
    Returns (mesh, info)."""
    bd, hb, drop, tc, te, groove = CYM[kind]
    drop *= D / (18 * IN)
    hb *= (D / (18 * IN)) ** 0.5
    R = D / 2
    rh = 0.0066
    rb = bd * D / 2
    china = kind == "china"
    rf = 0.80 * R
    fh = 0.024 * D / (18 * IN)

    def ytop(r):
        r = np.asarray(r, float)
        sb = np.clip((r - rh) / (rb - rh), 0, 1)
        if china:
            bell = hb * (1 - sb ** 7) ** 2.2
            s1 = np.clip((r - rb) / (rf - rb), 0, 1)
            s2 = np.clip((r - rf) / (R - rf), 0, 1)
            bow = -drop * s1 + fh * s2 ** 1.5
        else:
            bell = hb * (1 - sb ** 2.2) ** 1.7
            s = np.clip((r - rb) / (R - rb), 0, 1)
            bow = -drop * (0.55 * s + 0.45 * s * s)
        return np.where(r <= rb, bell, bow)

    def thick(r):
        s = np.clip((r - rh) / (R - rh), 0, 1)
        return tc + (te - tc) * s ** 0.8

    nbell = S(12, 6)
    ring = 0.0068 / max(DETAIL, 0.35)
    nbow = max(8, int((R - rb) / ring))
    if china:
        nb1 = max(6, int(nbow * (rf - rb) / (R - rb)))
        bow_r = np.concatenate([np.linspace(rb, rf, nb1 + 1)[1:],
                                np.linspace(rf, R, nbow - nb1 + 1)[1:]])
    else:
        bow_r = np.linspace(rb, R, nbow + 1)[1:]
    tb = np.linspace(0, 1, nbell + 1)
    bell_r = rh + (rb - rh) * (1 - np.cos(tb * math.pi / 2)) ** 0.85
    radii = np.concatenate([bell_r, bow_r])
    yt = ytop(radii)
    bot_r = radii[::2] if radii[-1] == radii[::2][-1] else np.append(radii[::2], R)
    yb = ytop(bot_r) - thick(bot_r)

    prof = [(r, y) for r, y in zip(bot_r, yb)]
    tilt = [(-1) ** i * groove * 0.7 for i in range(len(bot_r))]
    tilt[0] = tilt[-1] = 0
    prof.append((R + te * 0.35, ytop(R) - te * 0.5))
    tilt.append(0)
    for i, (r, y) in enumerate(zip(radii[::-1], yt[::-1])):
        prof.append((r, y))
        tilt.append(0 if i == 0 else (-1) ** i * groove)
    tilt[-1] = 0
    y0 = yb[0]
    prof = [(r, y - y0) for r, y in prof]
    m = lathe(prof, S(72 if D > 0.44 else 64 if D > 0.38 else 56), closed=True,
              smooth=38, tilt=tilt)
    rr = np.linspace(rh, R, 160)
    info = {"top": float(tc), "edge_top": float(ytop(R) - y0),
            "edge_bot": float(ytop(R) - te - y0), "R": R,
            "r": rr, "top_y": ytop(rr) - y0, "bot_y": ytop(rr) - thick(rr) - y0}
    return m, info


def cym_surfaces(info, base, inverted):
    """Upper / lower surface heights of a mounted cymbal vs radius."""
    if inverted:
        return (info["r"], base + info["top"] - info["bot_y"],
                base + info["top"] - info["top_y"])
    return info["r"], base + info["top_y"], base + info["bot_y"]


def cymbal_holder(g, stack, base_felt=True):
    """Cymbal(s) on a holder rod.  g's frame: origin at top of bottom felt,
    +Y along rod.  stack = list of (comp, mesh, info, inverted, material)."""
    seg = S(20)
    # cup washer + bottom felt
    g.add("Chrome", lathe([(0.0042, -0.0155), (0.017, -0.0155), (0.019, -0.011),
                           (0.0175, -0.0105), (0.0042, -0.0122)], seg,
                          closed=True))
    g.add("Felt", cylinder(0.0165, 0.0105, seg, y0=-0.0105, bevel=0.0015))
    y = 0.0          # top of the felt below the current cymbal
    prev = None
    for i, (comp, mesh, info, inverted, mat) in enumerate(stack):
        base = y
        if prev is not None:
            # lift the cymbal until it clears the one below it everywhere
            r1, top1 = prev
            r2, _, bot2 = cym_surfaces(info, 0.0, inverted)
            rs = np.linspace(0.012, min(r1[-1], r2[-1]), 120)
            need = float(np.max(np.interp(rs, r1, top1) + 0.003 -
                                np.interp(rs, r2, bot2)))
            base = max(need, y + 0.004)
            g.add("Felt", cylinder(0.0155, base - y, seg, y0=y, bevel=0.0015))
        if inverted:
            Mc = chain(T(0, base + info["top"], 0), Rx(math.pi))
        else:
            Mc = T(0, base, 0)
        gc = g.sub(Mc, comp)
        gc.add(mat, mesh)
        r, top_s, _ = cym_surfaces(info, base, inverted)
        prev = (r, top_s)
        y = base + info["top"]
    g.add("Felt", cylinder(0.0155, 0.0095, seg, y0=y, bevel=0.0015))
    y += 0.0095
    g.add("Chrome", wing_nut(0.0058, 0.011, 0.017), T(0, y, 0))
    g.add("Rubber", cylinder(0.0054, y + 0.012, S(12), y0=-0.012))
    g.add("Chrome", cylinder(0.0042, y + 0.034, S(10), y0=-0.07, bevel=0.001))


# ---------------------------------------------------------------------------
# stands & hardware
# ---------------------------------------------------------------------------
def tripod(g, cx, cz, collar_y, foot_r, leg_r, az_deg, tube_r, brace=True,
           mat_leg="Chrome"):
    """Double-braced tripod base around a vertical tube at (cx, cz)."""
    c = np.array([cx, 0, cz])
    seg = S(14)
    g.add("BlackMetal", lathe([(tube_r + 0.001, collar_y - 0.024),
                               (tube_r + 0.010, collar_y - 0.024),
                               (tube_r + 0.012, collar_y - 0.018),
                               (tube_r + 0.012, collar_y + 0.018),
                               (tube_r + 0.010, collar_y + 0.024),
                               (tube_r + 0.001, collar_y + 0.024)], S(20),
                              closed=True), T(cx, 0, cz))
    low_y = collar_y * 0.42
    if brace:
        g.add("BlackMetal", lathe([(tube_r + 0.001, low_y - 0.016),
                                   (tube_r + 0.008, low_y - 0.016),
                                   (tube_r + 0.009, low_y + 0.016),
                                   (tube_r + 0.001, low_y + 0.016)], S(20),
                                  closed=True), T(cx, 0, cz))
    for a in az_deg:
        d = np.array([math.sin(math.radians(a)), 0, math.cos(math.radians(a))])
        top = c + d * (tube_r + 0.014) + np.array([0, collar_y, 0])
        foot = c + d * foot_r + np.array([0, 0.026, 0])
        g.add(mat_leg, tube_between(top, foot, leg_r, seg))
        ldir = unit(foot - top)
        # hinge knuckle
        g.add("BlackMetal", rbox(0.016, 0.03, 0.022,
                                 center=(0, 0, 0)), frame(top, ldir, d))
        g.add("Rubber", rubber_foot(leg_r * 1.6, 0.04).transformed(
            frame(foot + ldir * 0.012, -ldir)))
        if brace:
            p = top + (foot - top) * 0.55
            b0 = c + d * (tube_r + 0.009) + np.array([0, low_y, 0])
            g.add(mat_leg, tube_between(b0, p, leg_r * 0.62, S(10)))
            g.add("BlackMetal", rbox(0.012, 0.018, 0.016), frame(p, ldir, d))


def memory_lock(g, p, r, h=0.022):
    g.add("BlackMetal", lathe([(r + 0.0005, -h / 2), (r + 0.008, -h / 2),
                               (r + 0.009, -h / 2 + 0.003),
                               (r + 0.009, h / 2), (r + 0.0005, h / 2)],
                              S(18), closed=True), T(*p))
    g.add("Chrome", key_bolt(0.0035, 0.007), chain(T(*p), Rz(-math.pi / 2),
                                                    T(0, r + 0.008, 0)))


def height_clamp(g, p, r_in, r_out):
    """Tube height-adjust joint with a wing bolt."""
    x, y, z = p
    g.add("BlackMetal", lathe([(r_in, y - 0.004), (r_out + 0.009, y - 0.004),
                               (r_out + 0.009, y + 0.028), (r_in + 0.004, y + 0.03),
                               (r_in, y + 0.03)], S(20), closed=True),
          T(x, 0, z))
    g.add("Chrome", wing_nut(0.005, 0.01, 0.014),
          chain(T(x, y + 0.013, z), Rz(-math.pi / 2), T(0, r_out + 0.008, 0)))


def build_throne(kit, cx, cz, seat_h=0.565):
    g = G(kit, "Throne")
    tripod(g, cx, cz, 0.24, 0.32, 0.0105, (60, 180, 300), 0.02)
    g.add("BlackMetal", cylinder(0.02, 0.36, S(20), y0=0.12, bevel=0.002),
          T(cx, 0, cz))
    # threaded spindle
    n = S(40, 16)
    prof = [(0.0115 + (0.0012 if i % 2 else 0), 0.40 + i * 0.0025)
            for i in range(n)]
    prof = [(0, 0.40)] + prof + [(0, prof[-1][1])]
    g.add("Chrome", lathe(prof, S(16), smooth=70), T(cx, 0, cz))
    memory_lock(g, (cx, 0.47, cz), 0.0125, 0.024)
    g.add("Chrome", cylinder(0.0205, 0.012, S(20), y0=0.475), T(cx, 0, cz))
    # seat plate + cushion
    g.add("BlackMetal", lathe([(0, seat_h - 0.105), (0.13, seat_h - 0.105),
                               (0.135, seat_h - 0.095), (0, seat_h - 0.095)],
                              S(32)), T(cx, 0, cz))
    g.add("BlackMetal", cylinder(0.03, seat_h - 0.105 - 0.48, S(20), y0=0.48),
          T(cx, 0, cz))
    R = 0.195
    prof = [(0, seat_h - 0.095), (R - 0.02, seat_h - 0.095),
            (R - 0.004, seat_h - 0.088), (R, seat_h - 0.072),
            (R, seat_h - 0.024)]
    for a in np.linspace(0, 90, 7)[1:]:
        ar = math.radians(a)
        prof.append((R - 0.022 + 0.022 * math.cos(ar),
                     seat_h - 0.024 + 0.022 * math.sin(ar) - 0.0))
    prof += [(R * 0.6, seat_h + 0.004), (0, seat_h + 0.008)]
    g.add("Leather", lathe(prof, S(48)), T(cx, 0, cz))
    # red piping on the top seam and bottom seam
    g.add("Accent", torus(R - 0.0045, 0.0032, S(48), S(8)),
          T(cx, seat_h - 0.012, cz))
    g.add("Accent", torus(R + 0.0005, 0.0028, S(48), S(8)),
          T(cx, seat_h - 0.074, cz))
    return np.array([cx, seat_h, cz])


def build_snare_stand(kit, cx, cz, top_y, axis):
    """Snare basket stand. top_y = height of the basket arms."""
    g = G(kit, "SnareStand")
    tripod(g, cx, cz, 0.20, 0.23, 0.0095, (0, 120, 240), 0.0125)
    g.add("Chrome", cylinder(0.0125, 0.30, S(16), y0=0.16, bevel=0.002),
          T(cx, 0, cz))
    height_clamp(g, (cx, 0.455, cz), 0.0095, 0.0125)
    tilt_y = top_y - 0.075
    g.add("Chrome", cylinder(0.0095, tilt_y - 0.46, S(14), y0=0.46),
          T(cx, 0, cz))
    # ratchet tilter
    Mt = chain(T(cx, tilt_y, cz))
    g.add("BlackMetal", cylinder(0.021, 0.024, S(24), y0=-0.012, bevel=0.002),
          chain(Mt, Rz(math.pi / 2)))
    g.add("Chrome", t_handle(0.03, 0.0032, 0.016),
          chain(Mt, Rz(-math.pi / 2), T(0, 0.012, 0)))
    # basket (rotated to the snare axis)
    Mb = frame(np.array([cx, tilt_y, cz]), axis, (1, 0, 0))
    gb = g.sub(Mb)
    gb.add("Chrome", cylinder(0.010, 0.05, S(14), y0=0.0))
    gb.add("BlackMetal", lathe([(0, 0.035), (0.024, 0.035), (0.026, 0.05),
                                (0.022, 0.062), (0, 0.062)], S(20)))
    for k, a in enumerate((90, 210, 330)):
        d = np.array([math.cos(math.radians(a)), 0, math.sin(math.radians(a))])
        p0 = np.array([0, 0.052, 0]) + d * 0.02
        p1 = np.array([0, 0.062, 0]) + d * 0.135
        p2 = np.array([0, 0.088, 0]) + d * 0.168
        path = fillet_path([p0, p1, p2], 0.02, 6)
        gb.add("Chrome", sweep(path, 0.0055, S(10)))
        gb.add("Rubber", tube_between(p1 + (p2 - p1) * 0.45, p2 + unit(p2 - p1)
                                      * 0.006, 0.0085, S(12), bevel=0.002))


def build_hihat(kit, cx, cz, bottom_y):
    """Hi-hat stand + cymbals. bottom_y = height of the bottom-hat seat."""
    g = G(kit, "HiHat_Stand")
    tube_r = 0.0135
    tripod(g, cx, cz, 0.33, 0.27, 0.0095, (90, 210, 330), tube_r)
    # pedal (toward -Z)
    gp = g.sub(T(cx, 0, cz))
    gp.add("BlackMetal", rbox(0.10, 0.008, 0.40, center=(0, 0.004, -0.18)))
    gp.add("Rubber", rbox(0.11, 0.003, 0.05, center=(0, 0.0015, -0.355)))
    for sx in (-1, 1):
        prof = Polygon([(-0.03, 0.006), (0.03, 0.006), (0.012, 0.15),
                        (-0.012, 0.15)])
        post = extrude(round_poly(prof, 0.004), 0.01, z0=-0.005)
        gp.add("BlackMetal", post, chain(T(sx * 0.047, 0, -0.005),
                                         Ry(math.pi / 2)))
        # spring housings
        gp.add("Chrome", cylinder(0.0105, 0.16, S(16), y0=0.14, bevel=0.002),
               T(sx * 0.047, 0, -0.005))
        gp.add("BlackMetal", cylinder(0.0125, 0.012, S(16), y0=0.295,
                                      bevel=0.002), T(sx * 0.047, 0, -0.005))
    gp.add("BlackMetal", rbox(0.11, 0.022, 0.03, center=(0, 0.30, -0.005)))
    gp.add("BlackMetal", rbox(0.11, 0.02, 0.026, center=(0, 0.148, -0.005)))
    # footboard
    toe = np.array([0, 0.075, -0.045])
    heel = np.array([0, 0.022, -0.31])
    fl = np.linalg.norm(toe - heel)
    ang = math.atan2(toe[1] - heel[1], toe[2] - heel[2])
    fb = Polygon([(-0.034, 0), (0.034, 0), (0.04, fl - 0.03), (0.03, fl),
                  (-0.03, fl), (-0.04, fl - 0.03)])
    fbm = extrude(round_poly(fb, 0.006), 0.007, z0=-0.007)
    Mf = chain(T(*heel), Rx(-ang), P_XZ)
    gp.add("BlackMetal", fbm, Mf)
    for k in range(7):
        gp.add("Chrome", rbox(0.05, 0.004, 0.0035,
                              center=(0, 0.002, 0.06 + k * 0.022)),
               chain(T(*heel), Rx(-ang)))
    gp.add("Accent", rbox(0.012, 0.0016, fl * 0.7, center=(0, 0.0008, fl * 0.5)),
           chain(T(*heel), Rx(-ang), T(0, 0.001, 0)))
    gp.add("BlackMetal", rbox(0.075, 0.012, 0.06, center=(0, 0.012, -0.34)))
    gp.add("Chrome", tube_between((-0.04, 0.022, -0.31), (0.04, 0.022, -0.31),
                                  0.006, S(12)))
    # linkage from toe up to the pull rod
    gp.add("Chrome", tube_between(toe + np.array([0, 0.004, 0.002]),
                                  np.array([0, 0.148, -0.005]), 0.004, S(8)))
    # tubes
    g.add("Chrome", cylinder(tube_r, 0.68 - 0.16, S(18), y0=0.16, bevel=0.002),
          T(cx, 0, cz))
    height_clamp(g, (cx, 0.68, cz), 0.0098, tube_r)
    memory_lock(g, (cx, 0.73, cz), 0.0098)
    g.add("Chrome", cylinder(0.0098, bottom_y - 0.02 - 0.68, S(16), y0=0.68),
          T(cx, 0, cz))
    # bottom cymbal seat cup with felt
    g.add("BlackMetal", lathe([(0.004, bottom_y - 0.03), (0.014, bottom_y - 0.03),
                               (0.024, bottom_y - 0.012), (0.024, bottom_y - 0.009),
                               (0.004, bottom_y - 0.009)], S(20), closed=True),
          T(cx, 0, cz))
    g.add("Felt", cylinder(0.021, 0.009, S(20), y0=bottom_y - 0.009,
                           bevel=0.0015), T(cx, 0, cz))
    # cymbals: bottom hat bell-down, top hat bell-up with clutch
    bot, ib = cymbal_mesh(14 * IN, "hihat")
    top, it = cymbal_mesh(14 * IN, "hihat")
    gb = G(kit, "HiHat_Bottom", T(cx, bottom_y + ib["top"], cz))
    gb.add("Bronze", bot, Rx(math.pi))
    # bottom hat edge height (flipped): bell side down
    edge_b = bottom_y + ib["top"] - ib["edge_bot"]
    gap = 0.014
    top_seat = edge_b + gap - it["edge_bot"]
    gt = G(kit, "HiHat_Top", T(cx, top_seat, cz))
    gt.add("Bronze", top)
    # clutch
    gt.add("Felt", cylinder(0.0165, 0.009, S(20), y0=-0.009, bevel=0.0015))
    gt.add("Chrome", lathe([(0.0045, -0.03), (0.011, -0.03), (0.012, -0.024),
                            (0.012, -0.009), (0.0045, -0.009)], S(18),
                           closed=True))
    gt.add("Chrome", key_bolt(0.0032, 0.007), chain(T(0, -0.021, 0),
                                                   Rz(-math.pi / 2),
                                                   T(0, 0.011, 0)))
    gt.add("Felt", cylinder(0.0165, 0.009, S(20), y0=it["top"], bevel=0.0015))
    gt.add("Chrome", hex_nut(0.0085, 0.008), T(0, it["top"] + 0.009, 0))
    gt.add("Chrome", hex_nut(0.0085, 0.008), T(0, it["top"] + 0.019, 0))
    # pull rod
    g.add("Chrome", cylinder(0.0035, top_seat + 0.09 - (bottom_y - 0.02), S(10),
                             y0=bottom_y - 0.02, bevel=0.001), T(cx, 0, cz))


def build_pedal(kit, comp, px, side):
    """Single bass drum pedal at x=px. side=+1 puts the spring on +X."""
    g = G(kit, comp, T(px, 0, 0))
    seg = S(16)
    # base plate & heel
    base = Polygon([(-0.052, -0.225), (0.052, -0.225), (0.056, 0.12),
                    (0.05, 0.19), (-0.05, 0.19), (-0.056, 0.12)])
    base = round_poly(base, 0.008).difference(
        round_poly(Polygon([(-0.025, -0.12), (0.025, -0.12), (0.025, 0.04),
                            (-0.025, 0.04)]), 0.008))
    g.add("BlackMetal", extrude(base, 0.006), P_XZ)
    for x, z in ((-0.045, -0.21), (0.045, -0.21), (-0.045, 0.17), (0.045, 0.17)):
        g.add("Rubber", cylinder(0.008, 0.003, S(12), y0=-0.0025), T(x, 0, z))
    g.add("BlackMetal", rbox(0.078, 0.012, 0.055, center=(0, 0.012, -0.195)))
    g.add("Chrome", tube_between((-0.04, 0.022, -0.168), (0.04, 0.022, -0.168),
                                 0.0055, S(12)))
    # footboard
    heel = np.array([0, 0.022, -0.168])
    toe = np.array([0, 0.096, 0.072])
    fl = np.linalg.norm(toe - heel)
    ang = math.atan2(toe[1] - heel[1], toe[2] - heel[2])
    fb = Polygon([(-0.032, 0), (0.032, 0), (0.043, fl - 0.04), (0.038, fl),
                  (-0.038, fl), (-0.043, fl - 0.04)])
    Mf = chain(T(*heel), Rx(-ang))
    g.add("BlackMetal", extrude(round_poly(fb, 0.007), 0.008, z0=-0.008),
          Mf @ P_XZ)
    # grip: chrome studs + red racing stripe + toe stop
    for k in range(9):
        g.add("Chrome", rbox(0.054 + 0.002 * k, 0.003, 0.004,
                             center=(0, 0.0015, 0.05 + k * 0.02)), Mf)
    g.add("Accent", rbox(0.010, 0.0014, fl * 0.62, center=(0, 0.0007,
                                                           fl * 0.55)), Mf)
    g.add("BlackMetal", rbox(0.07, 0.012, 0.012, center=(0, 0.004, fl - 0.008)),
          Mf)
    # hoop clamp under the batter hoop
    g.add("BlackMetal", rbox(0.105, 0.012, 0.06, center=(0, 0.006, 0.152)))
    g.add("BlackMetal", rbox(0.105, 0.03, 0.012, center=(0, 0.018, 0.177)))
    g.add("Chrome", t_handle(0.028, 0.0034, 0.02),
          chain(T(0.054 * side, 0.016, 0.155), Rz(-side * math.pi / 2)))
    # frame posts
    prof = Polygon([(0.068, 0.006), (0.13, 0.006), (0.118, 0.13),
                    (0.092, 0.13)])
    prof = round_poly(prof.union(circle_poly(0.105, 0.145, 0.016, 20)), 0.003)
    post = extrude(prof, 0.011, z0=-0.0055)
    for sx in (-1, 1):
        g.add("BlackMetal", post, chain(T(sx * 0.048, 0, 0), Ry(-math.pi / 2)))
        g.add("Chrome", cylinder(0.0115, 0.006, S(18), bevel=0.001),
              chain(T(sx * 0.0535, 0.145, 0.105), Rz(-sx * math.pi / 2)))
    axle_y, axle_z = 0.145, 0.105
    g.add("Chrome", tube_between((-0.066, axle_y, axle_z), (0.066, axle_y, axle_z),
                                 0.0045, S(10)))
    # cam / sprocket
    cam = lathe([(0.005, -0.007), (0.024, -0.007), (0.026, -0.005),
                 (0.026, 0.005), (0.024, 0.007), (0.005, 0.007)], S(28),
                closed=True)
    g.add("Chrome", cam, chain(T(0, axle_y, axle_z), Rz(math.pi / 2)))
    # chain links: up from the toe, over the back of the cam
    pts = [np.array([0, 0.098, 0.081]), np.array([0, axle_y, 0.081])]
    for a in np.linspace(180, 95, 4):
        ar = math.radians(a)
        pts.append(np.array([0, axle_y + 0.026 * math.sin(ar),
                             axle_z + 0.026 * math.cos(ar)]))
    path = []
    for i in range(len(pts) - 1):
        L = np.linalg.norm(pts[i + 1] - pts[i])
        n = max(1, int(L / 0.009))
        for s in np.linspace(0, 1, n, endpoint=False):
            path.append(pts[i] + (pts[i + 1] - pts[i]) * s)
    path.append(pts[-1])
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        mid = (a + b) / 2
        d = unit(b - a)
        L = np.linalg.norm(b - a) + 0.003
        w = 0.0105 if i % 2 else 0.0078
        g.add("Chrome", rbox(w, L, 0.003, bevel=0.0012),
              frame(mid, d, (1, 0, 0)))
    # spring assembly on the outer side
    sx = 0.064 * side
    g.add("Chrome", rbox(0.007, 0.012, 0.042, center=(0, 0, -0.012)),
          T(sx, axle_y, axle_z))
    g.add("Chrome", helix(0.0065, 0.0042, 16, 0.0011, S(12, 8), 6),
          T(sx, 0.056, axle_z - 0.03))
    g.add("Chrome", cylinder(0.0022, 0.05, S(8), y0=0.008),
          T(sx, 0, axle_z - 0.03))
    g.add("Chrome", hex_nut(0.0065, 0.006), T(sx, 0.038, axle_z - 0.03))
    g.add("BlackMetal", rbox(0.014, 0.012, 0.02, center=(sx, 0.012,
                                                          axle_z - 0.03)))
    # beater (separate component so it can be animated)
    gb = G(kit, comp + "_Beater", chain(T(px, axle_y, axle_z), Rx(-0.55)))
    gb.add("Chrome", rbox(0.022, 0.03, 0.024, center=(0, 0.004, 0)))
    gb.add("Chrome", key_bolt(0.003, 0.006), chain(T(0, 0.006, 0.012),
                                                   Rx(math.pi / 2)))
    gb.add("Chrome", cylinder(0.0036, 0.19, S(10), y0=0.0))
    gb.add("Chrome", cylinder(0.0055, 0.008, S(12), y0=0.13))
    head = chain(T(0, 0.185, 0), Rx(math.pi / 2))
    gb.add("BlackMetal", lathe([(0, -0.03), (0.022, -0.03), (0.026, -0.022),
                                (0.026, 0.0), (0, 0.0)], S(24)), head)
    gb.add("HeadCoated", lathe([(0, 0.0), (0.026, 0.0), (0.026, 0.024),
                                (0.02, 0.031), (0, 0.033)], S(24)), head)


def build_rack(kit, y=0.80):
    """Curved 3-sided rack.  Returns helpers to locate clamps."""
    g = G(kit, "Rack")
    r = 0.019
    seg = S(24)
    zc, Ra = -0.75, 1.25
    a_end = math.asin(0.70 / Ra)
    arc = [np.array([Ra * math.sin(a), y, zc + Ra * math.cos(a)])
           for a in np.linspace(-a_end, a_end, S(44, 16))]
    g.add("Chrome", sweep(arc, r, seg, caps=True))
    left0, right0 = arc[0], arc[-1]
    left1 = np.array([-1.15, y, -0.05])
    right1 = np.array([1.40, y, 0.10])
    wings = [(left0, left1), (right0, right1)]
    for a, b in wings:
        d = unit(b - a)
        g.add("Chrome", tube_between(a + d * 0.03, b + d * 0.04, r, seg))
        g.add("Rubber", tube_between(b + d * 0.04, b + d * 0.065, r + 0.0015,
                                     seg, bevel=0.004))
    legs = [left0, right0, left1, right1]
    foot_dirs = [unit(np.cross(unit(left1 - left0), [0, 1, 0])),
                 unit(np.cross(unit(right1 - right0), [0, 1, 0])),
                 unit(np.cross(unit(left1 - left0), [0, 1, 0])),
                 unit(np.cross(unit(right1 - right0), [0, 1, 0]))]
    for p, fd in zip(legs, foot_dirs):
        base = np.array([p[0], 0, p[2]])
        g.add("Chrome", tube_between(base + [0, 0.04, 0], p + [0, 0.07, 0], r,
                                     seg))
        g.add("Rubber", cylinder(r + 0.002, 0.012, seg, bevel=0.003),
              T(p[0], y + 0.07, p[2]))
        # joint clamp around the leg at bar height
        g.add("BlackMetal", lathe([(r + 0.001, y - 0.045), (r + 0.012, y - 0.045),
                                   (r + 0.015, y - 0.04), (r + 0.015, y + 0.04),
                                   (r + 0.012, y + 0.045), (r + 0.001, y + 0.045)],
                                  S(24), closed=True), T(p[0], 0, p[2]))
        g.add("Chrome", t_handle(0.034, 0.0038, 0.016),
              chain(T(p[0], y + 0.02, p[2]),
                    M4(frame((0, 0, 0), -fd)[:3, :3]), T(0, r + 0.014, 0)))
        # T-foot
        f0 = base + fd * 0.17 + [0, 0.02, 0]
        f1 = base - fd * 0.17 + [0, 0.02, 0]
        g.add("Chrome", tube_between(f0, f1, 0.0155, seg))
        for q, dd in ((f0, fd), (f1, -fd)):
            g.add("Rubber", tube_between(q - dd * 0.005, q + dd * 0.025, 0.0175,
                                         seg, bevel=0.004))
        g.add("BlackMetal", rbox(0.06, 0.07, 0.06, center=(0, 0.035, 0),
                                 bevel=0.008), T(base[0], 0.0, base[2]))
    # sockets where bars enter the corner clamps
    for p, q in ((left0, left1), (right0, right1)):
        d = unit(q - p)
        g.add("BlackMetal", rbox(0.05, 0.05, 0.06, bevel=0.007),
              frame(p + d * 0.045, d, (0, 1, 0)))
    for p, q in ((left0, arc[1]), (right0, arc[-2])):
        d = unit(q - p)
        g.add("BlackMetal", rbox(0.05, 0.05, 0.06, bevel=0.007),
              frame(p + d * 0.045, d, (0, 1, 0)))

    def arc_point(x):
        z = zc + math.sqrt(Ra * Ra - x * x)
        p = np.array([x, y, z])
        t = unit(np.array([1.0, 0, -x / (z - zc)]))
        return p, t

    def wing_point(which, t):
        a, b = wings[0] if which == "L" else wings[1]
        return a + (b - a) * t, unit(b - a)

    return g, arc_point, wing_point


def rack_clamp(g, p, tdir, post_dir_xz, post_r=0.011):
    """Multi-clamp on a rack tube at p.  Returns centre of the post hole."""
    r = 0.019
    side = unit(np.array([post_dir_xz[0], 0, post_dir_xz[2]]))
    side = unit(side - np.dot(side, tdir) * tdir)
    g.add("BlackMetal", rbox(0.056, 0.058, 0.06, bevel=0.008),
          frame(p, tdir, (0, 1, 0)))
    pc = p + side * (r + post_r + 0.012)
    g.add("BlackMetal", rbox(0.044, 0.07, 0.044, bevel=0.007), frame(pc, (0, 1, 0),
                                                                    side))
    g.add("Chrome", t_handle(0.03, 0.0036, 0.014),
          chain(M4(frame(p + np.array([0, 0.029, 0]), (0, 1, 0), tdir)[:3, :3],
                   t=p + np.array([0, 0.029, 0]))))
    g.add("Chrome", key_bolt(0.0036, 0.007),
          chain(M4(frame((0, 0, 0), side)[:3, :3], t=pc + side * 0.022)))
    return pc


def ratchet(g, p, axis, r=0.022, w=0.012, mat="BlackMetal"):
    M = frame(p, axis)
    g.add(mat, cylinder(r, w, S(24), y0=-w, bevel=0.002), M)
    g.add(mat, cylinder(r, w, S(24), y0=0.0005, bevel=0.002), M)
    g.add("Chrome", wing_nut(0.0055, 0.01, 0.016), chain(M, T(0, w, 0)))


def build_boom(kit, comp, rack, attach, cym_origin, cym_axis, post_h=None):
    """Rack-mounted cymbal boom.  attach=(point, tube_dir)."""
    g = G(kit, comp)
    p, tdir = attach
    pc = rack_clamp(g, p, tdir, cym_origin - p)
    E = cym_origin - cym_axis * 0.075
    if post_h is None:
        post_h = max(0.10, (E[1] - p[1]) * 0.35)
    Tp = np.array([pc[0], p[1] + post_h, pc[2]])
    g.add("Chrome", cylinder(0.011, Tp[1] - 0.022 - (p[1] - 0.05), S(16),
                             y0=p[1] - 0.05, bevel=0.002),
          T(pc[0], 0, pc[2]))
    memory_lock(g, (pc[0], p[1] + 0.05, pc[2]), 0.011)
    bdir = unit(E - Tp)
    pax = np.cross(bdir, [0, 1, 0])
    if np.linalg.norm(pax) < 1e-3:
        pax = np.array([1.0, 0, 0])
    pax = unit(pax)
    ratchet(g, Tp, pax)
    g.add("Chrome", tube_between(Tp - bdir * 0.09, E, 0.0082, S(14)))
    g.add("Chrome", cylinder(0.014, 0.05, S(18), bevel=0.003),
          frame(Tp - bdir * 0.12, bdir))
    g.add("Rubber", cylinder(0.0143, 0.006, S(18), bevel=0.002),
          frame(Tp - bdir * 0.126, bdir))
    # end tilter
    ratchet(g, E, pax, 0.014, 0.009)
    return g


def tom_arm(kit, comp, rack_pt, tdir, recv, recv_dir):
    """L-arm from a rack clamp to a tom receiver."""
    g = G(kit, comp)
    pc = rack_clamp(g, rack_pt, tdir, recv - rack_pt, 0.0064)
    up = np.array([pc[0], recv[1], pc[2]])
    path = fillet_path([np.array([pc[0], rack_pt[1] - 0.05, pc[2]]), up,
                        recv - recv_dir * 0.01], 0.05, 10)
    g.add("Chrome", sweep(path, 0.0064, S(12)))
    memory_lock(g, (pc[0], rack_pt[1] + 0.05, pc[2]), 0.0064)
    return g


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
DRUMMER = np.array([0.0, 1.25, -0.62])


def cym_axis(center, tilt_deg):
    d = DRUMMER - center
    d[1] = 0
    d = unit(d)
    a = math.radians(tilt_deg)
    return unit(np.array([0, math.cos(a), 0]) + d * math.sin(a))


def tom_axis(center, tilt_deg):
    return cym_axis(center, tilt_deg)


def build_kit(detail=1.0):
    global DETAIL, MICRO
    DETAIL = detail
    MICRO = detail >= 0.75
    kit = Kit()

    # --- bass drums ---------------------------------------------------
    kD, kH = 22 * IN, 18 * IN
    kR = kD / 2
    z_batter = 0.15
    ky = kR + 0.0175 + 0.012
    for comp, kx in (("Kick_L", -0.335), ("Kick_R", 0.335)):
        c = np.array([kx, ky, z_batter + kH / 2])
        M = frame(c, (0, 0, -1), (1, 0, 0))
        port = (0.12 * (1 if kx > 0 else -1), -0.13, 0.06)
        g, an = build_drum(kit, comp, kD, kH, M, 10, "kick", reso="HeadLogo",
                           lug_phase=0.0, badge_phi=math.radians(18 + 36 * 2),
                           port=port)
        # spurs
        for phi in (math.radians(198), math.radians(342)):
            yloc = -kH / 2 + 0.10
            shell_bracket(g, kR, phi, yloc, (0.03, 0.06, 0.034))
            p0 = g.world(np.array([(kR + 0.026) * math.cos(phi), yloc,
                                   (kR + 0.026) * math.sin(phi)]))
            out = np.sign(math.cos(phi))
            p1 = p0 + np.array([out * 0.05, -0.02, 0.02])
            foot = np.array([kx + out * (kR + 0.12), 0.03, c[2] + kH / 2 + 0.06])
            path = fillet_path([p0, p1, foot], 0.05, 8)
            kit.add(comp, "Chrome", sweep(path, 0.0068, S(14)))
            fd = unit(foot - p1)
            kit.add(comp, "Rubber",
                    rubber_foot(0.0105, 0.04).transformed(frame(foot + fd * 0.004,
                                                                -fd)))
        build_pedal(kit, "Pedal_" + comp[-1], kx, 1 if kx > 0 else -1)

    # --- rack -----------------------------------------------------------
    rack_g, arc_point, wing_point = build_rack(kit)

    # --- rack toms ------------------------------------------------------
    toms = [("Tom_10", 10 * IN, 8 * IN, np.array([-0.33, 0.905, 0.20]), 6),
            ("Tom_12", 12 * IN, 9 * IN, np.array([0.035, 0.935, 0.25]), 6),
            ("Tom_13", 13 * IN, 10 * IN, np.array([0.40, 0.905, 0.20]), 6)]
    for comp, D, H, c, n in toms:
        ax = tom_axis(c, 18)
        M = frame(c, ax, (1, 0, 0))
        # find the azimuth that faces the rack (+Z world)
        Minv = np.linalg.inv(M)
        dz = apply_dir(Minv, (0, 0, 1))
        phi_m = math.atan2(dz[2], dz[0])
        g, an = build_drum(kit, comp, D, H, M, n, "tom",
                           lug_phase=phi_m + math.pi / n,
                           badge_phi=phi_m + math.pi)
        R = D / 2
        ym = -H * 0.18
        shell_bracket(g, R, phi_m, ym, (0.028, 0.05, 0.036), bolt=False)
        recv_l = np.array([(R + 0.045) * math.cos(phi_m), ym,
                           (R + 0.045) * math.sin(phi_m)])
        g.add("Chrome", rbox(0.034, 0.03, 0.03, center=(0, 0, 0)),
              chain(az(phi_m), T(R + 0.04, ym, 0)))
        g.add("Chrome", wing_nut(0.005, 0.01, 0.014),
              chain(az(phi_m), T(R + 0.04, ym + 0.015, 0)))
        recv = g.world(recv_l)
        rp, rt = arc_point(c[0])
        tom_arm(kit, "TomArm_" + comp[4:], rp, rt, recv,
                unit(np.array([recv[0] - rp[0], 0, recv[2] - rp[2]])))

    # --- floor toms ------------------------------------------------------
    for comp, D, H, cx, cz, top, legs in (
            ("FloorTom_16", 16 * IN, 16 * IN, 0.62, -0.20, 0.625, (0, 120, 240)),
            ("FloorTom_18", 18 * IN, 16 * IN, 1.10, -0.45, 0.645, (60, 180, 300))):
        c = np.array([cx, top - H / 2, cz])
        M = frame(c, (0, 1, 0), (1, 0, 0))
        g, an = build_drum(kit, comp, D, H, M, 8, "floor",
                           lug_phase=math.radians(22.5),
                           badge_phi=math.radians(270))
        R = D / 2
        for a in legs:
            phi = math.radians(a)
            yb = H / 2 - 0.085
            shell_bracket(g, R, phi, yb, (0.028, 0.05, 0.03))
            d = np.array([math.cos(phi), 0, math.sin(phi)])
            top_p = g.world(np.array([0, H / 2 - 0.055, 0]) + d * (R + 0.032))
            foot = np.array([c[0], 0.03, c[2]]) + apply_dir(M, d) * (R + 0.11)
            kit.add(comp, "Chrome", tube_between(top_p, foot, 0.0055, S(12),
                                                 bevel=0.001))
            fd = unit(foot - top_p)
            kit.add(comp, "Rubber", rubber_foot(0.011, 0.04).transformed(
                frame(foot + fd * 0.006, -fd)))

    # --- snare ------------------------------------------------------------
    sD, sH = 14 * IN, 6.5 * IN
    sc = np.array([-0.07, 0.567, -0.17])
    sax = tom_axis(sc, 5)
    Ms = frame(sc, sax, (1, 0, 0))
    g, an = build_drum(kit, "Snare", sD, sH, Ms, 10, "snare",
                       reso="HeadClear", lug_phase=math.radians(18),
                       badge_phi=math.radians(90))
    R = sD / 2
    h = sH / 2
    phi_s = math.radians(180)
    # strainer (throw-off) + butt plate
    A = az(phi_s)
    g.add("Chrome", rbox(0.022, 0.05, 0.032, center=(R + 0.011, -h + 0.04, 0)), A)
    g.add("BlackMetal", rbox(0.007, 0.055, 0.009,
                             center=(R + 0.025, -h + 0.045, 0)),
          chain(A, T(0, 0, 0)))
    g.add("Chrome", knurl_knob(0.0085, 0.016), chain(A, T(R + 0.014, -h + 0.065,
                                                         0)))
    B = az(phi_s + math.pi)
    g.add("Chrome", rbox(0.018, 0.034, 0.026, center=(R + 0.009, -h + 0.03, 0)),
          B)
    g.add("Chrome", key_bolt(0.0035, 0.006), chain(B, T(R + 0.018, -h + 0.03, 0),
                                                  Rz(-math.pi / 2)))
    # snare wires under the bottom head
    wy = -an["yt"] - 0.0018
    for k in range(18):
        zz = -0.036 + k * (0.072 / 17)
        g.add("Chrome", tube_between((-0.15, wy, zz), (0.15, wy, zz), 0.0007, 3,
                                     caps=False), A)
    for xx in (-0.158, 0.158):
        g.add("Chrome", rbox(0.016, 0.0018, 0.082, center=(xx, wy, 0)), A)
    for xx, tx in ((-0.166, -(R + 0.008)), (0.166, R + 0.008)):
        p0 = np.array([xx, wy, 0])
        p1 = np.array([tx, -an["yt"] + 0.004, 0])
        d = unit(p1 - p0)
        L = np.linalg.norm(p1 - p0)
        g.add("Rubber", rbox(0.0012, L, 0.012, bevel=0.0004),
              chain(A, frame((p0 + p1) / 2, d, (0, 0, 1))))
    build_snare_stand(kit, sc[0], sc[2], sc[1] - h - 0.022, sax)

    # --- hi-hat -----------------------------------------------------------
    build_hihat(kit, -0.70, -0.13, 0.985)

    # --- throne -----------------------------------------------------------
    seat = build_throne(kit, 0.0, -0.62)
    kit.meta["seat"] = seat.tolist()

    # --- cymbals on rack booms --------------------------------------------
    cyms = [
        # comp,          size, kind,   centre,                tilt, attach
        ("Crash_18", 18, "crash", np.array([-0.60, 1.40, 0.36]), 20,
         ("arc", -0.56)),
        ("Crash_19", 19, "crash", np.array([-0.20, 1.52, 0.50]), 18,
         ("arc", -0.16)),
        ("Splash_10", 10, "splash", np.array([0.20, 1.30, 0.44]), 15,
         ("arc", 0.21)),
        ("Crash_20", 20, "crash", np.array([0.58, 1.50, 0.52]), 18,
         ("arc", 0.60)),
        ("Ride_22", 22, "ride", np.array([0.80, 1.16, 0.20]), 12,
         ("R", 0.17)),
        ("China_18", 18, "china", np.array([1.16, 1.42, 0.02]), 12,
         ("R", 0.76)),
    ]
    for comp, size, kind, center, tilt, (where, t) in cyms:
        ax = cym_axis(center, tilt)
        mesh, info = cymbal_mesh(size * IN, kind)
        inverted = kind == "china"
        attach = arc_point(t) if where == "arc" else wing_point(where, t)
        gb = build_boom(kit, "Boom_" + comp, None, attach, center, ax)
        gh = G(kit, "Boom_" + comp, frame(center, ax, (1, 0, 0)))
        mat = "BronzeDark" if kind == "china" else "Bronze"
        cymbal_holder(gh, [(comp, mesh, info, inverted, mat)])
    # china/splash stack on the left wing
    center = np.array([-1.00, 1.22, 0.06])
    ax = cym_axis(center, 6)
    m1, i1 = cymbal_mesh(16 * IN, "china")
    m2, i2 = cymbal_mesh(12 * IN, "splash")
    build_boom(kit, "Boom_Stack", None, wing_point("L", 0.62), center, ax)
    gh = G(kit, "Boom_Stack", frame(center, ax, (1, 0, 0)))
    cymbal_holder(gh, [("Stack_China16", m1, i1, True, "BronzeDark"),
                       ("Stack_Splash12", m2, i2, False, "Bronze")])

    # --- rug --------------------------------------------------------------
    rug = round_poly(Polygon([(-1.45, -1.15), (1.55, -1.15), (1.55, 0.95),
                              (-1.45, 0.95)]), 0.05)
    kit.add("Rug", "Rug", extrude(rug, 0.008, z0=-0.008), P_XZ)
    return kit


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
# The kit is built with the drummer facing +Z.  Mirroring Z makes the
# drummer face -Z (Roblox forward) with the floor toms on the drummer's
# right hand side (standard right-handed setup).
EXPORT_ROT = Sc(1, 1, -1)

MATERIALS = {
    # name: (diffuse rgb 0-1, specular, roughness-ish, roblox hint)
    "Chrome":     ((0.80, 0.81, 0.84), "Chrome hardware"),
    "Finish":     ((0.035, 0.035, 0.04), "Gloss black lacquer shells & hoops"),
    "Accent":     ((0.62, 0.02, 0.04), "Blood-red pinstripes / inlays"),
    "HeadCoated": ((0.93, 0.92, 0.88), "White coated batter heads"),
    "HeadBlack":  ((0.05, 0.05, 0.055), "Black resonant heads"),
    "HeadClear":  ((0.80, 0.80, 0.78), "Snare-side head"),
    "HeadLogo":   ((1.0, 1.0, 1.0), "Bass drum front heads (logo texture)"),
    "Bronze":     ((0.80, 0.58, 0.26), "Brilliant cymbal bronze"),
    "BronzeDark": ((0.55, 0.38, 0.17), "Raw / dark china bronze"),
    "BlackMetal": ((0.07, 0.07, 0.075), "Black powder-coated castings"),
    "Rubber":     ((0.06, 0.06, 0.06), "Rubber feet, caps, gaskets"),
    "Felt":       ((0.55, 0.05, 0.07), "Red cymbal felts"),
    "Leather":    ((0.05, 0.05, 0.05), "Throne vinyl"),
    "Rug":        ((0.12, 0.12, 0.13), "Drum rug"),
}


def export_all(kit, out_dir, base="MetalDrumKit"):
    os.makedirs(out_dir, exist_ok=True)
    parts = kit.merged()
    obj = os.path.join(out_dir, base + ".obj")
    mtl = base + ".mtl"
    stud = 1.0 / STUD
    write_obj(obj, mtl, parts, scale=stud, M=EXPORT_ROT)
    with open(os.path.join(out_dir, mtl), "w") as fh:
        for name, ((r, g_, b), desc) in MATERIALS.items():
            fh.write(f"# {desc}\nnewmtl {name}\nKd {r:.3f} {g_:.3f} {b:.3f}\n"
                     f"Ka 0 0 0\nKs 0.5 0.5 0.5\nNs 200\nd 1\nillum 2\n")
            if name == "HeadLogo":
                fh.write("map_Kd kick_logo.png\n")
            fh.write("\n")
    stats = []
    tot = 0
    for name, mat, m in parts:
        stats.append((name, mat, m.ntris))
        tot += m.ntris
    seat = apply(EXPORT_ROT, np.array(kit.meta["seat"])) * stud
    lo = np.min([apply(EXPORT_ROT, m.v).min(0) for _, _, m in parts], axis=0)
    hi = np.max([apply(EXPORT_ROT, m.v).max(0) for _, _, m in parts], axis=0)
    info = {"parts": len(parts), "triangles": int(tot),
            "max_part_triangles": int(max(s[2] for s in stats)),
            "size_studs": ((hi - lo) * stud).round(2).tolist(),
            "size_m": (hi - lo).round(3).tolist(),
            "seat_studs": seat.round(3).tolist()}
    with open(os.path.join(out_dir, base + "_stats.json"), "w") as fh:
        json.dump({"summary": info,
                   "parts": [{"name": n, "material": m, "tris": t}
                             for n, m, t in stats]}, fh, indent=1)
    return parts, info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "..", "export"))
    ap.add_argument("--name", default="MetalDrumKit")
    a = ap.parse_args()
    kit = build_kit(a.detail)
    parts, info = export_all(kit, a.out, a.name)
    print(json.dumps(info, indent=1))
