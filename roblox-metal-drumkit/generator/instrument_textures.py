"""Finishes for the guitars and basses (opaque PNGs, embedded in the FBX).

Body textures use the same planar mapping as the meshes (instruments.UV), so
a sunburst can follow each body's own outline.  Also writes grey grain maps
for the necks, used only by the renders and the web preview.

Run:  python instrument_textures.py [OUT_DIR]
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

import instruments as I
from make_patterns import pnoise

RES = 1024


def field(d, res=RES):
    """X, Y (mm) of every pixel and the distance inside the body edge (mm)."""
    body = I.polygon(d["outline"], d.get("corners", ()))
    uv = I.UV(body)
    px = uv.size / res
    im = Image.new("L", (res, res), 0)
    pts = [((x - uv.x0) / px, res - (y - uv.y0) / px) for x, y in body.exterior.coords]
    ImageDraw.Draw(im).polygon(pts, fill=255)
    mask = np.asarray(im) > 0
    dist = distance_transform_edt(mask) * px
    u = (np.arange(res) + 0.5) / res
    X = (uv.x0 + u * uv.size)[None, :].repeat(res, 0)
    Y = (uv.y0 + (1 - u) * uv.size)[:, None].repeat(res, 1)
    return X, Y, dist


def ramp(dist, stops):
    ds = np.array([s[0] for s in stops], float)
    cs = np.array([s[1] for s in stops], float)
    return np.stack([np.interp(dist, ds, cs[:, k]) for k in range(3)], -1)


def straight_grain(X, Y, rng, period=2.4, strength=0.08, warp=5.0, sharp=6):
    """Grain lines along the neck axis (Y), wandering slowly."""
    n = pnoise(rng, 5.0, X.shape)
    m = pnoise(rng, 3.0, X.shape)
    t = (X + warp * 3 * n + 2.0 * np.sin(Y / 37.0)) / period
    g = (0.5 + 0.5 * np.sin(2 * math.pi * t)) ** sharp
    var = 0.6 + 0.4 * (m * 0.5 + 0.5)
    return 1.0 - strength * g * var


def ash_grain(X, Y, rng):
    """Open-pored ash: strong dark lines and cathedral arches."""
    n = pnoise(rng, 4.8, X.shape)
    arch = 0.00012 * (Y - 160.0) ** 2
    t = (X * 0.9 + 26 * n + np.where(np.abs(X) < 70, arch, arch * 0.3)) / 4.2
    g = (0.5 + 0.5 * np.sin(2 * math.pi * t)) ** 4
    fine = straight_grain(X, Y, rng, 0.9, 0.06, 3.0, 8)
    return (1.0 - 0.34 * g) * fine


def flame(X, Y, rng):
    """Book-matched flame maple: chevron stripes across the grain."""
    n = pnoise(rng, 4.8, X.shape)
    amp = 0.4 + 0.6 * (pnoise(rng, 4.0, X.shape) * 0.5 + 0.5)
    t = (Y + 0.3 * np.abs(X) + 30 * n) / 10.0
    s = np.sin(2 * math.pi * t)
    return 1.0 + 0.12 * amp * s - 0.04 * amp * np.abs(s)


def tortoise(rng, res=RES):
    n1 = pnoise(rng, 3.3, (res, res))
    n2 = pnoise(rng, 3.4, (res, res))
    base = np.array([88.0, 28.0, 9.0])
    dark = np.array([16.0, 6.0, 3.0])
    light = np.array([150.0, 66.0, 22.0])
    t = np.clip((n1 * 0.7 + n2 * 0.3 + 0.12) * 4.5, 0, 1)[..., None]
    rgb = base * (1 - t) + dark * t
    lt = np.clip((-n2 - 0.35) * 4, 0, 1)[..., None]
    return rgb * (1 - lt) + light * lt


BURSTS = {
    "burst_3ts": [(0, (14, 9, 7)), (9, (30, 15, 9)), (24, (112, 24, 12)), (44, (184, 74, 22)),
                  (70, (230, 160, 52))],
    "burst_cherry": [(0, (56, 8, 8)), (10, (104, 14, 12)), (28, (168, 34, 22)),
                     (58, (214, 112, 46)), (92, (232, 168, 78))],
    "burst_tobacco": [(0, (18, 11, 7)), (14, (44, 23, 11)), (40, (118, 60, 22)),
                      (78, (196, 126, 54))],
    "burst_fireglo": [(0, (78, 6, 6)), (14, (132, 12, 10)), (40, (196, 34, 22)),
                      (80, (232, 82, 34))],
}


def body_texture(d, style, rng):
    X, Y, dist = field(d)
    if style == "burst_3ts":
        rgb = ramp(dist, BURSTS["burst_3ts"]) * straight_grain(X, Y, rng, 2.6, 0.06)[..., None]
    elif style == "burst_cherry_flame":
        rgb = ramp(dist, BURSTS["burst_cherry"]) * flame(X, Y, rng)[..., None]
        rgb *= straight_grain(X, Y, rng, 1.6, 0.05)[..., None]
    elif style == "burst_tobacco":
        rgb = ramp(dist, BURSTS["burst_tobacco"]) * straight_grain(X, Y, rng, 2.2, 0.1)[..., None]
    elif style == "burst_fireglo":
        rgb = ramp(dist, BURSTS["burst_fireglo"]) * straight_grain(X, Y, rng, 1.8, 0.07)[..., None]
    elif style == "ash_blonde":
        base = ramp(dist, [(0, (196, 128, 52)), (6, (226, 168, 80)), (30, (234, 180, 94))])
        rgb = base * ash_grain(X, Y, rng)[..., None]
    elif style == "ash_natural":
        base = ramp(dist, [(0, (196, 158, 108)), (6, (220, 184, 130)), (30, (226, 192, 140))])
        rgb = base * ash_grain(X, Y, rng)[..., None]
    else:
        raise ValueError(style)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def wood_grey(rng, kind, res=512):
    yy, xx = np.mgrid[0:res, 0:res].astype(float)
    X = xx * 0.5
    Y = (res - yy) * 0.5
    if kind == "maple":
        g = straight_grain(X, Y, rng, 1.8, 0.1, 4.0, 6)
        g *= 1 - 0.04 * (pnoise(rng, 2.0, (res, res)) * 0.5 + 0.5)
    else:  # rosewood: dark streaks
        g = straight_grain(X, Y, rng, 1.2, 0.3, 6.0, 2)
        g *= 1 - 0.25 * np.clip(pnoise(rng, 2.2, (res, res)), 0, 1)
    return np.clip(g * 255, 0, 255).astype(np.uint8)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(21)
    for d in I.INSTRUMENTS:
        for key, p in d["palette"].items():
            style = p.get("texture")
            if not style:
                continue
            if style == "tortoise":
                img = np.clip(tortoise(rng), 0, 255).astype(np.uint8)
            else:
                img = body_texture(d, style, rng)
            path = os.path.join(out_dir, "%s_%s.png" % (d["id"], key))
            Image.fromarray(img, "RGB").save(path, optimize=True)
            print("wrote", path)
    for kind in ("maple", "rosewood"):
        path = os.path.join(out_dir, "%s_grain.png" % kind)
        Image.fromarray(wood_grey(rng, kind), "L").save(path)
        print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "export", "instruments",
                      "textures"))
