"""Generate the favicon and home-screen icons from the logo shapes.

The shapes match static/img/logo.svg (64x64 design grid): a dark purple
background, a gold ring and a gold four-point sparkle.

Run from the project root:  python tools/make_icons.py
Writes PNG/ICO files to static/favicon/. Needs Pillow (in requirements.txt).
"""
import os

from PIL import Image, ImageChops, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "favicon")
S = 1024            # draw large, then scale down for smooth edges
U = S / 64          # one unit of the 64x64 design grid

BG_CENTER, BG_EDGE = (0x3A, 0x23, 0x78), (0x0B, 0x08, 0x16)
GOLD_STOPS = [(0.0, (0xF7, 0xDC, 0x8B)), (0.5, (0xE3, 0xB7, 0x5B)), (1.0, (0xA8, 0x76, 0x1A))]


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def background():
    """Radial gradient, lighter slightly above the centre (like the SVG)."""
    grad = Image.radial_gradient("L").resize((int(S * 1.5), int(S * 1.5)), Image.Resampling.BICUBIC)
    # radial_gradient is 0 in the centre and 255 at the edge; centre it at (50%, 35%)
    left, top = int(S * 0.75 - S * 0.5), int(S * 0.75 - S * 0.35)
    mask = grad.crop((left, top, left + S, top + S))
    return Image.composite(Image.new("RGB", (S, S), BG_EDGE), Image.new("RGB", (S, S), BG_CENTER), mask)


def gold():
    """Diagonal gold gradient (top-left light, bottom-right dark)."""
    image = Image.new("RGB", (S, S))
    pixels = image.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * (S - 1))
            for (t0, c0), (t1, c1) in zip(GOLD_STOPS, GOLD_STOPS[1:]):
                if t <= t1:
                    pixels[x, y] = lerp(c0, c1, (t - t0) / (t1 - t0))
                    break
    return image


def cubic(p0, p1, p2, p3, steps=40):
    return [tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
                  for a, b, c, d in zip(p0, p1, p2, p3))
            for t in (i / steps for i in range(steps + 1))]


def shapes_mask(ring_width, star_reach):
    """Ring + sparkle as a white-on-black mask."""
    mask = Image.new("L", (S, S), 0)
    draw = ImageDraw.Draw(mask)
    r = 21 * U
    draw.ellipse((32 * U - r - ring_width / 2, 32 * U - r - ring_width / 2,
                  32 * U + r + ring_width / 2, 32 * U + r + ring_width / 2), fill=255)
    draw.ellipse((32 * U - r + ring_width / 2, 32 * U - r + ring_width / 2,
                  32 * U + r - ring_width / 2, 32 * U + r - ring_width / 2), fill=0)

    # Four-point sparkle, same curves as the SVG path (which has star_reach 17):
    # from one tip to the next, e.g. M32 15 C33.6 26.4 37.6 30.4 49 32
    c, scale = 32, star_reach / 17
    k1, k2 = 1.6 * scale, 5.6 * scale
    pts = []
    for (tx, ty), (nx, ny) in (((0, -1), (1, 0)), ((1, 0), (0, 1)), ((0, 1), (-1, 0)), ((-1, 0), (0, -1))):
        start = (c + tx * star_reach, c + ty * star_reach)
        ctrl1 = (c + nx * k1 + tx * k2, c + ny * k1 + ty * k2)
        ctrl2 = (c + nx * k2 + tx * k1, c + ny * k2 + ty * k1)
        end = (c + nx * star_reach, c + ny * star_reach)
        pts += cubic(start, ctrl1, ctrl2, end)
    draw.polygon([(x * U, y * U) for x, y in pts], fill=255)
    return mask


def render(rounded, small=False):
    # Small icons get a thicker ring and bigger sparkle so they stay readable
    ring_width = (5.0 if small else 3.5) * U
    star_reach = 19 if small else 17
    image = background()
    image.paste(gold(), (0, 0), shapes_mask(ring_width, star_reach))
    image = image.convert("RGBA")
    if rounded:
        corners = Image.new("L", (S, S), 0)
        ImageDraw.Draw(corners).rounded_rectangle((0, 0, S - 1, S - 1), radius=14 * U, fill=255)
        image.putalpha(ImageChops.multiply(image.getchannel("A"), corners))
    return image


def save(image, name, size):
    image.resize((size, size), Image.Resampling.LANCZOS).save(os.path.join(OUT, name), optimize=True)
    print("wrote", name)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # Home-screen icons: full square, iOS/Android round the corners themselves
    square = render(rounded=False)
    save(square.convert("RGB"), "apple-touch-icon.png", 180)
    save(square, "android-chrome-192x192.png", 192)
    save(square, "android-chrome-512x512.png", 512)
    # Browser tab icons: rounded square with transparent corners
    small = render(rounded=True, small=True)
    save(small, "favicon-32x32.png", 32)
    save(small, "favicon-16x16.png", 16)
    small.resize((256, 256), Image.Resampling.LANCZOS).save(
        os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico")
