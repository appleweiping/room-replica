"""Integration regression for retained furniture albedo and portable UV mapping.

Run with Blender --background --python-exit-code 1 --python this file.
No room native file is required or changed, and no image is rendered.
"""

from pathlib import Path
import json
import struct
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import box, material  # noqa: E402
from materials_v2 import _load_image, _oak  # noqa: E402
from wood_materials_v3 import STAIN, refine_wood_materials  # noqa: E402
from wood_uv_v3 import refine_wood_uvs  # noqa: E402

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
base = material("Honey oak / regression fixture", (0.34, 0.20, 0.095), 0.39)
tex = ROOT / "assets/textures"
_oak(
    base,
    *[
        _load_image(tex / name, space)
        for name, space in (
            ("oak_veneer_01_diff_2k.jpg", "sRGB"),
            ("oak_veneer_01_rough_2k.jpg", "Non-Color"),
            ("oak_veneer_01_nor_gl_2k.jpg", "Non-Color"),
        )
    ],
)
objects = [box("Wardrobe_slab_door", (x, 0, 1), (0.419, 0.024, 1.797), base) for x in (-0.22, 0.22)]
parent = bpy.data.objects.new("Dresser / origin", None)
bpy.context.scene.collection.objects.link(parent)
drawer = box("Dresser drawer 1", (0, 1, 0.5), (0.8, 0.03, 0.24), base)
drawer.parent = parent
parent.scale = (0.81, 0.95, 0.84)
objects.append(drawer)
bpy.context.view_layer.update()
before = {
    o.name: (tuple(v.co[:] for v in o.data.vertices), tuple(map(tuple, o.matrix_world)))
    for o in objects
}
assignment = refine_wood_materials({"oak": base}, tex)
assert set(assignment["quiet_veneer_objects"]) == {o.name for o in objects}
quiet = objects[0].active_material
color = quiet.node_tree.nodes["Oak / captured cathedral grain"]
assert color.image is not None and color.outputs["Color"].is_linked
assert len([n for n in quiet.node_tree.nodes if n.type == "TEX_IMAGE"]) == 1
uv_report = refine_wood_uvs()
for board in uv_report["board_details"]:
    assert board["no_wrap"]
    assert all(0 < low < high < 1 for low, high in board["image_uv_bounds"])
uvs = {o.name: tuple(tuple(p.uv) for p in o.data.uv_layers.active.data) for o in objects}
refine_wood_uvs()
assert uvs == {o.name: tuple(tuple(p.uv) for p in o.data.uv_layers.active.data) for o in objects}
assert before == {
    o.name: (tuple(v.co[:] for v in o.data.vertices), tuple(map(tuple, o.matrix_world)))
    for o in objects
}

with tempfile.TemporaryDirectory(prefix="room-wood-regression-") as temp:
    path = Path(temp) / "boards.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_extras=True,
        export_image_format="AUTO",
    )
    blob = path.read_bytes()
    assert blob[:4] == b"glTF"
    size, kind = struct.unpack_from("<II", blob, 12)
    assert kind == 0x4E4F534A
    document = json.loads(blob[20 : 20 + size])
    mat = next(m for m in document["materials"] if m["name"] == quiet.name)
    pbr = mat["pbrMetallicRoughness"]
    assert "baseColorTexture" in pbr, "Portable furniture lost its albedo image"
    assert max(abs(a - b) for a, b in zip(pbr["baseColorFactor"], STAIN)) < 1e-6
    texture = document["textures"][pbr["baseColorTexture"]["index"]]
    sampler = document["samplers"][texture["sampler"]]
    assert sampler["wrapS"] == sampler["wrapT"] == 33071
print(
    "WOOD_MATERIAL_REGRESSION_PASS: albedo, parented dresser, physical crops, idempotent UVs, portable factor and clamp"
)
