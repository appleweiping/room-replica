"""Separate quiet furniture veneer from stronger door-panel oak grain.

Run after layout and before wood_uv_v3. This creates material derivatives in
memory from attributed source assets; it does not modify or project photographs.
The reference-informed straight grain is an AI-assisted reconstruction, not a scan.
"""

from pathlib import Path

import bpy
import numpy as np

from materials_v2 import _linear, _load_image, _packed_image, _pixels, _srgb


VERSION = "3.0.0"
ALBEDO_MEAN = np.array((0.5444, 0.4090, 0.2851))
STAIN = (0.52, 0.33, 0.105, 1.0)


def _normalized_albedo(path, name, contrast):
    # Native source grain is V-oriented; the project's manufactured grain is U.
    rgb = np.rot90(_pixels(_load_image(path, "sRGB"))[:, :, :3], 1)
    linear = _linear(rgb)
    mean = np.mean(linear, axis=(0, 1), dtype=np.float64)
    relative = np.power(np.maximum(linear / mean, 1e-4), contrast)
    relative *= ALBEDO_MEAN / np.mean(relative, axis=(0, 1), dtype=np.float64)
    return _packed_image(name, _srgb(relative), "sRGB", path.name)


def refine_wood_materials(M, texture_dir):
    """Assign fine straight veneer to furniture, retaining panel-oak structure.

    Mean pigment and lighting remain fixed for a controlled texture comparison.
    The nonperiodic generated swatch stays within 0..1 via wood_uv_v3's board
    crop constraint; it must not be advertised or sampled as a seamless tile.
    """
    texture_dir = Path(texture_dir)
    base = M["oak"]
    nodes = base.node_tree.nodes
    albedo = _normalized_albedo(
        texture_dir / "oak_veneer_01_diff_2k.jpg",
        "WOODV3 restrained cathedral oak albedo.png",
        0.90,
    )
    albedo["license"] = "CC0-1.0 derivative of Poly Haven Oak Veneer 01"
    nodes["Oak / captured cathedral grain"].image = albedo
    base["wood_uv_period_m"] = 1.8
    base["wood_uv_no_wrap"] = False
    base["wood_material_version"] = VERSION

    name = "Honey oak / reference-informed straight furniture veneer"
    quiet = bpy.data.materials.get(name)
    if quiet is None:
        quiet = base.copy()
        quiet.name = name
    quiet["wood_uv_period_m"] = 3.0
    quiet["wood_uv_no_wrap"] = True
    quiet["wood_material_version"] = VERSION
    quiet["authorship"] = "AI-assisted reference reconstruction; see assets/WOOD_V3_SOURCES.json"
    quiet["color_comparison"] = "Mean linear pigment held equal to cathedral material"
    qnodes, qlinks = quiet.node_tree.nodes, quiet.node_tree.links
    printed = _normalized_albedo(
        texture_dir / "oak_honey_straight_reference_v3.png",
        "WOODV3 reference-informed straight oak albedo.png",
        0.88,
    )
    printed["license"] = "Project AI-assisted reference reconstruction; not a measured scan"
    printed["seamless"] = False
    color = qnodes["Oak / captured cathedral grain"]
    color.image = printed
    color.label = "Reference-informed fine straight grain / single board crop"
    color.extension = "EXTEND"
    qnodes["Oak amber stain"].inputs[7].default_value = STAIN
    mapping = next(n for n in qnodes if n.type == "MAPPING")
    mapping.name = "Oak / preserve 3 metre straight-grain swatch scale"
    mapping.inputs["Scale"].default_value = (1.15 / 3.0, 0.72 / 3.0, 1.0)
    bs = qnodes["Principled BSDF"]
    # A different grain must not carry the cathedral scan's registered normals.
    for socket in (bs.inputs["Roughness"], bs.inputs["Normal"]):
        for link in list(socket.links):
            qlinks.remove(link)
    bs.inputs["Roughness"].default_value = 0.44
    bump = qnodes.get("Oak / restrained grain relief") or qnodes.new("ShaderNodeBump")
    bump.name = "Oak / restrained grain relief"
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.00010
    qlinks.new(color.outputs["Color"], bump.inputs["Height"])
    qlinks.new(bump.outputs["Normal"], bs.inputs["Normal"])
    # Remove disconnected captured maps so portable export cannot mistake them
    # for texture evidence belonging to the reconstructed straight veneer.
    for node in list(qnodes):
        if node.type == "TEX_IMAGE" and node != color:
            qnodes.remove(node)
    assert color.name in qnodes, "Straight veneer albedo node was removed"
    assert color.outputs["Color"].is_linked, "Straight veneer has no albedo connection"
    assigned = []
    for obj in bpy.context.scene.objects:
        parent = obj.parent
        dresser_member = False
        while parent is not None:
            dresser_member |= parent.name == "Dresser / origin"
            parent = parent.parent
        if obj.type != "MESH" or not (
            dresser_member
            or obj.name.startswith(("Wardrobe_", "Dresser_", "Bed_4x4_post", "Bed_end_ladder_rail"))
        ):
            continue
        for slot in obj.material_slots:
            if slot.material == base or slot.material == quiet:
                slot.material = quiet
                assigned.append(obj.name)
    return {
        "version": VERSION,
        "quiet_veneer_objects": assigned,
        "cathedral_relative_contrast_power": 0.90,
        "straight_relative_contrast_power": 0.88,
        "mean_albedo_before_stain": ALBEDO_MEAN.tolist(),
        "straight_grain_period_m": 3.0,
        "straight_grain_seamless": False,
    }
