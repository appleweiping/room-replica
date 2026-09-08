"""Blender integration regression: an unmarked camera must survive render evaluation.

Run: blender --background --python-exit-code 1 --python tests/blender_reference_camera.py
Two separated emissive panels make the wrong camera visibly distinguishable.
"""

from pathlib import Path
import hashlib
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.timeline_markers.clear()
scene.world.color = (0, 0, 0)
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

for x, color in [(-2, (1, 0, 0, 1)), (2, (0, 0, 1, 1))]:
    bpy.ops.mesh.primitive_plane_add(size=2, location=(x, 0, 0))
    mat = bpy.data.materials.new("panel")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emission.outputs[0], output.inputs[0])
    bpy.context.object.data.materials.append(mat)

cameras = []
for name, x in [("Camera_Bedroom", -2), ("Camera_Reference_13", 2)]:
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = 2
    cam = bpy.data.objects.new(name, data)
    scene.collection.objects.link(cam)
    cam.location = (x, 0, 3)
    cameras.append(cam)
scene.camera = cameras[0]
marker = scene.timeline_markers.new("bedroom", frame=1)
marker.camera = cameras[0]
scene.frame_set(1)

with tempfile.TemporaryDirectory(prefix="room-camera-regression-") as folder:
    folder = Path(folder)
    native = folder / "fixture.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(native))
    before = hashlib.sha256(native.read_bytes()).hexdigest()
    render.ROOT = folder
    render.main(["--reference", "13", "--resolution", "64", "--samples", "1", "--threads", "2"])
    image = bpy.data.images.load(str(folder / "renders/reference-13.jpg"))
    index = (24 * 64 + 32) * 4
    center = tuple(image.pixels[index : index + 3])
    assert center[2] > 0.8 and center[0] < 0.05, f"Wrong camera panel: RGB {center}"
    assert marker.camera == cameras[0], "Marker binding was not restored"
    assert scene.camera == cameras[0], "Original active camera was not restored"
    assert scene.frame_current == 1
    assert hashlib.sha256(native.read_bytes()).hexdigest() == before
    bpy.data.images.remove(image)
print("REFERENCE_CAMERA_REGRESSION_PASS", flush=True)
