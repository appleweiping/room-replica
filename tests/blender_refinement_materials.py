"""Exercise the guard/wood boundary and actual rotated VCT glTF portability.

Run with Blender --background --python-exit-code 1 --python this_file.py.
The guard's extruded end faces previously collapsed to zero UV area, although
its isolated rendered front face appeared correct.
"""

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
from bed_guard_v4 import refine_bed_guard  # noqa: E402
from wood_uv_v3 import refine_wood_uvs  # noqa: E402
from vinyl_layout_v4 import refine_vinyl_layout  # noqa: E402
from vinyl_material_v4 import refine_vinyl_material  # noqa: E402

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
oak = material("Regression oak", (0.25, 0.15, 0.05), 0.45)
black = material("Regression black", (0.02, 0.02, 0.02), 0.5)
box("Bed_guard_oak_cap", (0, 3.46, 0.68), (0.75, 0.04, 0.14), oak, 0)
box("Bed_guard_panel", (0, 3.43, 0.68), (0.72, 0.01, 0.12), black, 0)
for y in (3.5, 4.3):
    box("Bed_support_steel", (0, y, 0.35), (2.03, 0.04, 0.04), black, 0)
bpy.context.scene["bed_support_v4_config"] = "integration test fixture"
bpy.context.view_layer.update()
refine_bed_guard()
report = refine_wood_uvs()
assert report["objects"] >= 1
cap = bpy.data.objects["Bed_guard_oak_cap"]
uv = cap.data.uv_layers["UVMap"]
for face in cap.data.polygons:
    coords = [uv.data[i].uv for i in face.loop_indices]
    area = abs(sum(a.x * b.y - b.x * a.y for a, b in zip(coords, coords[1:] + coords[:1]))) / 2
    assert area > 1e-12, ("Collapsed guard UV", face.index)

mats = {key: material(key, (0.4, 0.4, 0.4), 0.6) for key in ("tilecream", "tilegray")}
box("Floor_Vinyl_fixture", (0, 0, 0.007), (0.3, 0.3, 0.014), mats["tilecream"], 0)
room = {"left": -0.27, "right": 0.49, "floor_transition_y": 0.43}
layout = refine_vinyl_layout(mats, room, {"yaw_deg": 13}, gray_cells=[[5, -1]])
refine_vinyl_material(mats)
tiles = [o for o in bpy.data.objects if o.name.startswith("Floor_Vinyl_")]
assert len(tiles) == layout["tiles"]
assert any(len(o.data.polygons[1].vertices) != 4 for o in tiles), "Clipped polygon fixture missing"
pitch = layout["parameters"]["pitch_m"]
for tile in tiles:
    face = next(p for p in tile.data.polygons if p.normal.z > 0.5)
    loops = list(face.loop_indices)
    layer = tile.data.uv_layers["UVMap"]
    for a, b in zip(loops, loops[1:] + loops[:1]):
        pa = tile.data.vertices[tile.data.loops[a].vertex_index].co
        pb = tile.data.vertices[tile.data.loops[b].vertex_index].co
        uv_length = (layer.data[a].uv - layer.data[b].uv).length
        assert abs(uv_length * pitch - (pa - pb).length) < 2e-6
        assert abs(pa.z - 0.014) < 1e-7

with tempfile.TemporaryDirectory(prefix="room-refinement-export-") as temp:
    path = Path(temp) / "fixture.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_tangents=True,
        export_image_format="AUTO",
    )
    content = path.read_bytes()
    size, kind = struct.unpack_from("<II", content, 12)
    assert kind == 0x4E4F534A
    doc = json.loads(content[20 : 20 + size])
    for key in mats:
        mat = next(m for m in doc["materials"] if m["name"] == key)
        pbr = mat["pbrMetallicRoughness"]
        assert "baseColorTexture" in pbr and "metallicRoughnessTexture" in pbr
        assert "normalTexture" in mat
        assert math.isclose(mat["normalTexture"]["scale"], 0.30, abs_tol=1e-6)
        for texture in (
            pbr["baseColorTexture"],
            pbr["metallicRoughnessTexture"],
            mat["normalTexture"],
        ):
            assert texture.get("texCoord", 0) == 0
print("REFINEMENT_MATERIALS_PASS: guard end-face UVs, clipped metric VCT, actual three-map GLB")
