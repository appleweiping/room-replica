"""Mask-restricted photograph sampling onto the actual packet's existing UVs.

Only the packaging region is sampled; no screen text is extracted. The saved
captured layer and estimated base color are separate, with explicit fill masks.
"""

from pathlib import Path
import argparse
import hashlib
import importlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter, map_coordinates, median_filter

P = Path(__file__).resolve().parent
ROOT = P.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--reference", type=Path)
parser.add_argument("--ocio-config", type=Path, required=True)
parser.add_argument("--ocio-module-dir", type=Path)
args = parser.parse_args()
if args.ocio_module_dir:
    sys.path.insert(0, str(args.ocio_module_dir))
ocio = importlib.import_module("PyOpenColorIO")

recipe = json.loads((P / "sampling-recipe.json").read_text(encoding="utf8"))
source = args.reference or ROOT / recipe["reference_file"]
assert hashlib.sha256(source.read_bytes()).hexdigest() == recipe["reference_sha256"]
photo = Image.open(source).convert("RGB")
mask_image = Image.new("L", photo.size, 0)
draw = ImageDraw.Draw(mask_image)
draw.polygon([tuple(v) for v in recipe["outer_mask_polygon"]], fill=255)
for polygon in recipe["occlusion_polygons"]:
    draw.polygon([tuple(v) for v in polygon], fill=0)
mask_image.save(P / "source-package-mask.png")
valid_source = np.asarray(mask_image) > 0
raw_source = np.asarray(photo).astype(float) / 255
source_rgba = np.zeros((*raw_source.shape[:2], 4), dtype=np.uint8)
source_rgba[valid_source, :3] = np.uint8(np.rint(raw_source[valid_source] * 255))
source_rgba[valid_source, 3] = 255
# Crop retained pixels to the product region; no hidden RGB survives alpha=0.
Image.fromarray(source_rgba).crop((1140, 660, 1550, 955)).save(P / "masked-source-package.png")

spec_mask_im = Image.new("L", photo.size, 0)
dr = ImageDraw.Draw(spec_mask_im)
for poly in recipe["specular_suppression_polygons"]:
    dr.polygon([tuple(v) for v in poly], fill=255)
spec_region = (np.asarray(spec_mask_im) > 0) & valid_source
lum = raw_source @ np.array([0.2126, 0.7152, 0.0722])
local = gaussian_filter(median_filter(lum, size=11), 5)
ceiling = local * 1.16 + 0.025
scale = np.minimum(1, ceiling / np.maximum(lum, 1e-5))
scale = np.where(spec_region, scale, 1)
deglinted = raw_source * scale[..., None]

n = 1024
y, x = np.mgrid[:n, :n]
u = x / (n - 1)
v = 1 - y / (n - 1)
across = np.clip((1 - np.cos(2 * np.pi * u)) * 0.5, 0, 1)
interp = RegularGridInterpolator(
    (recipe["uv_rows_v"], recipe["uv_columns_across"]),
    np.array(recipe["source_pixel_grid"]),
    bounds_error=False,
    fill_value=None,
)
xy = interp(np.stack((v, across), -1))
source_valid = (
    map_coordinates(valid_source.astype(float), [xy[..., 1], xy[..., 0]], order=0, mode="constant")
    > 0.5
)
source_valid &= (u >= 0.005) & (u <= 0.495)


def sample(image):
    return np.stack(
        [
            map_coordinates(image[..., k], [xy[..., 1], xy[..., 0]], order=1, mode="nearest")
            for k in range(3)
        ],
        -1,
    )


captured = sample(raw_source)
deglinted_uv = sample(deglinted)
raw_rgba = np.zeros((n, n, 4), np.uint8)
raw_rgba[source_valid, :3] = np.uint8(np.rint(np.clip(captured[source_valid], 0, 1) * 255))
raw_rgba[source_valid, 3] = 255
Image.fromarray(raw_rgba).save(P / "captured-front-panel.png")
Image.fromarray(np.uint8(~source_valid) * 255).save(P / "inferred-texels.png")
suppression = (
    map_coordinates(1 - scale, [xy[..., 1], xy[..., 0]], order=1, mode="nearest") * source_valid
)
Image.fromarray(np.uint8(np.clip(suppression * 255, 0, 255))).save(
    P / "captured-highlight-reduction.png"
)

# Fill only with unprinted material color; hidden words/logos are not invented.
gold = np.median(raw_source[850:880, 1280:1335].reshape(-1, 3), axis=0)
dark = np.median(raw_source[771:787, 1370:1390].reshape(-1, 3), axis=0)
fill = np.where((v < 0.39)[..., None], gold, dark)
filled = np.where(source_valid[..., None], deglinted_uv, fill)
config = ocio.Config.CreateFromFile(str(args.ocio_config))
look = ocio.LookTransform()
look.setSrc("Linear Rec.709")
look.setDst("Linear Rec.709")
look.setLooks("AgX - Medium High Contrast")
view = ocio.DisplayViewTransform()
view.setSrc("Linear Rec.709")
view.setDisplay("sRGB")
view.setView("AgX")
group = ocio.GroupTransform()
group.appendTransform(look)
group.appendTransform(view)
group.setDirection(ocio.TRANSFORM_DIR_INVERSE)
linear = filled.astype(np.float32).reshape(-1, 3)
config.getProcessor(group).getDefaultCPUProcessor().applyRGB(linear)
linear = linear.reshape(n, n, 3) * recipe["linear_rgb_gain"]
outside = (linear < 0) | (linear > 0.92)
linear = np.clip(linear, 0, 0.92)
base = np.where(
    linear <= 0.0031308, linear * 12.92, 1.055 * np.maximum(linear, 0) ** (1 / 2.4) - 0.055
)
Image.fromarray(np.uint8(np.rint(np.clip(base, 0, 1) * 255))).save(P / "estimated-basecolor.png")

# Compression normal is authored independently of the photographed ink. This
# prevents the brand lettering from becoming fake embossed geometry.
rng = np.random.default_rng(601)
height = np.zeros((n, n))
for i in range(23):
    cu, cv = rng.uniform(0.055, 0.46), rng.uniform(0.03, 0.42)
    angle = rng.uniform(-1.0, 2.1)
    q = (u - cu) * np.cos(angle) + (v - cv) * np.sin(angle)
    d = -(u - cu) * np.sin(angle) + (v - cv) * np.cos(angle)
    width = rng.uniform(0.0025, 0.0055)
    length = rng.uniform(0.035, 0.12)
    height += rng.uniform(-0.8, 0.8) * np.exp(-((d / width) ** 2)) * np.exp(-((q / length) ** 4))
height *= np.clip(np.minimum(u, 0.5 - u) / 0.02, 0, 1) * np.clip(v / 0.025, 0, 1)
dy, dx = np.gradient(height)
normal = np.stack((-dx * 3, dy * 3, np.ones_like(dx)), -1)
normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
Image.fromarray(np.uint8(np.rint(np.clip(normal * 0.5 + 0.5, 0, 1) * 255))).save(
    P / "shallow-compression-normal.png"
)

files = {
    p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in P.glob("*.png")
}
report = {
    "version": "6.0.0",
    "source_photo_sha256": recipe["reference_sha256"],
    "source_photo": recipe["reference_file"],
    "sampled_content": "Visible main potato-chip wrapper only: photographed Lay’s logo, red band, black/gold printed film. No exact product model inferred.",
    "excluded_content": "Laptop/tablet/phone contents, desk/background, overlaid small sachets and their unrelated print. Transparent output pixels are zero RGB.",
    "sampling": "One manually constrained 4×3 UV-to-photo control grid on the existing three-dimensional v5 wrapper. No camera-plane geometry or whole-photo billboard.",
    "source_views": "Photograph12 supplies texels; 2 and 9 inform/verify appearance but are not stitched into this candidate.",
    "captured_layer": "captured-front-panel.png retains original photographed illumination. It is diagnostic, not used directly by the material.",
    "estimated_layer": "estimated-basecolor.png uses selective local highlight reduction and a common RGB gain under fixed Cycles/AgX/exposure. Residual captured shadows remain; this is not measured albedo.",
    "unobserved_texels": "Explicitly flagged in inferred-texels.png; filled with plain sampled unprinted gold/dark color, without reconstructed hidden writing.",
    "normal": "Authored deterministic shallow compression field, seed601. No luminance-to-height conversion of the brand/ink.",
    "observed_texel_fraction_full_wrap": float(np.mean(source_valid)),
    "observed_texel_fraction_front_half": float(np.mean(source_valid[:, :512])),
    "highlight_reduced_observed_fraction": float(np.mean(suppression[source_valid] > 0.01)),
    "basecolor_clipped_channel_fraction": float(np.mean(outside)),
    "license": "Photo-derived packaging artwork retains its underlying rights and trademarks; the source photo is the author's own. Do not relabel the captured artwork CC0. The separate authored compression normal is original project artwork.",
    "files": files,
}
(P / "PROVENANCE.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print("CAPTURED", report["observed_texel_fraction_front_half"], "FRONT_TEXELS", flush=True)
