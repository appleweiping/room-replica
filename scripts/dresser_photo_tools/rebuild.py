"""Rectify only three bare wooden drawer faces; retain masks and estimates."""

from pathlib import Path
import hashlib
import json
import argparse
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates, label

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--reference", type=Path, default=ROOT / "references/c2d339261e96b29ef5bc46021753e752.jpg"
)
parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/dresser-photo-rebuild")
args = parser.parse_args()
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
source = args.reference.resolve()
published = ROOT / "assets/textures/dresser_photo_v5"
expected = json.loads((published / "PROVENANCE.json").read_text(encoding="utf8"))
if hashlib.sha256(source.read_bytes()).hexdigest() != expected["source_sha256"]:
    raise ValueError(
        "This recipe requires the exact reference-14 source recorded in PROVENANCE.json"
    )
im = Image.open(source).convert("RGB")
raw_photo = np.asarray(im) / 255
quads = {
    3: [[442, 892], [829, 903], [828, 974], [457, 962]],
    2: [[458, 979], [828, 989], [826, 1069], [473, 1058]],
    1: [[474, 1074], [826, 1084], [824, 1159], [487, 1146]],
}
exclusions = [
    {
        "name": "power cable and local shadow",
        "polygon": [
            [753, 882],
            [780, 884],
            [773, 943],
            [773, 991],
            [770, 1049],
            [773, 1081],
            [771, 1124],
            [754, 1165],
            [735, 1162],
            [753, 1119],
            [754, 1082],
            [751, 1049],
            [753, 989],
            [755, 945],
        ],
    },
    {
        "name": "hanging sticker and edge shadow",
        "polygon": [[726, 884], [763, 888], [763, 920], [735, 919]],
    },
]
W, H = 512, 138
v, u = np.mgrid[0 : 1 : complex(H), 0 : 1 : complex(W)]


def lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def srgb(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.maximum(x, 0) ** (1 / 2.4) - 0.055)


def save(a, p):
    Image.fromarray(np.rint(np.clip(a, 0, 1) * 255).astype("uint8")).save(OUT / p)


records = []
for number, quad in sorted(quads.items()):
    A = []
    b = []
    for (a, c), (x, y) in zip(((0, 0), (1, 0), (1, 1), (0, 1)), quad):
        A.extend([[a, c, 1, 0, 0, 0, -a * x, -c * x], [0, 0, 0, a, c, 1, -a * y, -c * y]])
        b.extend([x, y])
    hm = np.r_[np.linalg.solve(A, b), 1].reshape(3, 3)
    q = np.stack([u, v, np.ones_like(u)], -1) @ hm.T
    pixels = q[:, :, :2] / q[:, :, 2:]
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([tuple(p) for p in quad], fill=255)
    draw.line([tuple(p) for p in quad + [quad[0]]], width=3, fill=255)
    for item in exclusions:
        draw.polygon([tuple(p) for p in item["polygon"]], fill=0)
    valid = map_coordinates(np.asarray(mask), [pixels[:, :, 1], pixels[:, :, 0]], order=0) > 127
    captured = np.stack(
        [
            map_coordinates(raw_photo[:, :, k], [pixels[:, :, 1], pixels[:, :, 0]], order=1)
            for k in range(3)
        ],
        -1,
    )
    rgb = lin(captured)
    filled = rgb.copy()
    parts, n = label(~valid)
    fills = []
    for component in range(1, n + 1):
        yy, xx = np.where(parts == component)
        x0, x1 = xx.min(), xx.max() + 1
        y0, y1 = yy.min(), yy.max() + 1
        region = parts[y0:y1, x0:x1] == component
        possible = [
            dx
            for dx in range(-W, W)
            if dx and 0 <= x0 + dx and x1 + dx <= W and valid[y0:y1, x0 + dx : x1 + dx].all()
        ]
        if not possible:
            raise ValueError("No observed same-row donor")
        dx = min(possible, key=abs)
        donor = rgb[y0:y1, x0 + dx : x1 + dx].copy()
        # Grain runs horizontally; same-row donor preserves its observed scale.
        for row in range(y1 - y0):
            ids = np.flatnonzero(region[row])
            if not len(ids):
                continue
            edges = [x0 + ids[0] - 1, x0 + ids[-1] + 1]
            left, right = edges
            scale_left = (
                rgb[y0 + row, left] / np.maximum(donor[row, ids[0]], 0.0001)
                if 0 <= left < W and valid[y0 + row, left]
                else np.ones(3)
            )
            scale_right = (
                rgb[y0 + row, right] / np.maximum(donor[row, ids[-1]], 0.0001)
                if 0 <= right < W and valid[y0 + row, right]
                else scale_left
            )
            t = (np.arange(x1 - x0) - ids[0]) / max(1, ids[-1] - ids[0])
            correction = np.exp(
                (1 - t[:, None]) * np.log(np.clip(scale_left, 0.4, 2.5))
                + t[:, None] * np.log(np.clip(scale_right, 0.4, 2.5))
            )
            donor[row] *= correction
        filled[y0:y1, x0:x1][region] = donor[region]
        fills.append(
            {
                "component": component,
                "destination_xyxy": [int(x0), int(y0), int(x1), int(y1)],
                "horizontal_donor_offset_px": dx,
                "pixels": int(region.sum()),
            }
        )
    feats = np.stack([np.ones_like(u), u - 0.5, v - 0.5], -1)
    selected = valid & (np.indices(valid.shape).sum(0) % 3 == 0)
    coeff = np.linalg.lstsq(feats[selected], np.log(np.maximum(rgb[selected], 0.0001)), rcond=None)[
        0
    ]
    trend = (u - 0.5)[:, :, None] * coeff[1] + (v - 0.5)[:, :, None] * coeff[2]
    estimate = np.exp(np.log(np.maximum(filled, 0.0001)) - trend)
    stem = f"drawer-{number}"
    save(np.where(valid[:, :, None], captured, 0), stem + "-masked-captured.png")
    save(srgb(filled), stem + "-filled-captured.png")
    save(valid, stem + "-observed-mask.png")
    save(srgb(estimate), stem + "-estimated-basecolor-uncalibrated.png")
    save(srgb(estimate), stem + "-estimated-basecolor.png")
    records.append(
        {
            "object": f"Dresser drawer {number}",
            "source_quad_tl_tr_br_bl": quad,
            "homography_uv_to_source": hm.tolist(),
            "rectified_size": [W, H],
            "native_front_size_m": [0.73462725, 0.1961064],
            "inferred_fraction": float((~valid).mean()),
            "fills": fills,
            "first_order_log_illumination_coefficients": coeff.tolist(),
        }
    )
report = {
    "version": "5.0-experimental",
    "source_reference": 14,
    "source_filename": source.name,
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "method": "Three separate photographed wood interiors, each used once on its corresponding rigid drawer face. Masked cord, shadow and sticker filled from nearest observed same-row patch of the same drawer. First-order log illumination estimate; not measured albedo. No source photograph text or personal objects in delivered maps.",
    "source_size": list(im.size),
    "exclusions": exclusions,
    "boards": records,
    "limitations": [
        "Manual sample quads are inset and approximate, not surveyed corners.",
        "512x138 resampling adds no captured detail to roughly 350x80 source pixels.",
        "Source illumination and smartphone color processing are unknown; remaining broad color will be checked in actual Cycles views.",
        "Drawer mesh, original UV0, unobserved edge/back PBR and physical size remain unchanged.",
    ],
}
(OUT / "PROVENANCE.json").write_text(json.dumps(report, indent=2), encoding="utf8")
calibration = json.loads((published / "COLOR_CALIBRATION.json").read_text(encoding="utf8"))
for number, gain in enumerate(calibration["board_center_gains"], 1):
    captured = (
        np.asarray(Image.open(OUT / f"drawer-{number}-estimated-basecolor-uncalibrated.png")) / 255
    )
    save(srgb(lin(captured) * np.asarray(gain)), f"drawer-{number}-estimated-basecolor.png")
(OUT / "COLOR_CALIBRATION.json").write_text(json.dumps(calibration, indent=2), encoding="utf8")
print("DRAWER_TEXTURES_READY", [(r["object"], round(r["inferred_fraction"], 4)) for r in records])
