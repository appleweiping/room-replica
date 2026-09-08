"""Per-drawer photographed grain estimates on the three observed front faces.

Apply after wood_uv_v3/wood_photo_v4. Photographed illumination is only
approximately removed; these assets are not measured reflectance.
"""

from pathlib import Path
import bpy

VERSION = "5.0-experimental"


def refine_dresser_wood(texture_dir=None):
    directory = (
        Path(texture_dir)
        if texture_dir
        else Path(__file__).resolve().parents[1] / "assets/textures/dresser_photo_v5"
    )
    audit = []
    for number in (1, 2, 3):
        ob = bpy.data.objects.get(f"Dresser drawer {number}")
        if ob is None or ob.type != "MESH":
            raise ValueError("Required dresser front missing")
        if ob.get("dresser_photo_v5_applied"):
            audit.append({"object": ob.name, "already_applied": True})
            continue
        path = directory / f"drawer-{number}-estimated-basecolor.png"
        if not path.is_file():
            raise FileNotFoundError(path)
        if len(ob.data.uv_layers) != 1:
            raise ValueError("Expected original UV0 only")
        ob.data = ob.data.copy()
        mesh = ob.data
        active = mesh.uv_layers.active_index
        uv = mesh.uv_layers.new(name="Dresser own front board")
        material = mesh.materials[0].copy()
        material.name = f"WoodPhotoV5 | Dresser own drawer {number}"
        nodes, links = material.node_tree.nodes, material.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        image = nodes.new("ShaderNodeTexImage")
        image.name = "Own drawer photographed grain"
        image.image = bpy.data.images.load(str(path), check_existing=True)
        image.image.colorspace_settings.name = "sRGB"
        image.image.pack()
        image.extension = "EXTEND"
        coord = nodes.new("ShaderNodeUVMap")
        coord.uv_map = uv.name
        links.new(coord.outputs["UV"], image.inputs["Vector"])
        for socket in ("Base Color", "Normal"):
            for link in list(bsdf.inputs[socket].links):
                links.remove(link)
        links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
        material["provenance"] = (
            "Reference 14 bare wood only; same-drawer inferred mask fills; estimated base color, not measured albedo"
        )
        mesh.materials.append(material)
        world = [ob.matrix_world @ v.co for v in mesh.vertices]
        ymin, ymax = min(v.y for v in world), max(v.y for v in world)
        zmin, zmax = min(v.z for v in world), max(v.z for v in world)
        nm = ob.matrix_world.to_3x3().inverted().transposed()
        fronts = 0
        # Copy existing charts on edge/back faces; front receives one exact 0..1 chart.
        for i in range(len(uv.data)):
            uv.data[i].uv = mesh.uv_layers[0].data[i].uv
        for face in mesh.polygons:
            normal = (nm @ face.normal).normalized()
            if normal.x < 0.99:
                continue
            face.material_index = len(mesh.materials) - 1
            fronts += 1
            for index in face.loop_indices:
                p = world[mesh.loops[index].vertex_index]
                uv.data[index].uv = ((p.y - ymin) / (ymax - ymin), (p.z - zmin) / (zmax - zmin))
        if fronts != 1:
            raise ValueError(f"Expected one rigid +X drawer front, got {fronts}")
        mesh.uv_layers.active_index = active
        ob["dresser_photo_v5_applied"] = True
        audit.append(
            {
                "object": ob.name,
                "front_faces": fronts,
                "source_reference": 14,
                "uv_index": 1,
                "repeat_count": [1, 1],
            }
        )
    return {"version": VERSION, "objects": audit}
