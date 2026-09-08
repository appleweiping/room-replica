"""Create original, reproducible textile and small graphic assets (no photo pixels)."""

from pathlib import Path
import random, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "textures"
OUT.mkdir(parents=True, exist_ok=True)
random.seed(521)
N = 1536


def textile(name, base, large=False):
    im = Image.new("RGB", (N, N), base)
    d = ImageDraw.Draw(im)
    spacing = 385 if large else 170
    for gy in range(-1, N // spacing + 2):
        for gx in range(-1, N // spacing + 2):
            x = (
                gx * spacing
                + (gy % 2) * spacing / 2
                + random.uniform(-spacing * 0.24, spacing * 0.24)
            )
            y = gy * spacing + random.uniform(-spacing * 0.23, spacing * 0.23)
            sz = random.uniform(37, 65) if large else random.uniform(12, 24)
            for lx, ly, angle in [
                (-sz * 0.8, sz * 0.65, -0.8),
                (sz * 0.6, sz * 0.8, 0.4),
                (-sz * 0.7, -sz * 0.7, 2.1),
            ]:
                cx, cy = x + lx, y + ly
                vx, vy = math.cos(angle) * sz * 0.9, math.sin(angle) * sz * 0.9
                pts = [
                    (cx - vx, cy - vy),
                    (cx - vy * 0.45, cy + vx * 0.45),
                    (cx + vx, cy + vy),
                    (cx + vy * 0.45, cy - vx * 0.45),
                ]
                d.polygon(
                    pts,
                    fill=random.choice(
                        [(108, 128, 107), (128, 143, 113), (137, 150, 128), (99, 118, 99)]
                    ),
                )
                d.line([(cx - vx, cy - vy), (cx + vx, cy + vy)], fill=(88, 101, 80), width=2)
            for ring in range(5):
                radius = sz * (1 - ring * 0.16)
                for p in range(7):
                    theta = p * math.tau / 7 + ring * 0.8
                    cx = x + math.cos(theta) * radius * 0.37
                    cy = y + math.sin(theta) * radius * 0.32
                    r = radius * 0.64
                    shade = ring * 12 + random.randrange(-12, 13)
                    color = (max(139, 231 - shade), max(71, 170 - shade), max(98, 183 - shade))
                    d.ellipse(
                        (cx - r, cy - r * 0.7, cx + r, cy + r * 0.7),
                        fill=color,
                        outline=(
                            max(106, color[0] - 25),
                            max(58, color[1] - 27),
                            max(78, color[2] - 24),
                        ),
                        width=1,
                    )
            if large:
                # Thin botanical arcs characteristic of the blue floral comforter.
                pts = []
                for k in range(70):
                    t = k / 69
                    pts.append((x + sz + 140 * t, y + sz * math.sin(t * 5) * 0.5))
                d.line(pts, fill=(119, 145, 151), width=2)
    ar = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(521)
    grain = rng.normal(0, 1.6, (N, N, 1))
    weave = (np.arange(N)[None, :, None] % 3 == 0) * -2 + (
        np.arange(N)[:, None, None] % 3 == 0
    ) * 1.5
    Image.fromarray(np.uint8(np.clip(ar + grain + weave, 0, 255))).save(OUT / name)


def carpet():
    rng = np.random.default_rng(11)
    base = rng.normal(0, 5, (768, 768))
    col = np.zeros((768, 768, 3), dtype=float) + [78, 76, 70]
    rows = rng.normal(0, 3, (768, 1))
    stripes = np.sin(np.arange(768) * 2.5)[None, :] * 3
    col += base[:, :, None] + rows[:, :, None] + stripes[:, :, None]
    Image.fromarray(np.uint8(np.clip(col, 0, 255))).save(OUT / "carpet_weave.png")


def graphics():
    im = Image.new("RGB", (640, 880), "#eeeae2")
    d = ImageDraw.Draw(im)
    d.text((50, 45), "RESIDENT INFORMATION", fill="#292b28")
    d.line((50, 90, 590, 90), fill="#747771", width=2)
    for r in range(13):
        d.rectangle((380, 130 + r * 45, 565, 163 + r * 45), fill="#64675e")
        d.line((65, 140 + r * 40, 290, 140 + r * 40), fill="#aaa99e", width=2)
    d.polygon(
        [(120, 650), (90, 710), (110, 710), (110, 765), (132, 765), (132, 710), (152, 710)],
        outline="#34382f",
        width=3,
    )
    d.text((50, 825), "Reconstruction / generic notice", fill="#65635d")
    im.save(OUT / "door_notice.png")


if __name__ == "__main__":
    textile("rose_cotton.png", (223, 210, 185))
    textile("blue_floral.png", (140, 175, 203), True)
    carpet()
    graphics()
    print("Created four original textures in", OUT)
