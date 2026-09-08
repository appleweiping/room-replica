"""Author deterministic plain-weave maps, without photographic input."""

from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/textures/backpack_v4"
OUT.mkdir(parents=True, exist_ok=True)
n = 2048
period_m = 0.064
threads = 160
pitch = period_m / threads
y, x = np.mgrid[:n, :n].astype(np.float32) / n * threads
fx = x - np.floor(x) - 0.5
fy = y - np.floor(y) - 0.5
wx = np.sqrt(np.maximum(0, 1 - (fx / 0.485) ** 2))
wy = np.sqrt(np.maximum(0, 1 - (fy / 0.485) ** 2))
parity = ((np.floor(x) + np.floor(y)).astype(np.int32) % 2).astype(np.float32)
# Alternating warp/weft overlap. Each yarn has a rounded cross-section and
# 8 micron filament relief; no random object-scale surface bumps are baked.
h = (wx * (0.38 + 0.62 * parity) + wy * (1 - 0.62 * parity)) * 0.000026
h += 0.0000018 * (np.cos(x * 2 * np.pi * 5) + np.cos(y * 2 * np.pi * 5))
dy, dx = np.gradient(h, period_m / n)
normal = np.stack((-dx, dy, np.ones_like(dx)), axis=-1)
normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
Image.fromarray(np.clip((normal * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)).save(
    OUT / "plain_weave_normal.png"
)
value = 0.96 + 0.04 * (wx + wy - 1)
Image.fromarray(np.clip(value * 255, 0, 255).astype(np.uint8)).save(
    OUT / "plain_weave_variation.png"
)
rough = 0.63 + 0.055 * (1 - np.minimum(wx, wy))
Image.fromarray(np.clip(rough * 255, 0, 255).astype(np.uint8)).save(
    OUT / "plain_weave_roughness.png"
)
for level in (0.62, 0.81, 0.76, 0.68, 0.89):
    Image.fromarray(np.clip((rough + level - 0.65) * 255, 0, 255).astype(np.uint8)).save(
        OUT / f"plain_weave_roughness_{round(level * 100):02d}.png"
    )
manifest = {
    "asset": "Backpack V4 authored plain weave",
    "origin": "Original deterministic procedural textile; no source photograph or downloaded material used.",
    "recipe": {
        "tile_width_m": period_m,
        "yarn_pitch_m": pitch,
        "thread_count_each_axis": threads,
        "height_scale_m": 0.000026,
        "resolution": [n, n],
        "normal_convention": "OpenGL tangent space",
    },
    "licensing": "Authored for this project; no third-party asset license. Follows the project asset licensing terms.",
    "appearance_limit": "Generic woven polyester/nylon approximation. It is not a measured scan of the photographed backpack.",
    "files": {
        p.relative_to(ROOT).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in OUT.glob("*.png")
    },
}
P = ROOT / "assets/provenance"
P.mkdir(exist_ok=True)
(P / "backpack_surface_v4.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
