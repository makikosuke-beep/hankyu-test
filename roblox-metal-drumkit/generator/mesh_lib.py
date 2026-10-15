"""Small procedural mesh toolkit (numpy only, plus scipy/shapely/trimesh helpers).

Every primitive returns a ``Mesh`` that already carries per-corner normals
(auto-smoothed by angle) and per-corner UVs, so meshes can be transformed and
merged freely and written straight to OBJ / handed to Blender.

Coordinates are metres, Y-up.
"""
import math

import numpy as np

TAU = 2.0 * math.pi


# ---------------------------------------------------------------------------
# vector / matrix helpers
# ---------------------------------------------------------------------------
def unit(v, axis=-1):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=axis, keepdims=True)
    return v / np.where(n < 1e-20, 1.0, n)


def rot_axis(axis, ang):
    """3x3 rotation matrix (Rodrigues) around ``axis`` by ``ang`` radians."""
    k = unit(axis)
    x, y, z = k
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ])


def M4(R=None, t=(0, 0, 0), s=1.0):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = np.asarray(R, float) * s
    else:
        M[:3, :3] *= s
    M[:3, 3] = t
    return M


def T(x=0.0, y=0.0, z=0.0):
    return M4(t=(x, y, z))


def Rx(a):
    return M4(rot_axis((1, 0, 0), a))


def Ry(a):
    return M4(rot_axis((0, 1, 0), a))


def Rz(a):
    return M4(rot_axis((0, 0, 1), a))


def Sc(sx, sy, sz):
    M = np.eye(4)
    M[0, 0], M[1, 1], M[2, 2] = sx, sy, sz
    return M


def chain(*Ms):
    out = np.eye(4)
    for M in Ms:
        out = out @ M
    return out


def frame(origin, y_axis, x_hint=(1, 0, 0)):
    """4x4 frame whose local +Y is ``y_axis`` and local +X is as close as
    possible to ``x_hint``. Right-handed (Z = X x Y)."""
    Y = unit(y_axis)
    xh = np.asarray(x_hint, float)
    X = xh - np.dot(xh, Y) * Y
    if np.linalg.norm(X) < 1e-6:
        xh = np.array([0, 0, 1.0]) if abs(Y[2]) < 0.9 else np.array([1.0, 0, 0])
        X = xh - np.dot(xh, Y) * Y
    X = unit(X)
    Z = np.cross(X, Y)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = X, Y, Z
    M[:3, 3] = origin
    return M


def az(phi):
    """Rotation about +Y that takes local +X to (cos phi, 0, sin phi).
    Matches the angle convention used by ``lathe``."""
    return Ry(-phi)


def apply(M, p):
    p = np.asarray(p, float)
    return p @ M[:3, :3].T + M[:3, 3]


def apply_dir(M, d):
    return unit(np.asarray(d, float) @ M[:3, :3].T)


# ---------------------------------------------------------------------------
# Mesh container
# ---------------------------------------------------------------------------
class Mesh:
    __slots__ = ("v", "f", "cn", "cuv")

    def __init__(self, v, f, cn, cuv):
        self.v = np.asarray(v, float).reshape(-1, 3)
        self.f = np.asarray(f, np.int64).reshape(-1, 3)
        self.cn = np.asarray(cn, float).reshape(-1, 3, 3)
        self.cuv = np.asarray(cuv, float).reshape(-1, 3, 2)

    @property
    def ntris(self):
        return len(self.f)

    def transformed(self, M):
        A = M[:3, :3]
        v = self.v @ A.T + M[:3, 3]
        # normal matrix (inverse transpose) handles non-uniform scale/mirror
        N = np.linalg.inv(A).T
        cn = unit(self.cn @ N.T)
        f, cuv = self.f, self.cuv
        if np.linalg.det(A) < 0:
            f = f[:, ::-1]
            cn = cn[:, ::-1]
            cuv = cuv[:, ::-1]
        return Mesh(v, f, cn, cuv)

    @staticmethod
    def merge(meshes):
        meshes = [m for m in meshes if m is not None and m.ntris]
        if not meshes:
            return None
        vs, fs, cns, cuvs = [], [], [], []
        off = 0
        for m in meshes:
            vs.append(m.v)
            fs.append(m.f + off)
            cns.append(m.cn)
            cuvs.append(m.cuv)
            off += len(m.v)
        return Mesh(np.concatenate(vs), np.concatenate(fs),
                    np.concatenate(cns), np.concatenate(cuvs))

    def bounds(self):
        return self.v.min(0), self.v.max(0)


def xf(mesh_or_list, M):
    if isinstance(mesh_or_list, (list, tuple)):
        return [m.transformed(M) for m in mesh_or_list]
    return mesh_or_list.transformed(M)


# ---------------------------------------------------------------------------
# normals & uvs
# ---------------------------------------------------------------------------
def _autosmooth(v, f, fn, angle_deg):
    """Per-corner normals: angle-weighted average of the faces around each
    (welded) vertex whose normal is within ``angle_deg`` of the corner's face."""
    q = np.round(v * 2e5).astype(np.int64)
    _, wid = np.unique(q, axis=0, return_inverse=True)
    wid = wid.reshape(-1)
    F = len(f)
    cv = wid[f].reshape(-1)
    cf = np.repeat(np.arange(F), 3)
    p = v[f]
    e1 = unit(p[:, [1, 2, 0]] - p)
    e2 = unit(p[:, [2, 0, 1]] - p)
    cang = np.arccos(np.clip((e1 * e2).sum(-1), -1, 1)).reshape(-1)

    order = np.argsort(cv, kind="stable")
    scv = cv[order]
    starts = np.searchsorted(scv, scv, "left")
    ends = np.searchsorted(scv, scv, "right")
    counts = ends - starts
    N = len(scv)
    ia = np.repeat(np.arange(N), counts)
    off = np.arange(ia.size) - np.repeat(np.cumsum(counts) - counts, counts)
    ib = starts[ia] + off
    scf = cf[order]
    fa, fb = scf[ia], scf[ib]
    m = (fn[fa] * fn[fb]).sum(1) >= math.cos(math.radians(angle_deg)) - 1e-9
    w = cang[order][ib][m]
    acc = np.zeros((N, 3))
    for k in range(3):
        acc[:, k] = np.bincount(ia[m], weights=fn[fb[m], k] * w, minlength=N)
    out = np.empty_like(acc)
    out[order] = acc
    out = out.reshape(F, 3, 3)
    bad = np.linalg.norm(out, axis=-1) < 1e-12
    out[bad] = np.repeat(fn[:, None, :], 3, 1)[bad]
    return unit(out)


def _boxuv(v, f, cn, scale=4.0):
    p = v[f]  # F,3,3
    ax = np.argmax(np.abs(cn), axis=-1)
    u = np.where(ax == 0, p[..., 2], p[..., 0])
    w = np.where(ax == 1, p[..., 2], p[..., 1])
    return np.stack([u, w], -1) * scale


def finalize(v, f, smooth=40.0, cuv=None, uv_scale=4.0):
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    fn = np.cross(b - a, c - a)
    ar = np.linalg.norm(fn, axis=1)
    keep = ar > 1e-15
    f = f[keep]
    fn = fn[keep] / ar[keep, None]
    if cuv is not None:
        cuv = np.asarray(cuv)[keep]
    cn = _autosmooth(v, f, fn, smooth)
    if cuv is None:
        cuv = _boxuv(v, f, cn, uv_scale)
    return Mesh(v, f, cn, cuv), keep


def _orient_like(v, f, idx, want):
    """Flip all faces if face ``idx`` points against ``want``."""
    a, b, c = v[f[idx, 0]], v[f[idx, 1]], v[f[idx, 2]]
    n = np.cross(b - a, c - a)
    if np.dot(n, want) < 0:
        return f[:, ::-1]
    return f


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def lathe(profile, segs=32, closed=False, smooth=40.0, tilt=None, phase=0.0,
          uv=True):
    """Revolve a (r, y) profile around +Y.

    Orientation rule: for outward-facing normals trace the profile
    counter-clockwise in the (r, y) plane (r to the right, y up), e.g. go UP the
    outside wall.  ``tilt`` (one angle per profile point, radians) rotates the
    final normals in the meridian plane - used to fake lathe grooves on
    cymbals without extra geometry.
    """
    prof = np.asarray(profile, float)
    P = len(prof)
    ang = phase + TAU * np.arange(segs) / segs
    c, s = np.cos(ang), np.sin(ang)
    r, y = prof[:, 0], prof[:, 1]
    V = np.stack([r[:, None] * c[None, :],
                  np.repeat(y[:, None], segs, 1),
                  r[:, None] * s[None, :]], -1).reshape(-1, 3)
    rows = P if closed else P - 1
    i = np.arange(rows)
    i2 = (i + 1) % P
    j = np.arange(segs)
    I, J = np.meshgrid(i, j, indexing="ij")
    I2 = i2[I]
    J2 = (J + 1) % segs
    a = I * segs + J
    b = I2 * segs + J
    cc = I2 * segs + J2
    d = I * segs + J2
    f = np.concatenate([np.stack([a, b, cc], -1).reshape(-1, 3),
                        np.stack([a, cc, d], -1).reshape(-1, 3)])
    # uvs: u around, v along profile length
    seg_len = np.linalg.norm(np.diff(np.vstack([prof, prof[:1]]), axis=0), axis=1)
    vcoord = np.concatenate([[0], np.cumsum(seg_len)])
    tot = max(vcoord[-1] if closed else vcoord[P - 1], 1e-9)
    vI = vcoord[I] / tot
    vI2 = vcoord[I + 1] / tot
    uJ = J / segs
    uJ2 = (J + 1) / segs
    uv_a = np.stack([uJ, vI], -1)
    uv_b = np.stack([uJ, vI2], -1)
    uv_c = np.stack([uJ2, vI2], -1)
    uv_d = np.stack([uJ2, vI], -1)
    cuv = np.concatenate([np.stack([uv_a, uv_b, uv_c], -2).reshape(-1, 3, 2),
                          np.stack([uv_a, uv_c, uv_d], -2).reshape(-1, 3, 2)])
    mesh, keep = finalize(V, f, smooth, cuv if uv else None)
    if tilt is not None:
        tilt = np.asarray(tilt, float)
        vid = mesh.f  # F,3
        row = vid // segs
        col = vid % segs
        tt = tilt[row]
        phi = ang[col]
        k = np.stack([-np.sin(phi), np.zeros_like(phi), np.cos(phi)], -1)
        n = mesh.cn
        ct, st = np.cos(tt)[..., None], np.sin(tt)[..., None]
        kn = np.cross(k, n)
        kd = (k * n).sum(-1, keepdims=True)
        mesh.cn = unit(n * ct + kn * st + k * kd * (1 - ct))
    return mesh


def cylinder(r, h, segs=16, caps=True, smooth=40.0, y0=0.0, bevel=0.0):
    """Cylinder along +Y from y0 to y0+h."""
    if bevel > 0:
        b = min(bevel, r * 0.45, h * 0.45)
        prof = [(r - b, y0), (r, y0 + b), (r, y0 + h - b), (r - b, y0 + h)]
    else:
        prof = [(r, y0), (r, y0 + h)]
    if caps:
        prof = [(0, y0)] + prof + [(0, y0 + h)]
    return lathe(prof, segs, smooth=smooth)


def tube_between(p0, p1, r, segs=16, caps=True, bevel=0.0, smooth=40.0):
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    L = np.linalg.norm(p1 - p0)
    m = cylinder(r, L, segs, caps, smooth, bevel=bevel)
    return m.transformed(frame(p0, p1 - p0))


def torus(R, r, segs=32, rsegs=12, smooth=60.0):
    a = TAU * np.arange(rsegs) / rsegs
    # counter-clockwise around the tube centre -> outward normals
    prof = np.stack([R + r * np.cos(a), r * np.sin(a)], -1)
    return lathe(prof, segs, closed=True, smooth=smooth)


def sphere(r, segs=16, rings=8):
    a = np.linspace(-math.pi / 2, math.pi / 2, rings + 1)
    prof = np.stack([r * np.cos(a), r * np.sin(a)], -1)
    prof[0, 0] = prof[-1, 0] = 0
    return lathe(prof, segs, smooth=80)


def sweep(path, radius, segs=12, caps=True, smooth=50.0, radii=None):
    """Circular tube swept along a polyline with parallel-transport frames."""
    P = np.asarray(path, float)
    n = len(P)
    rad = np.full(n, radius) if radii is None else np.asarray(radii, float)
    Tg = np.zeros_like(P)
    Tg[1:-1] = unit(unit(P[2:] - P[1:-1]) + unit(P[1:-1] - P[:-2]))
    Tg[0] = unit(P[1] - P[0])
    Tg[-1] = unit(P[-1] - P[-2])
    ref = np.array([0, 1.0, 0]) if abs(Tg[0][1]) < 0.9 else np.array([1.0, 0, 0])
    Nn = np.zeros_like(P)
    Nn[0] = unit(ref - np.dot(ref, Tg[0]) * Tg[0])
    for i in range(1, n):
        axis = np.cross(Tg[i - 1], Tg[i])
        sa = np.linalg.norm(axis)
        if sa < 1e-9:
            Nn[i] = Nn[i - 1]
        else:
            ang = math.atan2(sa, np.dot(Tg[i - 1], Tg[i]))
            Nn[i] = rot_axis(axis, ang) @ Nn[i - 1]
        Nn[i] = unit(Nn[i] - np.dot(Nn[i], Tg[i]) * Tg[i])
    B = np.cross(Tg, Nn)
    th = TAU * np.arange(segs) / segs
    dirs = (np.cos(th)[None, :, None] * Nn[:, None, :] +
            np.sin(th)[None, :, None] * B[:, None, :])
    V = (P[:, None, :] + rad[:, None, None] * dirs).reshape(-1, 3)
    I, J = np.meshgrid(np.arange(n - 1), np.arange(segs), indexing="ij")
    J2 = (J + 1) % segs
    a = I * segs + J
    b = (I + 1) * segs + J
    c = (I + 1) * segs + J2
    d = I * segs + J2
    f = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3),
                        np.stack([a, c, d], -1).reshape(-1, 3)])
    f = _orient_like(V, f, 0, dirs[0, 0])
    if caps:
        c0 = len(V)
        c1 = c0 + 1
        V = np.vstack([V, P[0], P[-1]])
        j = np.arange(segs)
        j2 = (j + 1) % segs
        f0 = np.stack([np.full(segs, c0), j2, j], -1)
        f0 = _orient_like(V, f0, 0, -Tg[0])
        last = (n - 1) * segs
        f1 = np.stack([np.full(segs, c1), last + j, last + j2], -1)
        f1 = _orient_like(V, f1, 0, Tg[-1])
        f = np.concatenate([f, f0, f1])
    mesh, _ = finalize(V, f, smooth)
    return mesh


def fillet_path(pts, radius, segs=8):
    """Round the interior corners of a polyline with quadratic arcs."""
    pts = [np.asarray(p, float) for p in pts]
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, c, b = pts[k - 1], pts[k], pts[k + 1]
        d1 = unit(c - a)
        d2 = unit(b - c)
        cosang = np.clip(np.dot(d1, d2), -1, 1)
        ang = math.acos(cosang)
        if ang < 1e-3:
            out.append(c)
            continue
        t = radius * math.tan(ang / 2)
        t = min(t, 0.45 * np.linalg.norm(c - a), 0.45 * np.linalg.norm(b - c))
        A = c - d1 * t
        Bp = c + d2 * t
        for s in np.linspace(0, 1, segs + 1):
            out.append((1 - s) ** 2 * A + 2 * (1 - s) * s * c + s ** 2 * Bp)
    out.append(pts[-1])
    return np.array(out)


def hull(points, smooth=20.0):
    from scipy.spatial import ConvexHull
    pts = np.asarray(points, float)
    h = ConvexHull(pts)
    f = h.simplices.copy()
    cen = pts[h.vertices].mean(0)
    a, b, c = pts[f[:, 0]], pts[f[:, 1]], pts[f[:, 2]]
    n = np.cross(b - a, c - a)
    flip = ((a - cen) * n).sum(1) < 0
    f[flip] = f[flip][:, ::-1]
    used = np.unique(f)
    remap = -np.ones(len(pts), np.int64)
    remap[used] = np.arange(len(used))
    mesh, _ = finalize(pts[used], remap[f], smooth)
    return mesh


def rbox(sx, sy, sz, bevel=None, center=(0, 0, 0)):
    """Chamfered box (crisp 45 degree bevels), centred."""
    if bevel is None:
        bevel = 0.18 * min(sx, sy, sz)
    b = min(bevel, 0.49 * min(sx, sy, sz))
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    pts = []
    for sxn in (-1, 1):
        for syn in (-1, 1):
            for szn in (-1, 1):
                pts += [
                    (sxn * hx, syn * (hy - b), szn * (hz - b)),
                    (sxn * (hx - b), syn * hy, szn * (hz - b)),
                    (sxn * (hx - b), syn * (hy - b), szn * hz),
                ]
    m = hull(pts, smooth=20.0)
    return m.transformed(T(*center))


def extrude(poly, h, smooth=35.0, z0=0.0):
    """Extrude a shapely polygon (XY plane) along +Z from z0 to z0+h."""
    import trimesh
    tm = trimesh.creation.extrude_polygon(poly, h)
    v = np.asarray(tm.vertices, float)
    v[:, 2] += z0
    mesh, _ = finalize(v, np.asarray(tm.faces), smooth)
    return mesh


def circle_poly(x, y, r, n=24):
    from shapely.geometry import Polygon
    a = TAU * np.arange(n) / n
    return Polygon(np.stack([x + r * np.cos(a), y + r * np.sin(a)], -1))


def round_poly(poly, r, quad_segs=3):
    """Round both convex and concave corners of a shapely polygon."""
    q = quad_segs
    p = poly.buffer(-r, quad_segs=q).buffer(r, quad_segs=q)
    return p.buffer(r * 0.6, quad_segs=q).buffer(-r * 0.6, quad_segs=q)


def helix(radius, pitch, turns, wire, segs_per_turn=14, wire_segs=6):
    n = int(turns * segs_per_turn) + 1
    t = np.linspace(0, turns * TAU, n)
    path = np.stack([radius * np.cos(t), t / TAU * pitch, radius * np.sin(t)], -1)
    return sweep(path, wire, wire_segs, caps=True, smooth=60)


def cyl_wrap(mesh, R):
    """Bend a mesh built flat (X = radial offset from R, Z = arc length,
    Y = axial) onto a cylinder of radius R around +Y."""
    v = mesh.v
    ang = v[:, 2] / R
    rr = R + v[:, 0]
    nv = np.stack([rr * np.cos(ang), v[:, 1], rr * np.sin(ang)], -1)
    # rotate corner normals by the angle of their vertex
    a = ang[mesh.f]  # F,3
    n = mesh.cn
    c, s = np.cos(a), np.sin(a)
    nx = n[..., 0] * c - n[..., 2] * s
    nz = n[..., 0] * s + n[..., 2] * c
    cn = np.stack([nx, n[..., 1], nz], -1)
    return Mesh(nv, mesh.f, unit(cn), mesh.cuv)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def write_obj(path, mtl_name, parts, scale=1.0, M=None):
    """parts: list of (name, material, Mesh)."""
    lines = [f"# Procedurally generated - Metal Drum Kit", f"mtllib {mtl_name}"]
    vo = no = to = 1
    for name, mat, mesh in parts:
        m = mesh if M is None else mesh.transformed(M)
        v = m.v * scale
        cn = m.cn.reshape(-1, 3)
        uv = m.cuv.reshape(-1, 2)
        nq, ninv = np.unique(np.round(cn, 4), axis=0, return_inverse=True)
        tq, tinv = np.unique(np.round(uv, 5), axis=0, return_inverse=True)
        ninv = ninv.reshape(-1, 3)
        tinv = tinv.reshape(-1, 3)
        lines.append(f"o {name}")
        lines.extend("v %.5f %.5f %.5f" % tuple(p) for p in v)
        lines.extend("vt %.5f %.5f" % tuple(p) for p in tq)
        lines.extend("vn %.4f %.4f %.4f" % tuple(p) for p in nq)
        lines.append(f"usemtl {mat}")
        lines.append("s off")
        F = m.f + vo
        T_ = tinv + to
        N_ = ninv + no
        lines.extend(
            "f %d/%d/%d %d/%d/%d %d/%d/%d" % (F[i, 0], T_[i, 0], N_[i, 0],
                                              F[i, 1], T_[i, 1], N_[i, 1],
                                              F[i, 2], T_[i, 2], N_[i, 2])
            for i in range(len(F)))
        vo += len(v)
        to += len(tq)
        no += len(nq)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
