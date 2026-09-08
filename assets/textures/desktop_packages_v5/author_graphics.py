"""Original small surface graphics; no reference-image pixels are read."""

from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

P = Path(__file__).resolve().parent
rng = np.random.default_rng(52105)


def normal(name, height, strength):
    dy, dx = np.gradient(height.astype(float))
    vector = np.stack((-dx * strength, dy * strength, np.ones_like(dx)), -1)
    vector /= np.linalg.norm(vector, axis=-1, keepdims=True)
    Image.fromarray(np.uint8(np.clip(vector * 0.5 + 0.5, 0, 1) * 255)).save(P / name)


# Repeating embossed dots following gently curved diamond bands. These are
# surface-scale paper embossing, not a surrogate for the roll silhouette.
n = 1024
y, x = np.mgrid[:n, :n]
a = x / n * 8
b = y / n * 8
diamond = np.abs((a + 0.16 * np.sin(b * np.pi)) % 1 - 0.5) + np.abs(b % 1 - 0.5)
dots = np.exp(-((np.sin(a * np.pi * 8)) ** 2 + (np.sin(b * np.pi * 8)) ** 2) / 0.16)
h = dots * np.exp(-(((diamond - 0.55) / 0.12) ** 2)) * 0.7
h += gaussian_filter(rng.normal(0, 0.018, (n, n)), 0.6)
normal("paper-emboss-normal.png", h, 3.0)
paper = np.clip(239 + gaussian_filter(rng.normal(0, 2, (n, n)), 0.55), 0, 255)
Image.fromarray(np.uint8(np.stack((paper, paper - 1, paper - 6), -1))).save(
    P / "paper-fiber-albedo.png"
)
r = np.sqrt(((x - n / 2) / (n / 2)) ** 2 + ((y - n / 2) / (n / 2)) ** 2)
angle = np.arctan2(y - n / 2, x - n / 2)
layers = 0.5 + 0.5 * np.cos(2 * np.pi * (r * 128 + 0.09 * np.sin(angle * 5) + angle / (2 * np.pi)))
normal(
    "paper-end-normal.png", layers * 0.13 + gaussian_filter(rng.normal(0, 0.06, (n, n)), 0.5), 1.7
)
end = 229 + 9 * layers + rng.normal(0, 0.7, (n, n))
Image.fromarray(np.uint8(np.clip(np.stack((end, end - 2, end - 9), -1), 0, 255))).save(
    P / "paper-end-albedo.png"
)

# Neutral, original packaging. UV V runs from the open gold end to the sealed
# dark end; the print wraps the actual irregular bag shell.
w, h = 1024, 1536
im = Image.new("RGB", (w, h), "#28261f")
d = ImageDraw.Draw(im)
d.rectangle((0, int(h * 0.57), w, h), fill="#94743b")
d.rectangle((0, int(h * 0.57), w, int(h * 0.582)), fill="#c5b07a")
d.polygon([(205, 230), (293, 230), (303, 1370), (231, 1370)], fill="#b74629")
font = lambda size: ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
bold = lambda size: ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
d.ellipse((150, 570, 376, 770), fill="#caaa63", outline="#d2c08b", width=4)
d.rounded_rectangle((133, 628, 397, 713), 7, fill="#a13927")
d.text((265, 668), "CRISPS", anchor="mm", font=bold(39), fill="#eee1b8")
d.text((263, 781), "LIGHTLY SALTED", anchor="mm", font=font(15), fill="#ddd0a3")
d.text((267, 943), "GOLDEN", anchor="mm", font=bold(32), fill="#44371f")
d.text((267, 981), "POTATO CRISPS", anchor="mm", font=font(19), fill="#44371f")
for yy in range(185, 450, 24):
    d.line((682, yy, 901 - (yy % 3) * 11, yy), fill="#918d7d", width=2)
d.text((690, 475), "CONTENTS  /  70 g", font=font(14), fill="#a29d8a")
im.save(P / "neutral-crisps-print.png")
rough = np.clip(139 + gaussian_filter(rng.normal(0, 11, (h, w)), 3), 0, 255)
Image.fromarray(np.uint8(rough)).save(P / "wrapper-roughness.png")
normal("wrapper-micro-normal.png", gaussian_filter(rng.normal(0, 1, (512, 512)), 2), 0.25)

files = {
    p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in sorted(P.glob("*.png"))
}
(P / "PROVENANCE.json").write_text(
    json.dumps(
        {
            "author": "Original procedural graphics authored by Codex for this room reconstruction",
            "method": "Deterministic NumPy/Pillow/SciPy raster drawing; no downloaded images, no photograph pixels, no personal screen information.",
            "seed": 52105,
            "references": [
                "User photographs 2, 9 and 12 inform object type and broad color distribution only."
            ],
            "license": "CC0-1.0 for these authored raster assets and this generating script.",
            "fonts": "Arial/Arial Bold rasterized with the local Windows font installation; font files are not redistributed.",
            "files": files,
        },
        indent=2,
    ),
    encoding="utf8",
)
print("AUTHORED", len(files), "texture files")
