"""Logo prints for the sticks (transparent PNG overlays).

The image wraps once round the stick (u, front of the stick = u 0.5) and runs
its whole length (v = height / length, tip at the top of the image), so the
part's own colour shows through wherever the image is transparent.

Run:  python stick_logos.py [OUT_DIR]
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sticks

W, H = 256, 1024
FONTS = {
    "serif_bold": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "serif_italic": "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf",
    "display": "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "sans": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "ja": "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
}

def font(key, size):
    return ImageFont.truetype(FONTS[key], size)


def text_art(text, key, px=160, spacing=0, fill=(255, 255, 255, 255)):
    """Horizontal text on a transparent canvas, cropped to its ink."""
    f = font(key, px)
    w = int(sum(f.getlength(c) for c in text) + spacing * px * len(text)) + px
    im = Image.new("RGBA", (w, int(px * 1.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = px * 0.3
    for c in text:
        d.text((x, px * 0.2), c, font=f, fill=fill)
        x += f.getlength(c) + spacing * px
    return im.crop(im.getbbox())


def hstack(items, gap_ratio=0.25):
    """Join artworks left to right, vertically centred.  items: (img, scale)."""
    imgs = [im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            for im, s in items]
    hmax = max(i.height for i in imgs)
    gap = int(hmax * gap_ratio)
    out = Image.new("RGBA", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), hmax))
    x = 0
    for i in imgs:
        out.alpha_composite(i, (x, (hmax - i.height) // 2))
        x += i.width + gap
    return out


def shape_art(kind, px=160, fill=(255, 255, 255, 255)):
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = px / 2
    if kind == "heart":
        r = px * 0.26
        d.ellipse((c - 2 * r + 2, c - 1.6 * r, c + 2, c + 0.4 * r), fill=fill)
        d.ellipse((c - 2, c - 1.6 * r, c + 2 * r - 2, c + 0.4 * r), fill=fill)
        d.polygon([(c - 1.93 * r, c - 0.3 * r), (c + 1.93 * r, c - 0.3 * r), (c, c + 1.75 * r)],
                  fill=fill)
    elif kind == "star":
        pts = []
        for k in range(10):
            r = px * (0.48 if k % 2 == 0 else 0.2)
            a = -math.pi / 2 + math.pi * k / 5
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        d.polygon(pts, fill=fill)
    elif kind == "bolt":
        s = px / 10
        d.polygon([(c + 1.2 * s, 0), (c - 3.2 * s, 5.4 * s), (c - 0.2 * s, 5.4 * s),
                   (c - 1.6 * s, 10 * s), (c + 3.4 * s, 3.8 * s), (c + 0.4 * s, 3.8 * s),
                   (c + 2.6 * s, 0)], fill=fill)
    elif kind == "crest":
        f = font("serif_bold", int(px * 0.62))
        d.ellipse((4, 4, px - 4, px - 4), outline=fill, width=max(2, px // 18))
        d.ellipse((px * 0.14, px * 0.14, px * 0.86, px * 0.86), outline=fill, width=max(1, px // 40))
        w = f.getlength("S")
        d.text((c - w / 2, c - px * 0.39), "S", font=f, fill=fill)
    return im.crop(im.getbbox())


def vertical_ja(text, px=200, fill=(255, 255, 255, 255)):
    """Japanese written top to bottom, upright when the stick stands."""
    cells = [text_art(c, "ja", px, fill=fill) for c in text]
    w = max(c.width for c in cells)
    gap = int(px * 0.12)
    out = Image.new("RGBA", (w, sum(c.height for c in cells) + gap * (len(cells) - 1)))
    y = 0
    for c in cells:
        out.alpha_composite(c, ((w - c.width) // 2, y))
        y += c.height + gap
    return out


class Canvas:
    def __init__(self, d):
        s = sticks.Stick(d)
        self.L = s.L
        self.C = 2 * math.pi * s.R
        self.im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def place_along(self, art, y_mid, height_mm, u=0.5):
        """Artwork drawn left-to-right, laid along the stick reading from the
        butt toward the tip, ``height_mm`` across the stick."""
        a = art.rotate(90, expand=True)          # reading upward
        self._paste(a, y_mid, height_mm * art.width / art.height, height_mm, u)

    def place_upright(self, art, y_mid, width_mm, u=0.5):
        """Artwork that stays upright when the stick stands on its butt."""
        self._paste(art, y_mid, width_mm * art.height / art.width, width_mm, u)

    def _paste(self, a, y_mid, len_mm, across_mm, u):
        px_w = max(1, round(across_mm / (self.C * 1000) * W))
        px_h = max(1, round(len_mm / (self.L * 1000) * H))
        # u grows toward the viewer's left on the front face: mirror to read right
        a = a.transpose(Image.FLIP_LEFT_RIGHT).resize((px_w, px_h), Image.LANCZOS)
        cx = u * W
        cy = (1 - y_mid / self.L) * H
        self.im.alpha_composite(a, (int(round(cx - px_w / 2)), int(round(cy - px_h / 2))))


def sovereign(c):
    gold = (128, 84, 18, 255)       # deep foil: reads on light hickory
    art = hstack([(shape_art("crest", 200, gold), 1.0),
                  (text_art("SOVEREIGN", "serif_bold", 160, 0.12, gold), 0.95),
                  (text_art("HICKORY  5A", "sans", 160, 0.1, gold), 0.42)], 0.5)
    c.place_along(art, 0.205, 6.4)


def ironstorm(c):
    red = (226, 26, 40, 255)
    art = hstack([(shape_art("bolt", 200, red), 1.0),
                  (text_art("IRON STORM", "display", 160, 0.04, red), 0.95),
                  (shape_art("bolt", 200, red), 1.0)], 0.35)
    c.place_along(art, 0.19, 7.2)


def sweetribbon(c):
    white = (255, 255, 255, 255)
    art = hstack([(shape_art("heart", 160, white), 0.7),
                  (text_art("Sweet Ribbon", "serif_italic", 160, 0.0, white), 1.0),
                  (shape_art("heart", 160, white), 0.7)], 0.35)
    c.place_along(art, 0.232, 6.2)


def starlight(c):
    gold = (240, 200, 96, 255)
    art = hstack([(shape_art("star", 160, gold), 0.8),
                  (text_art("Starlight", "serif_italic", 170, 0.02, gold), 1.0),
                  (shape_art("star", 160, gold), 0.55)], 0.3)
    c.place_along(art, 0.205, 7.0)


def yozakura(c):
    gold = (226, 184, 92, 255)
    c.place_upright(vertical_ja("夜桜", 220, gold), 0.215, 6.6)
    c.place_along(text_art("YOZAKURA", "sans", 160, 0.25, gold), 0.215, 2.0, u=0.38)


def neonpulse(c):
    white = (235, 250, 255, 255)
    art = hstack([(text_art("NEON", "display", 160, 0.06, white), 1.0),
                  (text_art("PULSE", "display", 160, 0.06, (0, 228, 255, 255)), 1.0)], 0.3)
    c.place_along(art, 0.104, 5.6)


DRAW = {"Sovereign": sovereign, "IronStorm": ironstorm, "SweetRibbon": sweetribbon,
        "Starlight": starlight, "Yozakura": yozakura, "NeonPulse": neonpulse}


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for d in sticks.DESIGNS:
        c = Canvas(d)
        DRAW[d["id"]](c)
        path = os.path.join(out_dir, "stick_%s.png" % d["id"])
        c.im.save(path, optimize=True)
        a = np.asarray(c.im)[..., 3]
        print("wrote", path, "ink px", int((a > 0).sum()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "export", "sticks", "logos"))
