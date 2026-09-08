"""Editable photographed wood estimates for both doors and the wardrobe.

Run after layout and wood_uv_v3. The original UV0 and PBR roughness/coat remain
intact; the directly connected base-colour image uses UV1. The entrance front
uses its own whole board once; the side door and wardrobe use local samples.
See assets/textures/wood_photo_v4/PROVENANCE.json for source and limitations.
"""

from pathlib import Path

import bpy


VERSION = "4.1.0"
UV_NAME = "Photo wood metres"
# Keep historical phases from the visually reviewed five-object experiment.
BOARDS = (
    ("Interior_Door leaf", "side", 0.72, 0.835, 1),
    ("Wardrobe_body", "wardrobe", 0.26, 1.505, 2),
    ("Wardrobe_slab_door", "wardrobe", 0.26, 1.505, 3),
    ("Wardrobe_slab_door.001", "wardrobe", 0.26, 1.505, 4),
)


def refine_photo_wood(M=None, texture_dir=None):
    """Apply accepted entrance/side-door/wardrobe surfaces, without moving them.

    `texture_dir` may point to the portable wood_photo_v4 asset directory.
    M is accepted for the project's refinement interface and is not mutated.
    Side-door/wardrobe edges use local samples; entry edges retain original PBR.
    Estimated illumination correction is not measured albedo. Source sampling
    used the closed entry-door pose; apply once after the static layout pass.
    """
    directory = (
        Path(texture_dir)
        if texture_dir is not None
        else Path(__file__).resolve().parents[1] / "assets/textures/wood_photo_v4"
    )
    for _, kind, _, _, _ in BOARDS:
        path = directory / (kind + "-estimated-basecolor.png")
        if not path.is_file():
            raise FileNotFoundError(path)
    if not (directory / "entry-estimated-basecolor.png").is_file():
        raise FileNotFoundError(directory / "entry-estimated-basecolor.png")
    audit = []
    for name, kind, width, height, historical_index in BOARDS:
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != "MESH":
            raise ValueError("Expected native wood mesh: " + name)
        if ob.get("wood_photo_v4_applied"):
            audit.append({"object": name, "already_applied": True})
            continue
        if len(ob.data.uv_layers) != 1:
            raise ValueError(name + " must have exactly UV0 before photo UV1")
        ob.data = ob.data.copy()
        mesh = ob.data
        active_index = mesh.uv_layers.active_index
        layer = mesh.uv_layers.new(name=UV_NAME)
        material = mesh.materials[0].copy()
        material.name = "WoodPhotoV4 | " + name
        nodes, links = material.node_tree.nodes, material.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        image_node = nodes.new("ShaderNodeTexImage")
        image_node.name = "Photo derived estimated base colour"
        image_node.image = bpy.data.images.load(
            str(directory / (kind + "-estimated-basecolor.png")), check_existing=True
        )
        image_node.image.colorspace_settings.name = "sRGB"
        image_node.image.pack()
        image_node.extension = "REPEAT"
        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = layer.name
        links.new(uv.outputs["UV"], image_node.inputs["Vector"])
        for link in list(bsdf.inputs["Base Color"].links):
            links.remove(link)
        links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
        # Synthetic macrograin normals cannot correspond to this real pattern.
        for link in list(bsdf.inputs["Normal"].links):
            links.remove(link)
        material["provenance"] = "User-photograph derivative; estimated base colour, not measured albedo"
        material["wood_photo_version"] = VERSION
        material["unobserved_surface"] = "Editable repeated local sample, not observed texels"
        mesh.materials[0] = material
        world = [ob.matrix_world @ v.co for v in mesh.vertices]
        normal_matrix = ob.matrix_world.to_3x3().inverted().transposed()
        phase_u, phase_v = historical_index * 0.217, historical_index * 0.173
        for polygon in mesh.polygons:
            normal = normal_matrix @ polygon.normal
            axis = max(range(3), key=lambda i: abs(normal[i]))
            for index in polygon.loop_indices:
                x, y, z = world[mesh.loops[index].vertex_index]
                u, v = ((y, z), (x, z), (x, y))[axis]
                layer.data[index].uv = (u / width + phase_u, v / height + phase_v)
        mesh.uv_layers.active_index = active_index
        ob["wood_photo_v4_applied"] = True
        audit.append({"object": name, "kind": kind, "uv_index": 1,
                      "sample_size_m": [width, height],
                      "historical_phase": [phase_u, phase_v]})
    audit.append(_entry_board(directory))
    return {"version": VERSION, "objects": audit}


def _entry_board(directory):
    """Single photographed front; original material remains on unseen edges."""
    name = "Entry_Door leaf"
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        raise ValueError("Expected native wood mesh: " + name)
    if ob.get("wood_photo_v4_applied"):
        return {"object": name, "already_applied": True}
    if len(ob.data.uv_layers) != 1:
        raise ValueError(name + " must have exactly UV0 before photo UV1")
    ob.data = ob.data.copy()
    mesh = ob.data
    active = mesh.uv_layers.active_index
    uv = mesh.uv_layers.new(name="Entry whole board")
    mat = mesh.materials[0].copy()
    mat.name = "WoodPhotoV4 | Entry own whole board"
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    image = nodes.new("ShaderNodeTexImage")
    image.name = "Entry own photographed full board"
    image.image = bpy.data.images.load(
        str(directory / "entry-estimated-basecolor.png"), check_existing=True
    )
    image.image.colorspace_settings.name = "sRGB"
    image.image.pack()
    image.extension = "EXTEND"
    coord = nodes.new("ShaderNodeUVMap")
    coord.uv_map = uv.name
    links.new(coord.outputs["UV"], image.inputs["Vector"])
    for link in list(bsdf.inputs["Base Color"].links):
        links.remove(link)
    links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    for link in list(bsdf.inputs["Normal"].links):
        links.remove(link)
    mat["wood_photo_version"] = VERSION
    mat["provenance"] = "Own entry ref1 whole board; 6.90% inferred same-board hidden wood; estimated illumination, not measured albedo"
    mesh.materials.append(mat)
    world = [ob.matrix_world @ vertex.co for vertex in mesh.vertices]
    xmin, xmax = min(p.x for p in world), max(p.x for p in world)
    zmin, zmax = min(p.z for p in world), max(p.z for p in world)
    normal_matrix = ob.matrix_world.to_3x3().inverted().transposed()
    fronts = 0
    for polygon in mesh.polygons:
        normal = normal_matrix @ polygon.normal
        if normal.y > 0.9:
            polygon.material_index = len(mesh.materials) - 1
            fronts += 1
        for index in polygon.loop_indices:
            x, _, z = world[mesh.loops[index].vertex_index]
            uv.data[index].uv = ((xmax - x) / (xmax - xmin), (z - zmin) / (zmax - zmin))
    if not fronts:
        raise ValueError("Closed entry front (+Y) was not found")
    mesh.uv_layers.active_index = active
    ob["wood_photo_v4_applied"] = True
    return {"object": name, "kind": "entry", "uv_index": 1,
            "horizontal_repeat_count": 1, "vertical_repeat_count": 1,
            "front_faces": fronts, "world_x": [xmin, xmax],
            "world_z": [zmin, zmax],
            "unobserved_faces": "Original editable PBR wood retained"}
