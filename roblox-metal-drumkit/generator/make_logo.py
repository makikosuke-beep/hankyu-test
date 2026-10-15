"""Bass drum front-head artwork (1024x1024 PNG, Roblox's max texture size).

The head's UVs map the membrane disk onto the unit square, so the circle of
radius 0.5 around the centre is the visible head.  Port holes sit low
(v ~ 0.27, u ~ 0.29 / 0.71), so the artwork is kept in the upper part.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SS = 2          # supersampling
N = 1024 * SS

FONTS = [
    "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def px(u, v):
    """UV (v up) -> pixel."""
    return u * N, (1 - v) * N


def vgrad(w, h, stops):
    """Vertical gradient image from [(t, (r,g,b)), ...]."""
    im = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / max(t1 - t0, 1e-6)
                im.putpixel((0, y), tuple(int(a + (b - a) * k)
                                          for a, b in zip(c0, c1)))
                break
    return im.resize((w, h))


def star_poly(cx, cy, r_out, r_in, n, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def main(out):
    img = Image.new("RGB", (N, N), (10, 10, 11))
    d = ImageDraw.Draw(img)
    c = N / 2
    # subtle radial sheen on the black head
    sheen = Image.new("L", (N, N), 0)
    ImageDraw.Draw(sheen).ellipse([c - N * 0.42, c - N * 0.55, c + N * 0.42,
                                   c + N * 0.05], fill=26)
    sheen = sheen.filter(ImageFilter.GaussianBlur(N * 0.08))
    img = Image.composite(Image.new("RGB", (N, N), (60, 60, 66)), img, sheen)
    d = ImageDraw.Draw(img)

    # rim rings
    for r, w, col in ((0.482, 0.006, (150, 10, 18)), (0.468, 0.0025,
                                                      (170, 170, 176))):
        d.ellipse([c - r * N, c - r * N, c + r * N, c + r * N], outline=col,
                  width=int(w * N))

    # emblem: saw-blade ring around a dark disc, above the port holes
    ex, ey = px(0.5, 0.665)
    R = 0.19 * N
    blade = star_poly(ex, ey, R, R * 0.86, 28, rot=0.05)
    glow = Image.new("L", (N, N), 0)
    ImageDraw.Draw(glow).polygon(blade, fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(N * 0.02))
    img = Image.composite(Image.new("RGB", (N, N), (120, 0, 8)), img,
                          glow.point(lambda v: int(v * 0.6)))
    d = ImageDraw.Draw(img)
    d.polygon(blade, fill=(165, 8, 20))
    d.ellipse([ex - R * 0.80, ey - R * 0.80, ex + R * 0.80, ey + R * 0.80],
              fill=(185, 185, 192))
    d.ellipse([ex - R * 0.75, ey - R * 0.75, ex + R * 0.75, ey + R * 0.75],
              fill=(14, 14, 16))
    # crossed drumsticks
    for sgn in (-1, 1):
        a = math.radians(55 * sgn)
        L = R * 0.66
        dx, dy = math.sin(a) * L, -math.cos(a) * L
        x0, y0, x1, y1 = ex - dx, ey - dy, ex + dx, ey + dy
        w = R * 0.07
        nx, ny = -dy / L * w / 2, dx / L * w / 2
        tip = 0.35
        d.polygon([(x0 + nx, y0 + ny), (x1 + nx * tip, y1 + ny * tip),
                   (x1 - nx * tip, y1 - ny * tip), (x0 - nx, y0 - ny)],
                  fill=(205, 205, 210))
        d.ellipse([x1 - w * 0.3, y1 - w * 0.3, x1 + w * 0.3, y1 + w * 0.3],
                  fill=(205, 205, 210))
    # lightning bolt in the middle
    s = R * 0.5
    bolt = [(0.10, -1.0), (-0.42, 0.10), (-0.02, 0.10), (-0.16, 1.0),
            (0.42, -0.16), (0.02, -0.16), (0.24, -1.0)]
    d.polygon([(ex + x * s, ey + y * s) for x, y in bolt], fill=(220, 20, 32),
              outline=(255, 210, 210), width=int(N * 0.002))

    # chrome lettering below the emblem
    text = "IRON STORM"
    f = font(int(N * 0.088))
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx, ty = px(0.5, 0.415)
    tx -= tw / 2
    ty -= th / 2 + bb[1]
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).text((tx, ty), text, font=f, fill=255)
    # slant it for an aggressive look
    yc = ty + bb[1] + th / 2
    mask = mask.transform((N, N), Image.AFFINE, (1, 0.22, -0.22 * yc, 0, 1, 0),
                          resample=Image.BICUBIC)
    outline = mask.filter(ImageFilter.MaxFilter(int(N * 0.012) | 1))
    img = Image.composite(Image.new("RGB", (N, N), (165, 8, 20)), img, outline)
    y0 = int(ty + bb[1])
    chrome = vgrad(N, N, [(0, (40, 40, 44)), (y0 / N, (250, 250, 255)),
                          ((y0 + th * 0.48) / N, (120, 122, 130)),
                          ((y0 + th * 0.52) / N, (60, 60, 66)),
                          ((y0 + th) / N, (235, 235, 240)), (1, (40, 40, 44))])
    img = Image.composite(chrome, img, mask)
    d = ImageDraw.Draw(img)
    f2 = font(int(N * 0.026))
    sub = "- DRUM WORKS -"
    bb = d.textbbox((0, 0), sub, font=f2)
    sx, sy = px(0.5, 0.33)
    d.text((sx - (bb[2] - bb[0]) / 2, sy), sub, font=f2, fill=(190, 190, 196))

    img = img.resize((1024, 1024), Image.LANCZOS)
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "kick_logo.png")
