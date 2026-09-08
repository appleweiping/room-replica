"""Explicitly masked household packaging capture; requires the private reference."""

from pathlib import Path
import argparse
import hashlib
import importlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates

P = Path(__file__).resolve().parent
R = P.parents[2]


def transform(quad, width, height):
    corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    equations, values = [], []
    for (u, v), (x, y) in zip(corners, quad):
        equations.extend([[u, v, 1, 0, 0, 0, -x * u, -x * v], [0, 0, 0, u, v, 1, -y * u, -y * v]])
        values.extend([x, y])
    h = np.r_[np.linalg.solve(equations, values), 1].reshape(3, 3)
    y, x = np.mgrid[:height, :width]
    q = np.stack((x / (width - 1), y / (height - 1), np.ones_like(x)), -1) @ h.T
    return q[..., :2] / q[..., 2:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--ocio-config", type=Path, required=True)
    parser.add_argument("--ocio-module-dir", type=Path)
    args = parser.parse_args()
    if args.ocio_module_dir:
        sys.path.insert(0, str(args.ocio_module_dir))
    ocio = importlib.import_module("PyOpenColorIO")
    recipe = json.loads((P / "sampling-recipe.json").read_text(encoding="utf8"))
    source = args.reference or R / recipe["source_file"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == recipe["source_sha256"]
    photo = Image.open(source).convert("RGB")
    rgb = np.array(photo) / 255
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
    processor = config.getProcessor(group).getDefaultCPUProcessor()
    result = {}
    for name, record in recipe["packages"].items():
        mask = Image.new("L", photo.size, 0)
        ImageDraw.Draw(mask).polygon([tuple(p) for p in record["source_mask"]], fill=255)
        mask.save(P / f"{name}-source-mask.png")
        valid_source = np.array(mask) > 0
        clean = np.zeros((*rgb.shape[:2], 4), np.uint8)
        clean[valid_source, :3] = np.rint(rgb[valid_source] * 255).astype(np.uint8)
        clean[valid_source, 3] = 255
        Image.fromarray(clean).crop(record["crop"]).save(P / f"{name}-masked-source.png")
        width, height = record["atlas_size"]
        captured = np.zeros((height, width, 4), np.uint8)
        # Plain sampled colors only for the hidden underside and unobserved edges.
        fallback = np.array(record["unobserved_srgb"])
        filled = np.broadcast_to(fallback, (height, width, 3)).copy()
        for surface in record["surfaces"]:
            y0, y1 = surface["atlas_rows"]
            xy = transform(surface["source_quad"], width, y1 - y0)
            co = [xy[..., 1], xy[..., 0]]
            valid = map_coordinates(valid_source.astype(float), co, order=0, mode="constant") > 0.5
            sampled = np.stack(
                [map_coordinates(rgb[..., k], co, order=1, mode="nearest") for k in range(3)], -1
            )
            target = captured[y0:y1]
            target[valid, :3] = np.rint(np.clip(sampled[valid], 0, 1) * 255).astype(np.uint8)
            target[valid, 3] = 255
            filled[y0:y1][valid] = sampled[valid]
        Image.fromarray(captured).save(P / f"{name}-captured.png")
        Image.fromarray(np.uint8(captured[..., 3] == 0) * 255).save(
            P / f"{name}-inferred-texels.png"
        )
        linear = filled.astype(np.float32).reshape(-1, 3)
        processor.applyRGB(linear)
        linear = linear.reshape(height, width, 3) * recipe["linear_rgb_gain"]
        clipped = np.mean((linear < 0) | (linear > 0.88))
        linear = np.clip(linear, 0, 0.88)
        srgb = np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)
        Image.fromarray(np.rint(srgb * 255).astype(np.uint8)).save(
            P / f"{name}-estimated-basecolor.png"
        )
        # Original tiny pressure lines, independent of captured writing.
        yy, xx = np.mgrid[:height, :width]
        u, v = xx / (width - 1), yy / (height - 1)
        rng = np.random.default_rng(710 if name == "wipes" else 711)
        field = np.zeros((height, width))
        for _ in range(19):
            cu, cv = rng.uniform(0, 1, 2)
            slope = rng.uniform(-2, 2)
            dd = v - cv - slope * (u - cu)
            field += (
                rng.uniform(-0.35, 0.35)
                * np.exp(-((dd / rng.uniform(0.007, 0.022)) ** 2))
                * np.exp(-(((u - cu) / rng.uniform(0.035, 0.13)) ** 4))
            )
        dy, dx = np.gradient(field)
        normals = np.stack((-dx * 2.8, dy * 2.8, np.ones_like(dx)), -1)
        normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
        Image.fromarray(np.rint(np.clip(normals * 0.5 + 0.5, 0, 1) * 255).astype(np.uint8)).save(
            P / f"{name}-pressure-normal.png"
        )
        result[name] = {
            "observed_atlas_fraction": float(np.mean(captured[..., 3] > 0)),
            "clipped_basecolor_channel_fraction": float(clipped),
        }
    report = {
        "version": "7.0.0",
        "source_file": recipe["source_file"],
        "source_sha256": recipe["source_sha256"],
        "method": "Hand-masked photograph11 household package surface samples mapped onto separately modeled volumes. References10/14 constrain/check placement; no multiview pixel stitch.",
        "captured_vs_estimated": "Captured images retain photographed illumination. Estimated color uses one common RGB gain under unchanged scene AgX/exposure; not measured albedo. No changes to room lighting.",
        "privacy": "Only necessary wet-wipe/snack surface pixels retained; alpha-zero pixels contain zero RGB. No original full photograph is copied into this asset folder.",
        "unseen": "Explicit inference masks identify plain-color unobserved underside and edge fill. Hidden writing is not invented.",
        "rights": "User-authorized photograph-derived packaging art retains underlying rights/trademarks. Do not describe it as CC0. Pressure normals are separately authored original project graphics, not writing converted to height.",
        "packages": result,
        "files": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in sorted(P.glob("*.png"))
        },
    }
    (P / "PROVENANCE.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
