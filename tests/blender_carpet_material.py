"""Verify physical tile UVs and actual portable colour/roughness/normal export."""

from pathlib import Path
import json
import math
import struct
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import box, material  # noqa: E402
from carpet_material_v3 import refine_carpet_material  # noqa: E402
from materials_v2 import _carpet, _load_image  # noqa: E402

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
tex = ROOT / "assets/textures"
mat = material("Carpet / export fixture", (0.065, 0.068, 0.073), 0.96)
_carpet(mat, _load_image(tex / "carpet_weave.png", "sRGB"))
tile = box("Floor_Carpet_0_0", (0, 0, 0), (0.2997, 0.4997, 0.006), mat, 0)
tile.rotation_euler.z = math.pi / 2
tile.scale.x = 0.9
bpy.context.view_layer.update()
before = (tuple(v.co[:] for v in tile.data.vertices), tuple(map(tuple, tile.matrix_world)))
report = refine_carpet_material(mat, tex)
assert report["tiles"] == 1
assert before == (tuple(v.co[:] for v in tile.data.vertices), tuple(map(tuple, tile.matrix_world)))
face = next(face for face in tile.data.polygons if face.normal.z > 0.5)
uvs = [tile.data.uv_layers["UVMap"].data[i].uv[:] for i in face.loop_indices]
span = [max(uv[j] for uv in uvs) - min(uv[j] for uv in uvs) for j in range(2)]
assert abs(span[0] * 0.50 - 0.2997 * 0.9) < 1e-6
assert abs(span[1] * 0.50 - 0.4997) < 1e-6

with tempfile.TemporaryDirectory(prefix="room-carpet-regression-") as temp:
    path = Path(temp) / "tile.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_tangents=True,
        export_image_format="AUTO",
    )
    data = path.read_bytes()
    size, kind = struct.unpack_from("<II", data, 12)
    assert kind == 0x4E4F534A
    doc = json.loads(data[20 : 20 + size])
    exported = next(m for m in doc["materials"] if m["name"] == mat.name)
    pbr = exported["pbrMetallicRoughness"]
    assert "baseColorTexture" in pbr, "Carpet lost its portable pigment"
    assert "metallicRoughnessTexture" in pbr, "Carpet lost registered roughness"
    assert "normalTexture" in exported, "Carpet lost its fibre normal"
    assert abs(exported["normalTexture"]["scale"] - 0.30) < 1e-6
    for texture in (
        pbr["baseColorTexture"],
        pbr["metallicRoughnessTexture"],
        exported["normalTexture"],
    ):
        assert texture.get("texCoord", 0) == 0
print("CARPET_MATERIAL_REGRESSION_PASS: three portable maps and physical clipped-tile UVs")
