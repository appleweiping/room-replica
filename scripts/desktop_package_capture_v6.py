"""Masked photograph-derived graphics on the actual v5 packet mesh.

The captured diagnostic layer is kept separate from the estimated base color.
No camera, device, supporting object, rim or mesh vertex is changed here.
"""

from pathlib import Path
import hashlib
import json

import bpy

VERSION = "6.0.0"
TARGET = "DesktopPackagesV5_Open_crisps_laminate_shell"


def refine_desktop_package_capture(texture_dir=None):
    scene = bpy.context.scene
    if scene.get("desktop_package_capture_v6") == VERSION:
        return json.loads(scene["desktop_package_capture_v6_audit"])
    if scene.get("desktop_packages_refinement") != "5.0.0":
        raise ValueError("Apply frozen desktop_packages_v5 before its capture material")
    directory = (
        Path(texture_dir)
        if texture_dir
        else Path(__file__).resolve().parents[1] / "assets/textures/desktop_package_capture_v6"
    )
    paths = [directory / "estimated-basecolor.png", directory / "shallow-compression-normal.png"]
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(p)
    obj = bpy.data.objects[TARGET]
    old_material = obj.data.materials[0].name
    old_mesh = obj.data
    obj.data = obj.data.copy()
    material = bpy.data.materials.new("DesktopPackageCaptureV6 / estimated photographed film")
    material.use_nodes = True
    material.diffuse_color = (0.16, 0.105, 0.043, 1)
    material["appearance_mode"] = (
        "Estimated base color under fixed lighting, with residual photographed shading; not measured reflectance."
    )
    tree = material.node_tree
    bs = tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value = 0.64
    bs.inputs["Metallic"].default_value = 0.025
    bs.inputs["Specular IOR Level"].default_value = 0.10
    for i, path in enumerate(paths):
        image = bpy.data.images.load(str(path), check_existing=True)
        image.colorspace_settings.name = "sRGB" if i == 0 else "Non-Color"
        image.pack()
        node = tree.nodes.new("ShaderNodeTexImage")
        node.name = (
            "Estimated masked photo color" if i == 0 else "Authored shallow film compression"
        )
        node.image = image
        node.extension = "REPEAT"
        if i == 0:
            tree.links.new(node.outputs["Color"], bs.inputs["Base Color"])
        else:
            normal = tree.nodes.new("ShaderNodeNormalMap")
            normal.inputs["Strength"].default_value = 0.68
            tree.links.new(node.outputs["Color"], normal.inputs["Color"])
            tree.links.new(normal.outputs["Normal"], bs.inputs["Normal"])
    obj.data.materials[0] = material
    assert len(obj.data.vertices) == len(old_mesh.vertices)
    assert all(tuple(a.co) == tuple(b.co) for a, b in zip(obj.data.vertices, old_mesh.vertices))
    audit = {
        "version": VERSION,
        "target_object": TARGET,
        "previous_outer_material": old_material,
        "new_outer_material": material.name,
        "geometry_and_uv_unchanged": True,
        "captured_layer_not_used_as_direct_shader": True,
        "estimated_texture_sha256": hashlib.sha256(paths[0].read_bytes()).hexdigest(),
        "normal_sha256": hashlib.sha256(paths[1].read_bytes()).hexdigest(),
        "source_brand": "Visible Lay’s logo; product model not inferred.",
        "material_limit": "Masked photo illumination is reduced, not solved. A low-specular, rough material avoids adding a second strong highlight field.",
        "recipe": "assets/textures/desktop_package_capture_v6/sampling-recipe.json",
    }
    scene["desktop_package_capture_v6"] = VERSION
    scene["desktop_package_capture_v6_audit"] = json.dumps(audit)
    return audit
