"""Build a drum kit from a JSON spec (piece list + lane codes).

Used for Beat Drummer: every playable piece carries the game's lane code
(BD, SN, HH, HT, LT, FT, CR, RD, ...) in its component name, e.g. "SN_Snare",
so the kit can replace an existing one piece-for-piece.

Spec coordinates are Roblox studs in the kit's own frame:
  +X = drummer's right, +Y = up, drummer faces -Z, origin on the floor.
Sizes are real drum sizes in inches; "scale" enlarges/shrinks the whole kit
(1.0 = realistic at 1 stud = 0.28 m).

Run:  python kitspec.py beatdrummer_spec.json --out ../export/beatdrummer
"""
import argparse
import json
import math
import os

import numpy as np

import drumkit as dk
from drumkit import (IN, G, Kit, S, T, build_boom, build_drive_shaft, build_drum,
                     build_hihat, build_pedal, build_snare_stand, build_throne,
                     cym_axis, cymbal_holder, cymbal_mesh, floor_tom_legs, frame,
                     kick_spurs, rack_tom_mount, rug, snare_hardware, tom_arm,
                     tom_axis, tom_mount_azimuth)
from mesh_lib import cylinder, lathe, rbox, sweep, tube_between, unit

CYMBAL_KIND = {"crash": "crash", "ride": "ride", "china": "china",
               "splash": "splash"}


# ---------------------------------------------------------------------------
# coordinates
# ---------------------------------------------------------------------------
class Space:
    """Converts spec positions (Roblox studs, drummer faces -Z) to the
    generator's internal metres (drummer faces +Z)."""

    def __init__(self, scale=1.0):
        self.scale = scale

    def p(self, v):
        x, y, z = (list(v) + [0, 0, 0])[:3]
        k = dk.STUD / self.scale
        return np.array([x * k, y * k, -z * k])


# ---------------------------------------------------------------------------
# rack that adapts to the pieces it carries
# ---------------------------------------------------------------------------
class Rack:
    def __init__(self, kit, half_width, front_z=0.50, y=0.80, radius=1.25):
        self.kit, self.hw, self.y = kit, half_width, y
        self.zc = front_z - radius
        self.Ra = radius
        a_end = math.asin(min(0.95, half_width / radius))
        self.arc = [np.array([radius * math.sin(a), y,
                              self.zc + radius * math.cos(a)])
                    for a in np.linspace(-a_end, a_end, S(40, 16))]
        self.wings = {}
        self.used = []

    def add_wing(self, side, end_xz):
        start = self.arc[0] if side < 0 else self.arc[-1]
        self.wings[side] = (start, np.array([end_xz[0], self.y, end_xz[1]]))

    def segments(self):
        segs = [(self.arc[i], self.arc[i + 1]) for i in range(len(self.arc) - 1)]
        for a, b in self.wings.values():
            segs.append((a, b))
        return segs

    def nearest(self, xz, keep_out=0.10, spacing=0.11):
        """Nearest rack point to an (x, z) target, away from joints and
        from clamps already placed."""
        q = np.array([xz[0], self.y, xz[1]])
        joints = [self.arc[0], self.arc[-1]] + [b for _, b in self.wings.values()]
        best = None
        for a, b in self.segments():
            d = b - a
            L = np.linalg.norm(d)
            for t in np.linspace(0, 1, 24):
                p = a + d * t
                if min(np.linalg.norm(p - j) for j in joints) < keep_out:
                    continue
                if any(np.linalg.norm(p - u) < spacing for u in self.used):
                    continue
                dist = np.linalg.norm((p - q)[[0, 2]])
                if best is None or dist < best[0]:
                    best = (dist, p, d / L)
        if best is None:
            raise ValueError("no free spot on the rack for %s" % (xz,))
        self.used.append(best[1])
        return best[1], best[2]

    def build(self):
        g = G(self.kit, "Rack")
        r = 0.019
        seg = S(24)
        y = self.y
        g.add("Chrome", sweep(self.arc, r, seg, caps=True))
        legs = []
        # legs at the arc ends; feet across the bar direction
        for end, nxt in ((self.arc[0], self.arc[1]), (self.arc[-1], self.arc[-2])):
            side = -1 if end[0] < 0 else 1
            if side in self.wings:
                a, b = self.wings[side]
                fd = unit(np.cross(unit(b - a), [0, 1, 0]))
            else:
                fd = unit(np.cross(unit(nxt - end), [0, 1, 0]))
            legs.append((end, fd))
            g.add("BlackMetal", rbox(0.05, 0.05, 0.06, bevel=0.007),
                  frame(end + unit(nxt - end) * 0.045, unit(nxt - end), (0, 1, 0)))
        for side, (a, b) in self.wings.items():
            d = unit(b - a)
            g.add("Chrome", tube_between(a + d * 0.03, b + d * 0.04, r, seg))
            g.add("Rubber", tube_between(b + d * 0.04, b + d * 0.065, r + 0.0015,
                                         seg, bevel=0.004))
            g.add("BlackMetal", rbox(0.05, 0.05, 0.06, bevel=0.007),
                  frame(a + d * 0.045, d, (0, 1, 0)))
            legs.append((b, unit(np.cross(d, [0, 1, 0]))))
        for p, fd in legs:
            base = np.array([p[0], 0, p[2]])
            g.add("Chrome", tube_between(base + [0, 0.04, 0], p + [0, 0.07, 0], r,
                                         seg))
            g.add("Rubber", cylinder(r + 0.002, 0.012, seg, bevel=0.003),
                  T(p[0], y + 0.07, p[2]))
            g.add("BlackMetal", lathe([(r + 0.001, y - 0.045),
                                       (r + 0.012, y - 0.045),
                                       (r + 0.015, y - 0.04),
                                       (r + 0.015, y + 0.04),
                                       (r + 0.012, y + 0.045),
                                       (r + 0.001, y + 0.045)], S(24),
                                      closed=True), T(p[0], 0, p[2]))
            g.add("Chrome", dk.t_handle(0.034, 0.0038, 0.016),
                  dk.chain(T(p[0], y + 0.02, p[2]),
                           dk.M4(frame((0, 0, 0), -fd)[:3, :3]),
                           T(0, r + 0.014, 0)))
            f0 = base + fd * 0.17 + [0, 0.02, 0]
            f1 = base - fd * 0.17 + [0, 0.02, 0]
            g.add("Chrome", tube_between(f0, f1, 0.0155, seg))
            for q, dd in ((f0, fd), (f1, -fd)):
                g.add("Rubber", tube_between(q - dd * 0.005, q + dd * 0.025, 0.0175,
                                             seg, bevel=0.004))
            g.add("BlackMetal", rbox(0.06, 0.07, 0.06, center=(0, 0.035, 0),
                                     bevel=0.008), T(base[0], 0.0, base[2]))
        return g


# ---------------------------------------------------------------------------
# spec -> kit
# ---------------------------------------------------------------------------
def comp_name(piece, default):
    return piece.get("name") or "%s_%s" % (piece["lane"], default)


def build_from_spec(spec, detail=None):
    detail = spec.get("detail", 1.0) if detail is None else detail
    dk.DETAIL = detail
    dk.MICRO = detail >= 0.75
    sp = Space(spec.get("scale", 1.0))
    kit = Kit()
    kit.meta["lanes"] = {}
    kit.meta["pivots"] = {}
    throne_pos = sp.p(spec.get("throne", {"pos": [0, 2.02, 2.36]})["pos"])

    def toward_drummer(p):
        d = throne_pos - np.asarray(p, float)
        d[1] = 0
        return unit(d) if np.linalg.norm(d) > 1e-6 else np.array([0, 0, -1.0])

    def pivot(comp, lane, kind, pos, up, face=None):
        kit.meta["pivots"][comp] = {
            "pos": np.asarray(pos, float).tolist(), "up": unit(up).tolist(),
            "face": (unit(face) if face is not None
                     else toward_drummer(pos)).tolist(),
            "lane": lane, "kind": kind}
    pieces = spec["pieces"]
    xs, zs = [], []

    def note(comp, lane, kind):
        kit.meta["lanes"][comp] = {"lane": lane, "kind": kind}

    # ---- bass drum(s) + pedals ------------------------------------------
    kicks = [p for p in pieces if p["type"] == "kick"]
    kick_out = 0.0
    for kp in kicks:
        D, H = kp.get("diameter", 22) * IN, kp.get("depth", 18) * IN
        R = D / 2
        pos = sp.p(kp["pos"])
        ky = R + 0.0175 + 0.012
        c = np.array([pos[0], ky, pos[2]])
        comp = comp_name(kp, "Kick")
        M = frame(c, (0, 0, -1), (1, 0, 0))
        port = (0.12, -0.13, 0.06) if kp.get("port", True) else None
        g, an = build_drum(kit, comp, D, H, M, kp.get("lugs", 10), "kick",
                           reso="HeadLogo" if kp.get("logo", True) else "HeadBlack",
                           lug_phase=0.0, badge_phi=math.radians(90), port=port)
        kick_spurs(kit, comp, g, c[0], c, R, H)
        note(comp, kp["lane"], "kick")
        pivot(comp, kp["lane"], "kick", c, (0, 0, -1), (0, 1, 0))
        kick_out = max(kick_out, abs(c[0]) + R + 0.04)
        xs += [c[0] - R - 0.15, c[0] + R + 0.15]
        zs += [c[2] - H / 2, c[2] + H / 2 + 0.12]
        # pedal(s): batter head plane sits at z = c.z - H/2 (pedal origin 0.15 behind)
        pz = (c[2] - H / 2) - 0.15
        mode = kp.get("pedal", spec.get("pedal", "single"))
        if mode == "double" and len(kicks) == 1:
            main = build_pedal(kit, "Pedal_Main", c[0], 1,
                               beaters=((0.028, "_BeaterR"), (-0.028, "_BeaterL")),
                               chain_x=0.028, pz=pz)
            sx = c[0] - 0.27
            slave = build_pedal(kit, "Pedal_Slave", sx, -1, beaters=(),
                                hoop_clamp=False, chain_x=0.0, pz=pz - 0.04)
            build_drive_shaft(kit, "Pedal_DriveShaft",
                              slave + np.array([0.075, 0, 0]),
                              main + np.array([-0.075, 0, 0]))
            note("Pedal_Main_BeaterR", kp["lane"], "beater")
            note("Pedal_Main_BeaterL", kp["lane"], "beater")
            for bx, suf in ((0.028, "R"), (-0.028, "L")):
                pivot("Pedal_Main_Beater" + suf, kp["lane"], "beater",
                      main + np.array([bx, 0, 0]), (0, 1, 0), (0, 0, 1))
        else:
            side = 1 if c[0] >= 0 else -1
            ax_ = build_pedal(kit, "Pedal_" + comp, c[0], side, pz=pz)
            note("Pedal_" + comp + "_Beater", kp["lane"], "beater")
            pivot("Pedal_" + comp + "_Beater", kp["lane"], "beater", ax_,
                  (0, 1, 0), (0, 0, 1))

    # ---- rack sized to clear the kick(s) --------------------------------
    rack = None
    if spec.get("rack", True):
        rack = Rack(kit, max(0.55, kick_out + 0.2),
                    front_z=spec.get("rack_front_z", 0.50))
        cyms = [p for p in pieces if p["type"] in CYMBAL_KIND or p["type"] == "stack"]
        for side in (-1, 1):
            far = [sp.p(p["pos"]) for p in cyms
                   if np.sign(sp.p(p["pos"])[0]) == side
                   and abs(sp.p(p["pos"])[0]) > rack.hw - 0.02]
            if far:
                end = rack.arc[0] if side < 0 else rack.arc[-1]
                tgt = max(far, key=lambda q: abs(q[0]))
                d = np.array([tgt[0] - end[0], tgt[2] - end[2]])
                L = max(0.3, np.linalg.norm(d) + 0.18)
                d = d / max(np.linalg.norm(d), 1e-6)
                rack.add_wing(side, (end[0] + d[0] * L, end[2] + d[1] * L))

    # ---- rack toms -------------------------------------------------------
    for tp in [p for p in pieces if p["type"] == "tom"]:
        D, H = tp.get("diameter", 12) * IN, tp.get("depth", 9) * IN
        c = sp.p(tp["pos"])
        comp = comp_name(tp, "Tom")
        ax = tom_axis(c, tp.get("tilt", 18))
        M = frame(c, ax, (1, 0, 0))
        phi_m = tom_mount_azimuth(M)
        n = tp.get("lugs", 6 if D < 0.33 else 8)
        g, an = build_drum(kit, comp, D, H, M, n, "tom",
                           lug_phase=phi_m + math.pi / n, badge_phi=phi_m + math.pi)
        note(comp, tp["lane"], "drum")
        pivot(comp, tp["lane"], "drum", c, ax)
        if rack is not None:
            recv = rack_tom_mount(g, M, D, H, phi_m)
            rp, rt = rack.nearest((recv[0], recv[2] + 0.25))
            tom_arm(kit, "TomArm_" + tp["lane"], rp, rt, recv,
                    unit(np.array([recv[0] - rp[0], 0, recv[2] - rp[2]])))

    # ---- floor toms ------------------------------------------------------
    for fp in [p for p in pieces if p["type"] == "floortom"]:
        D, H = fp.get("diameter", 16) * IN, fp.get("depth", 16) * IN
        c = sp.p(fp["pos"])
        comp = comp_name(fp, "FloorTom")
        M = frame(c, (0, 1, 0), (1, 0, 0))
        g, an = build_drum(kit, comp, D, H, M, fp.get("lugs", 8), "floor",
                           lug_phase=math.radians(22.5), badge_phi=math.radians(270))
        floor_tom_legs(kit, comp, g, M, c, D, H, fp.get("legs", (0, 120, 240)))
        note(comp, fp["lane"], "drum")
        pivot(comp, fp["lane"], "drum", c, (0, 1, 0))
        xs += [c[0] - D / 2 - 0.15, c[0] + D / 2 + 0.15]
        zs += [c[2] - D / 2 - 0.15, c[2] + D / 2 + 0.15]

    # ---- snare -----------------------------------------------------------
    for np_ in [p for p in pieces if p["type"] == "snare"]:
        D, H = np_.get("diameter", 14) * IN, np_.get("depth", 6.5) * IN
        c = sp.p(np_["pos"])
        comp = comp_name(np_, "Snare")
        ax = tom_axis(c, np_.get("tilt", 5))
        M = frame(c, ax, (1, 0, 0))
        g, an = build_drum(kit, comp, D, H, M, np_.get("lugs", 10), "snare",
                           reso="HeadClear", lug_phase=math.radians(18),
                           badge_phi=math.radians(90))
        snare_hardware(g, an, D, H)
        build_snare_stand(kit, c[0], c[2], c[1] - H / 2 - 0.022, ax,
                          legs=tuple(np_.get("legs", (0, 150, 210))))
        note(comp, np_["lane"], "drum")
        pivot(comp, np_["lane"], "drum", c, ax)

    # ---- hi-hat ----------------------------------------------------------
    for hp in [p for p in pieces if p["type"] == "hihat"]:
        c = sp.p(hp["pos"])
        lane = hp["lane"]
        hh = build_hihat(kit, c[0], c[2], c[1],
                    names=("HiHatStand", lane + "_Bottom", lane + "_Top"),
                    size=hp.get("diameter", 14),
                    legs=tuple(hp.get("legs", (90, 210, 330))))
        note(lane + "_Top", lane, "hihat_top")
        note(lane + "_Bottom", lane, "hihat_bottom")
        pivot(lane + "_Top", lane, "hihat_top", (c[0], hh["top_seat"], c[2]),
              (0, 1, 0))
        pivot(lane + "_Bottom", lane, "hihat_bottom",
              (c[0], hh["bottom_seat"], c[2]), (0, 1, 0))
        xs += [c[0] - 0.35, c[0] + 0.35]
        zs += [c[2] - 0.45, c[2] + 0.3]

    # ---- cymbals ---------------------------------------------------------
    for cp in [p for p in pieces if p["type"] in CYMBAL_KIND or p["type"] == "stack"]:
        c = sp.p(cp["pos"])
        ax = cym_axis(c, cp.get("tilt", 15))
        if cp["type"] == "stack":
            parts = []
            for i, sub in enumerate(cp["cymbals"]):
                m, inf = cymbal_mesh(sub["diameter"] * IN, sub["kind"])
                sub_comp = "%s_%s%d" % (cp["lane"], sub["kind"].capitalize(),
                                        sub["diameter"])
                parts.append((sub_comp, m, inf, sub.get("inverted", False),
                              "BronzeDark" if sub["kind"] == "china" else "Bronze"))
                note(sub_comp, cp["lane"], "cymbal")
                pivot(sub_comp, cp["lane"], "cymbal", c, ax)
        else:
            kind = CYMBAL_KIND[cp["type"]]
            m, inf = cymbal_mesh(cp.get("diameter", 18) * IN, kind)
            comp = comp_name(cp, cp["type"].capitalize())
            parts = [(comp, m, inf, cp.get("inverted", kind == "china"),
                      "BronzeDark" if kind == "china" else "Bronze")]
            note(comp, cp["lane"], "cymbal")
            pivot(comp, cp["lane"], "cymbal", c, ax)
        boom = "Boom_" + cp["lane"]
        if rack is not None:
            build_boom(kit, boom, None, rack.nearest((c[0], c[2])), c, ax)
        cymbal_holder(G(kit, boom, frame(c, ax, (1, 0, 0))), parts)
        xs += [c[0] - 0.3, c[0] + 0.3]

    if rack is not None:
        rack.build()
        for p in rack.arc + [b for _, b in rack.wings.values()]:
            xs += [p[0] - 0.25, p[0] + 0.25]
            zs += [p[2] - 0.25, p[2] + 0.25]

    # ---- throne + rug ----------------------------------------------------
    th = spec.get("throne", {"pos": [0, 2.02, 2.36]})
    if th:
        tc = sp.p(th["pos"])
        seat = build_throne(kit, tc[0], tc[2], seat_h=tc[1])
        kit.meta["seat"] = seat.tolist()
        xs += [tc[0] - 0.4, tc[0] + 0.4]
        zs += [tc[2] - 0.45, tc[2] + 0.3]
    if spec.get("rug", True):
        rug(kit, min(xs), min(zs), max(xs), max(zs))
    return kit


def lane_manifest(kit, spec):
    return {"name": spec.get("name", "Kit"), "scale": spec.get("scale", 1.0),
            "pieces": kit.meta.get("pivots_export", {})}


def lua_value(v, ind=""):
    if isinstance(v, dict):
        inner = ind + "\t"
        rows = ["%s[%s] = %s," % (inner, json.dumps(k), lua_value(x, inner))
                for k, x in v.items()]
        return "{\n" + "\n".join(rows) + "\n" + ind + "}"
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(
            isinstance(x, (int, float)) for x in v):
        return "Vector3.new(%s, %s, %s)" % tuple(repr(round(float(x), 4)) for x in v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return "nil"
    return repr(v)


def write_setup_script(path, name, pivots):
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "..", "roblox", "DrumKitSetup.lua"),
               encoding="utf-8").read()
    data = "local PIVOTS = " + lua_value(pivots) + " -- generated: " + name
    marker = "local PIVOTS = {} -- (kit-specific data is filled in by kitspec.py)"
    assert marker in tpl
    tpl = tpl.replace('workspace:FindFirstChild("MetalDrumKit")',
                      'workspace:FindFirstChild(%s)' % json.dumps(name))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(tpl.replace(marker, data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--detail", type=float, default=None)
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    kit = build_from_spec(spec, a.detail)
    name = a.name or spec.get("name", "DrumKit")
    parts, info = dk.export_all(kit, a.out, name, scale=spec.get("scale", 1.0))
    with open(os.path.join(a.out, name + "_lanes.json"), "w", encoding="utf-8") as fh:
        json.dump(lane_manifest(kit, spec), fh, indent=1, ensure_ascii=False)
    write_setup_script(os.path.join(a.out, name + "_Setup.lua"), name,
                       kit.meta.get("pivots_export", {}))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
