"""Shell pattern textures for the selectable kit finishes.

Each pattern is a 1024x256 RGBA PNG that wraps once around a drum shell
(u = around, v = along the shell depth; the bottom row of the image is the
resonant-head side).  The left and right edges tile seamlessly.

Transparent pixels show the MeshPart's Color in Roblox, so one texture works
with every shell colour:
  sparkle   - metal-flake glints over the chosen colour
  flames    - hot-rod flames in the chosen colour on black, silver pinstripe
  tiger     - black tiger stripes over the chosen colour
  carbon    - twill carbon-fibre weave tinted by the chosen colour
  burst     - chosen colour in the middle fading to black at both edges
  lightning - lightning bolts in the chosen colour on black

Run:  python make_patterns.py ../export/styles
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1024, 256
SS = 3  # supersampling for the vector patterns
BLACK = (12, 12, 14)


def rgba(rgb, alpha):
    """rgb: HxWx3 float 0-255, alpha: HxW float 0-1 -> PIL RGBA."""
    a = np.clip(alpha, 0, 1)
    out = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def wrap_draw(draw_fn, w=W * SS, h=H * SS):
    """Draw with horizontal wrap-around: shapes are drawn three times."""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for off in (-w, 0, w):
        draw_fn(d, off)
    return m


def down(img):
    return img.resize((W, H), Image.LANCZOS)


def blur_wrap(arr, radius):
    """Gaussian blur that wraps horizontally."""
    pad = int(radius * 3) + 1
    ext = np.concatenate([arr[:, -pad:], arr, arr[:, :pad]], axis=1)
    im = Image.fromarray(np.clip(ext, 0, 255).astype(np.uint8), "L")
    im = im.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(im, float)[:, pad:-pad]


# ---------------------------------------------------------------------------
def sparkle(rng):
    rgb = np.full((H, W, 3), 255.0)
    alpha = np.zeros((H, W))
    # fine dark grain gives the flakes depth
    grain = blur_wrap(rng.random((H, W)) * 255, 0.6) / 255
    alpha += (grain - 0.5).clip(0) * 0.25
    rgb[:] = 0
    flakes = np.zeros((H, W))
    n = 12000
    xs = rng.integers(0, W, n)
    ys = rng.integers(0, H, n)
    br = rng.random(n) ** 3
    for x, y, b in zip(xs, ys, br):
        flakes[y, x] = max(flakes[y, x], b)
    flakes = blur_wrap(flakes * 255, 0.75) / 255 * 4.5
    flakes = flakes.clip(0, 1)
    rgb = rgb * (1 - flakes[..., None]) + 255 * flakes[..., None]
    alpha = np.maximum(alpha, flakes * 0.6)
    return rgba(rgb, alpha)


def flames(rng):
    w, h = W * SS, H * SS
    tongues = []
    x = 0.0
    while x < w:
        width = rng.uniform(0.07, 0.12) * w
        height = rng.uniform(0.45, 0.82) * h
        lean = rng.uniform(0.35, 0.8) * width
        tongues.append((x, width, height, lean))
        x += width * rng.uniform(0.55, 0.8)

    def tongue_poly(off, x0, width, height, lean, grow=0.0):
        pts = []
        steps = 18
        base = h + 10
        left = [(x0 - grow, base)]
        right = [(x0 + width + grow, base)]
        for i in range(1, steps + 1):
            t = i / steps
            y = base - (height + grow) * t
            bend = lean * t ** 2.2
            half = (width / 2 + grow) * (1 - t) ** 0.9
            wob = math.sin(t * math.pi * 2.2) * width * 0.08
            cx = x0 + width / 2 + bend + wob
            left.append((cx - half, y))
            right.append((cx + half, y))
        tip = (x0 + width / 2 + lean * 1.12, base - (height + grow) * 1.04)
        pts = left + [tip] + right[::-1]
        return [(px + off, py) for px, py in pts]

    def shape(grow):
        return wrap_draw(lambda d, off: [d.polygon(tongue_poly(off, *t, grow=grow),
                                                   fill=255) for t in tongues])

    flame = np.asarray(down(shape(0)), float) / 255
    outline = np.asarray(down(shape(3.2 * SS)), float) / 255
    stripe = (outline - flame).clip(0, 1)
    # a "hot" white glow near the base of the flames, still tinted by the colour
    yy = np.linspace(0, 1, H)[:, None]
    hot = flame * (yy ** 3) * 0.45
    rgb = np.zeros((H, W, 3))
    rgb[:] = BLACK
    rgb = rgb * (1 - stripe[..., None]) + 225 * stripe[..., None]
    rgb = rgb * (1 - hot[..., None]) + 255 * hot[..., None]
    alpha = 1 - flame + stripe + hot
    return rgba(rgb, alpha)


def tiger(rng):
    w, h = W * SS, H * SS
    polys = []
    x = 0.0
    while x < w:
        x += rng.uniform(0.035, 0.07) * w
        from_top = rng.random() < 0.5
        length = rng.uniform(0.45, 0.95) * h
        width = rng.uniform(0.012, 0.03) * w
        drift = rng.uniform(-0.05, 0.05) * w
        steps = 14
        left, right = [], []
        for i in range(steps + 1):
            t = i / steps
            y = t * length if from_top else h - t * length
            cx = x + drift * t + math.sin(t * 5 + x) * width * 0.4
            half = width * (1 - t) ** 0.7 * (0.6 + 0.4 * math.sin(t * 3.1 + x))
            left.append((cx - half, y))
            right.append((cx + half, y))
        polys.append(left + right[::-1])
    m = wrap_draw(lambda d, off: [d.polygon([(px + off, py) for px, py in p], fill=255)
                                  for p in polys])
    m = m.filter(ImageFilter.GaussianBlur(SS * 0.8))
    a = np.asarray(down(m), float) / 255
    rgb = np.zeros((H, W, 3))
    rgb[:] = BLACK
    return rgba(rgb, a)


def carbon(rng):
    tow = 8  # pixels per tow; W and H are multiples of 4 * tow
    yy, xx = np.mgrid[0:H, 0:W]
    cx = (xx // tow)
    cy = (yy // tow)
    over = ((cx + cy) // 2) % 2 == 0  # 2x2 twill
    fx = (xx % tow + 0.5) / tow
    fy = (yy % tow + 0.5) / tow
    # shading across each tow (cylindrical highlight)
    across = np.where(over, fx, fy)
    shade = 0.5 + 0.5 * np.cos((across - 0.5) * math.pi)
    shade = np.where(over, shade * 1.0, shade * 0.8)
    rgb = np.zeros((H, W, 3))
    rgb[:] = (8, 8, 10)
    hi = (shade - 0.75).clip(0) * 1.2
    rgb = rgb * (1 - hi[..., None]) + 170 * hi[..., None]
    alpha = 0.72 - 0.32 * shade + hi * 0.25
    return rgba(rgb, alpha)


def burst(rng):
    v = np.linspace(-1, 1, H)[:, None] * np.ones((1, W))
    t = (np.abs(v) - 0.25) / 0.75
    t = t.clip(0, 1)
    a = t * t * (3 - 2 * t)
    rgb = np.zeros((H, W, 3))
    rgb[:] = (6, 6, 8)
    return rgba(rgb, a)


def lightning(rng):
    w, h = W * SS, H * SS
    bolts = []

    def bolt(x0, y0, x1, y1, depth=0):
        pts = [(x0, y0)]
        n = 6
        for i in range(1, n):
            t = i / n
            # zig-zag: alternate the sideways kick for a classic bolt shape
            pts.append((x0 + (x1 - x0) * t + (-1) ** i * rng.uniform(0.012, 0.025) * w,
                        y0 + (y1 - y0) * t + rng.uniform(-0.04, 0.04) * h))
        pts.append((x1, y1))
        bolts.append((pts, 5.5 if depth == 0 else 2.6))
        if depth == 0:
            i = rng.integers(2, n - 1)
            bx, by = pts[i]
            bolt(bx, by, bx + rng.choice([-1, 1]) * rng.uniform(0.04, 0.07) * w,
                 by + rng.uniform(0.15, 0.3) * h, 1)

    x = 0.0
    while x < w:
        # bolts strike diagonally across the shell depth
        bolt(x, rng.uniform(0.04, 0.15) * h, x + rng.uniform(0.07, 0.12) * w,
             rng.uniform(0.85, 0.97) * h)
        x += rng.uniform(0.15, 0.2) * w

    def draw(scale):
        return wrap_draw(lambda d, off: [d.line([(px + off, py) for px, py in p],
                                                fill=255, width=int(wd * SS * scale),
                                                joint="curve")
                                         for p, wd in bolts])

    core = np.asarray(down(draw(1.0)), float) / 255
    # blur with wrap-around so the glow tiles across the seam
    glow = blur_wrap(np.asarray(down(draw(3.5)), float), 7) / 255
    white = np.asarray(down(draw(0.35)), float) / 255
    rgb = np.zeros((H, W, 3))
    rgb[:] = BLACK
    rgb = rgb * (1 - white[..., None]) + 255 * white[..., None]
    alpha = 1 - np.maximum(core, glow * 0.85) + white
    return rgba(rgb, alpha)


# ---------------------------------------------------------------------------
# wood figures for the SOVEREIGN kit (stain colour shows through)
# ---------------------------------------------------------------------------
DARK = np.array([28.0, 14.0, 6.0])     # grain lines / figure shadows
LIGHT = np.array([255.0, 238.0, 205.0])  # chatoyant highlights


def pnoise(rng, beta=2.0, shape=(H, W)):
    """Periodic (tileable) 1/f noise in both directions, range ~[-1, 1]."""
    h, w = shape
    fy = np.fft.fftfreq(h)[:, None] * (h / w)
    fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    spec = (rng.normal(size=shape) + 1j * rng.normal(size=shape)) / f ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return n / (np.abs(n).max() + 1e-9)


def grain(rng, lines=46, warp=1.2, strength=0.22):
    """Fine grain lines running around the shell (along u)."""
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    n = pnoise(rng, 4.0)
    t = yy * lines + n * warp * lines * 0.05 + pnoise(rng, 3.2) * 0.8
    g = (0.5 + 0.5 * np.sin(t * 2 * math.pi)) ** 8
    var = 0.6 + 0.4 * (pnoise(rng, 3.0) * 0.5 + 0.5)
    return np.clip(g * strength * var, 0, 1)


def wood_rgba(dark, light):
    """dark / light: HxW 0..1 amounts -> RGBA overlay."""
    a = np.clip(dark + light, 0, 1)
    w = np.where(a > 1e-6, light / np.maximum(a, 1e-6), 0)[..., None]
    rgb = DARK * (1 - w) + LIGHT * w
    return rgba(rgb, a)


def flame(rng, stripes=44):
    """Flamed (curly) maple: shimmering bands across the grain."""
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    warp = pnoise(rng, 4.5) * 1.6 + np.sin(yy * math.pi * 2) * 0.25
    phase = xx * stripes + warp + yy * 1.6
    band = np.sin(phase * 2 * math.pi)
    amp = 0.45 + 0.55 * (pnoise(rng, 4.0) * 0.5 + 0.5)
    dark = np.clip(band, 0, 1) ** 1.3 * 0.3 * amp
    light = np.clip(-band, 0, 1) ** 1.8 * 0.1 * amp
    return dark + grain(rng, strength=0.12), light


def birdseye(rng):
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    eyes = np.zeros((H, W))
    rings = np.zeros((H, W))
    n = 1700
    for x0, y0, r in zip(rng.uniform(0, W, n), rng.uniform(0, H, n),
                         rng.uniform(1.0, 2.4, n)):
        x0i, y0i = int(x0), int(y0)
        rad = int(r * 3) + 2
        ys = np.arange(y0i - rad, y0i + rad + 1)
        xs = np.arange(x0i - rad, x0i + rad + 1) % W
        ys = ys[(ys >= 0) & (ys < H)]
        if not len(ys):
            continue
        dy = ys[:, None] - y0
        dx = ((xs[None, :] - x0 + W / 2) % W) - W / 2
        d = np.sqrt(dx * dx * 0.6 + dy * dy)
        sub = np.ix_(ys, xs)
        eyes[sub] = np.maximum(eyes[sub], np.exp(-(d / r) ** 2))
        rings[sub] = np.maximum(rings[sub], np.exp(-((d - r * 2.2) / (r * 0.6)) ** 2))
    dark = eyes * 0.6 + grain(rng, lines=60, strength=0.14)
    light = rings * 0.1
    return dark, light


def burl(rng):
    n1 = pnoise(rng, 4.2)
    n2 = pnoise(rng, 3.6)
    swirl = np.sin((n1 * 7 + n2 * 2.5) * math.pi * 2)
    lines = np.clip(swirl, 0, 1) ** 6
    blob = np.clip(pnoise(rng, 3.8) * 1.6, 0, 1)
    eyes = (pnoise(rng, 2.2) * 0.5 + 0.5) ** 10 * 6
    dark = np.clip(lines * 0.45 + blob * 0.3 + np.clip(eyes, 0, 0.8) * 0.7, 0, 0.95)
    light = np.clip(-swirl, 0, 1) ** 4 * 0.08
    return dark, light


def quilt(rng):
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    warp = pnoise(rng, 4.5) * 1.2
    a = np.sin((xx * 22 + warp) * 2 * math.pi)
    b = np.sin((yy * 5.5 + xx * 4 + warp * 0.7) * 2 * math.pi)
    blister = a * b + 0.3 * np.sin((xx * 44 + yy * 11 + warp) * 2 * math.pi)
    dark = np.clip(blister, 0, None) ** 1.4 * 0.36 + grain(rng, strength=0.1)
    light = np.clip(-blister, 0, None) ** 1.8 * 0.1
    return dark, light


def stripe(rng):
    """Macassar / zebrawood: bold dark streaks along the grain."""
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    warp = pnoise(rng, 3.4) * 1.4
    t = yy * 9 + warp + np.sin(xx * 2 * math.pi * 3) * 0.15
    s_ = 0.5 + 0.5 * np.sin(t * 2 * math.pi)
    width = 0.55 + 0.35 * pnoise(rng, 2.0)
    streak = np.clip((s_ - width) / (1 - width + 1e-6), 0, 1) ** 0.7
    dark = streak * 0.85 + grain(rng, lines=70, strength=0.2)
    return dark, np.zeros_like(dark)


def edge_burst(dark, light, inner=0.3):
    v = np.abs(np.linspace(-1, 1, H))[:, None] * np.ones((1, W))
    t = np.clip((v - inner) / (1 - inner), 0, 1)
    b = t * t * (3 - 2 * t)
    return np.clip(dark * (1 - b) + b * 0.97, 0, 1), light * (1 - b)


WOOD = {
    "flame": lambda rng: wood_rgba(*flame(rng)),
    "birdseye": lambda rng: wood_rgba(*birdseye(rng)),
    "burl": lambda rng: wood_rgba(*burl(rng)),
    "quilt": lambda rng: wood_rgba(*quilt(rng)),
    "stripe": lambda rng: wood_rgba(*stripe(rng)),
    "flameburst": lambda rng: wood_rgba(*edge_burst(*flame(rng))),
}


PATTERNS = {"sparkle": sparkle, "flames": flames, "tiger": tiger,
            "carbon": carbon, "burst": burst, "lightning": lightning}


def check_tiling(img):
    a = np.asarray(img, float)
    return float(np.abs(a[:, 0] - a[:, -1]).mean())


def main(out_dir, which="metal"):
    os.makedirs(out_dir, exist_ok=True)
    table = WOOD if which == "wood" else PATTERNS
    for i, (name, fn) in enumerate(table.items()):
        rng = np.random.default_rng(1234 + i)
        img = fn(rng)
        path = os.path.join(out_dir, "pattern_%s.png" % name)
        img.save(path)
        print("wrote", path, "edge diff %.1f" % check_tiling(img))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "styles",
         sys.argv[2] if len(sys.argv) > 2 else "metal")
